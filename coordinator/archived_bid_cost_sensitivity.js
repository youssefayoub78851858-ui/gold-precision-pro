"use strict";
// Historical BID-only DEVELOPMENT ARCHIVE sensitivity, NOT an independent
// out-of-sample validation. No live feed, requests, orders or new signals.
// Read only the existing SHA256-matched 2026-09/10 repository archives and
// run the same frozen V2 historical simulation with three fixed hypothetical
// round-trip price frictions. These are NOT observed broker spreads/fees.
const fs=require("node:fs");
const crypto=require("node:crypto");
const path=require("node:path");
const {audit:proof}=require("./xauusd_spread_proof_readiness");
const {backtestFrames}=require("./app/frozen/backtest");
const ROOT=path.resolve(__dirname,"..");
const SCENARIOS=Object.freeze([0.40,0.80,1.20]); // XAUUSD price units, assumed all-in roundtrip friction
const EXPECTED=Object.freeze(["2026-09-bid.json","2026-10-bid.json"]);
const sum=(xs,fn)=>xs.reduce((a,x)=>a+fn(x),0);
const round=x=>Math.round(x*1e6)/1e6;
// A descriptive break-even threshold of the fixed *development-period* trades.
// Holding entries/exits invariant: netR(cost) = grossR - cost * sum(1/stopDistance).
// No forward holdout, broker execution costs or source rights are certified.
function developmentBreakeven(grossR, reciprocalStopDistanceSum, count){
 if(!Number.isFinite(grossR)||!Number.isFinite(reciprocalStopDistanceSum)||
    !Number.isSafeInteger(count)||count<0||reciprocalStopDistanceSum<0)
   throw Error("INVALID_DEVELOPMENT_COST_BREAK_EVEN_INPUT");
 if(count===0){
  if(grossR!==0||reciprocalStopDistanceSum!==0)throw Error("UNSUPPORTED_EMPTY_TRADE_COSTS");
  return null;
 }
 if(!(reciprocalStopDistanceSum>0))throw Error("ZERO_STOP_DISTANCE_COST_DENOMINATOR");
 return round(Math.max(0,grossR/reciprocalStopDistanceSum));
}
function drawdownR(trades){
 let equity=0,peak=0,max=0;
 // Existing backtest excludes overlapping positions; exitIndex is
 // chronologically ordered per archive.
 for(const t of trades){
  equity+=t.netR;peak=Math.max(peak,equity);max=Math.max(max,peak-equity);
 }
 return round(max);
}
function inspect(root=ROOT){
 // Existing integrity guard checks every source file hash, OHLC, price
 // convention, and denies any invented ASK/MID basis.
 const p=proof(root);
 if(p.status!=="PROOF_BLOCKED"||p.counts?.recordedFiles!==2||
    p.counts.askM15!==0||p.counts.midM15!==0||
    p.filterHoldoutDataAvailable!==false||
    !Array.isArray(p.records)||p.records.length!==2||
    p.records.some(x=>!x.sha256MatchesManifest||x.declaredConvention!=="BID")||
    EXPECTED.some(name=>!p.records.some(x=>x.file===name)))
   throw Error("DEV_ARCHIVE_INTEGRITY_OR_PRICE_BASIS_UNVERIFIED");
 const periods=[],aggregated=Object.fromEntries(SCENARIOS.map(c=>[String(c),{
   closedTrades:0,rawSignals:0,netR:0,grossR:0,assumedCostR:0,netWinningTrades:0,
   maxDrawdownPerPeriodR:[],openAtEndByPeriod:[]}]));
 for(const name of EXPECTED){
  const doc=JSON.parse(fs.readFileSync(path.join(root,"research","recorded",name),"utf8"));
  if(doc.symbol!=="XAU/USD"||!doc.frames||doc.frames["15min"]?.length<100||
     doc.source?.includes("synthetic"))throw Error("ARCHIVE_SYMBOL_OR_HISTORY_INVALID");
  const results=[];let stableIdentity=null,periodGross=null,periodCostSlope=null,periodTradeCount=null;
  for(const assumed of SCENARIOS){
   const sim=backtestFrames(doc.frames,{spread:assumed,risk:1});
   // Cost scenarios must not alter candidate generation, entry/exit
   // order, risk distance, target, stop or outcome fill geometry.
   const identity=JSON.stringify(sim.tradesDetail.map(t=>[
    t.signalIndex,t.entryIndex,t.exitIndex,t.side,t.entry,t.stop,t.target,t.exitPrice,t.grossR
   ]));
   if(stableIdentity===null)stableIdentity=identity;
   else if(stableIdentity!==identity)throw Error("COST_SCENARIO_CHANGED_TRADE_GEOMETRY");
   if(sim.trades!==sim.tradesDetail.length)throw Error("TRADES_COUNT_MISMATCH");
   const gross=sum(sim.tradesDetail,t=>t.grossR);
   const net=sum(sim.tradesDetail,t=>t.netR);
   const costSlope=sum(sim.tradesDetail,t=>1/Math.abs(t.entry-t.stop));
   const costR=assumed*costSlope;
   if(periodGross===null){
     periodGross=gross;periodCostSlope=costSlope;periodTradeCount=sim.trades;
   }else if(Math.abs(periodGross-gross)>1e-9||
            Math.abs(periodCostSlope-costSlope)>1e-9||
            periodTradeCount!==sim.trades){
     throw Error("DEVELOPMENT_TRADES_CHANGED_WITH_ASSUMED_FRICTION");
   }
   if(Math.abs(net-(gross-costR))>1e-6||
      Math.abs(net-sim.totalR)>0.011)throw Error("BACKTEST_COST_ACCOUNTING_MISMATCH");
   const item={
     assumedRoundTripPriceFrictionUSDperOz:assumed,
     rawHistoricalSignals:sim.generatedSignals,
     closedTrades:sim.trades,
     openAtEnd:sim.openAtEnd,
     winningClosedTrades:sim.wins,
     historicalWinRatePercent:sim.trades?round(100*sim.wins/sim.trades):null,
     grossR:round(gross),assumedFrictionR:round(costR),
     netR:round(net),maxDrawdownR:drawdownR(sim.tradesDetail),
     profitFactorOnClosedTrades:sim.profitFactor
   };
   results.push(item);
   const agg=aggregated[String(assumed)];
   agg.closedTrades+=sim.trades;agg.rawSignals+=sim.generatedSignals;
   agg.netR+=net;agg.grossR+=gross;agg.assumedCostR+=costR;
   agg.netWinningTrades+=sim.wins;
   agg.maxDrawdownPerPeriodR.push(item.maxDrawdownR);
   agg.openAtEndByPeriod.push(sim.openAtEnd);
  }
  if(results.some((x,i)=>i>0&&(
      x.closedTrades!==results[0].closedTrades||
      x.rawHistoricalSignals!==results[0].rawHistoricalSignals||
      x.netR>results[i-1].netR+1e-6)))
   throw Error("INVALID_COST_SENSITIVITY_ORDERING");
  const meta=p.records.find(x=>x.file===name);
  periods.push({file:name,sha256:crypto.createHash("sha256")
     .update(fs.readFileSync(path.join(root,"research","recorded",name)))
     .digest("hex"),
    priceBasis:"BID_ONLY",m15Bars:meta.stored15MinuteBars,
    h1Bars:meta.storedHourBars,h4Bars:meta.stored4HourBars,
    firstOpenUTC:meta.firstM15UTC,lastOpenUTC:meta.lastM15UTC,
    developmentFrictionCeiling:{
      sample:"SAME_BID_ONLY_DEVELOPMENT_TRADES_NOT_FORWARD",
      historicalGrossRAtZeroAssumedFriction:round(periodGross),
      rLostPerUsdPerOzRoundTripFriction:round(periodCostSlope),
      hypotheticalBreakEvenAllInFrictionUsdPerOz:
        developmentBreakeven(periodGross,periodCostSlope,periodTradeCount),
      historicalPositiveNetBeyondCeilingNotSupported:true,
      commissionSlippageAndBrokerFillEvidenceAvailable:false,
      tradingApprovalGranted:false
    },
    scenarios:results});
 }
 const aggregate=SCENARIOS.map(cost=>{
  const a=aggregated[String(cost)];
  return {assumedRoundTripPriceFrictionUSDperOz:cost,
   acrossSeparateDevelopmentPeriods:true,
   closedTrades:a.closedTrades,rawHistoricalSignals:a.rawSignals,
   historicalWinRatePercent:a.closedTrades?round(100*a.netWinningTrades/a.closedTrades):null,
   grossR:round(a.grossR),assumedFrictionR:round(a.assumedCostR),
   netR:round(a.netR),maxDrawdownR:null,
   separatePeriodMaxDrawdownR:a.maxDrawdownPerPeriodR,
   separatelyOpenAtEnd:a.openAtEndByPeriod};
 });
 return {
  mode:"OFFLINE_FROZEN_V2_BID_DEVELOPMENT_COST_SENSITIVITY",
  dataOrigin:"EXISTING_SEPT_OCT_REPOSITORY_BID_ONLY_DEVELOPMENT_ARCHIVES",
  sourceAuthenticityIndependentlyVerified:false,
  archivedSHA256ManifestVerified:true,
  archivedBidM15Bars:p.counts.bidM15,
  archivedAskM15Bars:0,
  realBrokerHistoricalSpreadKnown:false,
  historicalSlippageCommissionKnown:false,
  spreadScenariosAreAssumptionsNotMarketObservations:true,
  strategy:"EXISTING_FROZEN_V2_EMA_RSI_ATR_BACKTEST",
  strategyChanged:false,
  notUltimateV3Performance:true,
  isIndependentHoldout:false,
  independentHoldoutRequired:true,
  executionAndDataRightsStillUnverified:true,
  pastArchiveUsedDuringDevelopment:true,
  scenariosUSDperOz:[...SCENARIOS],
  periods,aggregate,
  // The development-period break-even computation is NOT independent
  // prospective evidence. Show all periods separately; never combine a
  // purported capital drawdown curve across months.
  breakEvenFrictionOnlyDescriptiveNotTradingAuthority:true,
  label:"Descriptive development backtest. BID-only prices; hypothetical all-in price frictions. No real ASK fills, slippage, commissions, source-first-availability proof, or independent new holdout. NOT trading profitability.",
  signal:"WAIT",executable:false,tradeEligible:false,
  paperOrdersAllowed:false,providerRequestsMade:0,ordersSent:0,
  tradingReady:false,empiricalWinProbability:null,
  independentPerformanceProven:false
 };
}
module.exports={inspect,developmentBreakeven};
if(require.main===module){
 try{process.stdout.write(JSON.stringify(inspect(),null,2)+"\n");}
 catch(e){console.error("DEV_COST_SENSITIVITY_BLOCKED: "+e.message);process.exitCode=1;}
}
