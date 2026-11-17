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
 const freshArchive={
  mode:"PRIVATE_FORWARD_BIQUOTE_CAPTURE_NOT_TRADING_ADMISSIBLE",
  status:"PRIVATE_FORWARD_VAULT_METADATA_ONLY",signal:"WAIT",
  executable:false,researchEligible:false,tradeEligible:false,
  paperOrdersAllowed:false,tradeSignalReady:false,
  providerRequestsMade:0,ordersSent:0,
  independentBrokerEntitlementVerified:false,
  independentSessionCalendarVerified:false,
  historicalBidAskOhlcAvailable:false,noTradingAdmission:true,
  researchCandidate:"NONE",
  counts:{M15:3,H1:1,H4:0},quoteSamples:10,
  lastImportedUTC:"2026-11-18T01:30:00Z",
  forwardCoverage:{
   M15:{closedBars:3,firstClosedUTC:"2026-11-18T00:15:00Z",
    lastClosedUTC:"2026-11-18T00:45:00Z",latestContiguousBars:3,
    unclassifiedGapPairs:0,unclassifiedMissingSlots:0,ageAtLastImportSeconds:2700,
    rawBid:989898},
   H1:{closedBars:1,firstClosedUTC:"2026-11-18T01:00:00Z",
    lastClosedUTC:"2026-11-18T01:00:00Z",latestContiguousBars:1,
    unclassifiedGapPairs:0,unclassifiedMissingSlots:0,ageAtLastImportSeconds:1800},
   H4:{closedBars:0,firstClosedUTC:null,lastClosedUTC:null,
    latestContiguousBars:0,unclassifiedGapPairs:0,
    unclassifiedMissingSlots:0,ageAtLastImportSeconds:null}
  },
  quoteObservations:[{bid:999999,ask:1000000}]
 };
 const withArchive=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,biquotePrivateForwardVault:freshArchive
 })});
 a.equal(withArchive.httpStatus,200);
 a.equal(withArchive.body.biquotePrivateForwardVault.counts.M15,3);
 a.equal(withArchive.body.biquotePrivateForwardVault.tradeSignalReady,false);
 a.equal(withArchive.body.biquotePrivateForwardVault.forwardCoverage.H4.closedBars,0);
 a.ok(!JSON.stringify(withArchive).includes("989898"));
 a.ok(!JSON.stringify(withArchive).includes("999999"));
 a.ok(!JSON.stringify(withArchive).includes("quoteObservations"));
 const corruptArchive=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,biquotePrivateForwardVault:{...freshArchive,tradeSignalReady:true}
 })});
 a.equal(corruptArchive.httpStatus,503);
 const gapForged=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,biquotePrivateForwardVault:{...freshArchive,forwardCoverage:{
    ...freshArchive.forwardCoverage,M15:{
      ...freshArchive.forwardCoverage.M15,unclassifiedMissingSlots:-1}}
    }
 })});
 a.equal(gapForged.httpStatus,503);
 const unavailable=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,biquotePrivateForwardVault:{
   status:"VAULT_METADATA_UNAVAILABLE",signal:"WAIT",executable:false,
   privateToken:"secret-vault-token"}
 })});
 a.equal(unavailable.httpStatus,200);
 a.equal(unavailable.body.biquotePrivateForwardVault.status,"VAULT_METADATA_UNAVAILABLE");
 a.ok(!JSON.stringify(unavailable).includes("secret-vault-token"));
 const wrong=await relay(auth,{approved:true,fetchFn:async()=>({status:401,ok:false})});
 a.equal(wrong.httpStatus,401);
 const fault=await relay(auth,{approved:true,fetchFn:async()=>{throw Error("private secret")}});
 a.equal(fault.httpStatus,503);a.ok(!JSON.stringify(fault).includes("private secret"));
 const withAudit=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,audit:{status:"AUDIT_OK",lastObservedUTC:"2026-11-12T21:00:00Z",
   ageSeconds:1,alertCodes:["INTAKE_BLOCKED"],lastNotificationCode:"WAIT_EODHD_INTAKE",
   signal:"WAIT",executable:false,paperRunning:false,externalNotificationsSent:0,price:10000}
 })});
 a.equal(withAudit.httpStatus,200);
 a.equal(withAudit.body.audit.alertCodes[0],"INTAKE_BLOCKED");
 a.ok(!JSON.stringify(withAudit).includes("10000"));
 const tampered=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,audit:{...withAudit.body.audit,alertCodes:["<unsafe>"]}
 })});
 a.equal(tampered.httpStatus,503);
 const gated=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,paperGate:{mode:"PAPER_ADMISSION_REVIEW_ONLY",
   status:"BLOCKED",signal:"WAIT",executable:false,
   researchEligible:false,paperRunning:false,paperOrdersAllowed:false,
   ledgerCreatedByGate:false,simulationEvidenceIsLive:false,
   reasonCodes:["PAPER_LIVE_ACTIVATION_NOT_APPROVED",
    "SOURCE_LICENSE_AND_HISTORY_NOT_VERIFIED","RISK_AND_BROKER_COSTS_NOT_VERIFIED"],
   sensitivePrice:5555}
 })});
 a.equal(gated.httpStatus,200);
 a.equal(gated.body.paperGate.paperOrdersAllowed,false);
 a.ok(!JSON.stringify(gated).includes("5555"));
 const spoof=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,paperGate:{...gated.body.paperGate,paperOrdersAllowed:true,
   researchEligible:false,ledgerCreatedByGate:false,simulationEvidenceIsLive:false}
 })});
 a.equal(spoof.httpStatus,503);
 const withCost=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,paperGate:{...gated.body.paperGate,reviewOnly:undefined,
   researchEligible:false,ledgerCreatedByGate:false,
   simulationEvidenceIsLive:false,costReadiness:{
    mode:"BROKER_COST_EVIDENCE_REVIEW_ONLY",status:"BLOCKED",
    signal:"WAIT",executable:false,modelAvailable:true,
    realBrokerFeesVerified:false,realBidAskVerified:false,riskBudgetVerified:false,
    ordersAllowed:false,sampleTradeExecuted:false,secretBrokerQuote:999,
    reasonCodes:["BROKER_CONTRACT_AND_LOT_SPEC_UNVERIFIED",
     "LIVE_BID_ASK_SPREAD_EVIDENCE_MISSING",
     "COMMISSION_AND_SLIPPAGE_EVIDENCE_MISSING",
     "RISK_BUDGET_AND_STOP_DISTANCE_UNVERIFIED"]}}
 })});
 a.equal(withCost.httpStatus,200);
 a.equal(withCost.body.paperGate.costReadiness.status,"BLOCKED");
 a.ok(!JSON.stringify(withCost).includes("999"));
 const unsafeCost=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,paperGate:{...gated.body.paperGate,reviewOnly:undefined,
   researchEligible:false,ledgerCreatedByGate:false,
   simulationEvidenceIsLive:false,costReadiness:{
    mode:"BROKER_COST_EVIDENCE_REVIEW_ONLY",status:"BLOCKED",
    signal:"WAIT",executable:false,modelAvailable:true,
    realBrokerFeesVerified:true,realBidAskVerified:false,riskBudgetVerified:false,
    ordersAllowed:false,sampleTradeExecuted:false,
    reasonCodes:["BROKER_CONTRACT_AND_LOT_SPEC_UNVERIFIED",
     "LIVE_BID_ASK_SPREAD_EVIDENCE_MISSING",
     "COMMISSION_AND_SLIPPAGE_EVIDENCE_MISSING",
     "RISK_BUDGET_AND_STOP_DISTANCE_UNVERIFIED"]}}
 })});
 a.equal(unsafeCost.httpStatus,503);
 const recovery=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,audit:{status:"AUDIT_OK",lastObservedUTC:"2026-11-12T21:00:00Z",
   ageSeconds:10,alertCodes:["INTAKE_BLOCKED"],lastNotificationCode:"WAIT_EODHD_INTAKE",
   signal:"WAIT",executable:false,paperRunning:false,externalNotificationsSent:0,
   recovery:{state:"OBSERVATION_REPEATED_UNVERIFIED",consecutiveObservations:3,
    requiredObservations:3,lastObservedUTC:"2026-11-12T21:00:00Z",transitionCount:2,
    sourceVerified:false,paperOrdersAllowed:false,signal:"WAIT",executable:false,
    bid:999999,apiKey:"do-not-expose"}}
 })});
 a.equal(recovery.httpStatus,200);a.equal(recovery.body.audit.recovery.paperOrdersAllowed,false);
 a.ok(!JSON.stringify(recovery).includes("999999"));
 a.ok(!JSON.stringify(recovery).includes("do-not-expose"));
 const unsaferecovery=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,audit:{...recovery.body.audit,recovery:{
   ...recovery.body.audit.recovery,paperOrdersAllowed:true}}
 })});
 a.equal(unsaferecovery.httpStatus,503);
 console.log("PASS: public review proxy disabled by default; readonly-only relay; safe WAIT data");
})().catch(e=>{console.error(e);process.exitCode=1});
