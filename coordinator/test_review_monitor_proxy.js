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
 // Never trust upstream claims that a generic vendor pause certifies the
 // underlying broker's calendar, nor forward raw timestamps or BID/ASK.
 const refFrame=n=>({
  persistedClosed:n,gapPairs:0,unclassifiedMissingSlots:0,
  vendorPauseCandidateSlotsNotVerified:0,outsideVendorReferenceSlots:0,
  unknownReferenceSlots:0,comparisonHasAtLeastTwoBars:n>=2,
  rawBid:987654321,privateTimestamp:"2026-11-18T10:15:00Z"});
 const gapReference={
  mode:"BIQUOTE_PRIVATE_REFERENCE_GAP_COUNTS_ONLY",
  status:"REFERENCE_ONLY_NOT_BROKER_VERIFIED",
  signal:"WAIT",executable:false,researchEligible:false,
  paperOrdersAllowed:false,liveOrdersAllowed:false,
  independentBrokerCalendarVerified:false,sourceRightsVerified:false,
  allGapsRemainUnclassified:true,
  frames:{M15:refFrame(3),H1:refFrame(1),H4:refFrame(0)},
  providerApiKey:"PRIVATE_NEVER_FORWARD_KEY"};
 const withRef=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,biquotePrivateForwardVault:{...freshArchive,gapReference}
 })});
 a.equal(withRef.httpStatus,200);
 const mobileRef=withRef.body.biquotePrivateForwardVault.gapReference;
 a.equal(mobileRef.status,"REFERENCE_ONLY_NOT_BROKER_VERIFIED");
 a.equal(mobileRef.frames.M15.unclassifiedMissingSlots,0);
 a.equal(mobileRef.allGapsRemainUnclassified,true);
 a.equal(mobileRef.sourceRightsVerified,false);
 a.equal(mobileRef.paperOrdersAllowed,false);
 for(const secret of ["PRIVATE_NEVER_FORWARD_KEY","987654321","privateTimestamp",
                     "2026-11-18T10:15:00Z"]){
  a.ok(!JSON.stringify(withRef).includes(secret),"Private gap evidence must be aggregate-only");
 }
 for(const badRef of [
  {...gapReference,allGapsRemainUnclassified:false},
  {...gapReference,independentBrokerCalendarVerified:true},
  {...gapReference,sourceRightsVerified:true},
  {...gapReference,signal:"BUY"},
  {...gapReference,frames:{...gapReference.frames,M15:{
    ...gapReference.frames.M15,unclassifiedMissingSlots:1}}},
  {...gapReference,frames:{...gapReference.frames,M15:{
    ...gapReference.frames.M15,outsideVendorReferenceSlots:-1}}}
 ]){
  const no=await relay(auth,{approved:true,fetchFn:async()=>mock({
   ...expected,biquotePrivateForwardVault:{...freshArchive,gapReference:badRef}
  })});
  a.equal(no.httpStatus,503,"Unsafe broker session claim must fail closed");
  a.equal(no.body.signal,"WAIT");
 }
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
 const shadow={
  mode:"BIQUOTE_PRIVATE_FORWARD_V3_SHADOW_ONLY",
  signal:"WAIT",executable:false,paperOrdersAllowed:false,
  tradeEligible:false,researchEligible:false,brokerOrdersSent:0,
  sourceRequestsMade:0,approvedDirection:"NONE",signalReady:false,
  technicalWatch:"BUY",
  engineReview:"FROZEN_V3_COMPLETED_WITH_REAL_OBSERVED_CLOSED_BARS",
  reasonCodes:["UNDERLYING_BROKER_SESSION_UNVERIFIED",
               "NO_REAL_SIGNAL_WITHOUT_INDEPENDENT_CONTEXT_AND_RISK"],
  frames:{
   M15:{persistedClosed:80,contiguousClosed:48,neededContiguous:21,bid:987654},
   H1:{persistedClosed:40,contiguousClosed:40,neededContiguous:21},
   H4:{persistedClosed:23,contiguousClosed:23,neededContiguous:21}},
  spread:987654,entry:8888888,secretQuote:"NEVER_LEAK"}
 const sanitized=await relay(auth,{approved:true,fetchFn:async()=>mock({
    ...expected,biquoteForwardShadow:shadow})});
 a.equal(sanitized.httpStatus,200);
 a.equal(sanitized.body.signal,"WAIT");
 a.equal(sanitized.body.biquoteForwardShadow.technicalWatch,"BUY");
 a.equal(sanitized.body.biquoteForwardShadow.approvedDirection,"NONE");
 a.equal(sanitized.body.biquoteForwardShadow.paperOrdersAllowed,false);
 a.equal(sanitized.body.biquoteForwardShadow.frames.H4.contiguousClosed,23);
 for(const secret of ["987654","8888888","NEVER_LEAK","secretQuote"]){
   a.ok(!JSON.stringify(sanitized).includes(secret),"Private raw prices and secrets must not leak");
 }
 for(const delta of [{signal:"BUY"},{executable:true},{paperOrdersAllowed:true},
   {approvedDirection:"BUY"},{signalReady:true},{sourceRequestsMade:1},
   {reasonCodes:["<price>"]},{technicalWatch:"SELL",engineReview:"NOT_YET_READY"}]){
   const rejected=await relay(auth,{approved:true,fetchFn:async()=>mock({
     ...expected,biquoteForwardShadow:{...shadow,...delta}})});
   a.equal(rejected.httpStatus,503);
 }
 const emptyShadow=await relay(auth,{approved:true,fetchFn:async()=>mock({
   ...expected,biquoteForwardShadow:{...shadow,technicalWatch:"NONE",
    frames:undefined,engineReview:undefined}})});
 a.equal(emptyShadow.httpStatus,200);
 a.equal(emptyShadow.body.biquoteForwardShadow.technicalWatch,"NONE");
 const batch={
  mode:"GOLD_PRECISION_FOUR_STAGE_BATCH_READONLY_V1",
  signal:"WAIT",executable:false,paperOrdersAllowed:false,
  liveOrdersAllowed:false,tradeEligible:false,signalReady:false,
  researchEligible:false,brokerOrdersSent:0,providerRequestsMade:0,
  archiveWritesMade:0,paperLedgerWritesMade:0,
  rawMarketPricesExposed:false,
  brokerFeedRightsIndependentlyVerified:false,
  brokerSessionCalendarIndependentlyVerified:false,
  historicalBidAskExecutionVerified:false,
  outOfSampleNetExpectancyProven:false,
  stages:{
   data:{status:"SOURCE_NOT_QUALIFIED",sourceRightsVerified:false,
    independentBrokerCalendarVerified:false,liveProviderConnected:false,
    liveQuote:{bid:12345}},
   archive:{status:"NO_FORWARD_CAPTURE",
    closedCounts:{M15:0,H1:0,H4:0},
    consecutiveClosedCounts:{M15:0,H1:0,H4:0},
    dataSourceIndependentlyAuthenticated:false,sessionGapsProven:false,
    automaticQuoteDeletionAllowed:false,
    capacityStatus:"CAPACITY_HEADROOM",
    quoteSamplesRemaining:10000,quoteSamplesHardCap:10000,
    archiveCapacityExhausted:false,
    quoteSamples:[{ask:12346}]},
   analysis:{status:"WAIT_CLOSED_DATA_OR_CONTEXT",
    approvedDirection:"NONE",technicalWatch:"NONE",entry:null,
    stopLoss:null,takeProfit:null,winProbability:null,
    independentContextVerified:false,rawCandles:[{close:12347}]},
   context:{status:"INDEPENDENT_SOURCE_CONFIRMATIONS_REQUIRED"},
   paper:{status:"BLOCKED",paperOrdersAllowed:false,
    paperLedgerOpened:false,sampleTradesCreated:0,
    brokerCostsVerified:false,forwardNetPerformanceEstablished:false,
    fakeProfit:12348}
  },
  unknownApiKey:"PRIVATE_SECRET_TOKEN"
 };
 const outBatch=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,ultimateFourStageBatch:batch
 })});
 a.equal(outBatch.httpStatus,200);
 a.equal(outBatch.body.ultimateFourStageBatch.signal,"WAIT");
 a.equal(outBatch.body.ultimateFourStageBatch.paperOrdersAllowed,false);
 a.equal(outBatch.body.ultimateFourStageBatch.dataStatus,"SOURCE_NOT_QUALIFIED");
 a.equal(outBatch.body.ultimateFourStageBatch.archiveStatus,"NO_FORWARD_CAPTURE");
 a.equal(outBatch.body.ultimateFourStageBatch.analysisStatus,"WAIT_CLOSED_DATA_OR_CONTEXT");
 a.equal(outBatch.body.ultimateFourStageBatch.technicalWatch,"NONE");
 a.equal(outBatch.body.ultimateFourStageBatch.frameCounts.H4.contiguous,0);
 a.equal(outBatch.body.ultimateFourStageBatch.capacityStatus,"CAPACITY_HEADROOM");
 a.equal(outBatch.body.ultimateFourStageBatch.quoteSamplesRemaining,10000);
 a.equal(outBatch.body.ultimateFourStageBatch.capacityExhausted,false);
 const quality={...batch,
  stages:{...batch.stages,archive:{...batch.stages.archive,
   stage2Status:"WAIT_NO_FORWARD_CLOSED_BARS",
   stage2Frames:Object.fromEntries(["M15","H1","H4"].map(tf=>
    [tf,{persistedClosed:0,contiguousClosed:0,remainingUntil21:21,
      unclassifiedGapPairs:0,unclassifiedMissingSlots:0}])),
   stage2SourceVerified:false,stage2SessionCalendarVerified:false,
   stage2EligibleForPaper:false}}};
 const stage3={status:"WAIT_CLOSED_BAR_WARMUP",signal:"WAIT",
   minimumContiguousClosedEachFrame:21,framesWithWarmup:0,
   h4ContiguousClosed:0,h4RemainingUntil21:21,
   frozenV3Observed:false,crossFrameParityObserved:false,
   brokerRightsVerified:false,brokerSessionCalendarVerified:false,
   independentMacroOrderFlowVerified:false,
   paperOrdersAllowed:false,liveOrdersAllowed:false};
 const qualityWithV3={...quality,stages:{...quality.stages,
   analysis:{...quality.stages.analysis,stage3}}};
 const withQuality=await relay(auth,{approved:true,fetchFn:async()=>mock({
   ...expected,ultimateFourStageBatch:qualityWithV3
 })});
 a.equal(withQuality.httpStatus,200);
 a.equal(withQuality.body.ultimateFourStageBatch.stage2.signal,"WAIT");
 a.equal(withQuality.body.ultimateFourStageBatch.stage2.frames.H4.remainingUntil21,21);
 a.equal(withQuality.body.ultimateFourStageBatch.stage2.paperOrdersAllowed,false);
 a.equal(withQuality.body.ultimateFourStageBatch.stage3.status,"WAIT_CLOSED_BAR_WARMUP");
 a.equal(withQuality.body.ultimateFourStageBatch.stage3.h4RemainingUntil21,21);
 for(const attempted3 of [
   {status:"WAIT_INDEPENDENT_FEEDS_AND_RIGHTS"},
   {framesWithWarmup:3},
   {h4RemainingUntil21:0},
   {frozenV3Observed:true},
   {crossFrameParityObserved:true},
   {brokerRightsVerified:true},
   {paperOrdersAllowed:true},
   {liveOrdersAllowed:true}
 ]){
   const bad=await relay(auth,{approved:true,fetchFn:async()=>mock({
     ...expected,ultimateFourStageBatch:{...qualityWithV3,
       stages:{...qualityWithV3.stages,
         analysis:{...qualityWithV3.stages.analysis,
           stage3:{...stage3,...attempted3}}}}
   })});
   a.equal(bad.httpStatus,503,"Forged Stage 3 readiness blocked");
 }
 for(const attempted of [
  {stage2Status:"WAIT_INDEPENDENT_SOURCE_RIGHTS_AND_CALENDAR"},
  {stage2SourceVerified:true},
  {stage2EligibleForPaper:true},
  {stage2Frames:{...quality.stages.archive.stage2Frames,
   H4:{...quality.stages.archive.stage2Frames.H4,remainingUntil21:0}}},
  {stage2Frames:{...quality.stages.archive.stage2Frames,
   M15:{...quality.stages.archive.stage2Frames.M15,unclassifiedMissingSlots:-1}}}
 ]){
  const denial=await relay(auth,{approved:true,fetchFn:async()=>mock({
   ...expected,ultimateFourStageBatch:{...quality,
    stages:{...quality.stages,archive:{...quality.stages.archive,...attempted}}}
  })});
  a.equal(denial.httpStatus,503,"Forged Stage 2 status blocked");
 }
 for(const secret of ["12345","12346","12347","12348","PRIVATE_SECRET_TOKEN",
                      "fakeProfit","rawCandles","unknownApiKey"]){
  a.ok(!JSON.stringify(outBatch).includes(secret),"No prices or secrets on mobile");
 }
 for(const change of [{signal:"BUY"},{paperOrdersAllowed:true},
   {archiveWritesMade:1},{brokerOrdersSent:1},
   {outOfSampleNetExpectancyProven:true},{rawMarketPricesExposed:true},
   {stages:{...batch.stages,analysis:{...batch.stages.analysis,
    technicalWatch:"BUY"}}},
   {stages:{...batch.stages,paper:{...batch.stages.paper,
    paperOrdersAllowed:true}}},
   {stages:{...batch.stages,archive:{...batch.stages.archive,
    consecutiveClosedCounts:{M15:0,H1:0,H4:999}}}},
   {stages:{...batch.stages,archive:{...batch.stages.archive,
    capacityStatus:"CAPACITY_LIMIT_REACHED",archiveCapacityExhausted:false}}},
   {stages:{...batch.stages,archive:{...batch.stages.archive,
    quoteSamplesRemaining:-3}}},
   {stages:{...batch.stages,archive:{...batch.stages.archive,
    automaticQuoteDeletionAllowed:true}}}]){
   const bad=await relay(auth,{approved:true,fetchFn:async()=>mock({
    ...expected,ultimateFourStageBatch:{...batch,...change}})});
   a.equal(bad.httpStatus,503,"Forged batch readiness rejected");
 }
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
