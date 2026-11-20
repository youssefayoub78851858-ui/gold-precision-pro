"use strict";
/**
 * Sanitized, OFFLINE prospective paper-outcome arithmetic.
 * This audits caller-supplied observations only. It cannot authenticate a
 * vendor, broker fills, the preregistered freeze, or real-money performance.
 * Positive sample returns NEVER enable a BUY/SELL recommendation or order.
 */
const MODE="GOLD_PROSPECTIVE_PAPER_HOLDOUT_OFFLINE_V1";
const ORIGIN="UNATTESTED_SANITIZED_PAPER_LEDGER";
const FIRST=Date.parse("2026-11-18T00:00:00Z");
const CONTEXT_WIDTH=Object.freeze({H1:3600000,H4:14400000});
const SIGNAL_MAX_AGE_MS=900000;
// Risk is expressed in real dollar cents for descriptive R arithmetic.
// Sub-cent or subnormal 'risk' falsely creates massive/infinite R.
const MIN_INITIAL_RISK_USD=0.01;
const ISO=/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/;
const stamp=x=>typeof x==="string"&&ISO.test(x)&&Number.isFinite(Date.parse(x))&&
 new Date(x).toISOString().slice(0,19)===x.slice(0,19)?Date.parse(x):NaN;
const usd=x=>typeof x==="number"&&Number.isFinite(x)&&x>=0&&x<=1000000;
const pnl=x=>typeof x==="number"&&Number.isFinite(x)&&Math.abs(x)<=1000000;
const round=(x,d=4)=>Number(x.toFixed(d));
function blocked(status,reason){
 return {mode:MODE,status,reason,signal:"WAIT",executable:false,
  recommendationAllowed:false,tradeEligible:false,paperOrdersAllowed:false,
  liveOrdersAllowed:false,brokerOrdersSent:0,paperOrdersSent:0,
  providerRequestsMade:0,sourceRightsVerified:false,
  independentBrokerFillCostsVerified:false,independentHoldoutValidated:false,
  freezeIndependentlyAttested:false,profitabilityProven:false,
  sanitizedOnly:true,closedTrades:0,statistics:null};
}
function evaluate(input){
 if(input?.dataOrigin!==ORIGIN)return blocked("BLOCKED","UNTRUSTED_LEDGER_ORIGIN");
 const asOf=stamp(input.asOfUTC),freeze=stamp(input.freezeUTC);
 if(!Number.isFinite(asOf)||!Number.isFinite(freeze)||freeze<FIRST||freeze>=asOf)
  return blocked("BLOCKED","INVALID_OR_UNFROZEN_HOLDOUT_WINDOW");
 const trades=input.trades;
 if(!Array.isArray(trades)||trades.length>2000)
  return blocked("BLOCKED","INVALID_PAPER_TRADE_SET");
 if(trades.length===0)return blocked("NO_CLOSED_PAPER_TRADES","NO_HOLDOUT_RESULTS_YET");
 let prevExit=freeze,lastReceipt=freeze,peak=0,cumulative=0,maxDD=0,
  netTotal=0,winCount=0,profit=0,loss=0,rTotal=0,totalCosts=0;
 const ids=new Set();
 for(const t of trades){
  if(!t||typeof t!=="object"||Array.isArray(t)||
   typeof t.id!=="string"||!/^[a-zA-Z0-9_-]{1,40}$/.test(t.id)||
   ids.has(t.id)||!["BUY","SELL"].includes(t.side))
   return blocked("BLOCKED","INVALID_OR_DUPLICATE_TRADE_METADATA");
  ids.add(t.id);
  const decision=stamp(t.decisionUTC),entry=stamp(t.entryUTC),
   exit=stamp(t.exitUTC),receipt=stamp(t.firstObservedClosedUTC);
  // Separately assert when the M15 signal's CLOSED candle first became
  // visible. An exit receipt cannot establish that the signal existed
  // before the order decision (no "tomorrow's candle" leakage).
  // These are UNATTESTED caller-supplied times, never broker proof.
  const signalClosed=stamp(t.signalClosedUTC),
        signalSeen=stamp(t.signalFirstObservedUTC);
  if(![decision,entry,exit,receipt,signalClosed,signalSeen].every(Number.isFinite)||
   signalClosed%900000!==0||signalClosed>signalSeen||
   signalSeen>decision||signalClosed>decision||
   decision-signalClosed>SIGNAL_MAX_AGE_MS||
   decision<freeze||decision<prevExit||decision<lastReceipt||
   entry<decision||exit<=entry||
   receipt<exit||receipt<lastReceipt||receipt>asOf||exit>asOf)
   return blocked("BLOCKED","LOOKAHEAD_OR_NONCHRONOLOGICAL_PAPER_TRADE");
  // The M15 signal alone does not prove that its H1/H4 context was
  // closed and received BEFORE the same decision. Require both; untrusted
  // timestamps may only yield descriptive arithmetic, never approval.
  const closed=t.contextClosedUTC,seen=t.contextFirstObservedUTC;
  const exact=x=>x&&typeof x==="object"&&!Array.isArray(x)&&
   Object.keys(x).sort().join(",")==="H1,H4";
  if(!exact(closed)||!exact(seen)||!Object.keys(CONTEXT_WIDTH).every(tf=>{
    const end=stamp(closed[tf]),receiptAt=stamp(seen[tf]);
    return Number.isFinite(end)&&Number.isFinite(receiptAt)&&
     end%CONTEXT_WIDTH[tf]===0&&end<=receiptAt&&receiptAt<=decision&&
     decision-end<=CONTEXT_WIDTH[tf]+SIGNAL_MAX_AGE_MS;
  }))return blocked("BLOCKED","MULTITIMEFRAME_CONTEXT_NOT_KNOWN_AT_DECISION");
  prevExit=exit;lastReceipt=receipt;
  if(!pnl(t.grossPnLUsd)||!usd(t.spreadUsd)||!usd(t.slippageUsd)||
   !usd(t.commissionUsd)||!usd(t.initialRiskUsd)||
   t.initialRiskUsd<MIN_INITIAL_RISK_USD)
   return blocked("BLOCKED","UNVERIFIED_OR_INVALID_PAPER_COST_FIELDS");
  const cost=t.spreadUsd+t.slippageUsd+t.commissionUsd;
  const net=t.grossPnLUsd-cost;
  const ratio=net/t.initialRiskUsd;
  if(!Number.isFinite(net)||!Number.isFinite(ratio))
   return blocked("BLOCKED","INVALID_PAPER_NET_OR_RISK_RATIO");
  totalCosts+=cost;netTotal+=net;rTotal+=ratio;
  cumulative+=net;peak=Math.max(peak,cumulative);
  maxDD=Math.max(maxDD,peak-cumulative);
  if(net>0){winCount++;profit+=net;}
  else if(net<0)loss-=net;
 }
 const n=trades.length;
 return {...blocked("UNATTESTED_PAPER_ARITHMETIC_ONLY","INDEPENDENT_PROVENANCE_AND_COST_ATTESTATION_MISSING"),
  closedTrades:n,statistics:{
   totalGrossMinusModeledCostsUsd:round(netTotal,2),
   modeledCostsUsd:round(totalCosts,2),
   averageNetUsd:round(netTotal/n,2),
   averageNetR:round(rTotal/n),
   winRate:round(winCount/n),
   profitFactor:loss>0?round(profit/loss):null,
   maxRealizedDrawdownUsd:round(maxDD,2),
   sampleSizeAtLeast30:n>=30,
   inference:"DESCRIPTIVE_ONLY_NOT_STATISTICAL_PROOF",
   pricesAndIndividualFillsReturned:false
  }};
}
module.exports={evaluate};
if(require.main===module){
 let raw="";
 process.stdin.setEncoding("utf8");
 process.stdin.on("data",x=>{
  raw+=x;
  if(raw.length>1000000){process.stderr.write("PAPER_AUDIT_INPUT_TOO_LARGE\n");process.exit(2);}
 });
 process.stdin.on("end",()=>{
  try{process.stdout.write(JSON.stringify(evaluate(JSON.parse(raw)))+"\n");}
  catch(_){process.stdout.write(JSON.stringify(blocked("BLOCKED","INVALID_PAPER_AUDIT_INPUT"))+"\n");}
 });
}
