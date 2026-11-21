"use strict";
// One real offline integration exercise for six existing codepaths.
// No provider fetches, account access, external credentials or trades.
const a=require("node:assert/strict");
const {inspect,combine,collectOfflineReports}=require("./internal_offline_handoff");
function safe(r){
 a.equal(r.signal,"WAIT");a.equal(r.executable,false);
 a.equal(r.paperOrdersAllowed,false);a.equal(r.liveOrdersAllowed,false);
 a.equal(r.providerRequestsMade,0);a.equal(r.brokerOrdersSent,0);
 a.equal(r.paperOrdersSent,0);a.equal(r.credentialsRead,0);
 a.equal(r.paymentsMade,0);
 a.equal(r.providerConnectionEnabled,false);
 a.equal(r.independentSourceRightsVerified,false);
 a.equal(r.independentHoldoutValidated,false);
 a.equal(r.realMarketPriceAvailable,false);
 a.equal(r.externalProviderDecisionDeferredToLastStage,true);
 a.equal(r.signalCandidate,null);a.equal(r.entry,null);a.equal(r.stopLoss,null);
 a.equal(r.targets,null);
 a.equal(JSON.stringify(r).includes("SYNTHETIC_TEST_ONLY"),false);
 a.equal(JSON.stringify(r).includes("CST"),false);
 a.equal(JSON.stringify(r).includes("apiKey"),false);
}
const x=inspect();safe(x);
a.equal(x.mode,"GOLD_INTERNAL_OFFLINE_HANDOFF_V1");
a.equal(x.status,"OFFLINE_INTERFACES_CHECKED_EXTERNAL_EVIDENCE_PENDING");
a.equal(x.internalOfflineContractsChecked,true);
a.equal(x.internalCheckCount,6);
a.equal(x.releaseAudit.mode,"GOLD_PRELICENSE_RELEASE_AUDIT_V1");
a.equal(x.releaseAudit.status,"LOCAL_INTEGRATION_CONTRACTS_VALIDATED_ONLY");
a.equal(x.releaseAudit.internalSoftwareContractsChecked,6);
a.equal(x.releaseAudit.actualCIPassAttestedByRuntime,false);
a.equal(x.releaseAudit.prelicenseOperationalDrillAttestedByRuntime,false);
a.equal(x.releaseAudit.externalEvidenceVerifiedCount,0);
a.equal(x.releaseAudit.externalEvidenceRequiredCount,4);
a.equal(x.releaseAudit.externalEvidenceRequired.length,4);
a.equal(x.releaseAudit.readyForBuySell,false);
a.equal(x.releaseAudit.marketDataMayBeActivated,false);
a.equal(x.releaseAudit.readyForPaperExecution,false);
a.equal(x.releaseAudit.readyForLiveExecution,false);
a.equal(x.releaseAudit.signal,"WAIT");
a.equal(x.releaseAudit.executable,false);
a.equal(Object.keys(x.checks).length,6);
a(Object.values(x.checks).every(v=>v==="OFFLINE_CONTRACT_COMPATIBLE"));
a.equal(x.stageStatus.finalProvider,"DEFERRED_NOT_CONNECTED");
a.equal(x.finalExternalEvidenceRequired.length,4);
a.equal(x.warning.includes("not successful CI"),true);
const genuine=collectOfflineReports();
a.equal(genuine.sources.providerRequestsMade,0);
a.equal(genuine.signalEngine.signal,"WAIT");
a.equal(genuine.signalEngine.executable,false);
a.equal(genuine.signalEngine.paperOrdersAllowed,false);
a.equal(genuine.paperTerminal.mode,"OFFLINE_SYNTHETIC_REPLAY");
a.equal(genuine.paperTerminal.frameCounts.M15,512);
a.equal(genuine.paperTerminal.frameCounts.H4,32);
a.equal(genuine.paperTerminal.signal,"WAIT");
a.equal(genuine.paperTerminal.paperExecutionOnServer,false);
a.equal(genuine.paperTerminal.ordersSent,0);
// Mutating any one internal integration contract NEVER upgrades the output
// and cannot make the UI claim a live quote or permission to order.
const mutations=[
 ["sources",r=>r.steps.capitalDemo.privateCloudStorageApproved=true],
 ["sources",r=>r.providerRequestsMade=1],
 ["history",r=>r.singleSnapshotCanProve21H4M15Parity=true],
 ["history",r=>r.archiveCurrentlyVerified=true],
 ["chronology",r=>r.completedStages=4],
 ["chronology",r=>r.stages[0].complete=true],
 ["context",r=>r.allLayersQualified=true],
 ["paper",r=>r.executable=true],
 ["paper",r=>r.profitabilityProven=true],
 ["paperTerminal",r=>r.executable=true],
 ["paperTerminal",r=>r.paperExecutionOnServer=true],
 ["paperTerminal",r=>r.providerRequests=1],
 ["paperTerminal",r=>r.frameCounts.H4=1],
 ["signalEngine",r=>r.paperOrdersAllowed=true],
 ["signalEngine",r=>r.stages.validation.deploymentAdmissible=true],
 ["signalEngine",r=>r.stages.analysis.status="NOT_INVOKED"]
];
for(const [name,mutate] of mutations){
 const spoof=structuredClone(genuine);mutate(spoof[name]);
 const r=combine(spoof);safe(r);
 a.equal(r.status,"OFFLINE_INTEGRATION_CONTRACT_FAILED",name);
 a.equal(r.internalOfflineContractsChecked,false,name);
 a.equal(r.releaseAudit.status,"INTERNAL_INTEGRATION_RECHECK_REQUIRED",name);
 a.equal(r.releaseAudit.internalSoftwareContractsChecked,0,name);
 a.equal(r.releaseAudit.externalEvidenceVerifiedCount,0,name);
 a.equal(r.releaseAudit.readyForBuySell,false,name);
 a(Object.values(r.checks).includes("BLOCKED_CONTRACT_UNVERIFIED"),name);
}
for(const v of [null,{},[],{signal:"BUY"},true]){
 const y=combine(v);safe(y);
 a.equal(y.internalOfflineContractsChecked,false);
 a.equal(y.releaseAudit.internalSoftwareContractsChecked,0);
 a.equal(y.releaseAudit.readyForBuySell,false);
}
console.log("PASS unified offline XAUUSD readiness, V3 signal, macro clocks and paper holdout; no provider/payments/trading");
