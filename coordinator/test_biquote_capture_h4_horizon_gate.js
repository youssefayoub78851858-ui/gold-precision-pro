"use strict";
const assert=require("node:assert/strict");
const {assessWindow}=require("./biquote_capture_h4_horizon_gate");
const input={
 origin:"UNATTESTED_RENDER_COUNTS_NO_PRIVATE_ARCHIVE",
 startUTC:"2026-11-18T00:00:00Z",
 asOfUTC:"2026-11-19T12:46:02Z",
 endUTC:"2026-11-25T00:00:00Z",
 persistedClosedCounts:{M15:143,H1:35,H4:9},
 contiguousClosedCounts:{M15:48,H1:13,H4:9},
 privateH4OHLC:["NEVER_RETURN_PRICE_OR_VAULT"]
};
const out=assessWindow(input);
function safe(o){
 assert.equal(o.signal,"WAIT");assert.equal(o.executable,false);
 assert.equal(o.tradeEligible,false);assert.equal(o.liveOrdersAllowed,false);
 assert.equal(o.paperOrdersAllowed,false);assert.equal(o.brokerOrdersSent,0);
 assert.equal(o.sourceRequestsMade,0);assert.equal(o.firstSeenVerified,false);
 assert.equal(o.brokerSessionCalendarVerified,false);
 assert.equal(o.brokerRightsVerified,false);assert.equal(o.backupVerified,false);
 assert.equal(o.independentHoldoutValidated,false);
 assert.equal(o.captureExtended,false);assert.equal(o.collectorRestarted,false);
 const s=JSON.stringify(o);
 for(const key of ["NEVER_RETURN_PRICE_OR_VAULT",'"open"','"high"',
  '"low"','"close"','"bid"','"ask"','"token"','"password"'])
  assert(!s.includes(key));
}
safe(out);
assert.equal(out.status,"THEORETICAL_COUNT_CEILING_NOT_READINESS");
assert.equal(out.hypotheticalFutureH4Closures,33);
assert.equal(out.maxPossibleStoredH4,42);
assert.equal(out.maxPossibleContiguousH4,42);
assert.equal(out.rawStoredH4CountReachableByWindowEnd,false);
assert.equal(out.theoreticalWarmupH4ReachableByWindowEnd,true);
assert.equal(out.paperH4HistoryReachableByWindowEnd,false);
assert.equal(out.minPaperHistoryH4,50);
assert(out.blockers.includes(
 "H4_50_BAR_PAPER_HISTORY_MATHEMATICALLY_UNREACHABLE"));
// There is NO implied approval even if an optimistic hypothetical does
// reach 50 bars; the live collector has no per-candle first-receipt proof.
const optimistic=assessWindow({...input,persistedClosedCounts:
 {...input.persistedClosedCounts,H4:22},contiguousClosedCounts:
 {...input.contiguousClosedCounts,H4:22}});
safe(optimistic);
assert.equal(optimistic.maxPossibleStoredH4,55);
assert.equal(optimistic.paperH4HistoryReachableByWindowEnd,true);
assert.equal(optimistic.maxPossibleContiguousH4,55);
assert.equal(optimistic.tradeEligible,false);
// 50 stored H4 bars with a broken latest contiguous sequence do NOT
// qualify for a 50-H4 walk-forward paper history. Historical orphaned
// candles cannot replace missing closed slots or first-seen timestamps.
const broken=assessWindow({...input,persistedClosedCounts:
 {...input.persistedClosedCounts,H4:60},contiguousClosedCounts:
 {...input.contiguousClosedCounts,H4:9}});
safe(broken);
assert.equal(broken.rawStoredH4CountReachableByWindowEnd,true);
assert.equal(broken.maxPossibleStoredH4,93);
assert.equal(broken.maxPossibleContiguousH4,42);
assert.equal(broken.paperH4HistoryReachableByWindowEnd,false);
assert(broken.blockers.includes("RAW_H4_COUNT_CANNOT_REPLACE_CONTIGUOUS_HISTORY"));
// Halting at UTC midnight can only REDUCE the theoretical bound.
const nearEnd=assessWindow({...input,
 asOfUTC:"2026-11-24T23:58:00Z"});
safe(nearEnd);
assert.equal(nearEnd.hypotheticalFutureH4Closures,1);
assert.equal(nearEnd.maxPossibleStoredH4,10);
assert.equal(nearEnd.maxPossibleContiguousH4,10);
assert.equal(nearEnd.paperH4HistoryReachableByWindowEnd,false);
// Invented data, consent extensions and unbounded windows fail closed.
for(const mutate of [
 x=>{x.origin="REAL_BROKER_APPROVED";},
 x=>{x.endUTC="2026-11-26T00:00:00Z";},
 x=>{x.endUTC="2026-11-19T12:40:00Z";},
 x=>{x.asOfUTC="2026-11-18T00:00:00+00:00";},
 x=>{x.persistedClosedCounts.H4=-1;},
 x=>{x.persistedClosedCounts.H4="9";},
 x=>{x.persistedClosedCounts.H4=NaN;},
 x=>{x.persistedClosedCounts.H4=3.5;},
 x=>{delete x.persistedClosedCounts.H4;},
 x=>{x.persistedClosedCounts.SECRET=12;},
 x=>{delete x.contiguousClosedCounts;},
 x=>{x.contiguousClosedCounts.H4=10;},
 x=>{x.contiguousClosedCounts.H4=-1;},
 x=>{x.contiguousClosedCounts.H4="9";},
 x=>{x.contiguousClosedCounts.M15=151;},
 x=>{x.contiguousClosedCounts.SECRET=1;},
]){
 const item=structuredClone(input);mutate(item);
 const blocked=assessWindow(item);
 safe(blocked);assert.equal(blocked.status,"BLOCKED");
}
safe(assessWindow({}));
console.log("PASS no-network H4 capture horizon: contiguous-tail and raw counts are separate; 9+33 < 50 paper, trading WAIT");
