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
// Unknown log payload cannot turn into broker permission or price evidence.
const forged=reconcile({records:fixture.map(x=>({...x,canTrade:true,
 sourceRightsVerified:true,privateCandlePrice:"BROKER_SECRET"}))});
safe(forged);assert.equal(forged.status,good.status);
assert.equal(reconcile({records:[]}).status,"INCOMPLETE");
assert.equal(reconcile({records:null}).status,"BLOCKED");
console.log("PASS BiQuote Stage3 read-only counter reconciliation: M15/H1/H4, gap parity, OHLC windows, quote cadence, no orders");
