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
 // Price-free tick/candle quoteParity from the owner-only sealed feed:
 // 10 quote observations are NOT 10 independent historic BID/ASK bars.
 const quoteParity={
  mode:"PRIVATE_BIQUOTE_QUOTE_MID_CLOSED_OHLC_COUNTS_V1",
  status:"CONSISTENT_OBSERVED_SAMPLES_ONLY",signal:"WAIT",executable:false,
  researchEligible:false,paperOrdersAllowed:false,liveOrdersAllowed:false,
  brokerRightsVerified:false,brokerSessionCalendarVerified:false,
  independentBrokerPriceParityVerified:false,historicalBidAskOHLCVerified:false,
  sourceCandleBasis:"LIVE_MID_WITH_POSSIBLE_INITIAL_BID_SEED",
  sourceQuoteSamples:10,
  frames:{
   M15:{archivedClosedBars:3,comparableQuoteSamples:2,
     withinClosedOHLC:2,outsideClosedOHLC:0,notInArchivedClosedBars:8,
     distinctComparableClosedBars:1,rawPrice:"HIDE_PRIVATE_M15"},
   H1:{archivedClosedBars:1,comparableQuoteSamples:5,
     withinClosedOHLC:5,outsideClosedOHLC:0,notInArchivedClosedBars:5,
     distinctComparableClosedBars:1},
   H4:{archivedClosedBars:0,comparableQuoteSamples:0,
     withinClosedOHLC:0,outsideClosedOHLC:0,notInArchivedClosedBars:10,
     distinctComparableClosedBars:0}
  },secretBid:98765.5
 };
 const withQuoteParity=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,biquotePrivateForwardVault:{
   ...freshArchive,quoteCandleMidGeometry:quoteParity}
 })});
 a.equal(withQuoteParity.httpStatus,200);
 a.equal(withQuoteParity.body.biquotePrivateForwardVault.
   quoteCandleMidGeometry.frames.M15.withinClosedOHLC,2);
 a.equal(withQuoteParity.body.biquotePrivateForwardVault.
   quoteCandleMidGeometry.paperOrdersAllowed,false);
 a.ok(!JSON.stringify(withQuoteParity).includes("HIDE_PRIVATE_M15"));
 a.ok(!JSON.stringify(withQuoteParity).includes("98765.5"));
 for(const bad of [
  {brokerRightsVerified:true},{brokerSessionCalendarVerified:true},
  {historicalBidAskOHLCVerified:true},
  {independentBrokerPriceParityVerified:true},
  {liveOrdersAllowed:true},{status:"SOURCE_VERIFIED"},
  {sourceQuoteSamples:11},
  {frames:{...quoteParity.frames,
    M15:{...quoteParity.frames.M15,comparableQuoteSamples:3}}},
  {frames:{...quoteParity.frames,
    H4:{...quoteParity.frames.H4,outsideClosedOHLC:1}}},
  {status:"OBSERVED_MID_OUTSIDE_CLOSED_OHLC"}
 ]){
  const denied=await relay(auth,{approved:true,fetchFn:async()=>mock({
   ...expected,biquotePrivateForwardVault:{
    ...freshArchive,quoteCandleMidGeometry:{...quoteParity,...bad}}
  })});
  a.equal(denied.httpStatus,503,"No fake source or quote quoteParity proof");
 }
 // Metadata liveness is based on the sealed quote receipt and UTC.
 // No numeric price/spread from private storage may reach the mobile relay.
 const currentIso=new Date().toISOString();
 const freshStatus=(status,ageSeconds,asOfUTC=currentIso)=>({
  mode:"BIQUOTE_PRIVATE_CAPTURE_LIVENESS_DIAGNOSTIC_ONLY",
  status,ageSeconds,asOfUTC,signal:"WAIT",executable:false,
  paperOrdersAllowed:false,sourceQualified:false,
  brokerCalendarVerified:false,captureVerifiedByBroker:false,
  providerSecret:"NOT_IN_MOBILE_FRESHNESS"});
 const recentEnvelope={...freshArchive,lastImportedUTC:currentIso,
  captureFreshness:freshStatus("RECENT_UNVERIFIED",0)};
 const liveResult=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,biquotePrivateForwardVault:recentEnvelope
 })});
 a.equal(liveResult.httpStatus,200);
 a.equal(liveResult.body.biquotePrivateForwardVault.captureFreshness.status,
         "RECENT_UNVERIFIED");
 a.equal(liveResult.body.biquotePrivateForwardVault.captureFreshness.ageSeconds,0);
 a.equal(liveResult.body.biquotePrivateForwardVault.captureFreshness.paperOrdersAllowed,false);
 a.ok(!JSON.stringify(liveResult).includes("NOT_IN_MOBILE_FRESHNESS"));
 const tenMinBefore=new Date(Date.parse(currentIso)-600000).toISOString();
 const staleEnvelope={...freshArchive,lastImportedUTC:tenMinBefore,
  captureFreshness:freshStatus("STALE_OVER_5_MINUTES",600)};
 const staleResult=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,biquotePrivateForwardVault:staleEnvelope
 })});
 a.equal(staleResult.httpStatus,200);
 a.equal(staleResult.body.biquotePrivateForwardVault.captureFreshness.status,
         "STALE_OVER_5_MINUTES");
 a.equal(staleResult.body.biquotePrivateForwardVault.captureFreshness.ageSeconds,600);
 a.equal(staleResult.body.signal,"WAIT");
 const futureStamp=new Date(Date.parse(currentIso)+60000).toISOString();
 const futureResult=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,biquotePrivateForwardVault:{
    ...freshArchive,lastImportedUTC:futureStamp,
    captureFreshness:freshStatus("FUTURE_CAPTURE_OR_CLOCK_SKEW",null)}
 })});
 a.equal(futureResult.httpStatus,200);
 a.equal(futureResult.body.biquotePrivateForwardVault.captureFreshness.status,
         "FUTURE_CAPTURE_OR_CLOCK_SKEW");
 for(const [env,mut] of [
  [recentEnvelope,{status:"STALE_OVER_5_MINUTES"}],
  [staleEnvelope,{status:"RECENT_UNVERIFIED"}],
  [staleEnvelope,{ageSeconds:0}],
  [recentEnvelope,{sourceQualified:true}],
  [recentEnvelope,{brokerCalendarVerified:true}],
  [recentEnvelope,{paperOrdersAllowed:true}],
  [recentEnvelope,{captureVerifiedByBroker:true}],
  [recentEnvelope,{asOfUTC:"2020-01-01T00:00:00Z"}],
  [recentEnvelope,{ageSeconds:9999999}]
 ]){
  const rejected=await relay(auth,{approved:true,fetchFn:async()=>mock({
    ...expected,biquotePrivateForwardVault:{...env,
     captureFreshness:{...env.captureFreshness,...mut}}
  })});
  a.equal(rejected.httpStatus,503,"Invalid quote freshness cannot pass relay");
 }
 // A recent quote is independent of outdated M15 candles.
 const barAge={
  mode:"BIQUOTE_PRIVATE_CLOSED_FRAME_AGE_DIAGNOSTIC_ONLY",
  status:"AGE_COUNTS_ONLY_UNVERIFIED",signal:"WAIT",executable:false,
  paperOrdersAllowed:false,sourceQualified:false,
  brokerCalendarVerified:false,gapBridgingAllowed:false,
  asOfUTC:currentIso,
  frames:{
   M15:{status:"CANDLE_STALE_OVER_TWO_FRAMES",ageSeconds:3600,
    thresholdSeconds:1800,secretPrice:98989898},
   H1:{status:"RECENT_UNVERIFIED",ageSeconds:1000,thresholdSeconds:7200},
   H4:{status:"NO_CLOSED_BAR",ageSeconds:null,thresholdSeconds:28800}
  },providerSecret:"DO_NOT_COPY_CANDLE_PRICE"};
 const barEnvelope={...recentEnvelope,forwardCoverage:{
  ...recentEnvelope.forwardCoverage,
  M15:{...recentEnvelope.forwardCoverage.M15,
   lastClosedUTC:new Date(Date.parse(currentIso)-3600000).toISOString()},
  H1:{...recentEnvelope.forwardCoverage.H1,
   lastClosedUTC:new Date(Date.parse(currentIso)-1000000).toISOString()}},
  closedFrameFreshness:barAge};
 const aged=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,biquotePrivateForwardVault:barEnvelope
 })});
 a.equal(aged.httpStatus,200);
 a.equal(aged.body.signal,"WAIT");
 a.equal(aged.body.biquotePrivateForwardVault.captureFreshness.status,"RECENT_UNVERIFIED");
 a.equal(aged.body.biquotePrivateForwardVault.closedFrameFreshness.frames.M15.status,
         "CANDLE_STALE_OVER_TWO_FRAMES");
 a.equal(aged.body.biquotePrivateForwardVault.closedFrameFreshness.frames.H1.status,
         "RECENT_UNVERIFIED");
 a.equal(aged.body.biquotePrivateForwardVault.closedFrameFreshness.frames.H4.status,
         "NO_CLOSED_BAR");
 for(const secret of ["98989898","DO_NOT_COPY_CANDLE_PRICE","secretPrice","providerSecret"])
  a.ok(!JSON.stringify(aged).includes(secret));
 for(const mutated of [
  {...barAge,sourceQualified:true},
  {...barAge,brokerCalendarVerified:true},
  {...barAge,gapBridgingAllowed:true},
  {...barAge,paperOrdersAllowed:true},
  {...barAge,asOfUTC:"2020-01-01T00:00:00Z"},
  {...barAge,frames:{...barAge.frames,M15:{
   ...barAge.frames.M15,status:"RECENT_UNVERIFIED"}}},
  {...barAge,frames:{...barAge.frames,M15:{
   ...barAge.frames.M15,ageSeconds:1}}},
  {...barAge,frames:{...barAge.frames,H4:{
   ...barAge.frames.H4,status:"RECENT_UNVERIFIED"}}},
  {...barAge,frames:{...barAge.frames,H1:{
   ...barAge.frames.H1,thresholdSeconds:1800}}}
 ]){
  const bad=await relay(auth,{approved:true,fetchFn:async()=>mock({
   ...expected,biquotePrivateForwardVault:{...barEnvelope,closedFrameFreshness:mutated}
  })});
  a.equal(bad.httpStatus,503,"Fake closed-bar freshness must fail closed");
 }
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
 const parity={
  status:"CLOSED_ARCHIVE_GEOMETRY_ONLY_NOT_TRADE_PROOF",
  signal:"WAIT",paperOrdersAllowed:false,sourceRightsVerified:false,
  brokerCalendarVerified:false,
  frames:{
   H1:{higherClosedExamined:40,fullyCoveredCompared:10,
       fullyCoveredDisagreed:0,notFullyCovered:30,
       rawPrice:87654321},
   H4:{higherClosedExamined:23,fullyCoveredCompared:2,
       fullyCoveredDisagreed:0,notFullyCovered:21,
       rawHigh:76543210}},
  untrustedSecret:"PRIVATE_DO_NOT_FORWARD"
 };
 const warmup={
  status:"STRICT_RAW_CLOSED_BARS_BROKER_CALENDAR_UNVERIFIED",
  signal:"WAIT",paperOrdersAllowed:false,
  brokerCalendarVerified:false,sourceRightsVerified:false,
  gapBridgingAllowed:false,frames:{
   M15:{persistedClosed:80,strictLatestContiguous:48,remainingUntil21:0,
    unclassifiedMissingSlots:4,vendorPauseCandidatesNotVerified:4,
    outsideVendorReferenceSlots:0,unknownReferenceSlots:0,
    lastRunAfterUnclassifiedGap:true,privateRawOHLC:"DO_NOT_LEAK_WARMUP"},
   H1:{persistedClosed:40,strictLatestContiguous:40,remainingUntil21:0,
    unclassifiedMissingSlots:0,vendorPauseCandidatesNotVerified:0,
    outsideVendorReferenceSlots:0,unknownReferenceSlots:0,
    lastRunAfterUnclassifiedGap:false},
   H4:{persistedClosed:23,strictLatestContiguous:23,remainingUntil21:0,
    unclassifiedMissingSlots:0,vendorPauseCandidatesNotVerified:0,
    outsideVendorReferenceSlots:0,unknownReferenceSlots:0,
    lastRunAfterUnclassifiedGap:false}
  },secret:"CREDENTIAL_NOT_FOR_MOBILE"
 };
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
  spread:987654,entry:8888888,secretQuote:"NEVER_LEAK",
  diagnosticCrossFrameParity:parity,warmupContinuity:warmup}
 const sanitized=await relay(auth,{approved:true,fetchFn:async()=>mock({
    ...expected,biquoteForwardShadow:shadow})});
 a.equal(sanitized.httpStatus,200);
 a.equal(sanitized.body.signal,"WAIT");
 a.equal(sanitized.body.biquoteForwardShadow.technicalWatch,"BUY");
 a.equal(sanitized.body.biquoteForwardShadow.approvedDirection,"NONE");
 a.equal(sanitized.body.biquoteForwardShadow.paperOrdersAllowed,false);
 a.equal(sanitized.body.biquoteForwardShadow.frames.H4.contiguousClosed,23);
 a.equal(sanitized.body.biquoteForwardShadow.warmupContinuity.signal,"WAIT");
 a.equal(sanitized.body.biquoteForwardShadow.warmupContinuity.frames.M15.
   vendorPauseCandidatesNotVerified,4);
 a.equal(sanitized.body.biquoteForwardShadow.warmupContinuity.frames.M15.
   lastRunAfterUnclassifiedGap,true);
 a.equal(sanitized.body.biquoteForwardShadow.warmupContinuity.gapBridgingAllowed,false);
 a.ok(!JSON.stringify(sanitized).includes("DO_NOT_LEAK_WARMUP"));
 a.ok(!JSON.stringify(sanitized).includes("CREDENTIAL_NOT_FOR_MOBILE"));
 for(const secret of ["987654","8888888","NEVER_LEAK","secretQuote"]){
   a.ok(!JSON.stringify(sanitized).includes(secret),"Private raw prices and secrets must not leak");
 }
 // During H4 warmup the authenticated monitor may show real closed-bar
 // comparisons, but never fabricate coverage or certify the broker.
 const withParity=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,biquoteForwardShadow:{...shadow,diagnosticCrossFrameParity:parity}
 })});
 a.equal(withParity.httpStatus,200);
 const safeParity=withParity.body.biquoteForwardShadow.diagnosticCrossFrameParity;
 a.equal(safeParity.status,"CLOSED_ARCHIVE_GEOMETRY_ONLY_NOT_TRADE_PROOF");
 a.equal(safeParity.frames.H4.fullyCoveredCompared,2);
 a.equal(safeParity.frames.H4.notFullyCovered,21);
 a.equal(safeParity.frames.H1.fullyCoveredDisagreed,0);
 a.equal(safeParity.paperOrdersAllowed,false);
 a.equal(safeParity.brokerCalendarVerified,false);
 for(const sensitive of ["PRIVATE_DO_NOT_FORWARD","87654321","76543210",
                         "rawPrice","rawHigh"]){
  a.ok(!JSON.stringify(withParity).includes(sensitive));
 }
 for(const altered of [
  {...warmup,brokerCalendarVerified:true},
  {...warmup,sourceRightsVerified:true},
  {...warmup,gapBridgingAllowed:true},
  {...warmup,paperOrdersAllowed:true},
  {...warmup,frames:{...warmup.frames,M15:{
   ...warmup.frames.M15,strictLatestContiguous:80}}},
  {...warmup,frames:{...warmup.frames,M15:{
   ...warmup.frames.M15,vendorPauseCandidatesNotVerified:5}}},
  {...warmup,frames:{...warmup.frames,H4:{
   ...warmup.frames.H4,remainingUntil21:1}}},
  {...warmup,frames:{...warmup.frames,M15:{
   ...warmup.frames.M15,lastRunAfterUnclassifiedGap:false}}},
 ]){
  const denied=await relay(auth,{approved:true,fetchFn:async()=>mock({
   ...expected,biquoteForwardShadow:{...shadow,warmupContinuity:altered}
  })});
  a.equal(denied.httpStatus,503,"Forged warmup reference should fail closed");
 }
 // Never show an apparently strong BUY/SELL research watch from a
 // frozen-engine claim without both 21 closed bars AND archived H1/H4 parity.
 for(const fake of [
  {...shadow,diagnosticCrossFrameParity:undefined},
  {...shadow,diagnosticCrossFrameParity:null},
  {...shadow,frames:undefined},
  {...shadow,frames:{...shadow.frames,H4:{
    ...shadow.frames.H4,contiguousClosed:20}}},
  {...shadow,frames:{...shadow.frames,H1:{
    ...shadow.frames.H1,contiguousClosed:20}}},
  {...shadow,frames:{...shadow.frames,M15:{
    ...shadow.frames.M15,contiguousClosed:20}}},
  {...shadow,diagnosticCrossFrameParity:{
    ...parity,frames:{...parity.frames,H4:{
      ...parity.frames.H4,fullyCoveredCompared:0,notFullyCovered:23}}}},
  {...shadow,diagnosticCrossFrameParity:{
    ...parity,frames:{...parity.frames,H1:{
      ...parity.frames.H1,fullyCoveredCompared:0,notFullyCovered:40}}}},
 ]){
  const denied=await relay(auth,{approved:true,fetchFn:async()=>mock({
   ...expected,biquoteForwardShadow:fake
  })});
  a.equal(denied.httpStatus,503,"Incomplete V3 research proof must fail closed");
  a.equal(denied.body.signal,"WAIT");
  a.equal(denied.body.biquoteForwardShadow,undefined);
 }
 for(const forged of [
  {...parity,brokerCalendarVerified:true},
  {...parity,sourceRightsVerified:true},
  {...parity,paperOrdersAllowed:true},
  {...parity,frames:{...parity.frames,H4:{...parity.frames.H4,
     fullyCoveredCompared:23,notFullyCovered:0}}},
  {...parity,frames:{...parity.frames,H4:{...parity.frames.H4,
     fullyCoveredDisagreed:1}}},
  {...parity,frames:{...parity.frames,H1:{...parity.frames.H1,
     notFullyCovered:0}}},
  {...parity,frames:{...parity.frames,H1:{...parity.frames.H1,
     fullyCoveredDisagreed:11}}}
 ]){
  const blocked=await relay(auth,{approved:true,fetchFn:async()=>mock({
   ...expected,biquoteForwardShadow:{...shadow,diagnosticCrossFrameParity:forged}
  })});
  a.equal(blocked.httpStatus,503,"Forged H1/H4 OHLC evidence must fail closed");
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
    frames:undefined,engineReview:undefined,
    diagnosticCrossFrameParity:undefined,
    warmupContinuity:undefined}})});
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
 // JOINED snapshot regression: each individually valid panel MUST agree
 // on precisely the same sealed counts and bounded last-contiguous tail.
 // Fixtures are synthetic and never claim broker session/feed entitlements.
 const minutesBefore=n=>new Date(Date.parse(currentIso)-n*60000).toISOString();
 const combinedVault={...freshArchive,
  counts:{M15:80,H1:40,H4:23},
  lastImportedUTC:currentIso,
  captureFreshness:freshStatus("RECENT_UNVERIFIED",0),
  forwardCoverage:{
   M15:{...freshArchive.forwardCoverage.M15,
    closedBars:80,latestContiguousBars:48,
    lastClosedUTC:minutesBefore(2),
    unclassifiedMissingSlots:4,unclassifiedGapPairs:1},
   H1:{...freshArchive.forwardCoverage.H1,
    closedBars:40,latestContiguousBars:40,
    lastClosedUTC:minutesBefore(30)},
   H4:{...freshArchive.forwardCoverage.H4,
    closedBars:23,latestContiguousBars:23,
    firstClosedUTC:minutesBefore(360),
    lastClosedUTC:minutesBefore(120)}},
  gapReference:{...gapReference,frames:{
   M15:{...refFrame(80),gapPairs:1,unclassifiedMissingSlots:4,
    vendorPauseCandidateSlotsNotVerified:4},
   H1:refFrame(40),H4:refFrame(23)}},
  closedFrameFreshness:{
   mode:"BIQUOTE_PRIVATE_CLOSED_FRAME_AGE_DIAGNOSTIC_ONLY",
   status:"AGE_COUNTS_ONLY_UNVERIFIED",
   signal:"WAIT",executable:false,paperOrdersAllowed:false,
   sourceQualified:false,brokerCalendarVerified:false,
   gapBridgingAllowed:false,asOfUTC:currentIso,
   frames:{
    M15:{status:"RECENT_UNVERIFIED",ageSeconds:120,thresholdSeconds:1800},
    H1:{status:"RECENT_UNVERIFIED",ageSeconds:1800,thresholdSeconds:7200},
    H4:{status:"RECENT_UNVERIFIED",ageSeconds:7200,thresholdSeconds:28800}}}};
 const combinedBatch={...batch,stages:{...batch.stages,
  archive:{...batch.stages.archive,
   status:"FORWARD_CAPTURE_PRESENT_UNVERIFIED",
   closedCounts:{M15:80,H1:40,H4:23},
   consecutiveClosedCounts:{M15:48,H1:40,H4:23}},
  analysis:{...batch.stages.analysis,
   status:"FROZEN_V3_TECHNICAL_OBSERVATION_ONLY",
   technicalWatch:"BUY"}}};
 const joined=async(v=combinedVault,s=shadow,b=combinedBatch)=>relay(auth,{
  approved:true,fetchFn:async()=>mock({...expected,
   biquotePrivateForwardVault:v,biquoteForwardShadow:s,
   ultimateFourStageBatch:b})});
 const consistent=await joined();
 a.equal(consistent.httpStatus,200);
 a.equal(consistent.body.signal,"WAIT");
 a.equal(consistent.body.biquoteForwardShadow.technicalWatch,"BUY");
 a.equal(consistent.body.ultimateFourStageBatch.frameCounts.M15.contiguous,48);
 a.equal(consistent.body.ultimateFourStageBatch.stage3,undefined);
 a.equal(consistent.body.biquotePrivateForwardVault.counts.H4,23);
 for(const [v,s,b] of [
  [{...combinedVault,counts:{...combinedVault.counts,H4:22}},
   shadow,combinedBatch],
  [{...combinedVault,forwardCoverage:{...combinedVault.forwardCoverage,
    M15:{...combinedVault.forwardCoverage.M15,latestContiguousBars:46}}},
   shadow,combinedBatch],
  [{...combinedVault,gapReference:{...combinedVault.gapReference,
    frames:{...combinedVault.gapReference.frames,M15:{
     ...combinedVault.gapReference.frames.M15,
     vendorPauseCandidateSlotsNotVerified:0,outsideVendorReferenceSlots:4}}}},
   shadow,combinedBatch],
  [combinedVault,{...shadow,frames:{...shadow.frames,
    H4:{...shadow.frames.H4,persistedClosed:22}}},combinedBatch],
  [combinedVault,shadow,{...combinedBatch,stages:{
   ...combinedBatch.stages,archive:{...combinedBatch.stages.archive,
    consecutiveClosedCounts:{M15:48,H1:39,H4:23}}}}],
  [combinedVault,shadow,{...combinedBatch,stages:{
   ...combinedBatch.stages,analysis:{...combinedBatch.stages.analysis,
    technicalWatch:"SELL"}}}],
  [{...combinedVault,lastImportedUTC:tenMinBefore,
    captureFreshness:freshStatus("STALE_OVER_5_MINUTES",600)},
   shadow,combinedBatch],
  [{...combinedVault,closedFrameFreshness:{
    ...combinedVault.closedFrameFreshness,frames:{
     ...combinedVault.closedFrameFreshness.frames,H4:{
      status:"CANDLE_STALE_OVER_TWO_FRAMES",ageSeconds:30000,
      thresholdSeconds:28800}},
    asOfUTC:currentIso},forwardCoverage:{
     ...combinedVault.forwardCoverage,H4:{
      ...combinedVault.forwardCoverage.H4,
      lastClosedUTC:new Date(Date.parse(currentIso)-30000000).toISOString()}}},
   shadow,combinedBatch]
 ]){
  const rejected=await joined(v,s,b);
  a.equal(rejected.httpStatus,503,
    "Cross-panel mismatches or stale observations must fail closed");
  a.equal(rejected.body.signal,"WAIT");
  a.equal(rejected.body.biquoteForwardShadow,undefined);
  a.equal(rejected.body.ultimateFourStageBatch,undefined);
 }

 const paperHistory={mode:"BIQUOTE_PAPER_HISTORY_COUNT_PREFLIGHT_ONLY",
  status:"BELOW_50_CLOSED_BARS_PER_FRAME",signal:"WAIT",executable:false,
  paperOrdersAllowed:false,minimumClosedBarsEachFrame:50,
  closedCounts:{M15:0,H1:0,H4:0},missingUntil50:{M15:50,H1:50,H4:50},
  countMinimumMet:false,brokerSessionCalendarVerified:false,
  independentSourceRightsVerified:false,executionCostsVerified:false,
  sourceQuotesNotBrokerFills:true,privateBid:999991};
 const payload=ph=>({...batch,stages:{...batch.stages,
  paper:{...batch.stages.paper,historyReadiness:ph}}});
 const withHistory=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,ultimateFourStageBatch:payload(paperHistory)})});
 a.equal(withHistory.httpStatus,200);
 a.deepEqual(withHistory.body.ultimateFourStageBatch.paperHistory.missingUntil50,
  {M15:50,H1:50,H4:50});
 a.equal(withHistory.body.ultimateFourStageBatch.paperHistory.paperOrdersAllowed,false);
 a.ok(!JSON.stringify(withHistory).includes("999991"));
 for(const bad of [
  {status:"COUNT_FLOOR_REACHED_NOT_PAPER_READY"},{countMinimumMet:true},
  {paperOrdersAllowed:true},{minimumClosedBarsEachFrame:21},
  {missingUntil50:{M15:0,H1:50,H4:50}},{executionCostsVerified:true},
  {closedCounts:{M15:50,H1:0,H4:0}}
 ]){
  const rejected=await relay(auth,{approved:true,fetchFn:async()=>mock({
   ...expected,ultimateFourStageBatch:payload({...paperHistory,...bad})})});
  a.equal(rejected.httpStatus,503,"Forged paper-history proof must fail closed");
 }
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
 // One-shot completion audit is a computed blocker contract,
 // NEVER an all-green trade or order authorization.
 const completionAudit={
  mode:"GOLD_PRECISION_ONE_BATCH_COMPLETION_GATE_V1",
  status:"WAIT_EXTERNAL_EVIDENCE_AND_FORWARD_DATA",
  signal:"WAIT",executable:false,paperOrdersAllowed:false,
  liveOrdersAllowed:false,providerRequestsMade:0,brokerOrdersSent:0,
  independentMarketRightsVerified:false,brokerSessionDSTVerified:false,
  GCOrderFlowLicensed:false,independentMacroFeedsVerified:false,
  executionCostsVerified:false,outOfSampleNetExpectancyVerified:false,
  archiveIntegrityObserved:false,
  missingStrictClosedBarsUntil21:{M15:21,H1:21,H4:21},
  sessionWarmupRisk:{
   mode:"STRICT_GRID_WARMUP_BROKER_CALENDAR_EVIDENCE_PENDING_V1",
   status:"BROKER_SESSION_PROOF_REQUIRED",signal:"WAIT",
   executable:false,brokerCalendarVerified:false,
   sessionAwareWarmupAllowed:false,missingCandleBridgingAllowed:false,
   futureContinuityGuaranteed:false,rawGridOnly:true,
   strictContiguous:{M15:0,H1:0,H4:0},
   unclassifiedGapPairs:{M15:0,H1:0,H4:0},
   missingStrictClosedUntil21:{M15:21,H1:21,H4:21},
   rawH4Candles:"DO_NOT_SEND_PRIVATE_RAW_PRICE"},
  remainingBlockerCodes:[
   "NO_POST_HOLDOUT_CLOSED_CANDLES",
   "STRICT_M15_CLOSED_WARMUP_INCOMPLETE",
   "STRICT_H1_CLOSED_WARMUP_INCOMPLETE",
   "STRICT_H4_CLOSED_WARMUP_INCOMPLETE",
   "UNDERLYING_BROKER_MARKET_DATA_RIGHTS_UNCONFIRMED",
   "BROKER_XAUUSD_SESSION_DST_UNCONFIRMED",
   "GC_TRADES_MBO_MBP10_LICENSING_NOT_ESTABLISHED",
   "DXY_US02Y_US10Y_AND_EVENT_CONTEXT_NOT_INDEPENDENTLY_LIVE",
   "EXECUTION_BID_ASK_SPREAD_SLIPPAGE_FEES_UNVERIFIED",
   "OUT_OF_SAMPLE_NET_EXPECTANCY_NOT_PROVEN"
  ],
  privateProviderApiKey:"MUST_NOT_ESCAPE_MOBILE"};
 const withCompletion=await relay(auth,{approved:true,fetchFn:async()=>mock({
  ...expected,ultimateFourStageBatch:{...batch,completionAudit}
 })});
 a.equal(withCompletion.httpStatus,200);
 a.equal(withCompletion.body.signal,"WAIT");
 a.equal(withCompletion.body.ultimateFourStageBatch.completionAudit.status,
         "WAIT_EXTERNAL_EVIDENCE_AND_FORWARD_DATA");
 a.equal(withCompletion.body.ultimateFourStageBatch.completionAudit.
   missingStrictClosedBarsUntil21.H4,21);
 a.equal(withCompletion.body.ultimateFourStageBatch.completionAudit.
   remainingBlockerCodes.length,10);
 a.ok(!JSON.stringify(withCompletion).includes("MUST_NOT_ESCAPE_MOBILE"));
 a.ok(!JSON.stringify(withCompletion).includes("DO_NOT_SEND_PRIVATE_RAW_PRICE"));
 a.equal(withCompletion.body.ultimateFourStageBatch.completionAudit.
   sessionWarmupRisk.brokerCalendarVerified,false);
 a.equal(withCompletion.body.ultimateFourStageBatch.completionAudit.
   sessionWarmupRisk.futureContinuityGuaranteed,false);
 for(const badWarm of [
  {brokerCalendarVerified:true},{sessionAwareWarmupAllowed:true},
  {missingCandleBridgingAllowed:true},{futureContinuityGuaranteed:true},
  {rawGridOnly:false},
  {strictContiguous:{M15:21,H1:0,H4:0}},
  {unclassifiedGapPairs:{M15:0,H1:0,H4:1}},
  {missingStrictClosedUntil21:{M15:21,H1:21,H4:0}},
 ]){
  const denied=await relay(auth,{approved:true,fetchFn:async()=>mock({
   ...expected,ultimateFourStageBatch:{...batch,completionAudit:{
     ...completionAudit,sessionWarmupRisk:{
      ...completionAudit.sessionWarmupRisk,...badWarm
     }
   }}
  })});
  a.equal(denied.httpStatus,503,"Broker session bypass must be blocked");
 }
 for(const delta of [
  {independentMarketRightsVerified:true},{GCOrderFlowLicensed:true},
  {paperOrdersAllowed:true},{liveOrdersAllowed:true},
  {status:"READY_TO_TRADE"},
  {archiveIntegrityObserved:true},
  {missingStrictClosedBarsUntil21:{M15:0,H1:21,H4:21}},
  {remainingBlockerCodes:completionAudit.remainingBlockerCodes.slice(1)},
  {providerRequestsMade:1}
 ]){
  const rejected=await relay(auth,{approved:true,fetchFn:async()=>mock({
   ...expected,ultimateFourStageBatch:{...batch,
    completionAudit:{...completionAudit,...delta}}
  })});
  a.equal(rejected.httpStatus,503,"Completion claims must remain WAIT only");
 }
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
