'use strict';
// Pure mocks of documented FCLite methods: never import/install SDK or call FXCM.
const assert=require('node:assert/strict');
const {auditFcliteHistory}=require('./fxcm_fclite_history_audit');
const fixed={asOfUTC:'2026-11-13T16:00:00Z'};
function fixture(changes={}){
 const rows={Open:4000,High:4002,Low:3998,Close:4001};
 const h={getCount:()=>1,isBar:()=>changes.ticks?false:true,getDate:()=>changes.time||'2026-11-13T15:45:00Z'};
 for(const k of Object.keys(rows)){
  h['getBid'+k]=()=>changes.nan&&k==='High'?NaN:rows[k];
  h['getAsk'+k]=()=>changes.crossed?rows[k]-.2:rows[k]+.2;
 }
 return h;
}
function safe(r){
 assert.equal(r.signal,'WAIT');assert.equal(r.executable,false);
 assert.equal(r.paperOrdersAllowed,false);assert.equal(r.researchEligible,false);
 assert.equal(r.sourceRequestsMade,0);assert.equal(r.ordersSent,0);
 assert.equal(r.sdkLoaded,false);assert.equal(r.credentialsRead,false);
 assert.equal(r.liveQuoteHistoryParityVerified,false);
 assert.equal(r.sourceRightsVerified,false);assert.equal(r.engineStatus,'NOT_INVOKED');
}
const good=auditFcliteHistory(fixture(),fixed);safe(good);
assert.equal(good.structurallyValid,true);assert.equal(good.closedCandlesInspected,1);
for(const [change,error] of [
 [{crossed:true},'INVALID_OR_CROSSED_BID_ASK'],
 [{nan:true},'INVALID_OR_CROSSED_BID_ASK'],
 [{time:'2026-11-13T16:00:00Z'},'INCOMPLETE_OR_FUTURE_CANDLE'],
 [{time:'2026-11-13T17:45:00+02:00'},'UTC_ISO_Z_REQUIRED']
]){const r=auditFcliteHistory(fixture(change),fixed);safe(r);assert.equal(r.structurallyValid,false);assert(r.blockingReasons.includes(error));}
const missing=auditFcliteHistory({...fixture(),getBidClose:undefined},fixed);
safe(missing);assert(missing.blockingReasons.includes('BID_ASK_HISTORY_GETTERS_MISSING'));
const forged=auditFcliteHistory({...fixture(),rightsApproved:true,executable:true,paperOrdersAllowed:true},fixed);
safe(forged);assert.equal(forged.structurallyValid,true);
const wrong=auditFcliteHistory(fixture(),{...fixed,symbol:'GC'});safe(wrong);
assert(wrong.blockingReasons.includes('WRONG_INSTRUMENT'));

const dateResponse=auditFcliteHistory(fixture({time:new Date('2026-11-13T15:45:00Z')}),fixed);
safe(dateResponse);assert.equal(dateResponse.structurallyValid,true);
for(const [change,code] of [
 [{ticks:true},'TICK_HISTORY_IS_NOT_CANDLE_HISTORY'],
 [{time:new Date('invalid')},'INVALID_UTC_TIME'],
]){
 const result=auditFcliteHistory(fixture(change),fixed);
 safe(result);assert(result.blockingReasons.includes(code));
}
const noBarFlag=auditFcliteHistory({...fixture(),isBar:undefined},fixed);
safe(noBarFlag);assert(noBarFlag.blockingReasons.includes('BID_ASK_HISTORY_GETTERS_MISSING'));
const base=Date.parse('2026-11-13T12:00:00Z');
function multiFrame(factor,changes={}){
 const recs=Array.from({length:16/factor},(_,i)=>({
  t:new Date(base+i*factor*900000),o:4000+i*factor*.01,
 }));
 const h={getCount:()=>recs.length,isBar:()=>true,getDate:i=>recs[i].t};
 for(const k of ['Open','High','Low','Close']){
  h['getBid'+k]=i=>{
   const r=recs[i];
   const p={Open:r.o,High:r.o+.4+(factor-1)*.01,
    Low:r.o-.2,Close:r.o+(factor-1)*.01+.1};
   return p[k]+(changes.changeClose&&factor===16&&k==='Close'?.1:0);
  };
  h['getAsk'+k]=i=>h['getBid'+k](i)+.2;
 }
 return h;
}
function fixtureBundle(changes={}){return {
 M15:multiFrame(1),H1:multiFrame(4),H4:multiFrame(16,changes)
};}
const bundle=stageFcliteBundle(fixtureBundle(),fixed);
safe(bundle);assert.equal(bundle.structurallyValid,true);
assert.deepEqual(bundle.closedBarCounts,{M15:16,H1:4,H4:1});
assert.equal(bundle.quarantinedBidAskFrames.M15[0].bid.open,4000);
assert.equal(bundle.quarantinedBidAskFrames.M15[0].ask.open,4000.2);
assert.equal(bundle.readyForPaper,false);assert.equal(bundle.geometricWarmupOnly,false);
const mismatch=stageFcliteBundle(fixtureBundle({changeClose:true}),fixed);
safe(mismatch);assert.equal(mismatch.structurallyValid,false);
assert(mismatch.blockingReasons.includes('CROSS_TIMEFRAME_BID_ASK_OHLC_MISMATCH'));
assert.deepEqual(mismatch.quarantinedBidAskFrames,{});
const partial=stageFcliteBundle({...fixtureBundle(),M15:{...multiFrame(1),getCount:()=>15}},fixed);
safe(partial);assert(partial.blockingReasons.includes('PARTIAL_CROSS_TIMEFRAME_COVERAGE'));
const missingAggregate=stageFcliteBundle({...fixtureBundle(),H1:{...multiFrame(4),getCount:()=>3}},fixed);
safe(missingAggregate);assert(missingAggregate.blockingReasons.includes('MISSING_CROSS_TIMEFRAME_AGGREGATE'));
const missingFrame=stageFcliteBundle({M15:multiFrame(1),H1:multiFrame(4)},fixed);
safe(missingFrame);assert(missingFrame.blockingReasons.includes('THREE_FRAMES_REQUIRED'));

console.log('PASS: FCLite historical getter audit, 8 isolated assertions, no market-data connection');
