'use strict';
// 800 closed, correctly aligned M15 BID/ASK bars (50 H4) and simulated
// session closure/restart. Synthetic quotes only; no provider/secret/trading.
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {XauusdReview,aggregate,privateSave,privateLoadClosed,coldStartReview}=require('./eodhd_ws_bridge');
const M15=900000,START=Date.parse('2026-11-02T00:00:00.000Z');
assert.equal(START%(16*M15),0);
const days=[{start:START,bars:480},{start:START+7*24*60*60*1000,bars:320}];
let now=START,network=0;
const review=new XauusdReview(()=>now+1000);
const good=review.receive({status_code:200});
assert.equal(good.kind,'authorized');
function send(at,index){
 now=at;
 const bid=3900+Math.sin(index/19)*2.0+index*0.0005;
 const reply=review.receive({s:'XAUUSD',t:at,b:bid,a:bid+0.4});
 assert.equal(reply.kind,'quote',JSON.stringify({index,at,reply}));
 assert.equal(reply.signal,'WAIT');
 assert.equal(reply.executable,false);
}
for(let k=0;k<days.length;k++){
 const {start,bars}=days[k];
 if(k>0){
  const before=review.snapshot();
  assert.equal(before.frames.M15.length,480);
  assert.equal(before.latestQuote,null);
  assert.equal(review.receive({s:'XAUUSD',t:start+30000,b:3900,a:3900.4}).reason,'AUTHORIZATION_MISSING');
  assert.equal(review.receive({status_code:200}).kind,'authorized');
 }
 for(let i=0;i<bars;i++){
  for(let minute=0;minute<15;minute++)
   send(start+i*M15+30000+minute*60000,480*k+i);
 }
 // A next-frame tick confirms that the previous 15-minute candle completed,
 // but the newly open candle must be discarded across a simulated closure.
 send(start+bars*M15+30000,bars+480*k);
 const expectedClosed=k===0?480:800;
 const saved=review.snapshot();
 assert.equal(saved.frames.M15.length,expectedClosed);
 assert.equal(saved.bidFrames.M15.length,expectedClosed);
 assert.equal(saved.askFrames.M15.length,expectedClosed);
 assert.equal(saved.frames.H1.length,expectedClosed/4);
 assert.equal(saved.frames.H4.length,expectedClosed/16);
 assert.equal(saved.signal,'WAIT');
 assert.equal(saved.executable,false);
 assert.equal(saved.researchEligible,false);
 if(k===0){
  review.reset('OFFLINE_SIMULATED_48H_CLOSURE',true);
  assert.equal(review.snapshot().latestQuote,null);
  assert.equal(review.snapshot().frames.H4.length,30);
 }
}
const full=review.snapshot();
assert.deepEqual([full.frames.M15.length,full.frames.H1.length,full.frames.H4.length],[800,200,50]);
assert.deepEqual([full.bidFrames.M15.length,full.bidFrames.H1.length,full.bidFrames.H4.length],[800,200,50]);
assert.deepEqual([full.askFrames.M15.length,full.askFrames.H1.length,full.askFrames.H4.length],[800,200,50]);
assert.equal(full.closedHistoryGaps.unverifiedM15Discontinuities,1);
assert.equal(full.closedHistoryGaps.largestUnverifiedGapMinutes,48*60+15);
assert.equal(full.closedHistoryGaps.longestContiguousClosedM15,480);
for(const key of ['sessionVerified','indicatorWarmupReady','researchEligible','readyForTrading','executable'])
 assert.equal(full[key],false,'Counts cannot certify '+key);
assert.equal(full.closedHistoryGaps.independentlyVerifiedSessionCalendar,false);
assert.equal(full.signal,'WAIT');
// One absent M15 bar (even with 799 others) removes an entire H1 and H4.
const missing=full.bidFrames.M15.filter((_,i)=>i!==580);
assert.deepEqual([missing.length,aggregate(missing,4).length,aggregate(missing,16).length],[799,199,49]);
const root=fs.mkdtempSync(path.join(os.tmpdir(),'xau-first-month-'));
try{
 const dir=path.join(root,'private');
 privateSave(dir,full);
 const recovered=privateLoadClosed(dir,now+1000);
 assert.deepEqual([recovered.bidFrames.M15.length,recovered.bidFrames.M15.at(-1).openTime],
                  [800,full.bidFrames.M15.at(-1).openTime]);
 const cold=new XauusdReview(()=>now+2000);
 coldStartReview(cold,dir,now+1000);
 const snapshot=cold.snapshot();
 assert.deepEqual([snapshot.frames.M15.length,snapshot.frames.H1.length,snapshot.frames.H4.length],
                  [800,200,50]);
 assert.equal(snapshot.latestQuote,null);
 assert.equal(snapshot.authorized,undefined); // auth is private on review instance, never snapshotted
 assert.equal(cold.authorized,false);
 assert.equal(snapshot.executable,false);
 assert.equal(snapshot.researchEligible,false);
 assert.equal(snapshot.indicatorWarmupReady,false);
 assert.equal(snapshot.closedHistoryGaps.unverifiedM15Discontinuities,1);
 assert.equal(cold.receive({s:'XAUUSD',t:now+1000,b:4000,a:4000.4}).reason,'AUTHORIZATION_MISSING');
 const privateDisk=JSON.parse(fs.readFileSync(path.join(dir,'eodhd-private-review.json'),'utf8'));
 assert.equal(privateDisk.latestQuote,null);
 assert.equal(privateDisk.signal,'WAIT');
}finally{fs.rmSync(root,{force:true,recursive:true});}
assert.equal(network,0);
console.log(JSON.stringify({
 status:'PASS',scenario:'OFFLINE_SYNTHETIC_50_H4_WITH_48H_ASSUMED_CLOSURE',
 syntheticClosedM15:800,syntheticClosedH1:200,syntheticClosedH4:50,
 absentM15MakesH4:49,unverifiedM15Discontinuities:1,
 brokerConnections:0,providerRequests:0,paidKeysRead:0,ordersSent:0,
 signal:'WAIT',executable:false,sourceRightsVerified:false,
 independentMarketScheduleVerified:false,livePerformanceValidated:false
}));
