"use strict";
/*
 * OFFLINE adapter: Render log exports -> safe count-only collector cadence.
 * No API, network, secrets, price data, signed-vault access or executions.
 * Incoming Render logs remain UNATTESTED and cannot prove candle first-seen.
 */
const {audit}=require("./biquote_collector_log_cadence_gate");
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
 const samples=[],progress=[];
 let relevant=0,ignored=0;
 for(const row of input.logs){
  if(!row||typeof row!=="object"||Array.isArray(row)||
     typeof row.message!=="string"||typeof row.timestamp!=="string")
   return waiting("MALFORMED_RENDER_LOG_LINE");
  const logClock=msTime(row.timestamp);
  // Validate EVERY Render envelope, even an otherwise ignored log record:
  // malformed timestamps are evidence of a corrupt export, not safe noise.
  if(!logClock)return waiting("INVALID_RENDER_LOG_CLOCK");
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
   relevant++;
  }else{ignored++;}
 }
 samples.sort((a,b)=>Date.parse(a.asOfUTC)-Date.parse(b.asOfUTC));
 progress.sort((a,b)=>Date.parse(a.atUTC)-Date.parse(b.atUTC));
 const report=audit({
  origin:"RENDER_SANITIZED_COLLECTOR_LOGS_UNATTESTED",
  startUTC:input.startUTC,endUTC:input.endUTC,samples,progress
 });
 return {...report,renderLogEventsParsed:relevant,renderLogEventsIgnored:ignored,
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
