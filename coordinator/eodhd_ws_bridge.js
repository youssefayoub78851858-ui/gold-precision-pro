'use strict';
// EODHD XAUUSD private, fail-closed review connector. Never places orders.
const fs=require('node:fs'),path=require('node:path');
const WIDTH=900000,AGE=30000,FUTURE=5000,GAP=90000;
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
 reset(reason='STREAM_INTERRUPTED'){
  this.authorized=false;this.last=null;this.current=null;this.bars=[];
  this.quote=null;this.reason=reason;
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
   if(this.bars.length>320)this.bars.shift();
   this.current=null;
  }
  if(!this.current){
   this.current={start,first:x.t,last:x.t,bar:{
    openTime:new Date(start).toISOString(),open:mid,high:mid,low:mid,close:mid}};
  }else{
   const c=this.current.bar;this.current.last=x.t;
   c.high=Math.max(c.high,mid);c.low=Math.min(c.low,mid);c.close=mid;
  }
  this.last=x.t;this.count++;this.quote={bid:x.b,ask:x.a,timeUTC:new Date(x.t).toISOString()};
  this.reason='WAIT_INDEPENDENT_FEED_VALIDATION';
  return {kind:'quote',signal:'WAIT',executable:false};
 }
 snapshot(){
  return {provider:'EODHD',instrument:'XAU/USD',quoteType:'INDICATIVE_MIDQUOTE_OHLC',
   mode:'REVIEW_ONLY',researchEligible:false,signal:'WAIT',executable:false,
   readyForTrading:false,reason:this.reason,received:this.count,latestQuote:this.quote,
   frames:{M15:this.bars.slice(),H1:aggregate(this.bars,4),H4:aggregate(this.bars,16)}};
 }
}
function privateSave(dir,snapshot){
 fs.mkdirSync(dir,{recursive:true,mode:0o700});
 const dst=path.join(dir,'eodhd-private-review.json'),tmp=dst+'.tmp-'+process.pid;
 try{fs.writeFileSync(tmp,JSON.stringify(snapshot)+'\n',{mode:0o600,flag:'wx'});fs.renameSync(tmp,dst);}
 finally{try{fs.unlinkSync(tmp);}catch{}}
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
 let tries=0,socket,halted=false,lastSaved=0;
 const stop=()=>{halted=true;if(socket)socket.close();};
 process.on('SIGTERM',stop);process.on('SIGINT',stop);
 function connect(){
  if(halted)return;
  review.reset('CONNECTING');
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
   if(already||halted)return;already=true;review.reset('DISCONNECTED');
   try{privateSave(dir,review.snapshot());}catch{}
   setTimeout(connect,Math.min(300000,5000*Math.pow(2,Math.min(tries++,6))));
  };
  socket.addEventListener('close',disconnect);socket.addEventListener('error',disconnect);
 }
 connect();
}
if(require.main===module)run();
module.exports={XauusdReview,aggregate,privateSave,run};
