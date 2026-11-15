'use strict';
// Prospective candidate-level, AFTER-COST paired audit. Does NOT create
// signals; given a COMPLETE predeclared baseline candidate universe, computes
// fixed shadow selection from inputs asserted available at decision time.
// Input provenance/rights cannot be established by user-supplied metadata.
// The frozen V3 engine is not modified, fetched or executed by this module.
const crypto=require('node:crypto');
const RULES='GPP_FROZEN_V3_QUALITY_SHADOW_V1_2026_11_15';
const MAX_ROWS=5000;
const REQUIRED_CONTEXT=[
 'regime','directionConfirmedM15H1H4','liquidityConfirmedBeforeSignal',
 'volatilityShock','highImpactEventWindow','dxyConsistent','gcConsistent',
 'orderFlowConsistent','gcContractMatched','referenceSession',
 'verifiedSessionCalendar','netRewardRiskAtSignal',
 'featuresAvailableUTC','sourceEvidenceAvailableUTC'];
const DECISION_CODES=Object.freeze([
 'NOT_DIRECTIONAL','MTF_NOT_CONFIRMED','LIQUIDITY_NOT_CONFIRMED',
 'VOLATILITY_SHOCK','HIGH_IMPACT_NEWS','DXY_CONFLICT','GC_CONFLICT',
 'ORDER_FLOW_CONFLICT','GC_CONTRACT_MISMATCH',
 'REFERENCE_SESSION_EXCLUDED','BROKER_SESSION_UNVERIFIED',
 'COST_ADJUSTED_RR_LOW']);
function bad(reason){throw Error('PAIRED_AUDIT_REJECTED_'+reason);}
function ms(value){
 if(typeof value!=='string'||! /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(value))
  return NaN;
 const t=Date.parse(value);
 return Number.isFinite(t)&&new Date(t).toISOString().slice(0,19)===value.slice(0,19)?t:NaN;
}
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const sum=(a,b)=>a+b;
const rnd=x=>Math.round(x*1000000)/1000000;
function selection(f){
 if(!f||Object.keys(f).sort().join(',')!==[...REQUIRED_CONTEXT].sort().join(','))
  bad('FEATURE_SCHEMA_MISMATCH');
 const codes=[];
 const push=(yes,code)=>{if(yes)codes.push(code);};
 if(!['DIRECTIONAL','MIXED','CHOPPY'].includes(f.regime))bad('REGIME_UNKNOWN');
 if(!['LONDON','NEW_YORK','OVERLAP','ASIA_OR_OFF_HOURS'].includes(f.referenceSession))
  bad('REFERENCE_SESSION_UNKNOWN');
 if(!Number.isFinite(ms(f.featuresAvailableUTC))||
    !Array.isArray(f.sourceEvidenceAvailableUTC)||f.sourceEvidenceAvailableUTC.length!==5||
    f.sourceEvidenceAvailableUTC.some(t=>!Number.isFinite(ms(t))))
  bad('AS_OF_FEATURE_PROVENANCE_MISSING');
 for(const k of ['directionConfirmedM15H1H4','liquidityConfirmedBeforeSignal',
   'volatilityShock','highImpactEventWindow','dxyConsistent','gcConsistent',
   'orderFlowConsistent','gcContractMatched','verifiedSessionCalendar'])
  if(typeof f[k]!=='boolean')bad('FEATURE_TYPE_MISMATCH');
 if(!finite(f.netRewardRiskAtSignal)||f.netRewardRiskAtSignal < -100||
    f.netRewardRiskAtSignal>100)bad('PRECOMPUTED_NET_RR_INVALID');
 push(f.regime!=='DIRECTIONAL','NOT_DIRECTIONAL');
 push(!f.directionConfirmedM15H1H4,'MTF_NOT_CONFIRMED');
 push(!f.liquidityConfirmedBeforeSignal,'LIQUIDITY_NOT_CONFIRMED');
 push(f.volatilityShock,'VOLATILITY_SHOCK');
 push(f.highImpactEventWindow,'HIGH_IMPACT_NEWS');
 push(!f.dxyConsistent,'DXY_CONFLICT');
 push(!f.gcConsistent,'GC_CONFLICT');
 push(!f.orderFlowConsistent,'ORDER_FLOW_CONFLICT');
 push(!f.gcContractMatched,'GC_CONTRACT_MISMATCH');
 push(f.referenceSession==='ASIA_OR_OFF_HOURS','REFERENCE_SESSION_EXCLUDED');
 push(!f.verifiedSessionCalendar,'BROKER_SESSION_UNVERIFIED');
 push(f.netRewardRiskAtSignal<1.5,'COST_ADJUSTED_RR_LOW');
 return codes;
}
function metrics(rows){
 let sumR=0,peak=0,maxDD=0,wins=0,gains=0,losses=0,gross=0,costs=0;
 // Independent closed-trade ordering; overlapping trades are not modeled as
 // a reinvested portfolio. Drawdown is descriptive R by exit event.
 const sorted=[...rows].sort((a,b)=>ms(a.exitUTC)-ms(b.exitUTC)||a.id.localeCompare(b.id));
 for(const r of sorted){
  gross+=r.grossR;
  const cost=r.costs.spreadR+r.costs.slippageR+r.costs.commissionR;
  costs+=cost;
  const net=r.grossR-cost;
  sumR+=net;peak=Math.max(peak,sumR);maxDD=Math.max(maxDD,peak-sumR);
  if(net>0){wins++;gains+=net;}else if(net<0){losses+=-net;}
 }
 const n=rows.length;
 return {
  candidates:n,winCount:wins,winRatePercent:n?rnd(100*wins/n):null,
  grossR:rnd(gross),roundTripCostR:rnd(costs),netR:rnd(sumR),
  meanNetR:n?rnd(sumR/n):null,maxDrawdownR:rnd(maxDD),
  profitFactor:losses>0?rnd(gains/losses):null,
  overlappingTradesAndPortfolioRiskNotModeled:true,
  brokerExecutionIndependentlyVerified:false
 };
}
function audit(doc){
 if(!doc||typeof doc!=='object'||Array.isArray(doc)||
    !['SYNTHETIC_TEST_ONLY','LOCAL_RECORDED_RESEARCH_UNVERIFIED'].includes(doc.dataOrigin))
  bad('EXPLICIT_ORIGIN_REQUIRED');
 const meta=doc.manifest;
 if(!meta||meta.rules!==RULES||meta.frozenEngine!=='V3 Ultimate'||
    !Number.isInteger(meta.expectedCandidateCount)||meta.expectedCandidateCount<0||
    typeof meta.sourceDescription!=='string'||!meta.sourceDescription.trim()||
    typeof meta.candidatesSHA256!=='string'||!/^[a-f0-9]{64}$/.test(meta.candidatesSHA256))
  bad('FROZEN_PLAN_AND_HASH_MANIFEST_MISSING');
 const freeze=ms(meta.filterFrozenUTC),start=ms(meta.holdoutStartUTC),
 end=ms(meta.holdoutEndUTC),asOf=ms(meta.asOfUTC);
 if(![freeze,start,end,asOf].every(Number.isFinite)||freeze>start||
    start>=end||end>asOf)bad('FROZEN_HOLDOUT_WINDOW_INVALID');
 if(!Array.isArray(doc.candidates)||doc.candidates.length>MAX_ROWS||
    doc.candidates.length!==meta.expectedCandidateCount)
  bad('BASELINE_CANDIDATE_UNIVERSE_COUNT_MISMATCH');
 const digest=crypto.createHash('sha256').update(JSON.stringify(doc.candidates)).digest('hex');
 if(digest!==meta.candidatesSHA256)bad('BASELINE_CANDIDATE_SET_CHANGED');
 const accepted=[],denied=[],reasons={},ids=new Set();let lastSignal=-Infinity;
 for(const row of doc.candidates){
  if(!row||Object.keys(row).sort().join(',')!==
      ['id','signalUTC','entryUTC','exitUTC','side','grossR','costs','atSignal'].sort().join(',')||
     typeof row.id!=='string'||!row.id||row.id.length>128||ids.has(row.id))
   bad('CANDIDATE_ID_OR_SCHEMA_INVALID');
  ids.add(row.id);
  const signal=ms(row.signalUTC),entry=ms(row.entryUTC),exit=ms(row.exitUTC);
  if(![signal,entry,exit].every(Number.isFinite)||signal<=lastSignal||
     signal<start||signal>=end||signal<freeze||entry<=signal||exit<=entry||
     exit>asOf||signal%900000!==0)
   bad('CANDIDATE_TIMELINE_OR_M15_ALIGNMENT_INVALID');
  lastSignal=signal;
  if(!['BUY','SELL'].includes(row.side)||!finite(row.grossR)||Math.abs(row.grossR)>100||
      !row.costs||Object.keys(row.costs).sort().join(',')!=='commissionR,slippageR,spreadR'||
      Object.values(row.costs).some(x=>!finite(x)||x<0||x>50))
   bad('BROKER_COST_OR_GROSS_OUTCOME_INVALID');
  const sumCosts=Object.values(row.costs).reduce(sum,0);
  if(!Number.isFinite(row.grossR-sumCosts))bad('NET_OUTCOME_OVERFLOW');
  const f=row.atSignal,blocked=selection(f);
  if(ms(f.featuresAvailableUTC)>signal||f.sourceEvidenceAvailableUTC.some(t=>ms(t)>signal))
   bad('FUTURE_FEATURE_OR_SOURCE_REVEALED_BEFORE_SIGNAL');
  if(blocked.length===0)accepted.push(row);
  else {denied.push(row);for(const code of blocked)reasons[code]=(reasons[code]||0)+1;}
 }
 const baseline=metrics(doc.candidates),after=metrics(accepted);
 return {
  mode:'OFFLINE_PAIRED_QUALITY_FILTER_AUDIT',dataOrigin:doc.dataOrigin,
  rules:meta.rules,sourceDescription:meta.sourceDescription,
  manifestCandidateHash:meta.candidatesSHA256,
  window:{frozenUTC:meta.filterFrozenUTC,startUTC:meta.holdoutStartUTC,
   endUTC:meta.holdoutEndUTC,asOfUTC:meta.asOfUTC},
  baseline,shadowFiltered:after,
  suppressedCandidates:denied.length,blockingCodeCounts:reasons,
  deltaNetR: rnd(after.netR-baseline.netR),
  netPerformanceImprovementProven:false,
  statisticalSignificanceEstablished:false,
  candidateUniverseCompletenessIndependentlyVerified:false,
  decisionTimeFeaturesIndependentlyAttested:false,
  dataLicensingIndependentlyVerified:false,
  identicalFrozenCandidateSetIndependentlyRegenerated:false,
  thresholdOptimizationPerformed:false,
  signal:'WAIT',executable:false,researchEligible:false,paperOrdersAllowed:false,
  providerRequestsMade:0,ordersSent:0,
  warning:'Paired candidate arithmetic only; user-supplied source, filter feature timestamp, costs and complete baseline universe require external audit. This does NOT establish profitability or live trading reliability.'
 };
}
module.exports={RULES,DECISION_CODES,audit};
if(require.main===module){
 try{
  const fs=require('node:fs'),file=process.argv[2];
  if(!file)bad('LOCAL_JSON_FILE_REQUIRED');
  const stat=fs.lstatSync(file);
  if(!stat.isFile()||stat.isSymbolicLink()||stat.size>15000000)bad('UNSAFE_OR_OVERSIZE_FILE');
  process.stdout.write(JSON.stringify(audit(JSON.parse(fs.readFileSync(file,'utf8'))),null,2)+'\n');
 }catch(e){console.error(e.message.startsWith('PAIRED_AUDIT_REJECTED_')?e.message:'PAIRED_AUDIT_INPUT_INVALID');process.exitCode=1;}
}
