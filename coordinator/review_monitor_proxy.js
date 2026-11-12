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
 return {status:"WAIT_EODHD_INTAKE",dataStatus:input.dataStatus,
  signal:"WAIT",executable:false,researchEligible:false,engineStatus:"NOT_INVOKED",
  paperRunning:false,closedBarCounts:safe,
  intake:{status:"BLOCKED",blockingReasons:[...new Set(reasons)].slice(0,20)}};
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
