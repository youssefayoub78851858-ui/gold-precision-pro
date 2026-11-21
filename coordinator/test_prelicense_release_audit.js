"use strict";
const assert=require("node:assert/strict");
const {assess}=require("./prelicense_release_audit");
const {inspect}=require("./internal_offline_handoff");
const {validateInternalHandoff}=require("../review-dashboard");
const actual=inspect(),r=assess(actual);
assert.equal(r.mode,"GOLD_PRELICENSE_RELEASE_AUDIT_V1");
assert.equal(r.status,"LOCAL_INTEGRATION_CONTRACTS_VALIDATED_ONLY");
assert.equal(r.internalSoftwareContractsChecked,6);
assert.equal(r.externalEvidenceVerifiedCount,0);
assert.equal(r.actualCIPassAttestedByRuntime,false);
assert.equal(r.prelicenseOperationalDrillAttestedByRuntime,false);
assert.equal(r.readyForBuySell,false);
assert.equal(r.readyForPaperExecution,false);
assert.equal(r.readyForLiveExecution,false);
assert.equal(r.providerChoiceDeferredUntilFinalStage,true);
assert.equal(r.signal,"WAIT");assert.equal(r.executable,false);
assert.deepEqual(validateInternalHandoff(actual),{
  internalOfflineContractsChecked:true,signal:"WAIT",tradeReady:false
});
for(const spoof of [
 {...actual,releaseAudit:{...actual.releaseAudit,readyForBuySell:true}},
 {...actual,releaseAudit:{...actual.releaseAudit,externalEvidenceVerifiedCount:4}},
 {...actual,releaseAudit:{...actual.releaseAudit,actualCIPassAttestedByRuntime:true}},
 {...actual,releaseAudit:{...actual.releaseAudit,providerChosenOrConnected:true}},
 {...actual,releaseAudit:{...actual.releaseAudit,readyForPaperExecution:true}},
 {...actual,releaseAudit:{...actual.releaseAudit,externalEvidenceRequired:[]}}
]){
 assert.equal(validateInternalHandoff(spoof),null);
}
// Even forged 'full approval' flags supplied by an arbitrary caller cannot
// override immutable external blockers or the WAIT disposition.
for(const fake of [
 {...actual,readyForBuySell:true},
 {...actual,providerConnectionEnabled:true},
 {...actual,externalProviderDecisionDeferredToLastStage:false},
 null,{},[],{signal:"BUY",executable:true}
]){
 const v=assess(fake);
 assert.equal(v.status,"INTERNAL_INTEGRATION_RECHECK_REQUIRED");
 assert.equal(v.internalSoftwareContractsChecked,0);
 assert.equal(v.externalEvidenceVerifiedCount,0);
 assert.equal(v.signal,"WAIT");
 assert.equal(v.executable,false);
 assert.equal(v.readyForBuySell,false);
 assert.equal(v.readyForLiveExecution,false);
}
assert(!JSON.stringify(r).includes("CST"));
assert(!JSON.stringify(r).includes("apiKey"));
console.log("PASS prelicense release audit: local 6/6, external 0/4, no false approval");
