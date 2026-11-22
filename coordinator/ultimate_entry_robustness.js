'use strict';
/**
 * Independent, OFFLINE entry-cost/false-break robustness diagnostic.
 *
 * Evaluates the frozen V3 candidate; NEVER changes it or authorizes a
 * signal/paper/live order. No real broker-cost validation, network or
 * empirical win probability. Ratios are hypothesis screens only.
 */
const {checkFrame}=require('./v3_multitimeframe');
const STRESS=Object.freeze([1,1.5,2]);
const THRESHOLDS=Object.freeze({
  exploratoryMinStressRR:1.5,
  oppositeWickFraction:0.45,
  entryDistancePriorATR:0.75,
  atrLookback:14,
});
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const round=x=>finite(x)?Math.round(x*100000)/100000:null;
function base(reason){
 return {
  mode:'OFFLINE_ENTRY_ROBUSTNESS_STRESS_V1',
  status:'INSUFFICIENT_EVIDENCE',
  reason,
  candidateObserved:'NONE',
  postCostRiskQuality:'UNAVAILABLE',
  exploratoryWarnings:[],
  scenarios:[],
  metrics:{},
  stressMultipliers:STRESS,
  empiricalWinProbability:null,
  confidencePercent:null,
  thresholdsFixedNotOptimized:true,
  brokerCostsIndependentlyVerified:false,
  providerMarketDataRightsVerified:false,
  brokerFillsAndStopsVerified:false,
  forwardProfitabilityEstablished:false,
  effectOnFrozenCandidate:'NONE',
  tradePlanChanged:false,
  signal:'WAIT',executable:false,paperOrdersAllowed:false,
  liveOrdersAllowed:false,providerRequestsMade:0,ordersSent:0
 };
}
function inspect(snapshot,candidate,tradePlan,risk){
 const out=base('VALID_CLOSED_DATA_AND_BROKER_COSTS_REQUIRED');
 if(!['BUY','SELL'].includes(candidate))return out;
 out.candidateObserved=candidate;
 const asOf=snapshot?.asOfUTC;
 const now=typeof asOf==='string'&&/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(asOf)
  ?Date.parse(asOf):NaN;
 if(!finite(now)||new Date(now).toISOString().slice(0,19)!==asOf.slice(0,19))
  return {...out,reason:'EXPLICIT_UTC_DECISION_TIME_REQUIRED'};
 const frames=snapshot.frames;
 for(const [tf,width] of [['M15',15],['H1',60],['H4',240]]){
  const check=checkFrame(frames?.[tf],width,now);
  if(!check.ok)return {...out,reason:tf+'_INVALID_OR_STALE_CLOSED_CANDLES'};
 }
 const candles=frames.M15, last=candles.at(-1);
 if(candles.length<THRESHOLDS.atrLookback+2)
  return {...out,reason:'PRIOR_ATR_WARMUP_MISSING'};
 const prior=candles.slice(-THRESHOLDS.atrLookback-1,-1);
 const trs=prior.map((bar,i)=>{
  const predecessor=candles[candles.length-prior.length-2+i];
  const prevClose=predecessor.close;
  return Math.max(bar.high-bar.low,Math.abs(bar.high-prevClose),
                  Math.abs(bar.low-prevClose));
 });
 const atr=trs.reduce((a,c)=>a+c,0)/trs.length;
 if(!finite(atr)||atr<=0)return {...out,reason:'PRIOR_ATR_INVALID'};
 const numbers=[
  tradePlan?.entry,tradePlan?.stop,tradePlan?.target,tradePlan?.spread,
  risk?.slippage,risk?.valuePerPoint,risk?.commissionPerLot
 ];
 const [entry,stop,target,spread,slippage,valuePerPoint,commission]=numbers;
 const sign=candidate==='BUY'?1:-1;
 if(!numbers.every(finite)||entry<=0||stop<=0||target<=0||
    spread<0||slippage<0||valuePerPoint<=0||commission<0||
    sign*(entry-stop)<=0||sign*(target-entry)<=0)
  return {...out,reason:'DIRECTIONAL_PLAN_OR_BROKER_COST_ASSUMPTIONS_INVALID'};
 const reward=sign*(target-entry),loss=sign*(entry-stop);
 const warnings=[];
 const bodyDir=last.close>last.open?'UP':last.close<last.open?'DOWN':'FLAT';
 const lastRange=last.high-last.low;
 const opposingWick=sign===1?last.high-Math.max(last.close,last.open):
   Math.min(last.close,last.open)-last.low;
 const wickFraction=lastRange>0?opposingWick/lastRange:0;
 if(bodyDir!==(sign===1?'UP':'DOWN'))
  warnings.push('LAST_CLOSED_M15_CANDLE_NOT_IN_CANDIDATE_DIRECTION');
 if(wickFraction>=THRESHOLDS.oppositeWickFraction)
  warnings.push('OPPOSING_M15_WICK_HIGH_FRACTION');
 // Entry far from most recently observed close risks chasing a move.
 const entryDistanceATR=Math.abs(entry-last.close)/atr;
 if(entryDistanceATR>THRESHOLDS.entryDistancePriorATR)
  warnings.push('ENTRY_TOO_FAR_FROM_LAST_M15_CLOSE_VS_PRIOR_ATR');
 const scenarios=STRESS.map(multiplier=>{
  const roundTripCost=multiplier*(spread+slippage)+commission/valuePerPoint;
  const netReward=reward-roundTripCost,netLoss=loss+roundTripCost;
  return {
   spreadAndSlippageMultiplier:multiplier,
   netRewardRisk:round(netReward/netLoss),
   breakEvenWinRatePercent:netReward>0?round(100*netLoss/(netReward+netLoss)):null,
   profitableAtFullTargetUnderAssumptions:netReward>0
  };
 });
 if(scenarios.some(x=>x.netRewardRisk<THRESHOLDS.exploratoryMinStressRR))
  warnings.push('COST_STRESS_RR_BELOW_EXPLORATORY_FLOOR');
 if(scenarios.some(x=>x.profitableAtFullTargetUnderAssumptions===false))
  warnings.push('COST_STRESS_ERASES_GROSS_REWARD');
 const fragile=warnings.length>0;
 return {
  ...out,status:'STRESS_DIAGNOSTIC_ONLY',
  reason:'COSTS_UNVERIFIED_NO_EMPIRICAL_EDGE_ATTESTED',
  scenarios,
  exploratoryWarnings:warnings,
  postCostRiskQuality:fragile?'FRAGILE_UNDER_EXPLORATORY_RULES':
    'PASSED_SYNTHETIC_STRESS_ASSUMPTIONS_ONLY',
  metrics:{
   priorATR14:round(atr),lastCandleOpposingWickFraction:round(wickFraction),
   entryDistanceToLastCloseATR:round(entryDistanceATR),
   lastM15CandleDirection:bodyDir,
   costStressWorstNetRR:scenarios.at(-1).netRewardRisk
  }
 };
}
module.exports={inspect,STRESS,THRESHOLDS};
