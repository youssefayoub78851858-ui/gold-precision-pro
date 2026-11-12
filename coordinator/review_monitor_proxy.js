"use strict";
// Opt-in, fixed destination private network proxy for sanitized status ONLY.
const ENDPOINT="http://gold-precision-coordinator:3110/api/v3/monitor/status";
const states=new Set(["NOT_CONNECTED","BLOCKED","WAIT_STALE","WAIT_NO_VERIFIED_QUOTE","WAIT_REVIEW_OBSERVATION_ONLY"]);
const code=/^[A-Z0-9_]{3,90}$/;
const deny=(status,reason)=>({httpStatus:status,body:{
 status:reason,signal:"WAIT",executable:false,researchEligible:false,
 engineStatus:"NOT_INVOKED",paperRunning:false,
 closedBarCounts:{M15:0,H1:0,H4:0},intake:{status:"BLOCKED",blockingReasons:[reason]}
}});
function sanitize(input){
 if(!input||input.status!=="WAIT_EODHD_INTAKE"||!states.has(input.dataStatus)
   ||input.signal!=="WAIT"||input.executable!==false||input.researchEligible!==false
   ||input.engineStatus!=="NOT_INVOKED"||input.paperRunning!==false
   ||input.sourceRequestsMade!==0||input.providerAccessStartedByMonitor!==false)
  throw Error("Source is not non-executable research review");
 const safe={},counts=input.closedBarCounts||{},limits={M15:2048,H1:512,H4:128};
 for(const [tf,limit] of Object.entries(limits)){
  if(!Number.isInteger(counts[tf])||counts[tf]<0||counts[tf]>limit)
   throw Error("Invalid bar count");
  safe[tf]=counts[tf];
 }
 const reasons=input.intake?.blockingReasons;
 if(!Array.isArray(reasons)||reasons.length<1||reasons.length>50
    ||reasons.some(r=>typeof r!=="string"||!code.test(r)))throw Error("Unsafe reason");
 const audit=input.audit;
 let safeAudit=null;
 if(audit!==undefined){
  const statuses=new Set(["AUDIT_DISABLED","AUDIT_NOT_STARTED","AUDIT_OK",
                          "AUDIT_STALE","AUDIT_UNAVAILABLE"]);
  if(!audit||!statuses.has(audit.status)||audit.signal!=="WAIT"
     ||audit.executable!==false||audit.paperRunning!==false
     ||audit.externalNotificationsSent!==0)throw Error("Unsafe audit contract");
  const codes=audit.alertCodes;
  if(!Array.isArray(codes)||codes.length>20
     ||codes.some(v=>typeof v!=="string"||!code.test(v)))throw Error("Unsafe audit codes");
  const note=audit.lastNotificationCode,time=audit.lastObservedUTC,age=audit.ageSeconds;
  if(note!==null&&(typeof note!=="string"||!code.test(note)))throw Error("Unsafe audit notification");
  if(time!==null&&(typeof time!=="string"||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(time)))
    throw Error("Unsafe audit time");
  if(age!==null&&(!Number.isInteger(age)||age<0||age>315360000))throw Error("Unsafe audit age");
  safeAudit={status:audit.status,lastObservedUTC:time,ageSeconds:age,
             alertCodes:codes,lastNotificationCode:note,signal:"WAIT",
             executable:false,paperRunning:false,externalNotificationsSent:0};
 }
 const paper=input.paperGate;
 let safePaper=null;
 if(paper!==undefined){
  const codes=paper?.reasonCodes;
  if(paper.mode!=="PAPER_ADMISSION_REVIEW_ONLY"||paper.status!=="BLOCKED"
     ||paper.signal!=="WAIT"||paper.executable!==false
     ||paper.researchEligible!==false||paper.paperRunning!==false
     ||paper.paperOrdersAllowed!==false||paper.ledgerCreatedByGate!==false
     ||paper.simulationEvidenceIsLive!==false
     ||!Array.isArray(codes)||codes.length<3||codes.length>12
     ||codes.some(x=>typeof x!=="string"||!code.test(x))
     ||!codes.includes("PAPER_LIVE_ACTIVATION_NOT_APPROVED")
     ||!codes.includes("SOURCE_LICENSE_AND_HISTORY_NOT_VERIFIED")
     ||!codes.includes("RISK_AND_BROKER_COSTS_NOT_VERIFIED"))
    throw Error("Unsafe paper gate");
  safePaper={mode:"PAPER_ADMISSION_REVIEW_ONLY",status:"BLOCKED",
   signal:"WAIT",executable:false,reviewOnly:true,paperRunning:false,
   paperOrdersAllowed:false,reasonCodes:[...new Set(codes)]};
 }
 return {status:"WAIT_EODHD_INTAKE",dataStatus:input.dataStatus,
  signal:"WAIT",executable:false,researchEligible:false,engineStatus:"NOT_INVOKED",
  paperRunning:false,closedBarCounts:safe,
  intake:{status:"BLOCKED",blockingReasons:[...new Set(reasons)].slice(0,20)},
  ...(safeAudit?{audit:safeAudit}:{}),...(safePaper?{paperGate:safePaper}:{})};
}
async function relay(authorization,{approved=false,fetchFn=globalThis.fetch}={}){
 if(!approved)return deny(503,"REVIEW_MONITOR_PROXY_DISABLED");
 if(typeof authorization!=="string"||!/^Bearer [A-Za-z0-9_-]{32,128}$/.test(authorization))
  return deny(401,"MONITOR_VIEWER_AUTH_REQUIRED");
 try{
  const response=await fetchFn(ENDPOINT,{
   method:"GET",headers:{"X-Monitor-Viewer":authorization.slice(7),"Accept":"application/json"},
   redirect:"error",credentials:"omit",cache:"no-store",signal:AbortSignal.timeout(5000)
  });
  if(response.status===401)return deny(401,"MONITOR_VIEWER_AUTH_INVALID");
  if(!response.ok)return deny(503,"PRIVATE_MONITOR_UNAVAILABLE");
  if(Number(response.headers?.get?.("content-length")||0)>16000)throw Error("too large");
  const raw=await response.text();if(raw.length>16000)throw Error("too large");
  return {httpStatus:200,body:sanitize(JSON.parse(raw))};
 }catch{return deny(503,"PRIVATE_MONITOR_RESPONSE_REJECTED");}
}
module.exports={relay,sanitize,ENDPOINT};
