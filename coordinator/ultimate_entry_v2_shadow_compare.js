'use strict';
/*
 * Sept/Oct 2026 BID-only frozen V2 vs independent entry-stress shadow
 * research. Not V3, not broker-realistic execution, not independent holdout.
 * Uses same original signal universe, then replays accepted subset with
 * same frozen V2 historical backtester. NO orders or provider requests.
 */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {generateHistoricalSignals}=require('./app/frozen/strategy');
const {backtest}=require('./app/frozen/backtest');
const {inspect}=require('./ultimate_entry_robustness');
const {describeDataset}=require('./ultimate_entry_recorded_coverage');
const ROOT=path.resolve(__dirname,'../research/recorded');
const MONTHS=Object.freeze(['2026-09-bid.json','2026-10-bid.json']);
const COSTS=Object.freeze({spread:.4,slippage:.1,commissionPerLot:7,valuePerPoint:100});
const MAX_BYTES=1_000_000,MAX_SIGNALS=6000;
const safe=x=>typeof x==='number'&&Number.isFinite(x);
const round=x=>Math.round(x*1e5)/1e5;
function reject(code){throw Error('V2_BID_SHADOW_REJECTED_'+code);}
function read(p){
 const s=fs.lstatSync(p);
 if(!s.isFile()||s.isSymbolicLink()||s.size<=0||s.size>MAX_BYTES)reject('UNSAFE_RECORDED_PATH');
 return fs.readFileSync(p);
}
function loadLocked(){
 const manifest=JSON.parse(read(path.join(ROOT,'manifest.json')));
 if(!Array.isArray(manifest.datasets)||manifest.datasets.length!==2)reject('MANIFEST');
 return MONTHS.map((name,i)=>{
  const meta=manifest.datasets[i];
  if(meta?.file!==name||meta.priceConvention!=='BID'||! /^[a-f0-9]{64}$/.test(meta.sha256||''))reject('SOURCE_CONVENTION');
  const bytes=read(path.join(ROOT,name));
  if(crypto.createHash('sha256').update(bytes).digest('hex')!==meta.sha256)
   reject('DIGEST');
  const doc=JSON.parse(bytes.toString('utf8'));
  describeDataset(doc,meta);
  if(doc.symbol!=='XAU/USD')reject('INSTRUMENT');
  return {month:name.slice(0,7),doc};
 });
}
function modeled(trades,spread,slippage,commissionPrice){
 const completed=[...trades].sort((a,b)=>a.exitIndex-b.exitIndex||a.signalIndex-b.signalIndex);
 let sum=0,peak=0,dd=0,wins=0,gains=0,losses=0;
 for(const t of completed){
  const risk=Math.abs(t.entry-t.stop);
  if(!safe(risk)||risk<=0||!safe(t.grossR))reject('BAD_SIMULATED_TRADE');
  const net=t.grossR-(spread+slippage+commissionPrice)/risk;
  if(net>0){wins++;gains+=net;} else if(net<0)losses+=-net;
  sum+=net;peak=Math.max(peak,sum);dd=Math.max(dd,peak-sum);
 }
 return {closedTrades:completed.length,netWinningTrades:wins,
  modeledWinRatePercent:completed.length?round(100*wins/completed.length):null,
  modeledNetR:round(sum),modeledMaxClosedTradeDrawdownR:round(dd),
  modeledProfitFactor:losses?round(gains/losses):null,
  brokerFillsVerified:false};
}
function replay(doc,month){
 const bars=doc.frames['15min'];
 const signals=generateHistoricalSignals(doc.frames);
 if(signals.length>MAX_SIGNALS)reject('UNBOUNDED_SIGNAL_UNIVERSE');
 const frames=doc.frames,keys=['15min','1h','4h'],widths=[900000,3600000,14400000];
 const cursors=[0,0,0];
 let previous=-1;
 const accepted=[],codes={},rejected=[];
 for(const s of signals){
  if(!Number.isInteger(s.index)||s.index<=previous||s.index<0||s.index>=bars.length-1||
     !['BUY','SELL'].includes(s.side)||!safe(s.stop)||!safe(s.target))
   reject('FROZEN_V2_SIGNAL_INVALID');
  previous=s.index;
  const asOf=Date.parse(bars[s.index].datetime)+widths[0];
  const visible={};
  for(let k=0;k<keys.length;k++){
   const source=frames[keys[k]];
   while(cursors[k]<source.length&&Date.parse(source[cursors[k]].datetime)+widths[k]<=asOf)
    cursors[k]++;
   visible[['M15','H1','H4'][k]]=source.slice(0,cursors[k]);
  }
  const last=visible.M15.at(-1);
  if(!last||last.datetime!==bars[s.index].datetime)reject('DECISION_LOOKAHEAD_OR_MISSING_BAR');
  const costPlan={entry:last.close,stop:s.stop,target:s.target,spread:COSTS.spread};
  const risk={slippage:COSTS.slippage,commissionPerLot:COSTS.commissionPerLot,valuePerPoint:COSTS.valuePerPoint};
  const review=inspect({asOfUTC:new Date(asOf).toISOString(),frames:visible},s.side,costPlan,risk);
  if(review.signal!=='WAIT'||review.executable!==false||review.paperOrdersAllowed!==false)
   reject('AUDITOR_WOULD_PROMOTE_RESEARCH_TO_TRADE');
  if(review.status==='STRESS_DIAGNOSTIC_ONLY'&&
     review.postCostRiskQuality==='PASSED_SYNTHETIC_STRESS_ASSUMPTIONS_ONLY'){
   accepted.push(s);
  }else{
   const reasons=review.status==='STRESS_DIAGNOSTIC_ONLY'?
    review.exploratoryWarnings:[review.reason];
   rejected.push(s.index);
   for(const code of reasons)codes[code]=(codes[code]||0)+1;
  }
 }
 const before=backtest(bars,signals,{spread:COSTS.spread,risk:1});
 const after=backtest(bars,accepted,{spread:COSTS.spread,risk:1});
 const kept=new Set(accepted.map(s=>s.index));
 const sameBaselineTrades=before.tradesDetail.filter(t=>kept.has(t.signalIndex));
 if(sameBaselineTrades.length>before.trades)reject('BASELINE_COHORT_MISMATCH');
 const commission=COSTS.commissionPerLot/COSTS.valuePerPoint;
 const scenarios=[{name:'MODELED_BASE',spread:COSTS.spread,slippage:COSTS.slippage},
  {name:'MODELED_DOUBLE_SPREAD_AND_SLIPPAGE',spread:2*COSTS.spread,slippage:2*COSTS.slippage}];
 const stats=scenarios.map(c=>({
  scenario:c.name,
  baselinePath:modeled(before.tradesDetail,c.spread,c.slippage,commission),
  shadowFilterPath:modeled(after.tradesDetail,c.spread,c.slippage,commission),
  sameBaselineClosedTradeSubset:modeled(sameBaselineTrades,c.spread,c.slippage,commission),
  afterFilterPathMayAdmitDifferentOverlappingTrades:true
 }));
 return {
  month,
  dataOrigin:'BID_ONLY_PREVIOUSLY_RESEARCHED_UNLICENSED_BROKER_UNVERIFIED',
  baselineV2ResearchCandidates:signals.length,
  shadowRetainedCandidates:accepted.length,
  shadowRejectedCandidates:rejected.length,
  shadowFilterReasons:codes,
  frozenV2OriginalCandidatesUnchanged:true,
  sameBaselineClosedTrades:before.trades,
  shadowBacktestClosedTrades:after.trades,
  scenarios:stats
 };
}
function run(){
 const records=loadLocked();
 const months=records.map(x=>replay(x.doc,x.month));
 const outperformedEveryMonth=months.every(x=>
   x.scenarios.every(sc=>sc.shadowFilterPath.modeledNetR>
                      sc.baselinePath.modeledNetR));
 const allShadowPathsPositive=months.every(x=>
   x.scenarios.every(sc=>sc.shadowFilterPath.modeledNetR>0));
 const promotionBlockers=[
   'NO_INDEPENDENT_POST_FREEZE_HOLDOUT',
   'NO_BROKER_VERIFIED_BID_ASK_SPREAD_OR_REAL_FILL_COSTS',
   'NO_FULL_V3_MACRO_NEWS_ORDERFLOW_EVIDENCE',
   'CHANGED_OVERLAPPING_TRADE_PATH_NOT_CAUSAL_PAIRED_EDGE'
 ];
 if(!outperformedEveryMonth)
   promotionBlockers.push('SHADOW_FILTER_DID_NOT_OUTPERFORM_IN_EACH_RECORDED_MONTH');
 if(!allShadowPathsPositive)
   promotionBlockers.push('SHADOW_FILTER_HAS_NONPOSITIVE_MODELED_NET_R');
 return {
  mode:'FROZEN_V2_BID_RECORDED_ENTRY_SHADOW_COMPARISON_V1',
  status:'DESCRIPTIVE_NONINDEPENDENT_AFTER_COST_MODEL_ONLY',
  months,
  comparisonPromotionGate:{
   status:'BLOCKED_EXPLORATORY_RESEARCH_ONLY',
   shadowFilterOutperformedBothOldMonthsInBothCostScenarios:outperformedEveryMonth,
   allShadowMonthlyModeledNetRPositive:allShadowPathsPositive,
   shadowFilterAdoptionApproved:false,
   independentPerformanceImprovementProven:false,
   blockingReasons:promotionBlockers
  },
  costAssumptions:COSTS,
  v3UltimateComparisonPerformed:false,
  realBrokerBidAskExecutionVerified:false,
  historicalSessionCalendarIndependentlyVerified:false,
  independentlyLicensedData:false,
  independentProspectiveHoldout:false,
  statisticalSignificanceEstablished:false,
  incrementalWinRateImprovementProven:false,
  profitabilityProven:false,
  eligibleForPaperTrading:false,
  baselineAndShadowNotIdenticalTradePaths:true,
  sampleWarning:'Sept and Oct BID bars were used during development; constant spread, assumed slippage/commission, stop-first M15 approximation, and overlapping-trade path changes preclude reliable profitability claims. This is a frozen V2 research comparison, not V3 Ultimate or a new holdout.',
  signal:'WAIT',executable:false,paperOrdersAllowed:false,liveOrdersAllowed:false,
  providerRequestsMade:0,brokerOrdersSent:0
 };
}
module.exports={run,replay,modeled};
if(require.main===module){
 try{process.stdout.write(JSON.stringify(run())+'\n');}
 catch(e){console.error(/^V2_BID_SHADOW_REJECTED_/.test(e.message)?e.message:'V2_BID_SHADOW_INPUT_INVALID');process.exitCode=1;}
}
