"use strict";
/**
 * Pre-registered, descriptive gate for PROFITABILITY evaluation of prospective
 * paper closes. This is not a trade engine, real feed, source entitlement, or
 * proof of edge. It reuses the existing chronology and cost audit verbatim.
 *
 * Even extremely favourable outcomes can be fabricated by the caller. Never
 * promote this output to BUY/SELL, live signals, broker orders or a verified
 * win probability. A prospective observer must separately attest each input,
 * its frozen strategy, signed first-seen clock, complete WAIT/outage history,
 * independent source rights and broker-representative fills.
 */
const {evaluate}=require("./prospective_paper_holdout_audit");
const MODE="GOLD_PAPER_EDGE_PREDECLARED_DIAGNOSTIC_V1";
const MIN_TRADES=100,MIN_UTC_TRADE_DAYS=30,MIN_UTC_WEEKS=6;
const MAX_STUDY_CALENDAR_DAYS=90;
const RISK_FLOOR=.01;
const ROUND=x=>Number(x.toFixed(4));
const two=x=>Number(x.toFixed(2));
const isoDay=stamp=>stamp.slice(0,10);
function mondayUTC(s){
 const d=new Date(s.slice(0,10)+"T00:00:00Z");
 d.setUTCDate(d.getUTCDate()-(d.getUTCDay()+6)%7);
 return d.toISOString().slice(0,10);
}
function base(reason){
 return {
  mode:MODE,status:"BLOCKED",reason,
  signal:"WAIT",executable:false,
  recommendationAllowed:false,paperOrdersAllowed:false,
  liveOrdersAllowed:false,paperOrdersSent:0,brokerOrdersSent:0,
  providerRequestsMade:0,paymentsMade:0,
  costModelIndependentlyVerified:false,
  actualSourceRightsVerified:false,
  trueBrokerSessionCalendarVerified:false,
  frozenStrategyIndependentlyAttested:false,
  independentReceiptChainVerified:false,
  missingWaitAndOutageRecordsVerified:false,
  realMarketQuoteAndFillProvenanceVerified:false,
  futureMarketPerformanceProven:false,
  statisticallyVerifiedProfitable:false,
  profitableSignalDeploymentApproved:false,
  independentHoldoutValidated:false,
  sampleTradeCount:0,distinctUtcTradeDates:0,distinctUtcWeeks:0,
  daysSinceFreeze:null,nominalNetUsd:null,doubleCostStressNetUsd:null,
  modeledProfitFactor:null,arithmeticMeanNetR:null,
  conservativeDailyBlockResampleLower5PctNetR:null,
  chronologicalThirdsNetUsd:null,
  hypotheticalScreenChecksPassed:false,
  // Fixed in code; not selected from a positive observed backtest.
  screenRules:{
   minimumClosedTrades:MIN_TRADES,
   minimumDistinctUtcTradeDates:MIN_UTC_TRADE_DAYS,
   minimumDistinctUtcCalendarWeeks:MIN_UTC_WEEKS,
   maximumCalendarDays:MAX_STUDY_CALENDAR_DAYS,
   positiveNominalNetAfterCosts:true,
   positiveNetUnder2xModeledCosts:true,
   minimumModeledProfitFactor:1.2,
   positiveEachChronologicalThird:true,
   dailyClusterBootstrap5thPercentileMeanNetRPositive:true
  },
  diagnosticOnly:true
 };
}
function assess(input){
 const arithmetic=evaluate(input);
 if(arithmetic.status!=="UNATTESTED_PAPER_ARITHMETIC_ONLY"||
    !arithmetic.statistics||
    arithmetic.signal!=="WAIT"||arithmetic.executable!==false||
    arithmetic.independentHoldoutValidated!==false||
    arithmetic.profitabilityProven!==false){
  return base("COST_CHRONOLOGY_OR_CLOSED_PAPER_TRADES_NOT_VERIFIED");
 }
 const tr=input.trades,stats=arithmetic.statistics,n=tr.length;
 if(n!==arithmetic.closedTrades||
    !Number.isFinite(stats.totalGrossMinusModeledCostsUsd)||
    !Number.isFinite(stats.modeledCostDoubleStress?.netUsd)||
    !Number.isFinite(stats.averageNetR)){
  return base("UNRELIABLE_PAPER_ARITHMETIC_REPORT");
 }
 const days=new Map(),weeks=new Set();
 const segments=[0,0,0];
 let riskTotal=0,nominal=0,stress=0,profits=0,losses=0;
 for(let i=0;i<n;i++){
  const t=tr[i],cost=t.spreadUsd+t.slippageUsd+t.commissionUsd;
  const result=t.grossPnLUsd-cost;
  const stressed=t.grossPnLUsd-2*cost;
  const key=isoDay(t.decisionUTC);
  const entry=days.get(key)||{totalR:0,trades:0};
  entry.totalR+=result/t.initialRiskUsd;
  entry.trades++;
  days.set(key,entry);weeks.add(mondayUTC(t.decisionUTC));
  segments[Math.min(2,Math.floor(i*3/n))]+=result;
  riskTotal+=t.initialRiskUsd;nominal+=result;stress+=stressed;
  if(result>0)profits+=result;
  else if(result<0)losses-=result;
 }
 if(riskTotal<n*RISK_FLOOR||Math.abs(two(nominal)-stats.totalGrossMinusModeledCostsUsd)>.011||
    Math.abs(two(stress)-stats.modeledCostDoubleStress.netUsd)>.011)
  return base("COST_RECONCILIATION_CONTRADICTORY");
 // Deterministic UTC-day cluster resampling preserves *intra-day*
 // correlation (not correlation across days or regimes). Its 5th
 // percentile is an exploratory sensitivity measure, NOT a formal
 // confidence guarantee or evidence of broker fill provenance.
 const clusters=[...days.values()];
 let seed=0x4d415353;
 const series=[];
 for(let rep=0;rep<2000;rep++){
  let sumR=0,number=0;
  for(let k=0;k<clusters.length;k++){
   seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;seed>>>=0;
   const group=clusters[seed%clusters.length];
   sumR+=group.totalR;number+=group.trades;
  }
  series.push(sumR/number);
 }
 series.sort((a,b)=>a-b);
 const lower=series[Math.floor(series.length*.05)];
 const countDays=(Date.parse(input.asOfUTC)-Date.parse(input.freezeUTC))/86400000;
 const factor=losses>0?profits/losses:null;
 // No 'pass' even for fabricated 100 wins. This screen only identifies
 // a candidate research ledger for later *independent* verification.
 const numericScreen=n>=MIN_TRADES&&
    days.size>=MIN_UTC_TRADE_DAYS&&weeks.size>=MIN_UTC_WEEKS&&
    countDays<=MAX_STUDY_CALENDAR_DAYS&&
    nominal>0&&stress>0&&factor!==null&&factor>=1.2&&
    segments.every(x=>x>0)&&lower>0;
 return {...base("UNATTESTED_INPUTS_REQUIRE_FORWARD_INDEPENDENT_PROVENANCE"),
   status:"SANITIZED_PROFITABILITY_SCREEN_ONLY_NOT_MARKET_PROOF",
   sampleTradeCount:n,
   distinctUtcTradeDates:days.size,
   distinctUtcWeeks:weeks.size,
   daysSinceFreeze:ROUND(countDays),
   nominalNetUsd:two(nominal),
   doubleCostStressNetUsd:two(stress),
   modeledProfitFactor:factor===null?null:ROUND(factor),
   arithmeticMeanNetR:stats.averageNetR,
   conservativeDailyBlockResampleLower5PctNetR:ROUND(lower),
   chronologicalThirdsNetUsd:segments.map(two),
   hypotheticalScreenChecksPassed:numericScreen,
   // No independent broker ledger, data-source entitlement, immutable
   // freeze attestation or whole-session opportunity/WAIT accounting.
   statisticallyVerifiedProfitable:false,
   independentHoldoutValidated:false,
   profitableSignalDeploymentApproved:false
 };
}
module.exports={assess};
if(require.main===module){
 let input="";
 process.stdin.setEncoding("utf8");
 process.stdin.on("data",chunk=>{
  input+=chunk;
  if(input.length>1000000){
   process.stderr.write("EDGE_DIAGNOSTIC_INPUT_TOO_LARGE\n");
   process.exit(2);
  }
 });
 process.stdin.on("end",()=>{
  try{process.stdout.write(JSON.stringify(assess(JSON.parse(input)))+"\n");}
  catch(_){process.stdout.write(JSON.stringify(base("INVALID_INPUT"))+"\n");}
 });
}
