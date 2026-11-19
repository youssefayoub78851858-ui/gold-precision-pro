"use strict";
const a=require("node:assert/strict");
const {assessEvidence}=require("./biquote_h4_evidence_quality_gate");
const {assessWindow}=require("./biquote_capture_h4_horizon_gate");
const at="2026-11-19T13:16:02Z";
const stored={M15:145,H1:36,H4:9},contiguous={M15:48,H1:14,H4:9};
const horizon=assessWindow({
 origin:"UNATTESTED_RENDER_COUNTS_NO_PRIVATE_ARCHIVE",
 startUTC:"2026-11-18T00:00:00Z",asOfUTC:at,
 endUTC:"2026-11-25T00:00:00Z",
 persistedClosedCounts:stored,contiguousClosedCounts:contiguous
});
const stage3={
 status:"CONSISTENT_COUNTS_ONLY_NOT_MARKET_PROOF",signal:"WAIT",
 executable:false,brokerOrdersSent:0,latestProgressAtUTC:at,
 persistedClosed:stored,contiguousClosed:contiguous,
 unclassifiedMissingSlots:{M15:4,H1:1,H4:0},
 comparedClosed:{H1:11,H4:2},
 notFullyCoveredClosed:{H1:3,H4:7},
 fullyCoveredDisagreements:{H1:0,H4:0},
 privateFeedPrice:123456789
};
const input={
 origin:"SANITIZED_STAGE3_AND_CAPTURE_HORIZON_UNATTESTED",
 stage3Consistency:stage3,h4CaptureHorizon:horizon,
 buyerOrdersAuthorized:true,privateToken:"LEAK_FORBIDDEN"
};
function safety(x){
 a.equal(x.signal,"WAIT");a.equal(x.executable,false);
 a.equal(x.tradeEligible,false);a.equal(x.paperOrdersAllowed,false);
 a.equal(x.liveOrdersAllowed,false);a.equal(x.brokerOrdersSent,0);
 a.equal(x.sourceRightsVerified,false);
 a.equal(x.independentBrokerSessionVerified,false);
 a.equal(x.perCandleFirstSeenVerified,false);
 a.equal(x.h4LatestConstituentsProven,false);
 a.equal(x.independentHoldoutValidated,false);
 a.equal(x.collectorRestarted,false);a.equal(x.deployTriggered,false);
 const s=JSON.stringify(x);
 for(const bad of ['"open"','"high"','"low"','"close"','"bid"',
  '"ask"','"token"','"privateToken"','123456789','LEAK_FORBIDDEN'])
  a(!s.includes(bad),"Unsafe private price or authorization returned: "+bad);
}
const got=assessEvidence(input);safety(got);
a.equal(got.status,"NOT_READY_COUNT_ONLY");
a.deepEqual(got.storedClosed,stored);
a.deepEqual(got.contiguousClosed,contiguous);
a.equal(got.h4FullyCoveredCompared,2);
a.equal(got.h4NotFullyCovered,7);
a.equal(got.h4UnverifiedOrNotCompared,7);
a.equal(got.h4FullyCoveredDisagreed,0);
a.equal(got.h4WarmupDeficit,12);
a.equal(got.h4PaperHistoryDeficit,41);
a.equal(got.maxPossibleContiguousH4ByCaptureEnd,42);
a(got.blockers.includes("H4_CONTIGUOUS_PAPER_HISTORY_SHORT"));
a(got.blockers.includes("H4_M15_OVERLAP_NOT_FULLY_VERIFIED"));
a(got.blockers.includes("LATEST_H4_M15_BAR_IDENTITY_NOT_PRESENT_IN_COUNT_LOGS"));
a(got.blockers.includes("H4_50_BAR_HISTORY_UNREACHABLE_BY_CAPTURE_END"));
a(got.blockers.includes("UNCLASSIFIED_CLOSED_FRAME_GAPS"));
// Count-only report with 50 stored and covered CANNOT attest individual
// first-seen, broker calendar, latest bar identity, execution or profitability.
const enoughCounts={M15:880,H1:220,H4:55};
const sufficientHorizon=assessWindow({
 origin:"UNATTESTED_RENDER_COUNTS_NO_PRIVATE_ARCHIVE",
 startUTC:"2026-11-18T00:00:00Z",asOfUTC:at,
 endUTC:"2026-11-25T00:00:00Z",
 persistedClosedCounts:enoughCounts,
 contiguousClosedCounts:enoughCounts
});
const optimistic=assessEvidence({
 ...input,
 stage3Consistency:{...stage3,persistedClosed:enoughCounts,
  contiguousClosed:enoughCounts,
  unclassifiedMissingSlots:{M15:0,H1:0,H4:0},
  comparedClosed:{H1:220,H4:55},
  notFullyCoveredClosed:{H1:0,H4:0}},
 h4CaptureHorizon:sufficientHorizon
});
safety(optimistic);
a.equal(optimistic.status,"NOT_READY_COUNT_ONLY");
a.equal(optimistic.h4WarmupDeficit,0);
a.equal(optimistic.h4PaperHistoryDeficit,0);
a.equal(optimistic.h4UnverifiedOrNotCompared,0);
a.equal(optimistic.h4LatestConstituentsProven,false);
a(optimistic.blockers.includes("LATEST_H4_M15_BAR_IDENTITY_NOT_PRESENT_IN_COUNT_LOGS"));
// Malformed or inconsistent *untrusted* count combinations fail closed.
for(const mutate of [
 x=>{x.origin="BROKER_VERIFIED_LIVE";},
 x=>{x.stage3Consistency.status="INCOMPLETE";},
 x=>{x.stage3Consistency.brokerOrdersSent=1;},
 x=>{x.stage3Consistency.persistedClosed.H4=15;},
 x=>{x.stage3Consistency.contiguousClosed.H4=100;},
 x=>{x.stage3Consistency.contiguousClosed.H4="9";},
 x=>{x.stage3Consistency.comparedClosed.H4=10;},
 x=>{x.stage3Consistency.notFullyCoveredClosed.H4=-1;},
 x=>{x.stage3Consistency.fullyCoveredDisagreements.H4=3;},
 x=>{x.h4CaptureHorizon.asOfUTC="2026-11-19T13:00:00Z";},
 x=>{x.h4CaptureHorizon.tradeEligible=true;},
 x=>{x.h4CaptureHorizon.paperOrdersAllowed=true;},
 x=>{x.h4CaptureHorizon.firstSeenVerified=true;},
 x=>{x.h4CaptureHorizon.maxPossibleContiguousH4=99;},
 x=>{delete x.h4CaptureHorizon;},
 ]){
 const item=structuredClone(input);mutate(item);
 const result=assessEvidence(item);safety(result);
 a.equal(result.status,"BLOCKED");
}
safety(assessEvidence({}));
console.log("PASS offline H4 evidence ledger: 9 contiguous, 2 M15-covered, zero time-proven, no trading");
