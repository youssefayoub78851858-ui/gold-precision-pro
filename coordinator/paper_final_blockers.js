"use strict";
/**
 * Non-executable status of the five independently required paper-signal
 * prerequisites. Intentionally conservative: internal software tests, a
 * viewer session, a free spot quote and an archival backtest do NOT prove
 * source licensing, historical MTF parity or prospective paper performance.
 * No connection, secrets, prices, trading or subscription actions.
 */
const MODE="GOLD_PAPER_READINESS_BLOCKERS_V1";
const IDS=Object.freeze([
 "DURABLE_PAPER_STORAGE",
 "CLOUD_XAUUSD_DATA_RIGHTS",
 "VERIFIED_CLOSED_M15_H1_H4",
 "LICENSED_MACRO_GC_ORDERFLOW",
 "INDEPENDENT_FORWARD_PAPER_EVIDENCE"
]);
const BLOCKED="NOT_EXTERNALLY_VERIFIED";
function inspect(internal,startup){
 const release=internal?.releaseAudit;
 const internalSafe=internal?.mode==="GOLD_INTERNAL_OFFLINE_HANDOFF_V1"&&
  internal?.signal==="WAIT"&&internal?.executable===false&&
  internal?.paperOrdersAllowed===false&&internal?.liveOrdersAllowed===false&&
  internal?.providerRequestsMade===0&&internal?.brokerOrdersSent===0&&
  internal?.independentSourceRightsVerified===false&&
  internal?.realMarketPriceAvailable===false&&
  internal?.independentHoldoutValidated===false&&
  release?.mode==="GOLD_PRELICENSE_RELEASE_AUDIT_V1"&&
  release?.externalEvidenceVerifiedCount===0&&
  release?.externalEvidenceRequiredCount===4&&
  release?.allTradePrerequisitesSatisfied===false&&
  release?.readyForPaperExecution===false&&
  release?.readyForBuySell===false&&
  release?.signal==="WAIT"&&release?.executable===false;
 const diskOK=startup?.mode==="GOLD_PAPER_STARTUP_RECOVERY_GATE_V1"&&
  startup.status==="STARTUP_LOCAL_CHECKPOINT_READ_ONLY_VERIFIED"&&
  startup.checkpointSafe===true&&startup.paperResultsDisplayAllowed===true&&
  startup.backupOffsiteVerified===false&&
  startup.independentHoldoutValidated===false&&
  startup.marketDataConnected===false&&
  startup.paperOrdersAllowed===false&&startup.liveOrdersAllowed===false&&
  startup.providerRequestsMade===0&&startup.brokerOrdersSent===0&&
  startup.signal==="WAIT"&&startup.executable===false;
 const storageStatus=internalSafe&&diskOK?
  "LOCAL_CHECKPOINT_ONLY_OFFSITE_NOT_PROVEN":
  "DURABLE_STORAGE_AND_CHECKPOINT_NOT_VERIFIED";
 const requirements=IDS.map((id,i)=>({
  id,status:i===0?storageStatus:BLOCKED
 }));
 return Object.freeze({
  mode:MODE,
  status:internalSafe?"EXTERNAL_PREREQUISITES_PENDING":"INTERNAL_EVIDENCE_RECHECK_REQUIRED",
  requiredCount:IDS.length,
  locallyCheckedCount:internalSafe&&diskOK?1:0,
  externallyVerifiedCount:0,
  requirements,
  reviewServiceDeploymentAttested:false,
  actualGitHubCIPassAttestedByRuntime:false,
  licensedXauusdFeedReady:false,
  historicalM15H1H4ParityReady:false,
  externalMacroOrderflowReady:false,
  independentPaperHoldoutReady:false,
  automaticPaperLoggingEnabled:false,
  paperResultsStatisticallyValidated:false,
  nextM15ForecastAccuracyPct:null,
  readyForBuySell:false,
  readyForPaperExecution:false,
  liveExecutionEnabled:false,
  providerRequestsMade:0,
  brokerOrdersSent:0,
  paperOrdersSent:0,
  signal:"WAIT",
  executable:false
 });
}
module.exports={inspect,IDS};
