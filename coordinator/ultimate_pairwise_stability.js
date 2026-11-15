'use strict';
// Descriptive chronological stability check on a fixed, hash-locked paired
// candidate set. This is not bootstrap validation, significance or a strategy.
const {audit}=require('./ultimate_filter_pairwise_audit');
const MS=Date.parse;
function inspect(doc){
 const full=audit(doc);
 const n=doc.candidates.length;
 const first=doc.candidates.slice(0,Math.floor(n/2));
 const second=doc.candidates.slice(Math.floor(n/2));
 const cuts=[['FIRST_HALF',first],['SECOND_HALF',second]];
 const panels=cuts.map(([label,rows])=>{
  // The hash and universe for each half are NOT independent prospective
  // freezes. We only partition the already validated original candidate set.
  let retained=0,suppressed=0;
  let baseNet=0,keptNet=0;
  for(const row of rows){
   const costs=row.costs.spreadR+row.costs.slippageR+row.costs.commissionR;
   const net=row.grossR-costs;
   baseNet+=net;
   // Selection is re-evaluated by the original audit with a distinct
   // correctly hashed manifest. Never rewrite the frozen source candidate.
   const crypto=require('node:crypto');
   const slice={...doc,candidates:[row],manifest:{...doc.manifest,
    expectedCandidateCount:1,
    candidatesSHA256:crypto.createHash('sha256').update(JSON.stringify([row])).digest('hex')}};
   const part=audit(slice);
   if(part.shadowFiltered.candidates===1){retained++;keptNet+=net;}
   else suppressed++;
  }
  return {partition:label,candidates:rows.length,retained,suppressed,
   baselineNetR:Number(baseNet.toFixed(6)),
   shadowNetR:Number(keptNet.toFixed(6)),
   deltaNetR:Number((keptNet-baseNet).toFixed(6)),
   validIndependentHoldout:false,
   sampleSufficientForPerformanceClaims:false};
 });
 const anySmall=panels.some(x=>x.candidates<100||x.retained<30);
 const bothImproved=panels.every(x=>x.candidates>0&&x.deltaNetR>0);
 return {mode:'OFFLINE_FIXED_HOLDOUT_STABILITY_DIAGNOSTIC',
  rules:full.rules,candidateHash:full.manifestCandidateHash,
  originalCandidateCount:n,panels,
  descriptiveSameDirectionOfDelta:bothImproved,
  smallSampleOrSelectionWarning:anySmall,
  independentDataAndLicensingVerified:false,
  independentProspectiveReplication:false,
  statisticalSignificanceEstablished:false,
  netPerformanceImprovementProven:false,
  empiricalWinProbability:null,
  signal:'WAIT',executable:false,paperOrdersAllowed:false,
  providerRequestsMade:0,ordersSent:0,
  warning:'Chronological partitions of one frozen candidate universe; no independent test, statistical power, execution verification or claim of improved gold signals.'};
}
module.exports={inspect};
