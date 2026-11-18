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
  let recovery=null;
  if(audit.recovery!==undefined){
   const r=audit.recovery;
   const states=new Set(["RECOVERY_DISABLED","RECOVERY_NOT_STARTED","RECOVERY_UNAVAILABLE",
    "RECOVERY_STALE","SOURCE_ABSENT","SOURCE_REJECTED","SOURCE_INTERRUPTED",
    "OBSERVATION_SEEN_UNVERIFIED","OBSERVATION_REPEATED_UNVERIFIED"]);
   const validTime=r?.lastObservedUTC===null||(
    typeof r?.lastObservedUTC==="string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(r.lastObservedUTC));
   if(!r||!states.has(r.state)||!validTime||
      !Number.isInteger(r.consecutiveObservations)||r.consecutiveObservations<0||
      r.consecutiveObservations>3||r.requiredObservations!==3||
      !Number.isInteger(r.transitionCount)||r.transitionCount<0||r.transitionCount>1000000||
      r.sourceVerified!==false||r.paperOrdersAllowed!==false||
      r.signal!=="WAIT"||r.executable!==false)throw Error("Unsafe recovery audit");
   recovery={state:r.state,consecutiveObservations:r.consecutiveObservations,
    requiredObservations:3,lastObservedUTC:r.lastObservedUTC,
    transitionCount:r.transitionCount,sourceVerified:false,
    paperOrdersAllowed:false,signal:"WAIT",executable:false};
  }
  safeAudit={status:audit.status,lastObservedUTC:time,ageSeconds:age,
             alertCodes:codes,lastNotificationCode:note,signal:"WAIT",
             executable:false,paperRunning:false,externalNotificationsSent:0,
             ...(recovery?{recovery}:{})};
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
  const cost=paper.costReadiness;
  let costSafe;
  if(cost!==undefined){
   const checks=cost?.reasonCodes;
   const required=["BROKER_CONTRACT_AND_LOT_SPEC_UNVERIFIED",
     "LIVE_BID_ASK_SPREAD_EVIDENCE_MISSING",
     "COMMISSION_AND_SLIPPAGE_EVIDENCE_MISSING",
     "RISK_BUDGET_AND_STOP_DISTANCE_UNVERIFIED"];
   if(cost.mode!=="BROKER_COST_EVIDENCE_REVIEW_ONLY"||cost.status!=="BLOCKED"
      ||cost.signal!=="WAIT"||cost.executable!==false
      ||cost.modelAvailable!==true||cost.realBrokerFeesVerified!==false
      ||cost.realBidAskVerified!==false||cost.riskBudgetVerified!==false
      ||cost.ordersAllowed!==false||cost.sampleTradeExecuted!==false
      ||!Array.isArray(checks)||checks.length!==required.length
      ||required.some(c=>!checks.includes(c)))
      throw Error("Unsafe unverified cost model");
   costSafe={status:"BLOCKED",signal:"WAIT",executable:false,
    modelAvailable:true,realBrokerFeesVerified:false,realBidAskVerified:false,
    ordersAllowed:false,reasonCodes:required};
  }
  safePaper={mode:"PAPER_ADMISSION_REVIEW_ONLY",status:"BLOCKED",
   signal:"WAIT",executable:false,reviewOnly:true,paperRunning:false,
   paperOrdersAllowed:false,reasonCodes:[...new Set(codes)],
   ...(costSafe?{costReadiness:costSafe}:{})};
 }
 // A public/mobile proxy may forward ONLY counters and timestamps from the
 // authenticated, owner-only vault. Never forward raw BID/ASK or candle prices.
 let safeForward=null;
 if(input.biquotePrivateForwardVault!==undefined){
  const v=input.biquotePrivateForwardVault;
  if(v?.status==="VAULT_METADATA_UNAVAILABLE"){
   if(v.signal!=="WAIT"||v.executable!==false)
    throw Error("Unsafe vault error");
   safeForward={status:"VAULT_METADATA_UNAVAILABLE",signal:"WAIT",executable:false};
  }else{
   if(v?.mode!=="PRIVATE_FORWARD_BIQUOTE_CAPTURE_NOT_TRADING_ADMISSIBLE"||
      v.status!=="PRIVATE_FORWARD_VAULT_METADATA_ONLY"||
      v.signal!=="WAIT"||v.executable!==false||v.researchEligible!==false||
      v.tradeEligible!==false||v.paperOrdersAllowed!==false||
      v.tradeSignalReady!==false||v.providerRequestsMade!==0||v.ordersSent!==0||
      v.independentBrokerEntitlementVerified!==false||
      v.independentSessionCalendarVerified!==false||
      v.historicalBidAskOhlcAvailable!==false||v.noTradingAdmission!==true||
      v.researchCandidate!=="NONE")
    throw Error("Unsafe archive readiness");
   const utc=t=>typeof t==="string"&&
      /^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(t)&&
      Number.isFinite(Date.parse(t));
   if(!v.counts||!v.forwardCoverage||
      !Number.isInteger(v.quoteSamples)||v.quoteSamples<0||v.quoteSamples>10000||
      !(v.lastImportedUTC===null||utc(v.lastImportedUTC)))
    throw Error("Invalid archive metadata");
   const counts={},coverage={};
   for(const tf of ["M15","H1","H4"]){
    const n=v.counts[tf],f=v.forwardCoverage[tf];
    if(!Number.isInteger(n)||n<0||n>45000||!f||
       f.closedBars!==n||
       !Number.isInteger(f.latestContiguousBars)||f.latestContiguousBars<0||
       f.latestContiguousBars>n||
       !Number.isInteger(f.unclassifiedGapPairs)||f.unclassifiedGapPairs<0||
       f.unclassifiedGapPairs>n||
       !Number.isInteger(f.unclassifiedMissingSlots)||f.unclassifiedMissingSlots<0||
       f.unclassifiedMissingSlots>4500000||
       (n===0&&(f.firstClosedUTC!==null||f.lastClosedUTC!==null))||
       (n>0&&(!utc(f.firstClosedUTC)||!utc(f.lastClosedUTC)||
        Date.parse(f.firstClosedUTC)>Date.parse(f.lastClosedUTC)))||
       !(f.ageAtLastImportSeconds===null||(
         typeof f.ageAtLastImportSeconds==="number"&&
         Number.isFinite(f.ageAtLastImportSeconds)&&
         f.ageAtLastImportSeconds>=0&&f.ageAtLastImportSeconds<=31536000)))
      throw Error("Invalid closed-bar coverage");
    counts[tf]=n;
    coverage[tf]={closedBars:n,latestContiguousBars:f.latestContiguousBars,
      unclassifiedGapPairs:f.unclassifiedGapPairs,
      unclassifiedMissingSlots:f.unclassifiedMissingSlots,
      lastClosedUTC:f.lastClosedUTC,
      ageAtLastImportSeconds:f.ageAtLastImportSeconds};
   }
   if(Object.values(counts).some(n=>n>0)&&!utc(v.lastImportedUTC))
    throw Error("Missing archive update time");
   safeForward={mode:"PRIVATE_FORWARD_BIQUOTE_CAPTURE_NOT_TRADING_ADMISSIBLE",
    status:"PRIVATE_FORWARD_VAULT_METADATA_ONLY",signal:"WAIT",executable:false,
    tradeEligible:false,paperOrdersAllowed:false,researchEligible:false,
    tradeSignalReady:false,counts,quoteSamples:v.quoteSamples,
    lastImportedUTC:v.lastImportedUTC,forwardCoverage:coverage};
   // Receipt freshness is not a feed SLA. Validate the coordinator's
   // timestamp against this relay clock and the sealed arrival time.
   // A forged "recent" flag must never revive a stale observation.
   if(v.captureFreshness!==undefined){
    const f=v.captureFreshness;
    if(!f||f.mode!=="BIQUOTE_PRIVATE_CAPTURE_LIVENESS_DIAGNOSTIC_ONLY"||
       f.signal!=="WAIT"||f.executable!==false||
       f.paperOrdersAllowed!==false||f.sourceQualified!==false||
       f.brokerCalendarVerified!==false||
       f.captureVerifiedByBroker!==false)
     throw Error("Unsafe capture freshness contract");
    const asofSafe=typeof f.asOfUTC==="string"&&utc(f.asOfUTC)&&
      Math.abs(Date.now()-Date.parse(f.asOfUTC))<=120000;
    if(!asofSafe)throw Error("Unverified capture status UTC");
    const noCapture=v.quoteSamples===0||v.lastImportedUTC===null;
    let expected,age=null;
    if(noCapture){
     expected="NO_CAPTURE";
    }else{
     const diff=(Date.parse(f.asOfUTC)-Date.parse(v.lastImportedUTC))/1000;
     if(!Number.isFinite(diff))throw Error("Invalid capture clock delta");
     if(diff<0)expected="FUTURE_CAPTURE_OR_CLOCK_SKEW";
     else{
      age=Math.min(Math.floor(diff),31536000);
      expected=diff<=300?"RECENT_UNVERIFIED":"STALE_OVER_5_MINUTES";
     }
    }
    if(f.status!==expected||
       !(age===null?f.ageSeconds===null:
         Number.isInteger(f.ageSeconds)&&Math.abs(f.ageSeconds-age)<=1))
     throw Error("Forged capture liveness");
    safeForward.captureFreshness={
     mode:"BIQUOTE_PRIVATE_CAPTURE_LIVENESS_DIAGNOSTIC_ONLY",
     status:expected,signal:"WAIT",executable:false,
     paperOrdersAllowed:false,sourceQualified:false,
     brokerCalendarVerified:false,captureVerifiedByBroker:false,
     asOfUTC:f.asOfUTC,ageSeconds:age};
   }
   // Independently validate age of the last really CLOSED M15/H1/H4
   // candle. A fresh tick/quote cannot make a frozen candle history fresh.
   // These age thresholds are purely diagnostics, not broker trading hours.
   if(v.closedFrameFreshness!==undefined){
    const f=v.closedFrameFreshness;
    if(!f||f.mode!=="BIQUOTE_PRIVATE_CLOSED_FRAME_AGE_DIAGNOSTIC_ONLY"||
       f.status!=="AGE_COUNTS_ONLY_UNVERIFIED"||
       f.signal!=="WAIT"||f.executable!==false||
       f.paperOrdersAllowed!==false||f.sourceQualified!==false||
       f.brokerCalendarVerified!==false||f.gapBridgingAllowed!==false||
       typeof f.asOfUTC!=="string"||!utc(f.asOfUTC)||
       Math.abs(Date.now()-Date.parse(f.asOfUTC))>120000||
       !f.frames||Object.keys(f.frames).sort().join(",")!=="H1,H4,M15")
     throw Error("Unsafe closed-bar age diagnostic");
    const frames={};
    for(const [tf,width] of [["M15",900],["H1",3600],["H4",14400]]){
     const x=f.frames[tf],close=coverage[tf].lastClosedUTC,
       n=counts[tf],threshold=width*2;
     let status,age=null;
     if(n===0){
      status="NO_CLOSED_BAR";
     }else{
      if(typeof close!=="string"||!utc(close))
       throw Error("Unverifiable closed-bar timestamp");
      const diff=(Date.parse(f.asOfUTC)-Date.parse(close))/1000;
      if(!Number.isFinite(diff))throw Error("Unverifiable closed-bar clock");
      if(diff<0)status="FUTURE_CLOSE_OR_CLOCK_SKEW";
      else{
       age=Math.min(Math.floor(diff),31536000);
       status=diff<=threshold?"RECENT_UNVERIFIED":
         "CANDLE_STALE_OVER_TWO_FRAMES";
      }
     }
     if(!x||x.status!==status||x.thresholdSeconds!==threshold||
        !(age===null?x.ageSeconds===null:
          Number.isInteger(x.ageSeconds)&&Math.abs(x.ageSeconds-age)<=1))
      throw Error("Forged closed-bar age diagnostic");
     frames[tf]={status,ageSeconds:age,thresholdSeconds:threshold};
    }
    safeForward.closedFrameFreshness={
     mode:"BIQUOTE_PRIVATE_CLOSED_FRAME_AGE_DIAGNOSTIC_ONLY",
     status:"AGE_COUNTS_ONLY_UNVERIFIED",signal:"WAIT",executable:false,
     paperOrdersAllowed:false,sourceQualified:false,
     brokerCalendarVerified:false,gapBridgingAllowed:false,
     asOfUTC:f.asOfUTC,frames};
   }
   // Gap classification is a *vendor reference hypothesis*, not proof of
   // an upstream broker schedule. Forward aggregated integers only, never
   // timestamp arrays or market price payloads from the sealed vault.
   if(v.gapReference!==undefined){
    const g=v.gapReference,frameSummary={};
    if(g?.mode!=="BIQUOTE_PRIVATE_REFERENCE_GAP_COUNTS_ONLY"||
       g.status!=="REFERENCE_ONLY_NOT_BROKER_VERIFIED"||
       g.signal!=="WAIT"||g.executable!==false||
       g.researchEligible!==false||g.paperOrdersAllowed!==false||
       g.liveOrdersAllowed!==false||
       g.independentBrokerCalendarVerified!==false||
       g.sourceRightsVerified!==false||
       g.allGapsRemainUnclassified!==true)
     throw Error("Unsafe source gap reference");
    for(const tf of ["M15","H1","H4"]){
     const x=g.frames?.[tf],f=coverage[tf],n=counts[tf];
     if(!x||x.persistedClosed!==n||x.gapPairs!==f.unclassifiedGapPairs||
        x.unclassifiedMissingSlots!==f.unclassifiedMissingSlots||
        x.comparisonHasAtLeastTwoBars!==(n>=2)||
        !Number.isInteger(x.vendorPauseCandidateSlotsNotVerified)||
        !Number.isInteger(x.outsideVendorReferenceSlots)||
        !Number.isInteger(x.unknownReferenceSlots)||
        [x.vendorPauseCandidateSlotsNotVerified,x.outsideVendorReferenceSlots,
         x.unknownReferenceSlots].some(v=>v<0||v>4500000)||
        x.vendorPauseCandidateSlotsNotVerified+x.outsideVendorReferenceSlots+
         x.unknownReferenceSlots!==x.unclassifiedMissingSlots)
      throw Error("Forged or inconsistent source gap counts");
     frameSummary[tf]={
      unclassifiedMissingSlots:x.unclassifiedMissingSlots,
      vendorPauseCandidateSlotsNotVerified:x.vendorPauseCandidateSlotsNotVerified,
      outsideVendorReferenceSlots:x.outsideVendorReferenceSlots,
      unknownReferenceSlots:x.unknownReferenceSlots};
    }
    safeForward.gapReference={
     status:"REFERENCE_ONLY_NOT_BROKER_VERIFIED",
     signal:"WAIT",executable:false,paperOrdersAllowed:false,
     independentBrokerCalendarVerified:false,sourceRightsVerified:false,
     allGapsRemainUnclassified:true,frames:frameSummary};
   }
  }
 }
 // Only a fixed set of private V3 shadow diagnostics may cross into
 // authenticated Android viewer. NEVER forward price, plans or paper orders.
 let safeShadow=null;
 if(input.biquoteForwardShadow!==undefined){
  const x=input.biquoteForwardShadow;
  if(!x||x.mode!=="BIQUOTE_PRIVATE_FORWARD_V3_SHADOW_ONLY"||
     x.signal!=="WAIT"||x.executable!==false||
     x.paperOrdersAllowed!==false||x.tradeEligible!==false||
     x.researchEligible!==false||x.brokerOrdersSent!==0||
     x.sourceRequestsMade!==0||!["BUY","SELL","NONE"].includes(x.technicalWatch)||
     x.approvedDirection!=="NONE"||x.signalReady!==false||
     !Array.isArray(x.reasonCodes)||x.reasonCodes.length<1||
     x.reasonCodes.length>35||
     x.reasonCodes.some(code=>typeof code!=="string"||! /^[A-Z0-9_]{3,90}$/.test(code)))
   throw Error("Unsafe or forged shadow status");
  const allowed=x.technicalWatch!=="NONE" &&
   x.engineReview==="FROZEN_V3_COMPLETED_WITH_REAL_OBSERVED_CLOSED_BARS";
  if(x.technicalWatch!=="NONE"&&!allowed)throw Error("Unverified technical watch");
  const counts={};
  if(x.frames!==undefined){
   for(const tf of ["M15","H1","H4"]){
    const item=x.frames?.[tf];
    if(!item||!Number.isInteger(item.persistedClosed)||item.persistedClosed<0||
       item.persistedClosed>45000||
       !Number.isInteger(item.contiguousClosed)||item.contiguousClosed<0||
       item.contiguousClosed>48||
       item.contiguousClosed>item.persistedClosed||
       item.neededContiguous!==21)
      throw Error("Unsafe shadow history counts");
    counts[tf]={persistedClosed:item.persistedClosed,
      contiguousClosed:item.contiguousClosed,neededContiguous:21};
   }
  }
  // Compare already-closed archive OHLC without leaking price levels.
  // "Compared" is only the fully covered subset; the remainder must not
  // be silently counted as agreeing. All output remains WAIT-only.
  let safeParity=null;
  if(x.diagnosticCrossFrameParity!==undefined){
   const p=x.diagnosticCrossFrameParity,details={};
   if(!p||p.status!=="CLOSED_ARCHIVE_GEOMETRY_ONLY_NOT_TRADE_PROOF"||
      p.signal!=="WAIT"||p.sourceRightsVerified!==false||
      p.brokerCalendarVerified!==false||p.paperOrdersAllowed!==false||
      !x.frames||!counts.M15||!counts.H1||!counts.H4)
    throw Error("Unsafe shadow OHLC geometry");
   for(const tf of ["H1","H4"]){
    const v=p.frames?.[tf],end=counts[tf].contiguousClosed;
    if(!v||
       [v.higherClosedExamined,v.fullyCoveredCompared,
        v.fullyCoveredDisagreed,v.notFullyCovered].some(
           k=>!Number.isInteger(k)||k<0||k>48)||
       v.higherClosedExamined!==end||
       v.fullyCoveredCompared+v.notFullyCovered!==end||
       v.fullyCoveredDisagreed>v.fullyCoveredCompared||
       v.fullyCoveredCompared>Math.floor(counts.M15.contiguousClosed/
          (tf==="H1"?4:16))||
       (v.fullyCoveredDisagreed>0&&x.technicalWatch!=="NONE"))
      throw Error("Contradictory or inflated OHLC comparison");
    details[tf]={
      higherClosedExamined:end,
      fullyCoveredCompared:v.fullyCoveredCompared,
      fullyCoveredDisagreed:v.fullyCoveredDisagreed,
      notFullyCovered:v.notFullyCovered};
   }
   if(allowed && ["H1","H4"].some(tf=>
     details[tf].fullyCoveredCompared<1||
     details[tf].fullyCoveredDisagreed!==0))
    throw Error("Forged V3 observation without OHLC parity");
   safeParity={status:"CLOSED_ARCHIVE_GEOMETRY_ONLY_NOT_TRADE_PROOF",
     signal:"WAIT",paperOrdersAllowed:false,
     sourceRightsVerified:false,brokerCalendarVerified:false,frames:details};
  }
  // Sanitized *unverified* candle-continuity diagnostics. Persisted bars
  // do not substitute for the latest consecutive run, and vendor reference
  // pauses must never be treated as a broker-approved gap exemption.
  let safeWarmup=null;
  if(x.warmupContinuity!==undefined){
   const w=x.warmupContinuity,details={};
   if(!w||
      w.status!=="STRICT_RAW_CLOSED_BARS_BROKER_CALENDAR_UNVERIFIED"||
      w.signal!=="WAIT"||w.paperOrdersAllowed!==false||
      w.brokerCalendarVerified!==false||w.sourceRightsVerified!==false||
      w.gapBridgingAllowed!==false||
      !counts.M15||!counts.H1||!counts.H4||
      !w.frames||Object.keys(w.frames).sort().join(",")!=="H1,H4,M15")
     throw Error("Unsafe V3 warmup continuity status");
   for(const tf of ["M15","H1","H4"]){
    const v=w.frames[tf],expected=counts[tf];
    const fields=["persistedClosed","strictLatestContiguous","remainingUntil21",
      "unclassifiedMissingSlots","vendorPauseCandidatesNotVerified",
      "outsideVendorReferenceSlots","unknownReferenceSlots"];
    if(!v||fields.some(f=>!Number.isSafeInteger(v[f])||v[f]<0||
         v[f]>4500000)||
       v.persistedClosed!==expected.persistedClosed||
       v.strictLatestContiguous!==expected.contiguousClosed||
       v.remainingUntil21!==Math.max(0,21-expected.contiguousClosed)||
       v.vendorPauseCandidatesNotVerified+v.outsideVendorReferenceSlots+
         v.unknownReferenceSlots!==v.unclassifiedMissingSlots||
       typeof v.lastRunAfterUnclassifiedGap!=="boolean"||
       v.lastRunAfterUnclassifiedGap!==(
        v.unclassifiedMissingSlots>0&&expected.contiguousClosed<
        expected.persistedClosed))
      throw Error("Forged V3 warmup continuity counts");
    details[tf]={
      persistedClosed:expected.persistedClosed,
      strictLatestContiguous:expected.contiguousClosed,
      remainingUntil21:v.remainingUntil21,
      unclassifiedMissingSlots:v.unclassifiedMissingSlots,
      vendorPauseCandidatesNotVerified:v.vendorPauseCandidatesNotVerified,
      outsideVendorReferenceSlots:v.outsideVendorReferenceSlots,
      unknownReferenceSlots:v.unknownReferenceSlots,
      lastRunAfterUnclassifiedGap:v.lastRunAfterUnclassifiedGap};
   }
   safeWarmup={
     status:"STRICT_RAW_CLOSED_BARS_BROKER_CALENDAR_UNVERIFIED",
     signal:"WAIT",brokerCalendarVerified:false,
     sourceRightsVerified:false,gapBridgingAllowed:false,
     paperOrdersAllowed:false,frames:details};
  }
  // A vendor/backend assertion of "frozen V3" alone is never enough
  // to show even a research-only BUY/SELL watch on the Android monitor.
  // Require observed closed-bar warmup AND separately checked OHLC parity.
  // No inferred/generic session pause can fill missing constituent bars.
  if(allowed && (
    ["M15","H1","H4"].some(tf=>!counts[tf]||
      counts[tf].contiguousClosed<21)||
    !safeParity||
    !safeWarmup||
    ["H1","H4"].some(tf=>
      safeParity.frames[tf].fullyCoveredCompared<1||
      safeParity.frames[tf].fullyCoveredDisagreed!==0)
  ))throw Error("Frozen V3 watch missing archived warmup or parity proof");
  safeShadow={mode:"BIQUOTE_PRIVATE_FORWARD_V3_SHADOW_ONLY",
    signal:"WAIT",executable:false,paperOrdersAllowed:false,
    signalReady:false,approvedDirection:"NONE",
    technicalWatch:x.technicalWatch,
    engineReview:allowed?"FROZEN_V3_COMPLETED_WITH_REAL_OBSERVED_CLOSED_BARS":
      "NOT_YET_READY",
    frames:counts,
    ...(safeParity?{diagnosticCrossFrameParity:safeParity}:{}),
    ...(safeWarmup?{warmupContinuity:safeWarmup}:{}),
    reasonCodes:[...new Set(x.reasonCodes)].slice(0,30)};
 }
 // Four-stage owner-only status: fixed enums/counters ONLY. The full
 // private review (and any BID/ASK, raw bars or test PnL) never crosses this
 // sanitized monitor boundary. A synthetically healthy V3 is NOT approval.
 let safeBatch=null;
 if(input.ultimateFourStageBatch!==undefined){
  const x=input.ultimateFourStageBatch,st=x?.stages;
  const allowedData=new Set(["SOURCE_NOT_QUALIFIED",
    "SAMPLED_SOURCE_QUALITY_CHECKED_NOT_LICENSED"]);
  const allowedArchive=new Set(["NO_FORWARD_CAPTURE",
    "FORWARD_CAPTURE_PRESENT_UNVERIFIED","PRIVATE_VAULT_NOT_READABLE"]);
  const allowedAnalysis=new Set(["WAIT_CLOSED_DATA_OR_CONTEXT",
    "FROZEN_V3_TECHNICAL_OBSERVATION_ONLY"]);
  const frames=st?.archive?.closedCounts;
  const consecutive=st?.archive?.consecutiveClosedCounts;
  const cap=st?.archive?.capacityStatus;
  const capAllowed=new Set(["CAPACITY_HEADROOM","CAPACITY_WARNING",
    "CAPACITY_LIMIT_REACHED","CAPACITY_METADATA_UNAVAILABLE"]);
  const capRemaining=st?.archive?.quoteSamplesRemaining;
  const capLimit=st?.archive?.quoteSamplesHardCap;
  if(x?.mode!=="GOLD_PRECISION_FOUR_STAGE_BATCH_READONLY_V1"||
     x.signal!=="WAIT"||x.executable!==false||
     x.paperOrdersAllowed!==false||x.liveOrdersAllowed!==false||
     x.tradeEligible!==false||x.signalReady!==false||
     x.researchEligible!==false||x.brokerOrdersSent!==0||
     x.providerRequestsMade!==0||x.archiveWritesMade!==0||
     x.paperLedgerWritesMade!==0||x.rawMarketPricesExposed!==false||
     x.brokerFeedRightsIndependentlyVerified!==false||
     x.brokerSessionCalendarIndependentlyVerified!==false||
     x.historicalBidAskExecutionVerified!==false||
     x.outOfSampleNetExpectancyProven!==false||
     !allowedData.has(st?.data?.status)||
     st.data.sourceRightsVerified!==false||
     st.data.independentBrokerCalendarVerified!==false||
     st.data.liveProviderConnected!==false||
     !allowedArchive.has(st?.archive?.status)||
     st.archive.dataSourceIndependentlyAuthenticated!==false||
     st.archive.sessionGapsProven!==false||
     st.archive.automaticQuoteDeletionAllowed!==false||
     !capAllowed.has(cap)||
     (cap==="CAPACITY_METADATA_UNAVAILABLE"
      ?(capRemaining!==null||capLimit!==null||st.archive.archiveCapacityExhausted!==true)
      :(!Number.isInteger(capRemaining)||capRemaining<0||capRemaining>10000||
        capLimit!==10000||
        st.archive.archiveCapacityExhausted!==(cap==="CAPACITY_LIMIT_REACHED")))||
     !allowedAnalysis.has(st?.analysis?.status)||
     (st.analysis.status!=="FROZEN_V3_TECHNICAL_OBSERVATION_ONLY"&&
      st.analysis.technicalWatch!=="NONE")||
     st.analysis.approvedDirection!=="NONE"||
     !["BUY","SELL","NONE"].includes(st.analysis.technicalWatch)||
     st.analysis.entry!==null||st.analysis.stopLoss!==null||
     st.analysis.takeProfit!==null||st.analysis.winProbability!==null||
     st.analysis.independentContextVerified!==false||
     st.context?.status!=="INDEPENDENT_SOURCE_CONFIRMATIONS_REQUIRED"||
     st.paper?.status!=="BLOCKED"||
     st.paper.paperOrdersAllowed!==false||
     st.paper.paperLedgerOpened!==false||
     st.paper.sampleTradesCreated!==0||
     st.paper.brokerCostsVerified!==false||
     st.paper.forwardNetPerformanceEstablished!==false)
   throw Error("Unsafe four-stage batch admission");
  const countSafe={};
  for(const tf of ["M15","H1","H4"]){
   const n=frames?.[tf],k=consecutive?.[tf];
   if(!Number.isInteger(n)||n<0||n>45000||
      !Number.isInteger(k)||k<0||k>n)
     throw Error("Unsafe batch archive counts");
   countSafe[tf]={closed:n,contiguous:k};
  }
  let stage2Safe=null;
  const qualityStatus=st.archive.stage2Status;
  const qualityFrames=st.archive.stage2Frames;
  if(qualityStatus!==undefined||qualityFrames!==undefined){
   const required=(st.archive.status==="PRIVATE_VAULT_NOT_READABLE"
      ?"WAIT_PRIVATE_ARCHIVE_UNAVAILABLE":
      st.archive.status==="NO_FORWARD_CAPTURE"
      ?"WAIT_NO_FORWARD_CLOSED_BARS":
      ["M15","H1","H4"].some(tf=>consecutive[tf]<21)
      ?"WAIT_CONTIGUOUS_CLOSED_BAR_WARMUP"
      :"WAIT_INDEPENDENT_SOURCE_RIGHTS_AND_CALENDAR");
   if(qualityStatus!==required||!qualityFrames||
      st.archive.stage2SourceVerified!==false||
      st.archive.stage2SessionCalendarVerified!==false||
      st.archive.stage2EligibleForPaper!==false)
    throw Error("Unsafe Stage 2 admission");
   const records={};
   for(const tf of ["M15","H1","H4"]){
    const v=qualityFrames[tf];
    if(!v||!Number.isInteger(v.persistedClosed)||
       v.persistedClosed!==frames[tf]||
       !Number.isInteger(v.contiguousClosed)||
       v.contiguousClosed!==consecutive[tf]||
       !Number.isInteger(v.remainingUntil21)||
       v.remainingUntil21!==Math.max(0,21-consecutive[tf])||
       !Number.isInteger(v.unclassifiedGapPairs)||
       v.unclassifiedGapPairs<0||v.unclassifiedGapPairs>frames[tf]||
       !Number.isInteger(v.unclassifiedMissingSlots)||
       v.unclassifiedMissingSlots<0||v.unclassifiedMissingSlots>4500000)
     throw Error("Unsafe Stage 2 frame continuity");
    records[tf]={remainingUntil21:v.remainingUntil21,
      unclassifiedGapPairs:v.unclassifiedGapPairs,
      unclassifiedMissingSlots:v.unclassifiedMissingSlots};
   }
   stage2Safe={status:qualityStatus,frames:records,
     brokerRightsVerified:false,sessionCalendarVerified:false,
     paperOrdersAllowed:false,signal:"WAIT"};
  }
  let stage3Safe=null;
  const v3=st.analysis.stage3;
  if(v3!==undefined){
   const technical=st.analysis.status==="FROZEN_V3_TECHNICAL_OBSERVATION_ONLY";
   const ready=["M15","H1","H4"].filter(tf=>consecutive[tf]>=21).length;
   const expectedStatus=st.archive.status==="PRIVATE_VAULT_NOT_READABLE"
     ?"WAIT_ARCHIVE_UNAVAILABLE":ready<3
     ?"WAIT_CLOSED_BAR_WARMUP":technical
     ?"WAIT_INDEPENDENT_FEEDS_AND_RIGHTS":"WAIT_SHADOW_FRESHNESS_OR_PARITY";
   if(!v3||v3.status!==expectedStatus||v3.signal!=="WAIT"||
      v3.minimumContiguousClosedEachFrame!==21||
      v3.framesWithWarmup!==ready||
      v3.h4ContiguousClosed!==consecutive.H4||consecutive.H4>48||
      v3.h4RemainingUntil21!==Math.max(0,21-consecutive.H4)||
      v3.frozenV3Observed!==technical||
      v3.crossFrameParityObserved!==technical||
      v3.brokerRightsVerified!==false||
      v3.brokerSessionCalendarVerified!==false||
      v3.independentMacroOrderFlowVerified!==false||
      v3.paperOrdersAllowed!==false||v3.liveOrdersAllowed!==false)
    throw Error("Unsafe Stage 3 readiness");
   stage3Safe={status:expectedStatus,signal:"WAIT",
     framesWithWarmup:ready,
     h4ContiguousClosed:consecutive.H4,
     h4RemainingUntil21:v3.h4RemainingUntil21,
     frozenV3Observed:technical,crossFrameParityObserved:technical,
     brokerRightsVerified:false,brokerSessionCalendarVerified:false,
     independentMacroOrderFlowVerified:false,
     paperOrdersAllowed:false,liveOrdersAllowed:false};
  }
  safeBatch={mode:"GOLD_PRECISION_FOUR_STAGE_BATCH_READONLY_V1",
   signal:"WAIT",executable:false,paperOrdersAllowed:false,
   dataStatus:st.data.status,archiveStatus:st.archive.status,
   analysisStatus:st.analysis.status,paperStatus:"BLOCKED",
   independentlyQualified:false,liveOrdersAllowed:false,
   technicalWatch:st.analysis.status==="FROZEN_V3_TECHNICAL_OBSERVATION_ONLY"
     ?st.analysis.technicalWatch:"NONE",
   frameCounts:countSafe,
   capacityStatus:cap,quoteSamplesRemaining:capRemaining,
   quoteSamplesHardCap:capLimit,
   capacityExhausted:st.archive.archiveCapacityExhausted,
   ...(stage2Safe?{stage2:stage2Safe}:{}),
   ...(stage3Safe?{stage3:stage3Safe}:{})};
   // The four-stage WAIT-only checklist cannot claim source authorisation.
   // Derive the expected blockers from independently validated counters.
   if(x.completionAudit!==undefined){
    const a=x.completionAudit,missing={},blockers=[];
    if(st.archive.status==="PRIVATE_VAULT_NOT_READABLE")
     blockers.push("PRIVATE_VAULT_UNREADABLE");
    else if(st.archive.status==="NO_FORWARD_CAPTURE")
     blockers.push("NO_POST_HOLDOUT_CLOSED_CANDLES");
    for(const tf of ["M15","H1","H4"]){
     missing[tf]=Math.max(0,21-consecutive[tf]);
     if(missing[tf])blockers.push("STRICT_"+tf+"_CLOSED_WARMUP_INCOMPLETE");
    }
    blockers.push("UNDERLYING_BROKER_MARKET_DATA_RIGHTS_UNCONFIRMED",
      "BROKER_XAUUSD_SESSION_DST_UNCONFIRMED",
      "GC_TRADES_MBO_MBP10_LICENSING_NOT_ESTABLISHED",
      "DXY_US02Y_US10Y_AND_EVENT_CONTEXT_NOT_INDEPENDENTLY_LIVE",
      "EXECUTION_BID_ASK_SPREAD_SLIPPAGE_FEES_UNVERIFIED",
      "OUT_OF_SAMPLE_NET_EXPECTANCY_NOT_PROVEN");
    const warm=a?.sessionWarmupRisk;
    if(!warm||warm.mode!=="STRICT_GRID_WARMUP_BROKER_CALENDAR_EVIDENCE_PENDING_V1"||
       warm.status!=="BROKER_SESSION_PROOF_REQUIRED"||
       warm.signal!=="WAIT"||warm.executable!==false||
       warm.brokerCalendarVerified!==false||
       warm.sessionAwareWarmupAllowed!==false||
       warm.missingCandleBridgingAllowed!==false||
       warm.futureContinuityGuaranteed!==false||
       warm.rawGridOnly!==true||
       !warm.strictContiguous||!warm.unclassifiedGapPairs||
       !warm.missingStrictClosedUntil21||
       ["M15","H1","H4"].some(tf=>
         warm.strictContiguous[tf]!==consecutive[tf]||
         warm.missingStrictClosedUntil21[tf]!==missing[tf]||
         warm.unclassifiedGapPairs[tf]!==(
           stage2Safe?.frames?.[tf]?.unclassifiedGapPairs??0)))
      throw Error("Unverified broker-session warmup risk or forged gap exemption");
    if(!a||a.mode!=="GOLD_PRECISION_ONE_BATCH_COMPLETION_GATE_V1"||
       a.status!=="WAIT_EXTERNAL_EVIDENCE_AND_FORWARD_DATA"||
       a.signal!=="WAIT"||a.executable!==false||
       a.paperOrdersAllowed!==false||a.liveOrdersAllowed!==false||
       a.providerRequestsMade!==0||a.brokerOrdersSent!==0||
       a.independentMarketRightsVerified!==false||
       a.brokerSessionDSTVerified!==false||
       a.GCOrderFlowLicensed!==false||
       a.independentMacroFeedsVerified!==false||
       a.executionCostsVerified!==false||
       a.outOfSampleNetExpectancyVerified!==false||
       a.archiveIntegrityObserved!==(st.archive.status===
        "FORWARD_CAPTURE_PRESENT_UNVERIFIED")||
       !a.missingStrictClosedBarsUntil21||
       ["M15","H1","H4"].some(tf=>
        a.missingStrictClosedBarsUntil21[tf]!==missing[tf])||
       !Array.isArray(a.remainingBlockerCodes)||
       JSON.stringify(a.remainingBlockerCodes)!==JSON.stringify(blockers))
     throw Error("Unsafe or forged one-batch completion checklist");
    safeBatch.completionAudit={
      mode:"GOLD_PRECISION_ONE_BATCH_COMPLETION_GATE_V1",
      status:"WAIT_EXTERNAL_EVIDENCE_AND_FORWARD_DATA",
      signal:"WAIT",executable:false,
      paperOrdersAllowed:false,liveOrdersAllowed:false,
      archiveIntegrityObserved:a.archiveIntegrityObserved,
      missingStrictClosedBarsUntil21:missing,
      sessionWarmupRisk:{
       mode:"STRICT_GRID_WARMUP_BROKER_CALENDAR_EVIDENCE_PENDING_V1",
       status:"BROKER_SESSION_PROOF_REQUIRED",
       signal:"WAIT",executable:false,rawGridOnly:true,
       brokerCalendarVerified:false,sessionAwareWarmupAllowed:false,
       missingCandleBridgingAllowed:false,futureContinuityGuaranteed:false,
       strictContiguous:{...consecutive},
       unclassifiedGapPairs:Object.fromEntries(
        ["M15","H1","H4"].map(tf=>
         [tf,stage2Safe?.frames?.[tf]?.unclassifiedGapPairs??0])),
       missingStrictClosedUntil21:missing,
      },
      remainingBlockerCodes:blockers};
   }
 }
 // One archived observation feeds the Android vault, V3 and four-stage
 // panels. Mismatched closed-bar counts (or a research watch despite stale
 // candle endpoints) must fail closed, not show a misleading BUY/SELL.
 const frames3=["M15","H1","H4"];
 if(safeForward?.status==="PRIVATE_FORWARD_VAULT_METADATA_ONLY"){
  if(safeShadow?.frames&&Object.keys(safeShadow.frames).length>0){
   for(const tf of frames3){
    const frame=safeShadow.frames[tf],cv=safeForward.forwardCoverage[tf],
      warm=safeShadow.warmupContinuity?.frames?.[tf],
      gap=safeForward.gapReference?.frames?.[tf];
    if(!frame||frame.persistedClosed!==safeForward.counts[tf]||
       frame.contiguousClosed!==Math.min(48,cv.latestContiguousBars)||
       (warm&&(warm.unclassifiedMissingSlots!==cv.unclassifiedMissingSlots||
         warm.lastRunAfterUnclassifiedGap!==(
          cv.unclassifiedMissingSlots>0&&frame.contiguousClosed<frame.persistedClosed)))||
       (warm&&gap&&(
         warm.vendorPauseCandidatesNotVerified!==gap.vendorPauseCandidateSlotsNotVerified||
         warm.outsideVendorReferenceSlots!==gap.outsideVendorReferenceSlots||
         warm.unknownReferenceSlots!==gap.unknownReferenceSlots)))
     throw Error("Contradictory sealed archive versus frozen V3 counts");
   }
   if(safeShadow.technicalWatch!=="NONE"&&(
      safeForward.captureFreshness?.status!=="RECENT_UNVERIFIED"||
      !safeForward.closedFrameFreshness||
      frames3.some(tf=>safeForward.closedFrameFreshness.frames[tf].status!==
        "RECENT_UNVERIFIED")))
    throw Error("Research watch with stale or missing quote/candle age");
  }
  if(safeBatch){
   for(const tf of frames3){
    const b=safeBatch.frameCounts[tf],cv=safeForward.forwardCoverage[tf],
      stage2=safeBatch.stage2?.frames?.[tf];
    if(!b||b.closed!==safeForward.counts[tf]||
       b.contiguous!==Math.min(48,cv.latestContiguousBars)||
       (stage2&&(stage2.unclassifiedGapPairs!==cv.unclassifiedGapPairs||
        stage2.unclassifiedMissingSlots!==cv.unclassifiedMissingSlots)))
     throw Error("Contradictory sealed archive versus four-stage counts");
   }
  }
 }
 if(safeShadow?.frames&&Object.keys(safeShadow.frames).length>0&&safeBatch){
  for(const tf of frames3){
   const frame=safeShadow.frames[tf],b=safeBatch.frameCounts[tf];
   if(!frame||!b||frame.persistedClosed!==b.closed||
      frame.contiguousClosed!==b.contiguous)
    throw Error("Contradictory frozen V3 versus four-stage counts");
  }
  if(safeBatch.analysisStatus==="FROZEN_V3_TECHNICAL_OBSERVATION_ONLY"&&
     safeBatch.technicalWatch!==safeShadow.technicalWatch)
   throw Error("Contradictory V3 research watch across panels");
 }
 return {status:"WAIT_EODHD_INTAKE",dataStatus:input.dataStatus,
  signal:"WAIT",executable:false,researchEligible:false,engineStatus:"NOT_INVOKED",
  paperRunning:false,closedBarCounts:safe,
  intake:{status:"BLOCKED",blockingReasons:[...new Set(reasons)].slice(0,20)},
  ...(safeAudit?{audit:safeAudit}:{}),...(safePaper?{paperGate:safePaper}:{}),
  ...(safeForward?{biquotePrivateForwardVault:safeForward}:{}),
  ...(safeShadow?{biquoteForwardShadow:safeShadow}:{}),
  ...(safeBatch?{ultimateFourStageBatch:safeBatch}:{})};
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
