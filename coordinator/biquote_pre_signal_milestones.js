"use strict";
/**
 * Offline, privacy-safe four-stage readiness milestones.
 * A diagnostic summary, never a recommendation or order admission engine.
 * Inputs are existing point-in-time and count-only evidence reports.
 */
const MODE="GOLD_PRECISION_PRE_SIGNAL_MILESTONES_V1";
const NUM=x=>Number.isSafeInteger(x)&&x>=0&&x<=20000000;
const hardWait=()=>({mode:MODE,signal:"WAIT",executable:false,
 recommendationAllowed:false,tradeEligible:false,paperOrdersAllowed:false,
 liveOrdersAllowed:false,brokerOrdersSent:0,providerRequestsMade:0,
 sourceRightsVerified:false,upstreamBrokerScheduleVerified:false,
 independentHoldoutValidated:false});
function summarize(input){
 const p=input?.pointInTime,q=input?.countEvidence;
 const validPoint=p?.mode==="BIQUOTE_LOCAL_POINT_IN_TIME_DATA_GATE_V1"&&
  p?.signal==="WAIT"&&p?.executable===false&&p?.tradeEligible===false&&
  p?.paperOrdersAllowed===false&&p?.brokerOrdersSent===0&&
  p?.sourceRightsVerified===false&&p?.independentAvailabilityVerified===false&&
  NUM(p?.contiguousObservedClosed?.H4)&&
  NUM(p?.technicalWarmupMissing?.H4)&&
  NUM(p?.paperHistoryMissing?.H4)&&
  p.technicalWarmupMissing.H4===Math.max(0,21-p.contiguousObservedClosed.H4)&&
  p.paperHistoryMissing.H4===Math.max(0,50-p.contiguousObservedClosed.H4);
 const validCounts=q?.mode==="BIQUOTE_H4_EVIDENCE_QUALITY_LEDGER_COUNTS_ONLY"&&
  q?.signal==="WAIT"&&q?.executable===false&&q?.tradeEligible===false&&
  q?.perCandleFirstSeenVerified===false&&q?.h4LatestConstituentsProven===false&&
  q?.independentHoldoutValidated===false&&q?.sourceRightsVerified===false;
 const h4=validPoint?p.contiguousObservedClosed.H4:null;
 const local21=validPoint&&p.technicalWarmupMissing.H4===0&&
  p.warmupCrossFrameFullyVerified===true&&
  p.latestExpectedUTCGridClosedObservedAtDecision?.H4===true&&
  p.latestEligibleClosedObservedAtDecision?.H4===true&&
  p.localGeometryObserved===true;
 const local50=local21&&p.paperHistoryMissing.H4===0;
 const stages=[
  {id:"SOURCE_RIGHTS_AND_SESSION",state:"EXTERNAL_EVIDENCE_REQUIRED",complete:false,
   reason:"BIQUOTE_PRIVATE_USE_PERMISSION_IS_NOT_UPSTREAM_BROKER_ATTESTATION"},
  {id:"CLOSED_HISTORY_AND_PARITY",state:local50?"LOCAL_50_H4_ONLY_NOT_MARKET_PROOF":
   local21?"LOCAL_21_H4_ONLY_PAPER_HISTORY_PENDING":
   validPoint?"LOCAL_H4_HISTORY_INCOMPLETE_OR_UNVERIFIED":"NO_VALID_POINT_IN_TIME_REPORT",
   complete:false,requiredTechnicalH4:21,requiredPaperH4:50,
   observedContiguousH4:h4,remainingToTechnicalH4:h4===null?null:Math.max(0,21-h4),
   remainingToPaperH4:h4===null?null:Math.max(0,50-h4),
   localWarmupCrossFrameVerified:local21,
   independentPerBarParityProven:false,countOnlyLedgerRecognized:validCounts},
  {id:"MACRO_GC_ORDER_FLOW",state:"REALTIME_PROVENANCE_AND_SYNC_UNVERIFIED",complete:false,
   reason:"NO_LICENSED_SYNCHRONIZED_DXY_YIELDS_GC_AND_NEWS_EVIDENCE"},
  {id:"PROSPECTIVE_PAPER_HOLDOUT",state:"UNTOUCHED_AFTER_COST_RESULTS_REQUIRED",complete:false,
   reason:"NO_INDEPENDENT_NET_OF_SPREAD_BROKER_COST_VALIDATION"}
 ];
 return {...hardWait(),asOfUTC:validPoint&&typeof p.asOfUTC==="string"?
  p.asOfUTC:null,stages,completedStages:0,requiredStages:4,
  local21H4Observed:local21,local50H4Observed:local50,
  blockers:stages.map(x=>x.id)};
}
module.exports={summarize};
