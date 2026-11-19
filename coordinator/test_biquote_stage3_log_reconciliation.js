"use strict";
const assert=require("node:assert/strict");
const {reconcile}=require("./biquote_stage3_log_reconciliation");
const ISO="2026-11-19T11:30:02.";
const base={signal:"WAIT",executable:false,paperOrdersAllowed:false,brokerOrdersSent:0,dayIndex:1};
const progress={
 ...base,event:"BIQUOTE_STAGE3_CLOSED_BAR_PROGRESS",atUTC:ISO+"907797Z",
 frames:{
  M15:{persistedClosed:138,contiguousClosed:48,unclassifiedMissingSlots:4},
  H1:{persistedClosed:34,contiguousClosed:12,unclassifiedMissingSlots:1},
  H4:{persistedClosed:8,contiguousClosed:8,unclassifiedMissingSlots:0}
 }
};
const gap={
 ...base,event:"BIQUOTE_STAGE3_VENDOR_REFERENCE_GAPS",atUTC:ISO+"913637Z",phase:"NEW_CLOSED_BAR",
 frames:{M15:{unclassifiedMissingSlots:4},H1:{unclassifiedMissingSlots:1},
         H4:{unclassifiedMissingSlots:0}}
};
const overlap={
 ...base,event:"BIQUOTE_STAGE3_ARCHIVE_OHLC_OVERLAP",atUTC:ISO+"914494Z",phase:"NEW_CLOSED_BAR",
 frames:{
  H1:{fullyCoveredCompared:11,fullyCoveredDisagreed:0,
      higherClosedExamined:12,notFullyCovered:1},
  H4:{fullyCoveredCompared:2,fullyCoveredDisagreed:0,
      higherClosedExamined:8,notFullyCovered:6}
 }
};
const cadence={
 ...base,event:"BIQUOTE_STAGE3_QUOTE_RECEIPT_CADENCE",atUTC:ISO+"923920Z",phase:"NEW_CLOSED_BAR",
 sourceQuoteSamples:751,observedIntervals:750,
 intervalBins:{GT_150_LE_300_SECONDS:13,GT_300_LE_600_SECONDS:0,
  GT_3600_SECONDS:1,GT_600_LE_3600_SECONDS:0,LE_150_SECONDS:736}
};
function safe(res){
 assert.equal(res.signal,"WAIT");assert.equal(res.executable,false);
 assert.equal(res.tradeEligible,false);assert.equal(res.liveOrdersAllowed,false);
 assert.equal(res.paperOrdersAllowed,false);assert.equal(res.brokerOrdersSent,0);
 assert.equal(res.providerRequestsMade,0);
 assert.equal(res.firstObservedClosedUTCVerified,false);
 assert.equal(res.brokerRightsVerified,false);
 assert.equal(res.brokerSessionCalendarVerified,false);
 assert.equal(res.independentPriceParityVerified,false);
 assert.equal(res.executionBidAskVerified,false);
 assert.equal(res.independentTradeProfitabilityProven,false);
 for(const leak of ['"open"','"high"','"low"','"close"','"bid"','"ask"',
  '"price"','"token"','BROKER_SECRET'])
  assert(!JSON.stringify(res).includes(leak));
}
const fixture=[cadence,gap,progress,overlap];
const good=reconcile({records:fixture});safe(good);
assert.equal(good.status,"CONSISTENT_COUNTS_ONLY_NOT_MARKET_PROOF");
assert.equal(good.matchedEventCount,4);
assert.deepEqual(good.persistedClosed,{M15:138,H1:34,H4:8});
assert.deepEqual(good.unclassifiedMissingSlots,{M15:4,H1:1,H4:0});
assert.deepEqual(good.fullyCoveredDisagreements,{H1:0,H4:0});
assert.deepEqual(good.comparedClosed,{H1:11,H4:2});
assert.equal(good.sourceQuoteSamples,751);
assert(good.blockers.includes("UNCLASSIFIED_CLOSED_CANDLE_GAPS"));
assert(good.blockers.includes("PARTIAL_M15_OVERLAP_NOT_VERIFIED"));
// Missing logs must never be silently manufactured as a complete cycle.
const incomplete=reconcile({records:fixture.filter(x=>x!==overlap)});safe(incomplete);
assert.equal(incomplete.status,"INCOMPLETE");
assert.equal(incomplete.matchedEventCount,3);
// The report cannot claim zero disagreements without an examined group.
assert.equal(incomplete.fullyCoveredDisagreements.H4,null);
const bad=[
 xs=>{xs[0].observedIntervals=749;},
 xs=>{xs[0].intervalBins.LE_150_SECONDS=735;},
 xs=>{xs[1].frames.H1.unclassifiedMissingSlots=0;},
 xs=>{xs[3].frames.H4.fullyCoveredCompared=3;},
 xs=>{xs[3].frames.H1.fullyCoveredDisagreed=12;},
 xs=>{xs[2].frames.H4.contiguousClosed=9;},
 xs=>{xs[2].frames.M15.persistedClosed=-1;},
 xs=>{xs[1].signal="SELL";},
 xs=>{xs[0].paperOrdersAllowed=true;},
 xs=>{xs[0].atUTC="2026-11-19T11:40:00Z";},
 xs=>{xs[0].intervalBins.LE_150_SECONDS=-1;},
 xs=>{xs[0].intervalBins.SECRET=1;},
 xs=>{xs[3].frames.H1.higherClosedExamined=35;},
 xs=>{xs[1].dayIndex=4;},
 xs=>{xs[2].atUTC="2026-11-19T11:30:02+00:00";},
];
for(const mutate of bad){
 const xs=structuredClone(fixture);mutate(xs);
 const got=reconcile({records:xs});safe(got);
 assert.notEqual(got.status,"CONSISTENT_COUNTS_ONLY_NOT_MARKET_PROOF");
}
// Duplicate events for the same read-only sample do not count as extra proof.
const duplicate=reconcile({records:[...fixture,gap]});safe(duplicate);
assert.equal(duplicate.status,"BLOCKED");
// Prior progress checks cannot regress even if latest tuple is consistent.
const prior=structuredClone(progress);
prior.atUTC="2026-11-19T11:00:03Z";
prior.frames.M15.persistedClosed=140;
const regressing=reconcile({records:[prior,...fixture]});safe(regressing);
assert.equal(regressing.status,"BLOCKED");
// Two real-like Stage3 cycles: 11:30 with 751 quotes, 11:46 with 759.
const olderCycle=structuredClone(fixture);
const newerCycle=structuredClone(fixture).map(x=>{
 x.atUTC=x.atUTC.replace("11:30:02","11:46:02");
 if(x.event==="BIQUOTE_STAGE3_CLOSED_BAR_PROGRESS")
  x.frames.M15.persistedClosed=139;
 if(x.event==="BIQUOTE_STAGE3_QUOTE_RECEIPT_CADENCE"){
  x.sourceQuoteSamples=759;x.observedIntervals=758;
  x.intervalBins.LE_150_SECONDS=744;
 }
 return x;
});
const twice=reconcile({records:[...newerCycle,...olderCycle]});
safe(twice);
assert.equal(twice.status,"CONSISTENT_COUNTS_ONLY_NOT_MARKET_PROOF");
assert.equal(twice.checkedProgressEvents,2);
assert.equal(twice.checkedQuoteCadenceEvents,2);
assert.equal(twice.sourceQuoteSamples,759);
assert.equal(twice.persistedClosed.M15,139);
// Latest healthy counts may never hide a *previous* quote counter regression.
const futureRollback=structuredClone(newerCycle);
const afterRollback=futureRollback.find(x=>x.event==="BIQUOTE_STAGE3_QUOTE_RECEIPT_CADENCE");
afterRollback.sourceQuoteSamples=750;
afterRollback.observedIntervals=749;
afterRollback.intervalBins.LE_150_SECONDS=735;
const rolled=reconcile({records:[...olderCycle,...futureRollback]});
safe(rolled);assert.equal(rolled.status,"BLOCKED");
assert(rolled.blockers.includes("HISTORICAL_STAGE3_QUOTE_CADENCE_REGRESSION"));
// Individual cadence buckets cannot go backward while the total grows.
const binsRolled=structuredClone(newerCycle);
const shrinkingBin=binsRolled.find(x=>x.event==="BIQUOTE_STAGE3_QUOTE_RECEIPT_CADENCE");
shrinkingBin.intervalBins.GT_150_LE_300_SECONDS=12;
shrinkingBin.intervalBins.LE_150_SECONDS=745;
const ruled=reconcile({records:[...olderCycle,...binsRolled]});
safe(ruled);assert.equal(ruled.status,"BLOCKED");
assert(ruled.blockers.includes("HISTORICAL_STAGE3_QUOTE_CADENCE_REGRESSION"));
// Even if the latest cadence is good, an older internally forged sum blocks.
const invalidHistory=structuredClone(olderCycle);
invalidHistory.find(x=>x.event==="BIQUOTE_STAGE3_QUOTE_RECEIPT_CADENCE")
 .intervalBins.LE_150_SECONDS=10;
const badHistory=reconcile({records:[...invalidHistory,...newerCycle]});
safe(badHistory);assert.equal(badHistory.status,"BLOCKED");
assert(badHistory.blockers.includes("HISTORICAL_STAGE3_QUOTE_CADENCE_CONTRADICTORY"));

// Unknown log payload cannot turn into broker permission or price evidence.
const forged=reconcile({records:fixture.map(x=>({...x,canTrade:true,
 sourceRightsVerified:true,privateCandlePrice:"BROKER_SECRET"}))});
safe(forged);assert.equal(forged.status,good.status);
assert.equal(reconcile({records:[]}).status,"INCOMPLETE");
assert.equal(reconcile({records:null}).status,"BLOCKED");
console.log("PASS BiQuote Stage3 read-only counter reconciliation: M15/H1/H4, gap parity, OHLC windows, quote cadence, no orders");
