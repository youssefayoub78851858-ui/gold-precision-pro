'use strict';
/**
 * Four-stage READ-ONLY research assembly.
 * Stages: closed data geometry, frozen V3 candidate/plan, independent context
 * vetoes, and prospective validation / paper readiness. Never a trade signal.
 * No network, disk, broker, subscription or real-order capability.
 */
const {evaluate}=require('./v3_ultimate');
const {review}=require('./ultimate_signal_quality_report');
const {checkFrame}=require('./v3_multitimeframe');
const {inspect:inspectContextTiming}=require('./independent_context_timing_preflight');
const {inspect:inspectVendorH4Session}=require('./biquote_session_h4_continuity_audit');

const TIMEFRAMES=Object.freeze({M15:15,H1:60,H4:240});
const CONTEXT=Object.freeze(['DXY','US02Y','US10Y','GC','calendar','headlines','orderFlow']);
const SAFE=Object.freeze({signal:'WAIT',executable:false,paperOrdersAllowed:false,
  liveOrdersAllowed:false,researchEligible:false,providerRequestsMade:0,
  alertsSent:0,profitabilityProven:false});
function time(value){
  if(typeof value!=='string'||!/^(20\d{2})-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(value))
    return NaN;
  const n=Date.parse(value);
  return Number.isFinite(n)&&new Date(n).toISOString().slice(0,19)===value.slice(0,19)?n:NaN;
}
function dataGeometry(frames,asOfUTC){
  const now=time(asOfUTC),details={},blockers=[];
  for(const [frame,minutes] of Object.entries(TIMEFRAMES)){
    const bars=frames?.[frame],check=Number.isFinite(now)
      ?checkFrame(bars,minutes,now):{ok:false,reason:'INVALID_INDEPENDENT_UTC_CLOCK'};
    const gaps=[];
    if(check.ok){
      const width=minutes*60000;
      for(let i=1;i<bars.length;i++){
        const before=Date.parse(bars[i-1].datetime??bars[i-1].timestamp);
        const next=Date.parse(bars[i].datetime??bars[i].timestamp);
        if(next-before!==width)gaps.push(i);
      }
    }
    if(!check.ok)blockers.push(frame+'_INVALID_OR_STALE_CLOSED_DATA');
    if(gaps.length)blockers.push(frame+'_SESSION_GAPS_UNVERIFIED');
    details[frame]={validClosedFrame:check.ok,barCount:Array.isArray(bars)?bars.length:0,
      unclassifiedGapCount:gaps.length,reason:check.ok?null:check.reason};
  }
  return {state:blockers.length?'BLOCKED':'GEOMETRY_ONLY',
    frames:details,blockers,independentSourceEntitlementVerified:false,
    brokerSessionCalendarVerified:false,historicalBidAskExecutionVerified:false};
}
function ladder(side,plan){
  if(!['BUY','SELL'].includes(side)||!plan||!Number.isFinite(plan.entry)||
     !Number.isFinite(plan.stop)||!Number.isFinite(plan.target)||
     !Number.isFinite(plan.spread)||plan.spread<0)return null;
  const d=Math.abs(plan.entry-plan.stop),sign=side==='BUY'?1:-1;
  if(!(d>0)||sign*(plan.entry-plan.stop)<=0||sign*(plan.target-plan.entry)<1.5*d)
    return null;
  const round=n=>Math.round(n*1000)/1000;
  const tp1=round(plan.entry+sign*d),tp2=round(plan.entry+sign*1.5*d);
  const tp3=round(plan.target);
  if(Math.min(tp1,tp2,tp3,plan.stop)<=0)return null;
  return {direction:side,entry:round(plan.entry),stopLoss:round(plan.stop),
    TP1:tp1,TP2:tp2,TP3:tp3,
    priceRisk:round(d),mode:'HYPOTHETICAL_SYNTHETIC_TEST_ONLY',
    tradeApproved:false,executable:false,brokerFillAssumptionsNotVerified:true};
}
function reviewFourStages(input){
  const origin=input?.dataOrigin,asOfUTC=input?.snapshot?.asOfUTC;
  const snapshot=input?.snapshot;
  const data=dataGeometry(snapshot?.frames,asOfUTC);
  const invalid=!Number.isFinite(time(asOfUTC));
  // Untrusted external context may only be compared at the EXACT
  // snapshot decision time. A credible-looking metadata packet from
  // another hour must not be presented as confirmation for this plan.
  const contextPacket=input?.contextTimeEvidence;
  const clocksAligned=!!contextPacket&&
    contextPacket.decisionUTC===asOfUTC&&contextPacket.asOfUTC===asOfUTC;
  const contextTiming=clocksAligned?
    inspectContextTiming(contextPacket):inspectContextTiming({});
  // Optional, separate Nov-2026 vendor-SUPPORT weekend exercise. Keep the
  // calendar check isolated from strict UTC-grid data geometry, which is
  // still the unchanged research/admission gate. Never infer a broker
  // attestation from a user-supplied or archived local receipt timestamp.
  const h4Packet=input?.h4SessionTimeEvidence;
  const h4ClockAligned=!!h4Packet&&h4Packet.asOfUTC===asOfUTC;
  const h4Timing=h4ClockAligned?
    inspectVendorH4Session(h4Packet):inspectVendorH4Session({});
  let core=null,independent=null;
  if(!invalid && snapshot && typeof snapshot==='object'){
    try{
      core=evaluate(snapshot);
      independent=review(snapshot);
    }catch(error){
      // Bad external evidence must never escape as an apparent opportunity.
      core=null;independent=null;
    }
  }
  const technical=core?.technical?.candidate||'NONE';
  const statuses=Object.fromEntries(CONTEXT.map(name=>[name,{
    status:core?.layers?.[name]?.status==='READY'?'PROVISIONAL_MODEL_EVIDENCE':'UNAVAILABLE',
    sourceIndependentRightsVerified:false,
    contextBlocked:core?.layers?.[name]?.blocked===true
  }]));
  const candidate=core?.researchCandidate||'NONE';
  const synthetic=origin==='SYNTHETIC_TEST_ONLY'&&
    CONTEXT.every(name=>snapshot?.feeds?.[name]?.mode==='synthetic');
  const hypothetical=synthetic&&data.blockers.length===0&&
    candidate!=='NONE'&&core.risk?.ok===true?
      ladder(candidate,core.tradePlan):null;
  const signalReasons=[...data.blockers,...(core?.monitoring?.blocked||['RESEARCH_ENGINE_NOT_READY'])];
  const contextBlockers=CONTEXT.filter(name=>statuses[name].status!=='PROVISIONAL_MODEL_EVIDENCE'||
    statuses[name].contextBlocked);
  return {...SAFE,mode:'FOUR_STAGE_PRIVATE_OFFLINE_RESEARCH_REVIEW',
    asOfUTC:invalid?null:asOfUTC,dataOrigin:origin||'UNVERIFIED',
    stages:{
      data:{status:data.state,checks:data.frames,
        blockers:[...data.blockers,'UPSTREAM_LICENSE_AND_BROKER_SESSION_NOT_ATTESTED'],
        // Separate vendor-conditional research clock, never an approval.
        vendorConditionalH4Timing:{
          mode:h4Timing.mode,
          status:h4ClockAligned?h4Timing.status:'NO_ALIGNED_H4_SESSION_TIMES',
          reason:h4ClockAligned?h4Timing.reason:'NO_ALIGNED_H4_SESSION_TIMES',
          decisionClockAligned:h4ClockAligned,
          barsWithLocalReceipt:h4Timing.barsWithLocalReceipt,
          rawUtcGridTail:h4Timing.rawUtcGridTail,
          vendorConditionalSessionTail:h4Timing.vendorConditionalSessionTail,
          providerDeclaredFullyClosedH4SlotsBridged:
            h4Timing.providerDeclaredFullyClosedH4SlotsBridged,
          missingProviderOpenH4Slots:h4Timing.missingProviderOpenH4Slots,
          unknownScheduleSlots:h4Timing.unknownScheduleSlots,
          conditional21H4Reached:h4Timing.conditional21H4Reached,
          conditional50H4Reached:h4Timing.conditional50H4Reached,
          originalBrokerSessionCalendarVerified:false,
          sourceRightsVerified:false,
          canReplaceStrictDataGate:false,
          sessionTimesCanAuthorizeTrades:false
        }},
      analysis:{status:core?'FROZEN_ENGINE_EVALUATED':'BLOCKED',
        technicalCandidate:technical,
        researchCandidate:synthetic?candidate:'NONE',
        reasons:[...new Set(signalReasons)],
        riskModelReady:core?.risk?.ok===true,
        independentQualityReviewAvailable:independent?.qualityDiagnostics?.status==='RESEARCH_DIAGNOSTIC_ONLY',
        qualityWarnings:independent?.qualityDiagnostics?.warnings||[],
        entryRobustness:independent?.entryRobustness ? {
          status:independent.entryRobustness.status,
          postCostRiskQuality:independent.entryRobustness.postCostRiskQuality,
          exploratoryWarnings:independent.entryRobustness.exploratoryWarnings,
          scenarios:independent.entryRobustness.scenarios,
          empiricalWinProbability:null,
          strategyChanged:false,
          paperOrdersAllowed:false,
          executable:false
        } : null},
      confirmation:{status:'INDEPENDENT_CONTEXT_NOT_VERIFIED',
        feeds:statuses,blockedLayers:contextBlockers,
        // Descriptive offline evidence only: no independent source,
        // rights or broker-native observation time is attested.
        externalContextTiming:{
          mode:contextTiming.mode,
          status:clocksAligned?contextTiming.status:'NO_ALIGNED_CONTEXT_TIMES',
          perLayer:contextTiming.perLayer,summary:contextTiming.summary,
          gcTradeDepthCrossCheck:contextTiming.gcTradeDepthCrossCheck||null,
          decisionClockAligned:clocksAligned,
          sourceIndependentlyAttested:false,
          contextCanAuthorizeTrading:false
        },
        sourceRightsVerified:false,independentMacroAndOrderFlowVerified:false},
      validation:{status:'NEW_HOLDOUT_AND_EXECUTION_COSTS_NOT_VALIDATED',
        forwardStartUTC:'2026-11-18T00:00:00Z',
        historicalBidAskAvailable:false,brokerCostsIndependentlyVerified:false,
        independentNetExpectancy:null,winProbability:null,
        deploymentAdmissible:false,paperFeedAdmissible:false}
    },
    hypotheticalSyntheticPlan:hypothetical,
    shadowVetoCodes:independent?.shadowVeto?.blockers||['SHADOW_REVIEW_NOT_READY'],
    noTradingReason:'Unlicensed or unverified upstream, broker costs, independent market evidence and untouched prospective performance. Research only.'};
}
module.exports={reviewFourStages,dataGeometry,ladder};
if(require.main===module){
  try{
    const fs=require('node:fs');
    const input=JSON.parse(fs.readFileSync(0,'utf8'));
    process.stdout.write(JSON.stringify(reviewFourStages(input))+'\n');
  }catch(e){console.error('FOUR_STAGE_OFFLINE_INPUT_REJECTED');process.exitCode=2;}
}
