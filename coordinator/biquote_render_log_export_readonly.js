"use strict";
/*
 * OFFLINE adapter: Render log exports -> safe count-only collector cadence.
 * No API, network, secrets, price data, signed-vault access or executions.
 * Incoming Render logs remain UNATTESTED and cannot prove candle first-seen.
 */
const {audit}=require("./biquote_collector_log_cadence_gate");
const {reconcile}=require("./biquote_stage3_log_reconciliation");
const {assessWindow}=require("./biquote_capture_h4_horizon_gate");
const {assessEvidence}=require("./biquote_h4_evidence_quality_gate");
const MAX=11000;
const ISO=/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z$/;
const waiting=reason=>({
 mode:"BIQUOTE_RENDER_LOG_WINDOW_ONLY_V1",status:"BLOCKED",signal:"WAIT",
 executable:false,tradeEligible:false,researchEligible:false,
 paperOrdersAllowed:false,liveOrdersAllowed:false,brokerOrdersSent:0,
 providerRequestsMade:0,sourceRightsVerified:false,
 brokerCalendarVerified:false,independentAvailabilityVerified:false,
 firstSeenPerClosedBarVerified:false,
 blockerCodes:["SANITIZED_RENDER_LOG_EXPORT_UNTRUSTED",reason]
});
function msTime(raw){
 if(typeof raw!=="string"||!ISO.test(raw))return null;
 const ms=Date.parse(raw);
 if(!Number.isFinite(ms))return null;
 const normal=new Date(ms).toISOString();
 if(normal.slice(0,19)!==raw.slice(0,19))return null;
 return {ms,iso:normal.replace(".000Z","Z")};
}
function extract(input){
 if(input?.source!=="RENDER_LOG_EXPORT_UNTRUSTED"||
    !Array.isArray(input.logs)||!input.logs.length||input.logs.length>MAX)
  return waiting("INVALID_RENDER_LOG_INPUT");
 const start=msTime(input.startUTC),end=msTime(input.endUTC);
 if(!start||!end||start.ms>=end.ms||end.ms-start.ms>7*86400000)
  return waiting("INVALID_EXPLICIT_EXPORT_WINDOW");
 const samples=[],progress=[],stageRecords=[];
 let relevant=0,ignored=0;
 for(const row of input.logs){
  if(!row||typeof row!=="object"||Array.isArray(row)||
     typeof row.message!=="string"||typeof row.timestamp!=="string")
   return waiting("MALFORMED_RENDER_LOG_LINE");
  const logClock=msTime(row.timestamp);
  // Validate EVERY Render envelope, even an otherwise ignored log record:
  // malformed timestamps are evidence of a corrupt export, not safe noise.
  if(!logClock)return waiting("INVALID_RENDER_LOG_CLOCK");
  if(logClock.ms<start.ms||logClock.ms>end.ms)
   return waiting("RENDER_LOG_RECORD_OUTSIDE_EXPLICIT_WINDOW");
  const message=row.message;
  const isSample=message.startsWith('{"')&&
    message.includes('"event":"BIQUOTE_REVIEW24H_SAMPLE"');
  const isStage=message.startsWith("BIQUOTE_SEVEN_DAY_STATUS ");
  if(!isSample&&!isStage){ignored++;continue;}
  let x;
  try{x=JSON.parse(isSample?message:message.slice("BIQUOTE_SEVEN_DAY_STATUS ".length));}
  catch{return waiting("MALFORMED_KNOWN_RENDER_LOG_EVENT");}
  if(!x||typeof x!=="object"||Array.isArray(x))
   return waiting("MALFORMED_KNOWN_RENDER_LOG_EVENT");
  if(isSample){
   if(x.event!=="BIQUOTE_REVIEW24H_SAMPLE")
    return waiting("MISMATCHED_RENDER_LOG_EVENT");
   const embedded=msTime(x.asOfUTC);
   if(!embedded||Math.abs(embedded.ms-logClock.ms)>10000)
    return waiting("COLLECTOR_LOG_CLOCK_CONTRADICTION");
   samples.push({
    asOfUTC:embedded.iso,slot:x.slot,
    archiveSavedSnapshotsSoFar:x.archiveSavedSnapshotsSoFar,
    archiveRejectedSnapshotsSoFar:x.archiveRejectedSnapshotsSoFar,
    archiveRejectionClass:x.archiveRejectionClass,
    httpAllOk:x.httpAllOk,geometryChecksOk:x.geometryChecksOk,
    geometryFailureClass:x.geometryFailureClass,
    signal:x.signal,executable:x.executable
   });
   relevant++;
  }else if(x.event==="BIQUOTE_STAGE3_CLOSED_BAR_PROGRESS"){
   const f=x.frames,frames={};
   if(!f||typeof f!=="object"||Array.isArray(f))
    return waiting("MALFORMED_PROGRESS_FRAME_LOG");
   for(const tf of ["M15","H1","H4"]){
    const item=f[tf];
    if(!item||typeof item!=="object"||Array.isArray(item))
     return waiting("MALFORMED_PROGRESS_FRAME_LOG");
    frames[tf]={
     persistedClosed:item.persistedClosed,
     contiguousClosed:item.contiguousClosed,
     unclassifiedMissingSlots:item.unclassifiedMissingSlots
    };
   }
   progress.push({atUTC:logClock.iso,frames,signal:x.signal,
    executable:x.executable,paperOrdersAllowed:x.paperOrdersAllowed,
    brokerOrdersSent:x.brokerOrdersSent});
   stageRecords.push({event:x.event,atUTC:logClock.iso,
    dayIndex:x.dayIndex,frames,signal:x.signal,executable:x.executable,
    paperOrdersAllowed:x.paperOrdersAllowed,brokerOrdersSent:x.brokerOrdersSent});
   relevant++;
  }else if(["BIQUOTE_STAGE3_VENDOR_REFERENCE_GAPS",
             "BIQUOTE_STAGE3_ARCHIVE_OHLC_OVERLAP",
             "BIQUOTE_STAGE3_QUOTE_RECEIPT_CADENCE"].includes(x.event)){
   // Only fixed count metadata. Never retain raw quote, candle or provider text.
   const frames={};
   const names=x.event==="BIQUOTE_STAGE3_ARCHIVE_OHLC_OVERLAP"?
    ["H1","H4"]:["M15","H1","H4"];
   if(x.event!=="BIQUOTE_STAGE3_QUOTE_RECEIPT_CADENCE"){
    for(const tf of names){
     const v=x.frames?.[tf];
     if(!v||typeof v!=="object")return waiting("MALFORMED_STAGE3_COUNT_FRAME");
     frames[tf]=x.event==="BIQUOTE_STAGE3_VENDOR_REFERENCE_GAPS"?
      {unclassifiedMissingSlots:v.unclassifiedMissingSlots}:
      {fullyCoveredCompared:v.fullyCoveredCompared,
       fullyCoveredDisagreed:v.fullyCoveredDisagreed,
       higherClosedExamined:v.higherClosedExamined,
       notFullyCovered:v.notFullyCovered};
    }
   }
   const intervals={};
   if(x.event==="BIQUOTE_STAGE3_QUOTE_RECEIPT_CADENCE"){
    for(const key of ["GT_150_LE_300_SECONDS","GT_300_LE_600_SECONDS",
      "GT_3600_SECONDS","GT_600_LE_3600_SECONDS","LE_150_SECONDS"])
     intervals[key]=x.intervalBins?.[key];
   }
   stageRecords.push({event:x.event,atUTC:logClock.iso,
    dayIndex:x.dayIndex,frames,
    sourceQuoteSamples:x.sourceQuoteSamples,observedIntervals:x.observedIntervals,
    intervalBins:intervals,signal:x.signal,executable:x.executable,
    paperOrdersAllowed:x.paperOrdersAllowed,brokerOrdersSent:x.brokerOrdersSent});
   relevant++;
  }else{ignored++;}
 }
 samples.sort((a,b)=>Date.parse(a.asOfUTC)-Date.parse(b.asOfUTC));
 progress.sort((a,b)=>Date.parse(a.atUTC)-Date.parse(b.atUTC));
 const stage=reconcile({records:stageRecords});
 if(stage.status==="BLOCKED")return waiting("CONTRADICTORY_STAGE3_COUNT_EVIDENCE");
 // A capture deadline is not the log-query end. Only explicitly supplied,
 // bounded collector dates may be combined with sanitized Stage3 counts.
 const wantsHorizon=input.captureStartUTC!==undefined||
                    input.captureEndUTC!==undefined;
 if(wantsHorizon&&
    (typeof input.captureStartUTC!=="string"||
     typeof input.captureEndUTC!=="string"))
  return waiting("CAPTURE_CUTOFF_PAIR_REQUIRED");
 const h4CaptureHorizon=wantsHorizon&&
  stage.status==="CONSISTENT_COUNTS_ONLY_NOT_MARKET_PROOF"?
   assessWindow({
    origin:"UNATTESTED_RENDER_COUNTS_NO_PRIVATE_ARCHIVE",
    startUTC:input.captureStartUTC,asOfUTC:stage.latestProgressAtUTC,
    endUTC:input.captureEndUTC,
    persistedClosedCounts:stage.persistedClosed,
    contiguousClosedCounts:stage.contiguousClosed
   }):null;
 const h4EvidenceQuality=h4CaptureHorizon?assessEvidence({
  origin:"SANITIZED_STAGE3_AND_CAPTURE_HORIZON_UNATTESTED",
  stage3Consistency:stage,h4CaptureHorizon
 }):null;
 const report=audit({
  origin:"RENDER_SANITIZED_COLLECTOR_LOGS_UNATTESTED",
  startUTC:input.startUTC,endUTC:input.endUTC,samples,progress
 });
 return {...report,stage3Consistency:stage,
  h4CaptureHorizon,h4EvidenceQuality,
  h4CaptureHorizonUnavailability:wantsHorizon&&!h4CaptureHorizon?
   "STAGE3_CYCLE_INCOMPLETE_NO_H4_HORIZON":null,
  renderLogEventsParsed:relevant,renderLogEventsIgnored:ignored,
  renderLogExportAuthenticated:false,privateVaultRead:false,
  brokerFirstSeenFromDeployedLegacyCollector:false};
}
module.exports={extract};
if(require.main===module){
 let raw="";
 process.stdin.setEncoding("utf8");
 process.stdin.on("data",x=>{
  raw+=x;
  if(raw.length>2500000){process.stderr.write("LOG_EXPORT_TOO_LARGE\n");process.exit(2);}
 });
 process.stdin.on("end",()=>{
  try{process.stdout.write(JSON.stringify(extract(JSON.parse(raw)))+"\n");}
  catch{process.stdout.write(JSON.stringify(waiting("INVALID_LOG_EXPORT"))+"\n");}
 });
}
