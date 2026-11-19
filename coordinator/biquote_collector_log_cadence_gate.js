"use strict";
/**
 * Zero-I/O, read-only audit of ALREADY SANITIZED Render collector LOG METADATA.
 * No market quotes, OHLC, credentials, provider fetch, vault disk, order path,
 * replay, or subscription. Log continuity NEVER proves market continuity.
 * On the currently deployed legacy collector, per-candle first-seen is UNKNOWN.
 */
const MAX=11000;
const PERIOD=120000;
const TIME=/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z$/;
const TFS=["M15","H1","H4"];
const FIXED=Object.freeze([
 "RUNNING_LEGACY_COLLECTOR_HAS_NO_PER_CANDLE_FIRST_SEEN",
 "UPSTREAM_MARKET_RIGHTS_UNVERIFIED",
 "BROKER_SESSION_GAPS_UNCLASSIFIED",
 "SPARSE_QUOTE_LOGS_NOT_EXECUTION_BID_ASK",
 "NO_INDEPENDENT_FORWARD_TRADING_VALIDATION"
]);
const safe=(state,reason,extra={})=>({
 mode:"BIQUOTE_RENDER_LOG_WINDOW_ONLY_V1",status:state,signal:"WAIT",
 executable:false,tradeEligible:false,researchEligible:false,
 paperOrdersAllowed:false,liveOrdersAllowed:false,
 brokerOrdersSent:0,paperOrdersCreated:0,providerRequestsMade:0,
 sourceRightsVerified:false,brokerCalendarVerified:false,
 independentAvailabilityVerified:false,brokerQuoteHistoryVerified:false,
 firstSeenPerClosedBarVerified:false,profitabilityProven:false,
 collectorRestarted:false,deployTriggered:false,
 sampleCount:0,reviewedProgressCount:0,missingLogSlots:0,
 recordedArchiveIncrease:0,recordedArchiveRejectionsIncrease:0,
 collectorSlotsWithoutRecordedArchiveOutcome:0,
 httpNonOkSamples:0,geometryNotOkSamples:0,
 unclassifiedFrameGaps:{M15:null,H1:null,H4:null},
 blockerCodes:[...FIXED,...(reason?[reason]:[])],...extra
});
function stamp(v){
 if(typeof v!=="string"||!TIME.test(v))return NaN;
 const n=Date.parse(v);
 return Number.isFinite(n)&&new Date(n).toISOString().slice(0,19)===v.slice(0,19)?n:NaN;
}
function int(v){return Number.isSafeInteger(v)&&v>=0&&v<=MAX*1000;}
function audit(input){
 if(input?.origin!=="RENDER_SANITIZED_COLLECTOR_LOGS_UNATTESTED")
  return safe("BLOCKED","UNTRUSTED_LOG_ORIGIN");
 const begin=stamp(input.startUTC),end=stamp(input.endUTC);
 if(!Number.isFinite(begin)||!Number.isFinite(end)||end<=begin||
    end-begin>7*86400000)
  return safe("BLOCKED","INVALID_EXPLICIT_LOG_WINDOW");
 const samples=input.samples, progress=input.progress;
 if(!Array.isArray(samples)||!samples.length||samples.length>MAX||
    !Array.isArray(progress)||progress.length>MAX)
  return safe("BLOCKED","INVALID_LOG_ARRAYS");
 let previous=null,missing=0,archiveIncrease=0,rejectionsIncrease=0;
 let unaccounted=0,httpNonOk=0,geometryNotOk=0;
 for(const rec of samples){
  if(!rec||typeof rec!=="object"||Array.isArray(rec))
   return safe("BLOCKED","MALFORMED_SAMPLE");
  const t=stamp(rec.asOfUTC);
  if(!Number.isFinite(t)||t<begin||t>end||
     rec.signal!=="WAIT"||rec.executable!==false||
     typeof rec.httpAllOk!=="boolean"||
     typeof rec.geometryChecksOk!=="boolean"||
     !int(rec.slot)||!int(rec.archiveSavedSnapshotsSoFar)||
     !int(rec.archiveRejectedSnapshotsSoFar))
   return safe("BLOCKED","UNSAFE_OR_INVALID_SAMPLE");
  if(previous){
   const slots=rec.slot-previous.slot;
   const time=t-previous.t;
   const savedDelta=rec.archiveSavedSnapshotsSoFar-previous.saved;
   const rejectedDelta=rec.archiveRejectedSnapshotsSoFar-previous.rejected;
   if(slots<=0||time<=0||time<slots*60000||time>slots*180000||
      rec.archiveSavedSnapshotsSoFar<previous.saved||
      rec.archiveRejectedSnapshotsSoFar<previous.rejected||
      savedDelta>slots||rejectedDelta>slots||
      savedDelta+rejectedDelta>slots)
    return safe("BLOCKED","NONMONOTONIC_OR_CONTRADICTORY_SAMPLE_SERIES");
   missing+=slots-1;
   archiveIncrease+=savedDelta;
   rejectionsIncrease+=rejectedDelta;
   // A collector slot without an archived outcome is a gap in evidence,
   // NOT necessarily a provider outage. Never count it as captured data.
   unaccounted+=slots-savedDelta-rejectedDelta;
  }
  if(!rec.httpAllOk)httpNonOk++;
  if(!rec.geometryChecksOk)geometryNotOk++;
  previous={t,slot:rec.slot,saved:rec.archiveSavedSnapshotsSoFar,
            rejected:rec.archiveRejectedSnapshotsSoFar};
 }
 let prevProgress=-Infinity,latest=null;
 for(const entry of progress){
  const t=stamp(entry?.atUTC),f=entry?.frames;
  if(!Number.isFinite(t)||t<begin||t>end||t<=prevProgress||
     entry.signal!=="WAIT"||entry.executable!==false||
     entry.paperOrdersAllowed!==false||entry.brokerOrdersSent!==0||
     !f||typeof f!=="object"||Array.isArray(f)||
     Object.keys(f).sort().join(",")!=="H1,H4,M15")
   return safe("BLOCKED","INVALID_CLOSED_BAR_LOG");
  const gaps={};
  for(const tf of TFS){
   const r=f[tf];
   if(!r||!int(r.persistedClosed)||!int(r.contiguousClosed)||
      !int(r.unclassifiedMissingSlots)||
      r.contiguousClosed>r.persistedClosed||
      (latest&&r.persistedClosed<latest.frames[tf].persistedClosed)||
      (latest&&r.unclassifiedMissingSlots<latest.frames[tf].unclassifiedMissingSlots))
    return safe("BLOCKED","INVALID_FRAME_PROGRESS");
   gaps[tf]=r.unclassifiedMissingSlots;
  }
  latest={t,frames:f,gaps};
  prevProgress=t;
 }
 const first=stamp(samples[0].asOfUTC);
 // A missing first or last 120-second slot must not count as covered.
 const covered=first-begin<=60000&&end-previous.t<=60000;
 const recentProgress=!!latest&&latest.t<=previous.t&&
                      previous.t-latest.t<=1800000;
 const blockers=[...FIXED];
 if(!covered)blockers.push("LOG_QUERY_EDGE_NOT_COVERED");
 if(missing)blockers.push("MISSING_COLLECTOR_LOG_SLOTS");
 if(unaccounted)blockers.push("COLLECTOR_SLOTS_WITHOUT_ARCHIVE_OUTCOME");
 if(httpNonOk)blockers.push("HTTP_NON_OK_COLLECTOR_LOG_SAMPLES");
 if(geometryNotOk)blockers.push("COLLECTOR_OHLC_GEOMETRY_NOT_PROVEN");
 if(!recentProgress)blockers.push("CLOSED_BAR_PROGRESS_NOT_RECENT_IN_LOG_WINDOW");
 if(latest&&TFS.some(tf=>latest.gaps[tf]>0))
  blockers.push("UNCLASSIFIED_CLOSED_BAR_TIME_GAPS_PRESENT");
 return safe(covered&&!missing&&!unaccounted&&recentProgress?
   "OBSERVED_LOG_CADENCE_ONLY_NOT_MARKET_PROOF":"PARTIAL_LOG_COVERAGE_NOT_PROOF",
   null,{
    windowStartUTC:input.startUTC,windowEndUTC:input.endUTC,
    firstObservedLogUTC:samples[0].asOfUTC,
    lastObservedLogUTC:samples.at(-1).asOfUTC,
    sampleCount:samples.length,reviewedProgressCount:progress.length,
    missingLogSlots:missing,recordedArchiveIncrease:archiveIncrease,
    recordedArchiveRejectionsIncrease:rejectionsIncrease,
    collectorSlotsWithoutRecordedArchiveOutcome:unaccounted,
    httpNonOkSamples:httpNonOk,geometryNotOkSamples:geometryNotOk,
    latestSavedSnapshots:previous.saved,latestRejectedSnapshots:previous.rejected,
    unclassifiedFrameGaps:latest?latest.gaps:{M15:null,H1:null,H4:null},
    logWindowEdgesObserved:covered,recentClosedProgressObserved:recentProgress,
    blockerCodes:blockers
   });
}
module.exports={audit};
if(require.main===module){
 let src="";
 process.stdin.setEncoding("utf8");
 process.stdin.on("data",c=>{src+=c;if(src.length>1000000){process.stderr.write("INPUT_TOO_LARGE\n");process.exit(2);}});
 process.stdin.on("end",()=>{
  try{process.stdout.write(JSON.stringify(audit(JSON.parse(src)))+"\n");}
  catch(_){process.stdout.write(JSON.stringify(safe("BLOCKED","INVALID_LOG_INPUT"))+"\n");}
 });
}
