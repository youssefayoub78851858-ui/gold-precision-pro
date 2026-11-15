'use strict';
// Independent optional quality review of the FROZEN V3 Ultimate research engine.
// No changes to frozen strategy decisions, trade-plan mechanics or admission.
// Caller supplies already-available closed candles and evidence; no network.
const {evaluate}=require('./v3_ultimate');
const {diagnostic}=require('./ultimate_signal_quality');
function review(input){
  const base=evaluate(input);
  const qualityDiagnostics=diagnostic(input.frames,input.asOfUTC,base.tradePlan,input.risk,base.layers);
  return {
    mode:'OFFLINE_INDEPENDENT_RESEARCH_REVIEW',
    asOfUTC:base.asOfUTC,
    sourceEngine:base.engine,
    sourceVersion:base.version,
    sourceResearchCandidate:base.researchCandidate,
    technicalCandidate:base.technical?.candidate||'NONE',
    qualityDiagnostics,
    sourceBlockers:[...base.monitoring.blocked],
    signal:'WAIT',executable:false,paperOrdersAllowed:false,
    strategyChanged:false,providerRequestsMade:0,
    reason:'Diagnostics only. Not tested for predictive benefit or authorized for trading.'
  };
}
module.exports={review};
if(require.main===module){
  try{
    const fs=require('node:fs');
    process.stdout.write(JSON.stringify(review(JSON.parse(fs.readFileSync(process.argv[2]||0,'utf8'))),null,2)+'\n');
  }catch(e){console.error(e.message);process.exitCode=1;}
}
