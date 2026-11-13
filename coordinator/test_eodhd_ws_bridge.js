'use strict';
const a=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {XauusdReview,aggregate,privateSave,privateLoadClosed}=require('./eodhd_ws_bridge');
const base=1794493813003,quote=(t,ask=3903.04,bid=3902.46)=>({s:'XAUUSD',a:ask,b:bid,t});
let now=base,review=new XauusdReview(()=>now+1000);
a.equal(review.receive(quote(base)).reason,'AUTHORIZATION_MISSING');
a.equal(review.receive({status_code:200}).kind,'authorized');
a.equal(review.receive(quote(base)).kind,'quote');
a.equal(review.snapshot().signal,'WAIT');
a.equal(review.snapshot().executable,false);
a.equal(review.snapshot().frames.M15.length,0);
review=new XauusdReview(()=>base+1000);review.receive({status_code:200});
a.equal(review.receive(quote(base,3902,3903)).reason,'INVALID_QUOTE');
review=new XauusdReview(()=>base+1000);review.receive({status_code:200});
a.equal(review.receive(quote(base-100000)).reason,'STALE_OR_FUTURE');
review=new XauusdReview(()=>base+1000);review.receive({status_code:200});
review.receive(quote(base));a.equal(review.receive(quote(base)).reason,'TICK_GAP_OR_ORDER');
a.equal(review.snapshot().frames.M15.length,0);
review=new XauusdReview(()=>base+1000);review.receive({status_code:200});
a.equal(review.receive({status_code:422}).reason,'PROVIDER_STATUS_422');
review=new XauusdReview(()=>base+1000);review.receive({status_code:200});
a.equal(review.receive('{invalid').reason,'INVALID_JSON');
const start=Math.floor(base/(16*900000))*(16*900000);
review=new XauusdReview(()=>now+1000);review.receive({status_code:200});
for(let i=0;i<16;i++){
 const s=start+i*900000;
 for(let j=1;j<=29;j++){now=s+j*30000;a.equal(review.receive(quote(now)).kind,'quote');}
 now=s+899000;a.equal(review.receive(quote(now)).kind,'quote');
}
now=start+16*900000+1000;
a.equal(review.receive(quote(now)).kind,'quote');
a.equal(review.snapshot().frames.M15.length,16);
a.equal(review.snapshot().frames.H1.length,4);
a.equal(review.snapshot().frames.H4.length,1);
a.equal(review.snapshot().researchEligible,false);
const barStart=Math.floor(base/900000)*900000;
let quoteNow=barStart;const quoteReview=new XauusdReview(()=>quoteNow+1000);
quoteReview.receive({status_code:200});
for(const [t,bid,ask] of [[barStart+1000,4000,4001],[barStart+30000,4002,4003],
 [barStart+60000,3999,4000],...Array.from({length:13},(_,i)=>[barStart+120000+i*60000,3999,4000])]){
 quoteNow=t;a.equal(quoteReview.receive(quote(t,ask,bid)).kind,'quote');
}
// An open M15 is not exposed as closed until the next M15 tick arrives.
a.equal(quoteReview.snapshot().bidFrames.M15.length,0);
quoteNow=barStart+900001;a.equal(quoteReview.receive(quote(quoteNow,4002,4001)).kind,'quote');
const split=quoteReview.snapshot();
a.equal(split.bidFrames.M15.length,1);
a.equal(split.askFrames.M15.length,1);
a.deepEqual([split.bidFrames.M15[0].open,split.bidFrames.M15[0].high,
 split.bidFrames.M15[0].low,split.bidFrames.M15[0].close],[4000,4002,3999,3999]);
a.deepEqual([split.askFrames.M15[0].open,split.askFrames.M15[0].high,
 split.askFrames.M15[0].low,split.askFrames.M15[0].close],[4001,4003,4000,4000]);
a.equal(split.frames.M15[0].close,3999.5);
a.equal(split.sessionVerified,false);
a.equal(split.indicatorWarmupReady,false);
a.equal(split.researchEligible,false);
a.equal(split.signal,'WAIT');
a.equal(split.executable,false);
const historySnapshot=review.snapshot();
review.reset();a.equal(review.snapshot().frames.M15.length,0);
a.equal(aggregate([],4).length,0);
// Private snapshots must not escape through inherited permissions or links.
const scratch=fs.mkdtempSync(path.join(os.tmpdir(),'gold-eodhd-private-'));
try{
 const secure=path.join(scratch,'secure'),payload={signal:'WAIT',executable:false};
 a.equal(privateLoadClosed(path.join(scratch,'missing'),now),null);
 // Persist a real-looking CLOSED sample already produced by the offline test.
 privateSave(secure,historySnapshot);
 const cold=privateLoadClosed(secure,now);
 a.equal(cold.frames.M15.length,16);
 const reloaded=new XauusdReview(()=>now+1000);
 reloaded.restoreClosed(cold);
 a.equal(reloaded.snapshot().frames.M15.length,16);
 a.equal(reloaded.snapshot().frames.H4.length,1);
 a.equal(reloaded.snapshot().latestQuote,null);
 a.equal(reloaded.snapshot().signal,'WAIT');
 a.equal(reloaded.snapshot().executable,false);
 a.equal(reloaded.authorized,false);
 a.equal(reloaded.receive(quote(now)).reason,'AUTHORIZATION_MISSING');
 reloaded.reset('DISCONNECTED',true);
 a.equal(reloaded.snapshot().frames.M15.length,16);
 a.equal(reloaded.snapshot().latestQuote,null);
 privateSave(secure,reloaded.snapshot());
 a.equal(privateLoadClosed(secure,now).bidFrames.M15.length,16);
 // Source identity tampering, crossed quotes and future candles are all denied.
 const corrupt=JSON.parse(fs.readFileSync(path.join(secure,'eodhd-private-review.json'),'utf8'));
 corrupt.bidFrames.M15[0].high+=10000;
 privateSave(secure,corrupt);
 a.throws(()=>privateLoadClosed(secure,now),/closed history/i);
 privateSave(secure,historySnapshot);
 const badFuture=JSON.parse(fs.readFileSync(path.join(secure,'eodhd-private-review.json'),'utf8'));
 badFuture.frames.M15.at(-1).openTime=new Date(now+900000).toISOString();
 privateSave(secure,badFuture);
 a.throws(()=>privateLoadClosed(secure,now),/closed history/i);
 privateSave(secure,historySnapshot);
 const badSource={...historySnapshot,instrument:'SILVER/USD'};
 privateSave(secure,badSource);
 a.throws(()=>privateLoadClosed(secure,now),/Closed history identity/);
 privateSave(secure,payload);
 const saved=path.join(secure,'eodhd-private-review.json');
 a.equal(fs.statSync(secure).mode&0o777,0o700);
 a.equal(fs.statSync(saved).mode&0o777,0o600);
 a.deepEqual(JSON.parse(fs.readFileSync(saved,'utf8')),payload);
 fs.chmodSync(secure,0o755);
 a.throws(()=>privateSave(secure,payload),/Unsafe private snapshot directory/);
 a.throws(()=>privateLoadClosed(secure,now),/Unsafe closed history directory/);
 fs.chmodSync(secure,0o700);
 const alias=path.join(scratch,'alias');
 fs.symlinkSync(secure,alias,'dir');
 a.throws(()=>privateSave(alias,payload),/Unsafe private snapshot directory/);
 fs.chmodSync(saved,0o644);
 a.throws(()=>privateSave(secure,payload),/Unsafe private snapshot destination/);
 a.throws(()=>privateLoadClosed(secure,now),/Unsafe closed history file/);
 fs.chmodSync(saved,0o600);
 const outside=path.join(scratch,'outside.txt');
 fs.writeFileSync(outside,'untouched');
 fs.unlinkSync(saved);
 fs.symlinkSync(outside,saved);
 a.throws(()=>privateSave(secure,payload),/Unsafe private snapshot destination/);
 a.equal(fs.readFileSync(outside,'utf8'),'untouched');
 // A previous process can leave an orphan named with a reused PID.
 // Its presence must not lock the snapshot writer after restart.
 fs.unlinkSync(saved);
 const orphan=saved+'.tmp-'+process.pid;
 fs.writeFileSync(orphan,'orphaned private temp',{mode:0o600});
 privateSave(secure,{signal:'WAIT',reason:'RESTART_SAFE'});
 a.deepEqual(JSON.parse(fs.readFileSync(saved,'utf8')),
              {signal:'WAIT',reason:'RESTART_SAFE'});
 a.equal(fs.readFileSync(orphan,'utf8'),'orphaned private temp');
}finally{fs.rmSync(scratch,{recursive:true,force:true});}

console.log('PASS: EODHD offline quote checks, private snapshot isolation and WAIT');
