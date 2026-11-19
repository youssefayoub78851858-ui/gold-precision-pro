"use strict";
const a=require("node:assert/strict");
const {extract}=require("./biquote_render_log_export_readonly");
const start=Date.parse("2026-11-19T11:00:00Z");
const iso=ms=>new Date(ms).toISOString().replace(".000Z","Z");
const logs=[];
for(let i=0;i<9;i++){
 const t=start+i*120000;
 const rec={archiveRejectedSnapshotsSoFar:7,archiveSavedSnapshotsSoFar:324+i,
  asOfUTC:iso(t+3033),event:"BIQUOTE_REVIEW24H_SAMPLE",slot:330+i,
  httpAllOk:true,geometryChecksOk:false,signal:"WAIT",executable:false,
  geometryDetail:{privateQuotePrice:"SENSITIVE_NEVER_RETURN"}};
 logs.push({timestamp:iso(t+3033.4),message:JSON.stringify(rec)});
}
function progress(t,old){
 return {timestamp:iso(t),message:"BIQUOTE_SEVEN_DAY_STATUS "+
  JSON.stringify({
   event:"BIQUOTE_STAGE3_CLOSED_BAR_PROGRESS",
   signal:"WAIT",executable:false,paperOrdersAllowed:false,
   brokerOrdersSent:0,
   frames:{
    M15:{persistedClosed:old?136:137,contiguousClosed:old?48:49,
          unclassifiedMissingSlots:4,privateCandlePrice:"NEVER_LEAK"},
    H1:{persistedClosed:34,contiguousClosed:12,unclassifiedMissingSlots:1},
    H4:{persistedClosed:8,contiguousClosed:8,unclassifiedMissingSlots:0}
   }})};
}
logs.push(progress(start+3016,true),progress(start+16*60000+3016,false));
logs.push({timestamp:iso(start+3*120000+50000),
 message:"SECRET_PROTECTED_PROVIDER_LINE bid 4444.0 token PASSWORD"});
logs.reverse(); // Render list_logs commonly returns descending results.
const packet={source:"RENDER_LOG_EXPORT_UNTRUSTED",
 startUTC:iso(start),endUTC:iso(start+16*60000+20000),logs};
function safe(x){
 a.equal(x.signal,"WAIT");a.equal(x.executable,false);
 a.equal(x.sourceRightsVerified,false);a.equal(x.brokerCalendarVerified,false);
 a.equal(x.independentAvailabilityVerified,false);
 a.equal(x.firstSeenPerClosedBarVerified,false);
 a.equal(x.brokerOrdersSent,0);a.equal(x.providerRequestsMade,0);
 const raw=JSON.stringify(x);
 for(const sensitive of ["SENSITIVE_NEVER_RETURN","NEVER_LEAK","PASSWORD",
                          "4444.0",'"bid"','"ask"','"open"','"close"'])
  a(!raw.includes(sensitive));
}
const good=extract(packet);safe(good);
a.equal(good.status,"OBSERVED_LOG_CADENCE_ONLY_NOT_MARKET_PROOF");
a.equal(good.sampleCount,9);
a.equal(good.recordedArchiveIncrease,8);
a.equal(good.latestSavedSnapshots,332);
a.equal(good.renderLogEventsParsed,11);
a.equal(good.renderLogEventsIgnored,1);
a.equal(good.geometryNotOkSamples,9);
a.equal(good.httpNonOkSamples,0);
a.equal(good.renderLogExportAuthenticated,false);
a.equal(good.privateVaultRead,false);
a.equal(good.brokerFirstSeenFromDeployedLegacyCollector,false);
a.equal(good.missingLogSlots,0);
a.equal(good.collectorSlotsWithoutRecordedArchiveOutcome,0);
a.equal(good.unclassifiedFrameGaps.M15,4);
// If one collector sample is missing, absent evidence is not invented.
const missing=structuredClone(packet);
missing.logs=missing.logs.filter(x=>!x.message.includes('"slot":334'));
const hole=extract(missing);safe(hole);
a.equal(hole.status,"PARTIAL_LOG_COVERAGE_NOT_PROOF");
a.equal(hole.missingLogSlots,1);
const untrusted=extract({...packet,source:"LIVE_BROKER_VERIFIED"});
safe(untrusted);a.equal(untrusted.status,"BLOCKED");
for(const mutate of [
 p=>{p.logs[0].timestamp="now";},
 p=>{p.logs[0].message="BIQUOTE_SEVEN_DAY_STATUS {invalid";},
 p=>{p.logs.find(x=>x.message.includes('"slot":335')).timestamp="2026-11-19T13:00:00Z";},
 p=>{let x=p.logs.find(x=>x.message.includes('"slot":335'));
     let v=JSON.parse(x.message);v.signal="BUY";x.message=JSON.stringify(v);},
 p=>{let x=p.logs.find(x=>x.message.includes('"slot":335'));
     let v=JSON.parse(x.message);v.archiveRejectedSnapshotsSoFar=8;x.message=JSON.stringify(v);},
 p=>{let x=p.logs.find(x=>x.message.includes("BIQUOTE_STAGE3_CLOSED_BAR_PROGRESS"));
     let v=JSON.parse(x.message.slice("BIQUOTE_SEVEN_DAY_STATUS ".length));
     v.frames.H4.contiguousClosed=25;
     x.message="BIQUOTE_SEVEN_DAY_STATUS "+JSON.stringify(v);},
]){
 const changed=structuredClone(packet);
 mutate(changed);
 const result=extract(changed);
 safe(result);a.equal(result.status,"BLOCKED");
}
a.equal(extract({}).status,"BLOCKED");
console.log("PASS no-network Render log export to count-only BiQuote gate; reverse order, missing slot, tampering, no prices, WAIT");
