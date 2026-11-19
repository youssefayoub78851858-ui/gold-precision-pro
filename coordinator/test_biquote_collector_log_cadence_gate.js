"use strict";
const assert=require("node:assert/strict");
const {audit}=require("./biquote_collector_log_cadence_gate");
const START=Date.parse("2026-11-19T11:00:00Z");
const iso=t=>new Date(t).toISOString().replace(".000Z","Z");
const frames={
 M15:{persistedClosed:136,contiguousClosed:48,unclassifiedMissingSlots:4},
 H1:{persistedClosed:34,contiguousClosed:12,unclassifiedMissingSlots:1},
 H4:{persistedClosed:8,contiguousClosed:8,unclassifiedMissingSlots:0}
};
const input={
 origin:"RENDER_SANITIZED_COLLECTOR_LOGS_UNATTESTED",
 startUTC:iso(START),endUTC:iso(START+6*120000+10000),
 samples:Array.from({length:7},(_,i)=>({
  asOfUTC:iso(START+i*120000+3000),slot:330+i,
  archiveSavedSnapshotsSoFar:324+i,archiveRejectedSnapshotsSoFar:7,
  archiveRejectionClass:"NONE",
  signal:"WAIT",executable:false,httpAllOk:true,geometryChecksOk:false,
  geometryFailureClass:"UNCLASSIFIED_M15_COVERAGE_GAP"
 })),
 progress:[{atUTC:iso(START+3016),frames,signal:"WAIT",executable:false,
            paperOrdersAllowed:false,brokerOrdersSent:0}]
};
function checked(r){
 assert.equal(r.signal,"WAIT");assert.equal(r.executable,false);
 assert.equal(r.tradeEligible,false);assert.equal(r.researchEligible,false);
 assert.equal(r.liveOrdersAllowed,false);assert.equal(r.paperOrdersAllowed,false);
 assert.equal(r.brokerOrdersSent,0);assert.equal(r.paperOrdersCreated,0);
 assert.equal(r.collectorRestarted,false);assert.equal(r.deployTriggered,false);
 assert.equal(r.providerRequestsMade,0);
 assert.equal(r.firstSeenPerClosedBarVerified,false);
 assert.equal(r.sourceRightsVerified,false);
 assert.equal(r.brokerCalendarVerified,false);
 assert.equal(r.profitabilityProven,false);
 const text=JSON.stringify(r);
 for(const privateKey of ['"bid"','"ask"','"open"','"high"','"low"',
                          '"close"','"price"','"token"'])
  assert(!text.includes(privateKey),"No private payload may leave log audit");
}
const good=audit(input);checked(good);
assert.equal(good.status,"OBSERVED_LOG_CADENCE_ONLY_NOT_MARKET_PROOF");
assert.equal(good.sampleCount,7);
assert.equal(good.missingLogSlots,0);
assert.equal(good.recordedArchiveIncrease,6);
assert.equal(good.recordedArchiveRejectionsIncrease,0);
assert.equal(good.newlyRejectedArchiveClasses.CLOSED_HISTORY_FRESHNESS,0);
assert.equal(good.newRejectionsWithUnknownClass,0);
assert.equal(good.collectorSlotsWithoutRecordedArchiveOutcome,0);
assert.equal(good.httpNonOkSamples,0);
assert.equal(good.geometryNotOkSamples,7);
assert.equal(good.geometryFailureClassCounts.UNCLASSIFIED_M15_COVERAGE_GAP,7);
assert.equal(good.geometryFailureClassCounts.OHLC_PRICE_DISAGREEMENT,0);
assert(good.blockerCodes.includes("REPORTED_M15_CONSTITUENT_COVERAGE_GAP"));
assert(good.blockerCodes.includes("COLLECTOR_OHLC_GEOMETRY_NOT_PROVEN"));
assert.equal(good.latestSavedSnapshots,330);
assert.equal(good.latestRejectedSnapshots,7);
assert.equal(good.unclassifiedFrameGaps.M15,4);
assert.equal(good.unclassifiedFrameGaps.H1,1);
assert.equal(good.unclassifiedFrameGaps.H4,0);
assert(good.blockerCodes.includes("RUNNING_LEGACY_COLLECTOR_HAS_NO_PER_CANDLE_FIRST_SEEN"));
assert(good.blockerCodes.includes("UNCLASSIFIED_CLOSED_BAR_TIME_GAPS_PRESENT"));
// A missing 2-minute slot in the logs is not dismissed as an allowed market pause.
const absent=structuredClone(input);
absent.samples.splice(3,1);
const hole=audit(absent);checked(hole);
assert.equal(hole.status,"PARTIAL_LOG_COVERAGE_NOT_PROOF");
assert.equal(hole.missingLogSlots,1);
assert(hole.blockerCodes.includes("MISSING_COLLECTOR_LOG_SLOTS"));
// One slot can be saved OR rejected, never counted twice.
const double=structuredClone(input);
double.samples[4].archiveRejectedSnapshotsSoFar++;
for(let i=5;i<double.samples.length;i++)double.samples[i].archiveRejectedSnapshotsSoFar++;
const over=audit(double);checked(over);
assert.equal(over.status,"BLOCKED");
assert(over.blockerCodes.includes("NONMONOTONIC_OR_CONTRADICTORY_SAMPLE_SERIES"));
// Missing archive outcomes are insufficient capture evidence even with every log.
const noSave=structuredClone(input);
for(let i=3;i<noSave.samples.length;i++)noSave.samples[i].archiveSavedSnapshotsSoFar--;
const lacking=audit(noSave);checked(lacking);
assert.equal(lacking.status,"PARTIAL_LOG_COVERAGE_NOT_PROOF");
assert.equal(lacking.collectorSlotsWithoutRecordedArchiveOutcome,1);
assert(lacking.blockerCodes.includes("COLLECTOR_SLOTS_WITHOUT_ARCHIVE_OUTCOME"));
const http=structuredClone(input);http.samples[4].httpAllOk=false;
const httpReport=audit(http);checked(httpReport);
assert.equal(httpReport.httpNonOkSamples,1);
assert(httpReport.blockerCodes.includes("HTTP_NON_OK_COLLECTOR_LOG_SAMPLES"));
// Actual-shaped 11:58/12:00 collector counters: archive rejects a
// stale closed candle while HTTP succeeds, but no market order can follow.
const freshness=structuredClone(input);
freshness.startUTC="2026-11-19T11:58:00Z";
freshness.endUTC="2026-11-19T12:00:13Z";
freshness.samples=[
 {asOfUTC:"2026-11-19T11:58:03Z",slot:359,
  archiveSavedSnapshotsSoFar:353,archiveRejectedSnapshotsSoFar:7,
  archiveRejectionClass:"NONE",
  signal:"WAIT",executable:false,httpAllOk:true,
  geometryChecksOk:false,geometryFailureClass:"UNCLASSIFIED_M15_COVERAGE_GAP"},
 {asOfUTC:"2026-11-19T12:00:03Z",slot:360,
  archiveSavedSnapshotsSoFar:353,archiveRejectedSnapshotsSoFar:8,
  archiveRejectionClass:"CLOSED_HISTORY_FRESHNESS",
  signal:"WAIT",executable:false,httpAllOk:true,
  geometryChecksOk:false,geometryFailureClass:"UNCLASSIFIED_M15_COVERAGE_GAP"}
];
freshness.progress=[{atUTC:"2026-11-19T11:58:03Z",frames,
 signal:"WAIT",executable:false,paperOrdersAllowed:false,brokerOrdersSent:0}];
const freshnessResult=audit(freshness);checked(freshnessResult);
assert.equal(freshnessResult.status,"OBSERVED_LOG_CADENCE_ONLY_NOT_MARKET_PROOF");
assert.equal(freshnessResult.recordedArchiveIncrease,0);
assert.equal(freshnessResult.recordedArchiveRejectionsIncrease,1);
assert.equal(freshnessResult.newlyRejectedArchiveClasses.CLOSED_HISTORY_FRESHNESS,1);
assert.equal(freshnessResult.newRejectionsWithUnknownClass,0);
assert(freshnessResult.blockerCodes.includes("ARCHIVE_CLOSED_HISTORY_FRESHNESS_REJECTED"));
const forgedReason=structuredClone(freshness);
forgedReason.samples[1].archiveRejectionClass="NONE";
const reasonBlocked=audit(forgedReason);checked(reasonBlocked);
assert.equal(reasonBlocked.status,"BLOCKED");
const phantomReject=structuredClone(input);
phantomReject.samples[4].archiveRejectionClass="CLOSED_HISTORY_FRESHNESS";
const phantomBlocked=audit(phantomReject);checked(phantomBlocked);
assert.equal(phantomBlocked.status,"BLOCKED");
// HTTP 200 does NOT imply price or closed-candle geometry validation.
assert.equal(good.geometryNotOkSamples,good.sampleCount);
// A caller cannot infer continuous collection from an unbounded or truncated query.
const truncated=structuredClone(input);truncated.samples.shift();
assert.equal(audit(truncated).logWindowEdgesObserved,false);
assert.equal(audit(truncated).status,"PARTIAL_LOG_COVERAGE_NOT_PROOF");
const late=structuredClone(input);late.progress=[];
assert.equal(audit(late).status,"PARTIAL_LOG_COVERAGE_NOT_PROOF");
// Inconsistent counters and fake trade eligibility fail closed.
const corruption=[
 x=>{x.samples[4].archiveSavedSnapshotsSoFar=100;},
 x=>{x.samples[4].archiveSavedSnapshotsSoFar=5;},
 x=>{x.samples[5].slot=x.samples[4].slot;},
 x=>{x.samples[5].asOfUTC=x.samples[4].asOfUTC;},
 x=>{x.samples[4].signal="BUY";},
 x=>{delete x.samples[4].httpAllOk;},
 x=>{x.samples[4].geometryChecksOk="true";},
 x=>{x.samples[4].geometryFailureClass="PRIVATE_PRICE_SECRET";},
 x=>{x.samples[4].archiveRejectionClass="PRIVATE_PROVIDER_MESSAGE";},
 x=>{x.samples[4].executable=true;},
 x=>{x.progress[0].brokerOrdersSent=1;},
 x=>{x.progress[0].frames.H4.contiguousClosed=21;},
 x=>{x.progress[0].frames.H1.unclassifiedMissingSlots=-1;},
 x=>{x.progress[0].atUTC="2026-11-19T11:00:03+00:00";},
 x=>{x.origin="BROKER_EXECUTION_CONFIRMED";},
 x=>{x.endUTC="2026-11-27T11:00:00Z";},
 x=>{x.samples[3].asOfUTC=iso(START+3*120000-130000);}
];
for(const mutate of corruption){
 const x=structuredClone(input);mutate(x);
 const out=audit(x);checked(out);
 assert.equal(out.status,"BLOCKED",JSON.stringify(x).slice(0,150));
}
// Read-only result is safe even if caller adds fabricated permissions.
const forged=audit({...input,signal:"BUY",canTrade:true,
 brokerSessionVerified:true,firstSeenPerClosedBarVerified:true});
checked(forged);assert.equal(forged.status,good.status);
assert.equal(audit({}).status,"BLOCKED");
console.log("PASS sanitized Render BiQuote collector cadence-only audit, actual-like 330-336 slots, missing logs, rejected forged authority; WAIT only");
