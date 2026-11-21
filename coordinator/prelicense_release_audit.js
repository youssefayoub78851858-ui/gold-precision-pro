"use strict";
/**
 * Pure final pre-license decision board. The internal integration verdict
 * comes from existing local checks; CI success is NOT asserted by a server.
 * This NEVER enables a source, BUY/SELL, paper orders, or live orders.
 * External evidence is not supplied to this module and always remains absent.
 */
const CHECKS=Object.freeze([
 "sourceRequirements","closedFrameCapacity","candleChronology",
 "externalContextClocks","paperCostHoldout","frozenResearchAndShadow"
]);
const REQUIRED=Object.freeze([
 "WRITTEN_PRIVATE_CLOUD_AND_STORAGE_DATA_RIGHTS",
 "BROKER_BID_ASK_AND_CLOSED_M15_H1_H4_NATIVE_SESSION_VERIFICATION",
 "LICENSED_DXY_GC_TRADE_DEPTH_AND_ORDERFLOW_PLUS_MACRO_COVERAGE",
 "UNTOUCHED_FORWARD_PAPER_HOLDOUT_WITH_BROKER_COST_EVIDENCE"
]);
function assess(handoff){
 const obj=handoff&&typeof handoff==="object"&&!Array.isArray(handoff)?handoff:{};
 const checks=obj.checks;
 const passes=obj.mode==="GOLD_INTERNAL_OFFLINE_HANDOFF_V1"&&
   obj.status==="OFFLINE_INTERFACES_CHECKED_EXTERNAL_EVIDENCE_PENDING"&&
   obj.internalOfflineContractsChecked===true&&obj.internalCheckCount===6&&
   obj.signal==="WAIT"&&obj.executable===false&&
   obj.paperOrdersAllowed===false&&obj.liveOrdersAllowed===false&&
   obj.providerConnectionEnabled===false&&obj.providerRequestsMade===0&&
   obj.brokerOrdersSent===0&&obj.paperOrdersSent===0&&
   obj.credentialsRead===0&&obj.paymentsMade===0&&
   obj.independentSourceRightsVerified===false&&
   obj.independentHoldoutValidated===false&&
   obj.realMarketPriceAvailable===false&&
   obj.externalProviderDecisionDeferredToLastStage===true&&
   obj.readyForBuySell!==true&&obj.readyForPaperExecution!==true&&
   obj.readyForLiveExecution!==true&&
   obj.signalCandidate===null&&obj.entry===null&&
   obj.stopLoss===null&&obj.targets===null&&
   obj.stageStatus?.finalProvider==="DEFERRED_NOT_CONNECTED"&&
   !!checks&&typeof checks==="object"&&!Array.isArray(checks)&&
   Object.keys(checks).sort().join(",")===CHECKS.slice().sort().join(",")&&
   CHECKS.every(k=>checks[k]==="OFFLINE_CONTRACT_COMPATIBLE")&&
   Array.isArray(obj.finalExternalEvidenceRequired)&&
   obj.finalExternalEvidenceRequired.length===REQUIRED.length&&
   REQUIRED.every((x,i)=>obj.finalExternalEvidenceRequired[i]===x);
 return {
  mode:"GOLD_PRELICENSE_RELEASE_AUDIT_V1",
  status:passes?"LOCAL_INTEGRATION_CONTRACTS_VALIDATED_ONLY":
                "INTERNAL_INTEGRATION_RECHECK_REQUIRED",
  internalSoftwareContractsChecked:passes?CHECKS.length:0,
  internalSoftwareContractsExpected:CHECKS.length,
  actualCIPassAttestedByRuntime:false,
  prelicenseOperationalDrillAttestedByRuntime:false,
  externalEvidenceVerifiedCount:0,
  externalEvidenceRequiredCount:REQUIRED.length,
  externalEvidenceRequired:REQUIRED.map(id=>({
   id,status:"EXTERNAL_EVIDENCE_NOT_AVAILABLE_HERE"
  })),
  providerChoiceDeferredUntilFinalStage:true,
  providerChosenOrConnected:false,
  paperForwardResultsVerified:false,
  actualBrokerTransactionCostsVerified:false,
  readyForBuySell:false,
  marketDataMayBeActivated:false,
  readyForPaperExecution:false,
  readyForLiveExecution:false,
  allPrelicenseWorkProvenComplete:false,
  allTradePrerequisitesSatisfied:false,
  signal:"WAIT",executable:false,
  paperOrdersAllowed:false,liveOrdersAllowed:false,
  providerRequestsMade:0,brokerOrdersSent:0,paperOrdersSent:0,
  marketPricesReturned:false,credentialsReturned:false,
  note:"Local interface checks are not GitHub CI proof, licensed feed proof, or profitability proof."
 };
}
module.exports={assess};
