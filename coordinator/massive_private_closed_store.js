'use strict';
// MASSIVE OFFLINE SYNTHETIC CLOSED BBO HISTORY STORE.
// Owner-only local fixtures; no real quotes, credentials, WebSockets,
// market feed permissions, strategy/candidate admission, or orders.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {MassiveQuoteStandby,aggregate}=require('./massive_ws_standby');
const FILE='massive-synthetic-closed-m15.json',MAX_BARS=2048,MAX_BYTES=2100000;
const FRAME_KEYS=['bidFrames','askFrames','frames'];
function fail(code){throw Error(code);}
function secureFolder(dir,create){
 if(typeof dir!=='string'||!path.isAbsolute(dir))fail('PRIVATE_ABSOLUTE_DIR_REQUIRED');
 if(create)fs.mkdirSync(dir,{recursive:true,mode:0o700});
 let stat;
 try{stat=fs.lstatSync(dir);}catch(e){if(e.code==='ENOENT')return null;throw e;}
 if(!stat.isDirectory()||stat.isSymbolicLink()||(stat.mode&0o077)!==0||
    (typeof process.getuid==='function'&&stat.uid!==process.getuid())||
    fs.realpathSync(dir)!==path.resolve(dir))fail('PRIVATE_DIRECTORY_NOT_OWNER_ONLY');
 return dir;
}
function ownerFile(file){
 let s;try{s=fs.lstatSync(file);}catch(e){if(e.code==='ENOENT')return false;throw e;}
 if(!s.isFile()||s.isSymbolicLink()||(s.mode&0o077)!==0||
    (typeof process.getuid==='function'&&s.uid!==process.getuid()))fail('UNSAFE_PRIVATE_HISTORY_FILE');
 return true;
}
function candle(bar,now){
 if(!bar||typeof bar!=='object'||Array.isArray(bar)||
    Object.keys(bar).sort().join(',')!=='close,high,low,open,openTime'||
    typeof bar.openTime!=='string')fail('INVALID_CLOSED_CANDLE');
 const timestamp=Date.parse(bar.openTime);
 if(!Number.isFinite(timestamp)||new Date(timestamp).toISOString()!==bar.openTime||
    timestamp%900000!==0||timestamp+900000>now)fail('UNALIGNED_OR_FUTURE_CLOSED_M15');
 if(!['open','high','low','close'].every(k=>typeof bar[k]==='number'&&
     Number.isFinite(bar[k])&&bar[k]>0)||
    bar.high<Math.max(bar.open,bar.close,bar.low)||
    bar.low>Math.min(bar.open,bar.close,bar.high))fail('INVALID_OHLC');
 return timestamp;
}
function checkedClosed(snapshot,now){
 if(!Number.isSafeInteger(now)||now<=0||!snapshot||typeof snapshot!=='object'||
    snapshot.provider!=='Massive'||snapshot.mode!=='OFFLINE_SYNTHETIC_REVIEW_ONLY'||
    snapshot.sourceDataMode!=='SYNTHETIC_TEST_ONLY'||
    snapshot.signal!=='WAIT'||snapshot.executable!==false||
    snapshot.researchEligible!==false||snapshot.paperOrdersAllowed!==false||
    snapshot.historicalLiveParityVerified!==false||
    snapshot.cloudRightsVerified!==false||snapshot.entitlementVerified!==false)
  fail('ONLY_SYNTHETIC_WAIT_CLOSED_BBO');
 let n;
 for(const group of FRAME_KEYS){
  const f=snapshot[group];
  if(!f||typeof f!=='object'||!Array.isArray(f.M15)||
     f.M15.length>MAX_BARS||!Array.isArray(f.H1)||!Array.isArray(f.H4))
    fail('INCOMPLETE_CLOSED_FRAME_FAMILY');
  if(n===undefined)n=f.M15.length;
  if(n!==f.M15.length)fail('BID_ASK_MID_TIMESTAMPS_DIFFER');
  let previous=-1;
  for(const c of f.M15){
   const current=candle(c,now);
   if(current<=previous)fail('CLOSED_BAR_REPLAY_OR_REORDER');
   previous=current;
  }
  const identical=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  if(!identical(aggregate(f.M15,4),f.H1)||!identical(aggregate(f.M15,16),f.H4))
   fail('FORGED_HIGHER_TIMEFRAMES');
 }
 const mid=snapshot.frames.M15,bids=snapshot.bidFrames.M15,asks=snapshot.askFrames.M15;
 const close=(x,y)=>Math.abs(x-y)<=Math.max(1e-8,Math.abs(x)*1e-10);
 for(let i=0;i<n;i++){
  const m=mid[i],b=bids[i],a=asks[i];
  if(m.openTime!==b.openTime||b.openTime!==a.openTime||
     !close(m.open,(a.open+b.open)/2)||!close(m.close,(a.close+b.close)/2)||
     b.open>a.open||b.close>a.close||
     b.high>a.high||b.low>a.low||
     m.high> (a.high+b.high)/2+1e-8||
     m.low < (a.low+b.low)/2-1e-8)
    fail('MID_BID_ASK_INCONSISTENT');
 }
 return n;
}
function canonical(snapshot,now){
 checkedClosed(snapshot,now);
 return {schemaVersion:1,provider:'Massive',sourceDataMode:'SYNTHETIC_TEST_ONLY',
   mode:'OFFLINE_PRIVATE_REHEARSAL_ONLY',signal:'WAIT',executable:false,
   researchEligible:false,paperOrdersAllowed:false,entitlementVerified:false,
   independentSessionCalendarVerified:false,
   // Save CLOSED M15 only; restore higher timeframes by recomputing.
   bidM15:snapshot.bidFrames.M15.map(x=>({...x})),
   askM15:snapshot.askFrames.M15.map(x=>({...x})),
   midM15:snapshot.frames.M15.map(x=>({...x}))};
}
function digest(payload){return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');}
function saveClosed(dir,snapshot,now){
 const p=canonical(snapshot,now),d=secureFolder(dir,true),target=path.join(d,FILE);
 ownerFile(target);
 const encoded=JSON.stringify({payload:p,sha256:digest(p)})+'\n';
 if(Buffer.byteLength(encoded)>MAX_BYTES)fail('HISTORY_SNAPSHOT_TOO_LARGE');
 const temp=target+'.tmp-'+crypto.randomBytes(10).toString('hex');
 let fd;
 try{
  fd=fs.openSync(temp,fs.constants.O_CREAT|fs.constants.O_EXCL|fs.constants.O_WRONLY,0o600);
  fs.writeFileSync(fd,encoded);fs.fsyncSync(fd);fs.closeSync(fd);fd=undefined;
  fs.renameSync(temp,target);
 }finally{
  if(fd!==undefined)fs.closeSync(fd);
  try{fs.unlinkSync(temp);}catch(e){if(e.code!=='ENOENT')throw e;}
 }
 return {mode:'OFFLINE_PRIVATE_SYNTHETIC_STORAGE',status:'CLOSED_HISTORY_SAVED',
  signal:'WAIT',executable:false,researchEligible:false,paperOrdersAllowed:false,
  closedM15Count:p.midM15.length,latestQuotePersisted:false,credentialsPersisted:false,
  realMarketDataStored:false,providerRequestsMade:0};
}
function loadClosed(dir,now){
 if(!Number.isSafeInteger(now)||now<=0)fail('INVALID_REVIEW_CLOCK');
 const d=secureFolder(dir,false);
 if(d===null)return null;
 const target=path.join(d,FILE);
 if(!ownerFile(target))return null;
 let fd;
 try{
  fd=fs.openSync(target,fs.constants.O_RDONLY|(fs.constants.O_NOFOLLOW||0));
  const stat=fs.fstatSync(fd);
  if(!stat.isFile()||(stat.mode&0o077)!==0||stat.size<20||
     stat.size>MAX_BYTES||
     (typeof process.getuid==='function'&&stat.uid!==process.getuid()))
   fail('UNSAFE_PRIVATE_HISTORY_FILE');
  const env=JSON.parse(fs.readFileSync(fd,'utf8'));
  const p=env?.payload;
  if(!p||Object.keys(env).sort().join(',')!=='payload,sha256'||
     !/^[a-f0-9]{64}$/.test(env.sha256)||digest(p)!==env.sha256||
     p.schemaVersion!==1||p.provider!=='Massive'||
     p.mode!=='OFFLINE_PRIVATE_REHEARSAL_ONLY'||
     p.sourceDataMode!=='SYNTHETIC_TEST_ONLY'||
     p.signal!=='WAIT'||p.executable!==false||
     p.entitlementVerified!==false||p.paperOrdersAllowed!==false||
     !Array.isArray(p.bidM15)||!Array.isArray(p.askM15)||
     !Array.isArray(p.midM15))
   fail('PRIVATE_SYNTHETIC_HISTORY_INTEGRITY_REJECTED');
  const frames=bars=>({M15:bars,H1:aggregate(bars,4),H4:aggregate(bars,16)});
  const rebuilt={provider:'Massive',mode:'OFFLINE_SYNTHETIC_REVIEW_ONLY',
    sourceDataMode:'SYNTHETIC_TEST_ONLY',signal:'WAIT',executable:false,
    researchEligible:false,paperOrdersAllowed:false,
    historicalLiveParityVerified:false,cloudRightsVerified:false,
    entitlementVerified:false,
    frames:frames(p.midM15),bidFrames:frames(p.bidM15),askFrames:frames(p.askM15)};
  checkedClosed(rebuilt,now);
  return rebuilt;
 }finally{if(fd!==undefined)fs.closeSync(fd);}
}
function coldRestore(review,dir,now){
 if(!(review instanceof MassiveQuoteStandby))fail('INVALID_OFFLINE_REVIEW_ENGINE');
 review.disconnect('OFFLINE_COLD_RESTORE_REQUIRES_NEW_AUTH');
 const restored=loadClosed(dir,now);
 if(!restored)return null;
 for(const [key,basis] of [['bid','bidFrames'],['ask','askFrames'],['mid','frames']])
  review.closed[key]=restored[basis].M15.map(x=>({...x}));
 return {mode:'OFFLINE_COLD_RESTORE_SYNTHETIC_ONLY',
  restoredM15Count:restored.frames.M15.length,
  signal:'WAIT',executable:false,researchEligible:false,
  paperOrdersAllowed:false,restoredLatestQuote:false,
  restoredAuthorization:false,providerRequestsMade:0};
}
module.exports={saveClosed,loadClosed,coldRestore};
