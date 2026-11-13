'use strict';
// EODHD XAUUSD private, fail-closed review connector. Never places orders.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const WIDTH=900000,AGE=30000,FUTURE=5000,GAP=90000,MAX_BARS=2048;
const valid=x=>typeof x==='number'&&Number.isFinite(x)&&x>0;
function aggregate(bars,n){
 const groups=new Map(),w=WIDTH*n;
 for(const b of bars){const s=Math.floor(Date.parse(b.openTime)/w)*w;
  if(!groups.has(s))groups.set(s,[]);groups.get(s).push(b);}
 return [...groups].sort((a,b)=>a[0]-b[0]).flatMap(([s,g])=>
  g.length!==n||g.some((b,i)=>Date.parse(b.openTime)!==s+i*WIDTH)?[]:
  [{openTime:new Date(s).toISOString(),open:g[0].open,
   high:Math.max(...g.map(x=>x.high)),low:Math.min(...g.map(x=>x.low)),
   close:g.at(-1).close}]);
}
class XauusdReview{
 constructor(clock=Date.now){this.clock=clock;this.reset('NOT_CONNECTED');this.count=0;}
 reset(reason='STREAM_INTERRUPTED',preserveClosed=false){
  this.authorized=false;this.last=null;this.current=null;
  if(!preserveClosed){this.bars=[];this.bidBars=[];this.askBars=[];}
  this.quote=null;this.reason=reason;
 }
 restoreClosed(history){
  // CLOSED bars only: never import a quote, auth flag, or open M15 candle.
  this.reset('WAIT_RESTORED_HISTORY_UNVERIFIED');
  this.bars=history.frames.M15.map(x=>({...x}));
  this.bidBars=history.bidFrames.M15.map(x=>({...x}));
  this.askBars=history.askFrames.M15.map(x=>({...x}));
 }
 receive(message){
  let x;try{x=typeof message==='string'?JSON.parse(message):message;}catch{
   this.reset('INVALID_JSON');return {kind:'blocked',reason:this.reason};}
  if(!x||typeof x!=='object'||Array.isArray(x)){
   this.reset('INVALID_JSON');return {kind:'blocked',reason:this.reason};}
  if(Object.hasOwn(x,'status')||Object.hasOwn(x,'status_code')){
   const code=x.status_code??x.status;
   if(code===200){this.authorized=true;this.reason='WAIT_HISTORY';return {kind:'authorized'};}
   this.reset('PROVIDER_STATUS_'+code);return {kind:'blocked',reason:this.reason};
  }
  if(x.s!=='XAUUSD')return {kind:'ignored'};
  if(!this.authorized)return {kind:'blocked',reason:'AUTHORIZATION_MISSING'};
  if(!valid(x.a)||!valid(x.b)||x.a<x.b||!Number.isSafeInteger(x.t)||x.t<=0){
   this.reset('INVALID_QUOTE');return {kind:'blocked',reason:this.reason};}
  const now=this.clock();
  if(!Number.isFinite(now)||now-x.t>AGE||x.t>now+FUTURE){
   this.reset('STALE_OR_FUTURE');return {kind:'blocked',reason:this.reason};}
  if(this.last!==null&&(x.t<=this.last||x.t-this.last>GAP)){
   this.reset('TICK_GAP_OR_ORDER');return {kind:'blocked',reason:this.reason};}
  const start=Math.floor(x.t/WIDTH)*WIDTH,mid=(x.a+x.b)/2;
  if(this.current&&this.current.start!==start){
   if(start!==this.current.start+WIDTH||
      this.current.first>this.current.start+60000||
      this.current.last<this.current.start+WIDTH-60000){
    this.reset('INCOMPLETE_M15');return {kind:'blocked',reason:this.reason};}
   this.bars.push(this.current.bar);
   this.bidBars.push(this.current.bidBar);
   this.askBars.push(this.current.askBar);
   if(this.bars.length>MAX_BARS)this.bars.shift();
   if(this.bidBars.length>MAX_BARS)this.bidBars.shift();
   if(this.askBars.length>MAX_BARS)this.askBars.shift();
   this.current=null;
  }
  if(!this.current){
   const candle=value=>({openTime:new Date(start).toISOString(),open:value,high:value,low:value,close:value});
   this.current={start,first:x.t,last:x.t,bar:candle(mid),bidBar:candle(x.b),askBar:candle(x.a)};
  }else{
   this.current.last=x.t;
   for(const [c,value] of [[this.current.bar,mid],[this.current.bidBar,x.b],[this.current.askBar,x.a]]){
    c.high=Math.max(c.high,value);c.low=Math.min(c.low,value);c.close=value;
   }
  }
  this.last=x.t;this.count++;this.quote={bid:x.b,ask:x.a,timeUTC:new Date(x.t).toISOString()};
  this.reason='WAIT_INDEPENDENT_FEED_VALIDATION';
  return {kind:'quote',signal:'WAIT',executable:false};
 }
 snapshot(){
  return {provider:'EODHD',instrument:'XAU/USD',quoteType:'INDICATIVE_MIDQUOTE_OHLC',
   mode:'REVIEW_ONLY',researchEligible:false,signal:'WAIT',executable:false,
   readyForTrading:false,sessionVerified:false,sessionStatus:'UNVERIFIED_PROVIDER_SESSION_CALENDAR',
   indicatorWarmupReady:false,reason:this.reason,received:this.count,latestQuote:this.quote,
   frames:{M15:this.bars.slice(),H1:aggregate(this.bars,4),H4:aggregate(this.bars,16)},
   bidFrames:{M15:this.bidBars.slice(),H1:aggregate(this.bidBars,4),H4:aggregate(this.bidBars,16)},
   askFrames:{M15:this.askBars.slice(),H1:aggregate(this.askBars,4),H4:aggregate(this.askBars,16)}};
 }
}
function privateSave(dir,snapshot){
 fs.mkdirSync(dir,{recursive:true,mode:0o700});
 // Do not follow a symlink or reuse a shared/wrong-owner directory.
 const info=fs.lstatSync(dir);
 if(!info.isDirectory()||(info.mode&0o077)!==0||
    (typeof process.getuid==='function'&&info.uid!==process.getuid()))
  throw Error('Unsafe private snapshot directory');
 const dst=path.join(dir,'eodhd-private-review.json'),tmp=dst+'.tmp-'+process.pid+'-'+crypto.randomBytes(12).toString('hex');
 // Existing snapshots must remain private; never replace attacker-controlled links.
 try{
  const previous=fs.lstatSync(dst);
  if(!previous.isFile()||(previous.mode&0o077)!==0||
     (typeof process.getuid==='function'&&previous.uid!==process.getuid()))
   throw Error('Unsafe private snapshot destination');
 }catch(error){if(error.code!=='ENOENT')throw error;}
 try{fs.writeFileSync(tmp,JSON.stringify(snapshot)+'\n',{mode:0o600,flag:'wx'});fs.renameSync(tmp,dst);}
 finally{try{fs.unlinkSync(tmp);}catch{}}
}

/**
 * Secure cold recovery of CLOSED history, never provider authorization or a
 * fresh quote. The existing private snapshot is the only persistence source.
 * Recompute H1/H4 from M15 to reject forged/mismatched aggregates.
 */
function privateLoadClosed(dir,now=Date.now()){
 if(!Number.isFinite(now)||now<=0)throw Error('Invalid independent clock');
 let folder;
 try{folder=fs.lstatSync(dir);}
 catch(e){if(e.code==='ENOENT')return null;throw e;}
 if(!folder.isDirectory()||(folder.mode&0o077)!==0||
    (typeof process.getuid==='function'&&folder.uid!==process.getuid()))
  throw Error('Unsafe closed history directory');
 const filename=path.join(dir,'eodhd-private-review.json');
 let fd;
 try{fd=fs.openSync(filename,fs.constants.O_RDONLY|(fs.constants.O_NOFOLLOW||0));}
 catch(e){if(e.code==='ENOENT')return null;throw e;}
 let raw;
 try{
  const st=fs.fstatSync(fd);
  if(!st.isFile()||(st.mode&0o077)!==0||st.size<2||st.size>1500000||
     (typeof process.getuid==='function'&&st.uid!==process.getuid()))
   throw Error('Unsafe closed history file');
  raw=JSON.parse(fs.readFileSync(fd,'utf8'));
 }finally{fs.closeSync(fd);}
 if(!raw||raw.provider!=='EODHD'||raw.instrument!=='XAU/USD'||
    raw.mode!=='REVIEW_ONLY'||raw.quoteType!=='INDICATIVE_MIDQUOTE_OHLC'||
    raw.signal!=='WAIT'||raw.executable!==false||
    raw.researchEligible!==false||raw.readyForTrading!==false)
  throw Error('Closed history identity rejected');
 const names=['frames','bidFrames','askFrames'];
 for(const name of names){
  const group=raw[name];
  if(!group||typeof group!=='object'||Array.isArray(group)||
     Object.keys(group).sort().join(',')!=='H1,H4,M15'||
     !Array.isArray(group.M15)||group.M15.length>MAX_BARS||
     !Array.isArray(group.H1)||group.H1.length>512||
     !Array.isArray(group.H4)||group.H4.length>128)
   throw Error('Invalid closed history frames');
 }
 const [mid,bid,ask]=names.map(name=>raw[name].M15),len=mid.length;
 if(bid.length!==len||ask.length!==len)throw Error('Closed history length mismatch');
 let previous=-1;
 for(let i=0;i<len;i++){
  const rows=[mid[i],bid[i],ask[i]];
  if(rows.some(row=>!row||typeof row!=='object'||Array.isArray(row)||
      Object.keys(row).sort().join(',')!=='close,high,low,open,openTime'))
   throw Error('Closed history bar format rejected');
  const stamp=rows[0].openTime,time=Date.parse(stamp);
  if(typeof stamp!=='string'||!Number.isSafeInteger(time)||time<0||
     new Date(time).toISOString()!==stamp||time%WIDTH!==0||
     time<=previous||time+WIDTH>now||
     rows.some(row=>row.openTime!==stamp))
   throw Error('Closed history clock or ordering invalid');
  previous=time;
  for(const row of rows){
   if(!['open','high','low','close'].every(k=>valid(row[k]))||
      row.high<Math.max(row.open,row.close,row.low)||
      row.low>Math.min(row.open,row.close,row.high))
    throw Error('Closed history OHLC rejected');
  }
  for(const key of ['open','high','low','close'])
   if(bid[i][key]>ask[i][key])throw Error('Closed history crossed');
  const close=(x,y)=>Math.abs(x-y)<=Math.max(1e-7,Math.abs(x)*1e-9);
  if(!close(mid[i].open,(bid[i].open+ask[i].open)/2)||
     !close(mid[i].close,(bid[i].close+ask[i].close)/2)||
     mid[i].high<bid[i].high||mid[i].high>ask[i].high||
     mid[i].low<bid[i].low||mid[i].low>ask[i].low)
   throw Error('Closed history midquote mismatch');
 }
 for(const family of names)
  for(const [interval,n] of [['H1',4],['H4',16]]){
   const expected=aggregate(raw[family].M15,n),stored=raw[family][interval];
   if(stored.length!==expected.length)throw Error('Closed aggregate count mismatch');
   for(let i=0;i<expected.length;i++)
    if(Object.keys(expected[i]).some(key=>stored[i]?.[key]!==expected[i][key])||
       Object.keys(stored[i]).sort().join(',')!=='close,high,low,open,openTime')
     throw Error('Closed aggregate mismatch');
  }
 // Only copy OHLC; never return latestQuote or untrusted status flags.
 const copy=rows=>rows.map(({openTime,open,high,low,close})=>({openTime,open,high,low,close}));
 return {frames:{M15:copy(mid)},bidFrames:{M15:copy(bid)},askFrames:{M15:copy(ask)}};
}
// Clear any previously fresh quote BEFORE opening a WebSocket. A quick
// restart must never let the monitor count yesterday's/last-process's tick
// as a new observation. Storage failure aborts the worker before networking.
function coldStartReview(review,dir,now=Date.now()){
 try{const closed=privateLoadClosed(dir,now);if(closed)review.restoreClosed(closed);}
 catch{review.reset('CLOSED_HISTORY_REJECTED');}
 privateSave(dir,review.snapshot());
}
function run(){
 if(process.env.EODHD_CONNECT_APPROVED!=='1'||
    process.env.EODHD_RIGHTS_APPROVED!=='1'||
    process.env.CUTOVER_MODE==='live'){
  console.log(JSON.stringify({status:'DISABLED_NO_NETWORK',signal:'WAIT',executable:false}));return;}
 const token=process.env.EODHD_API_TOKEN;
 if(!token||token==='demo'||token.length<12)throw Error('Paid EODHD token not configured');
 if(typeof WebSocket!=='function')throw Error('WebSocket requires Node 22+');
 const review=new XauusdReview(),dir=process.env.DATA_DIR||'/var/data/gold-live';
 coldStartReview(review,dir);
 let tries=0,socket,halted=false,lastSaved=0;
 const stop=()=>{halted=true;if(socket)socket.close();};
 process.on('SIGTERM',stop);process.on('SIGINT',stop);
 function connect(){
  if(halted)return;
  review.reset('CONNECTING',true);
  socket=new WebSocket('wss://ws.eodhistoricaldata.com/ws/forex?api_token='+encodeURIComponent(token));
  socket.addEventListener('open',()=>{tries=0;socket.send(JSON.stringify({action:'subscribe',symbols:'XAUUSD'}));});
  socket.addEventListener('message',e=>{
   const r=review.receive(String(e.data));
   if(r.kind==='blocked'){
    if(['PROVIDER_STATUS_403','PROVIDER_STATUS_422','PROVIDER_STATUS_401'].includes(r.reason))halted=true;
    try{privateSave(dir,review.snapshot());}catch{}
    console.error('EODHD quote intake blocked: '+r.reason);socket.close();return;
   }
   if((r.kind==='quote'||r.kind==='authorized')&&(Date.now()-lastSaved>5000||r.kind==='authorized')){
    try{privateSave(dir,review.snapshot());lastSaved=Date.now();}
    catch{review.reset('STORAGE_FAILED');socket.close();}
   }
  });
  let already=false;
  const disconnect=()=>{
   if(already||halted)return;already=true;review.reset('DISCONNECTED',true);
   try{privateSave(dir,review.snapshot());}catch{}
   setTimeout(connect,Math.min(300000,5000*Math.pow(2,Math.min(tries++,6))));
  };
  socket.addEventListener('close',disconnect);socket.addEventListener('error',disconnect);
 }
 connect();
}
if(require.main===module)run();
module.exports={XauusdReview,aggregate,privateSave,privateLoadClosed,coldStartReview,run};
