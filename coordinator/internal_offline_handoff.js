"use strict";
/**
 * Unified, offline-only integration gate for the EXISTING Gold Precision
 * research and paper pipeline. A green result means only that five existing
 * fail-closed interfaces are wired and contract-compatible. It NEVER proves
 * live source access, licensing, feed timeliness, broker fills, a backtest
 * edge, or permission to generate a trade. No credentials or network calls.
 *
 * The licensed XAUUSD provider handoff is intentionally the FINAL stage.
 */
const {inspect:preapproval}=require("./preapproval_four_tracks_status");
const {assess:capacity}=require("./biquote_snapshot_capacity_gate");
const {summarize:milestones}=require("./biquote_pre_signal_milestones");
const {inspect:contextTiming}=require("./independent_context_timing_preflight");
const {evaluate:paperAudit}=require("./prospective_paper_holdout_audit");
const {inspect:paperTerminal}=require("./paper-terminal-inspect");
const {sample:paperFixture}=require("../paper-terminal-core");
const {reviewFourStages}=require("./ultimate_four_stage_review");
const {assess:releaseAudit}=require("./prelicense_release_audit");
const syntheticFixture=require("./fixtures/ultimate-synthetic.json");

const BASE=Object.freeze({
  mode:"GOLD_INTERNAL_OFFLINE_HANDOFF_V1",
  signal:"WAIT",executable:false,researchEligible:false,
  paperOrdersAllowed:false,liveOrdersAllowed:false,
  providerRequestsMade:0,brokerOrdersSent:0,paperOrdersSent:0,
  credentialsRead:0,paymentsMade:0,
  providerConnectionEnabled:false,
  independentSourceRightsVerified:false,
  independentHoldoutValidated:false,
  realMarketPriceAvailable:false,
  externalProviderDecisionDeferredToLastStage:true
});
const FINAL=Object.freeze([
  "WRITTEN_PRIVATE_CLOUD_AND_STORAGE_DATA_RIGHTS",
  "BROKER_BID_ASK_AND_CLOSED_M15_H1_H4_NATIVE_SESSION_VERIFICATION",
  "LICENSED_DXY_GC_TRADE_DEPTH_AND_ORDERFLOW_PLUS_MACRO_COVERAGE",
  "UNTOUCHED_FORWARD_PAPER_HOLDOUT_WITH_BROKER_COST_EVIDENCE"
]);
function contract(r){
  return r&&typeof r==="object"&&!Array.isArray(r)&&r.signal==="WAIT"&&
    r.executable===false&&r.paperOrdersAllowed===false&&
    r.liveOrdersAllowed!==true&&
    r.providerRequestsMade===0&&
    (r.brokerOrdersSent===undefined||r.brokerOrdersSent===0)&&
    r.sourceRightsVerified!==true;
}
function collectOfflineReports(){
  // Every invocation is local and independent of user credentials.
  return {
    sources:preapproval(),
    history:capacity(),
    chronology:milestones({}),
    context:contextTiming({}),
    paper:paperAudit({}),
    // Exercise the actual synthetic 512-bar / three-timeframe terminal
    // into frozen V3. It can never create paper/live orders on the server.
    paperTerminal:paperTerminal(paperFixture()),
    signalEngine:reviewFourStages({
      dataOrigin:"SYNTHETIC_TEST_ONLY",snapshot:syntheticFixture
    })
  };
}
function combine(input){
  const x=input&&typeof input==="object"&&!Array.isArray(input)?input:{};
  const checks={
    sourceRequirements:contract(x.sources)&&
      x.sources.mode==="GOLD_PREAPPROVAL_FOUR_TRACKS_V1"&&
      x.sources.status==="OFFLINE_PREPARATION_ONLY"&&
      x.sources.allFourTracksTradeReady===false&&
      x.sources.steps?.capitalDemo?.connected===false&&
      x.sources.steps?.capitalDemo?.privateCloudStorageApproved===false,
    closedFrameCapacity:contract(x.history)&&
      x.history.mode==="BIQUOTE_SINGLE_SNAPSHOT_21_H4_PARITY_CAPACITY_ONLY"&&
      x.history.status==="SINGLE_SNAPSHOT_CAPACITY_INSUFFICIENT"&&
      x.history.archiveCurrentlyVerified===false&&
      x.history.requiredM15Constituents===336&&
      x.history.singleSnapshotCanProve21H4M15Parity===false,
    candleChronology:contract(x.chronology)&&
      x.chronology.mode==="GOLD_PRECISION_PRE_SIGNAL_MILESTONES_V1"&&
      x.chronology.completedStages===0&&
      x.chronology.requiredStages===4&&
      x.chronology.stages?.length===4&&
      x.chronology.stages.every(s=>s?.complete===false),
    externalContextClocks:contract(x.context)&&
      x.context.mode==="GOLD_EXTERNAL_CONTEXT_TIMING_PREFLIGHT_OFFLINE_V1"&&
      x.context.status==="BLOCKED"&&
      x.context.allLayersQualified===false&&
      x.context.verifiedLiveLayerCount===0,
    paperCostHoldout:contract(x.paper)&&
      x.paper.status==="BLOCKED"&&
      x.paper.statistics===null&&
      x.paper.independentHoldoutValidated===false&&
      x.paper.profitabilityProven===false&&
      x.paperTerminal?.mode==="OFFLINE_SYNTHETIC_REPLAY"&&
      x.paperTerminal?.dataOrigin==="SYNTHETIC_TEST_ONLY"&&
      x.paperTerminal?.signal==="WAIT"&&
      x.paperTerminal?.executable===false&&
      x.paperTerminal?.researchEligible===false&&
      x.paperTerminal?.connectedRealMarketData===false&&
      x.paperTerminal?.paperExecutionOnServer===false&&
      x.paperTerminal?.brokerExecution===false&&
      x.paperTerminal?.tradePlanExecutable===false&&
      x.paperTerminal?.providerRequests===0&&
      x.paperTerminal?.ordersSent===0&&
      x.paperTerminal?.credentialsRead===0&&
      x.paperTerminal?.frameCounts?.M15===512&&
      x.paperTerminal?.frameCounts?.H4===32,
    frozenResearchAndShadow:contract(x.signalEngine)&&
      x.signalEngine.mode==="FOUR_STAGE_PRIVATE_OFFLINE_RESEARCH_REVIEW"&&
      x.signalEngine.stages?.analysis?.status==="FROZEN_ENGINE_EVALUATED"&&
      x.signalEngine.stages?.confirmation?.sourceRightsVerified===false&&
      x.signalEngine.stages?.validation?.deploymentAdmissible===false&&
      x.signalEngine.profitabilityProven===false
  };
  const pass=Object.values(checks).every(Boolean);
  const report={...BASE,
    status:pass?"OFFLINE_INTERFACES_CHECKED_EXTERNAL_EVIDENCE_PENDING":
                "OFFLINE_INTEGRATION_CONTRACT_FAILED",
    internalOfflineContractsChecked:pass,
    internalCheckCount:Object.keys(checks).length,
    checks:Object.fromEntries(Object.entries(checks).map(([name,ok])=>
      [name,ok?"OFFLINE_CONTRACT_COMPATIBLE":"BLOCKED_CONTRACT_UNVERIFIED"])),
    stageStatus:{
      closedCandles:"INTERNAL_GEOMETRY_GATES_PRESENT_REAL_HISTORY_UNVERIFIED",
      signals:"FROZEN_V3_RESEARCH_ONLY_NO_ORDERS",
      macroAndFlow:"OFFLINE_CLOCKS_PARTIAL_US_OFFICIAL_NO_LICENSED_LIVE_FLOW",
      paper:"SYNTHETIC_OR_UNATTESTED_COST_AUDIT_NO_FORWARD_PROOF",
      finalProvider:"DEFERRED_NOT_CONNECTED"
    },
    finalExternalEvidenceRequired:[...FINAL],
    // No scores or BUY/SELL can leave this public, offline status endpoint.
    signalCandidate:null,entry:null,stopLoss:null,targets:null,
    warning:"Offline interface compatibility, not successful CI or trading readiness."
  };
  return {...report,releaseAudit:releaseAudit(report)};
}
function inspect(){
  try{return combine(collectOfflineReports());}
  catch(_error){return combine(null);}
}
module.exports={inspect,combine,collectOfflineReports};
