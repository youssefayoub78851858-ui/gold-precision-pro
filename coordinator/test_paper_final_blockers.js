"use strict";
const a=require("node:assert/strict");
const {inspect:internal}=require("./internal_offline_handoff");
const {inspect,IDS}=require("./paper_final_blockers");
const {wait}=require("./paper_startup_recovery_gate");
const ready=internal();
const verify=r=>{
 a.equal(r.mode,"GOLD_PAPER_READINESS_BLOCKERS_V1");
 a.equal(r.signal,"WAIT");a.equal(r.executable,false);
 a.equal(r.readyForBuySell,false);
 a.equal(r.readyForPaperExecution,false);
 a.equal(r.liveExecutionEnabled,false);
 a.equal(r.automaticPaperLoggingEnabled,false);
 a.equal(r.actualGitHubCIPassAttestedByRuntime,false);
 a.equal(r.reviewServiceDeploymentAttested,false);
 a.equal(r.paperResultsStatisticallyValidated,false);
 a.equal(r.nextM15ForecastAccuracyPct,null);
 a.equal(r.providerRequestsMade,0);
 a.equal(r.brokerOrdersSent,0);
 a.equal(r.paperOrdersSent,0);
 a.equal(r.requirements.length,5);
 a.deepEqual(r.requirements.map(x=>x.id),IDS);
 a.equal(r.externallyVerifiedCount,0);
 for(const x of r.requirements){
  a(["NOT_EXTERNALLY_VERIFIED",
     "DURABLE_STORAGE_AND_CHECKPOINT_NOT_VERIFIED",
     "LOCAL_CHECKPOINT_ONLY_OFFSITE_NOT_PROVEN"].includes(x.status));
 }
 for(const x of ["apiKey","cookie","authToken","sourcePrice","customerEmail"]){
  a(!JSON.stringify(r).includes(x));
 }
};
const noDisk=inspect(ready,wait("NO_PERSISTENT_PAPER_JOURNAL_CONFIGURED"));
verify(noDisk);
a.equal(noDisk.status,"EXTERNAL_PREREQUISITES_PENDING");
a.equal(noDisk.locallyCheckedCount,0);
a.equal(noDisk.requirements[0].status,
 "DURABLE_STORAGE_AND_CHECKPOINT_NOT_VERIFIED");
const validGate={...wait("STARTUP_LOCAL_CHECKPOINT_READ_ONLY_VERIFIED"),
 checkpointSafe:true,paperResultsDisplayAllowed:true};
const stored=inspect(ready,validGate);
verify(stored);
a.equal(stored.locallyCheckedCount,1);
a.equal(stored.requirements[0].status,
 "LOCAL_CHECKPOINT_ONLY_OFFSITE_NOT_PROVEN");
a.equal(stored.licensedXauusdFeedReady,false);
a.equal(stored.historicalM15H1H4ParityReady,false);
a.equal(stored.externalMacroOrderflowReady,false);
a.equal(stored.independentPaperHoldoutReady,false);
for(const fake of [
 {...validGate,liveOrdersAllowed:true},
 {...validGate,signal:"BUY"},
 {...validGate,executable:true},
 {...validGate,backupOffsiteVerified:true},
 {...validGate,marketDataConnected:true},
 {...validGate,providerRequestsMade:1},
 {...validGate,checkpointSafe:false},
 {...validGate,status:"READY"},
]){
 const test=inspect(ready,fake);verify(test);
 a.equal(test.locallyCheckedCount,0);
}
for(const altered of [
 {...ready,signal:"BUY"},
 {...ready,executable:true},
 {...ready,realMarketPriceAvailable:true},
 {...ready,providerRequestsMade:1},
 {...ready,releaseAudit:{...ready.releaseAudit,readyForBuySell:true}},
 null,{},false,
]){
 const test=inspect(altered,validGate);verify(test);
 a.equal(test.status,"INTERNAL_EVIDENCE_RECHECK_REQUIRED");
 a.equal(test.locallyCheckedCount,0);
}
console.log("PASS five explicit runtime blockers, zero live entitlement, no forged CI/disk/trading readiness");
