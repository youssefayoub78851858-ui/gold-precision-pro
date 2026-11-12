"use strict";
const a=require("node:assert/strict");
const {relay,ENDPOINT}=require("./review_monitor_proxy");
const token="R".repeat(48),auth="Bearer "+token;
const expected={status:"WAIT_EODHD_INTAKE",dataStatus:"NOT_CONNECTED",
 signal:"WAIT",executable:false,researchEligible:false,engineStatus:"NOT_INVOKED",
 paperRunning:false,sourceRequestsMade:0,providerAccessStartedByMonitor:false,
 closedBarCounts:{M15:0,H1:0,H4:0},
 intake:{status:"BLOCKED",blockingReasons:["EODHD_PRIVATE_BRIDGE_NOT_CONNECTED"]},
 latestQuote:{bid:9999},secret:"never print"};
const mock=body=>({status:200,ok:true,headers:{get:()=>null},text:async()=>JSON.stringify(body)});
(async()=>{
 let count=0;
 const disabled=await relay(auth,{fetchFn:()=>{count++;throw Error("unexpected")}});
 a.equal(disabled.httpStatus,503);a.equal(count,0);
 const missing=await relay("Bearer wrong",{approved:true,fetchFn:()=>{count++;throw Error("unexpected")}});
 a.equal(missing.httpStatus,401);a.equal(count,0);
 const ok=await relay(auth,{approved:true,fetchFn:async(url,options)=>{
  count++;a.equal(url,ENDPOINT);a.equal(options.headers["X-Monitor-Viewer"],token);
  a.equal(options.headers.Authorization,undefined);a.equal(options.redirect,"error");
  return mock(expected);
 }});
 a.equal(ok.httpStatus,200);a.equal(ok.body.status,"WAIT_EODHD_INTAKE");
 a.equal(ok.body.signal,"WAIT");a.equal(ok.body.executable,false);
 a.ok(!JSON.stringify(ok).includes("9999"));a.ok(!JSON.stringify(ok).includes("secret"));
 for(const change of [{signal:"BUY"},{executable:true},{researchEligible:true},{paperRunning:true},{engineStatus:"REVIEWED"},{sourceRequestsMade:1},{dataStatus:"UNKNOWN"},{closedBarCounts:{M15:-1,H1:0,H4:0}}]){
  const denied=await relay(auth,{approved:true,fetchFn:async()=>mock({...expected,...change})});
  a.equal(denied.httpStatus,503);a.equal(denied.body.signal,"WAIT");
 }
 const wrong=await relay(auth,{approved:true,fetchFn:async()=>({status:401,ok:false})});
 a.equal(wrong.httpStatus,401);
 const fault=await relay(auth,{approved:true,fetchFn:async()=>{throw Error("private secret")}});
 a.equal(fault.httpStatus,503);a.ok(!JSON.stringify(fault).includes("private secret"));
 console.log("PASS: public review proxy disabled by default; readonly-only relay; safe WAIT data");
})().catch(e=>{console.error(e);process.exitCode=1});
