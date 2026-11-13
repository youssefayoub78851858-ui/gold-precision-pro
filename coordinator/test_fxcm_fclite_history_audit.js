'use strict';
// Pure mocks of documented FCLite methods: never import/install SDK or call FXCM.
const assert=require('node:assert/strict');
const {auditFcliteHistory}=require('./fxcm_fclite_history_audit');
const fixed={asOfUTC:'2026-11-13T16:00:00Z'};
function fixture(changes={}){
 const rows={Open:4000,High:4002,Low:3998,Close:4001};
 const h={getCount:()=>1,getDate:()=>changes.time||'2026-11-13T15:45:00Z'};
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
console.log('PASS: FCLite historical getter audit, 8 isolated assertions, no market-data connection');
