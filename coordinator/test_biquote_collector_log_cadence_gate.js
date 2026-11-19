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
  signal:"WAIT",executable:false
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
