"use strict";
const assert=require("node:assert/strict");
const {assess}=require("./prospective_paper_edge_screen");
const FREEZE=Date.parse("2026-11-18T00:00:00Z");
const iso=n=>new Date(n).toISOString().replace(".000Z","Z");
const H=3600000,D=86400000;
function fixture(count=105, grossFn=i=>i%5===0?-.2:2){
 const trades=[];
 let day=Date.parse("2026-11-19T00:00:00Z"),number=0;
 while(number<count){
  const dow=new Date(day).getUTCDay();
  if(dow!==0&&dow!==6){
   for(const hour of [8,12,16]){
    if(number>=count)break;
    number++;
    const decision=day+hour*H,entry=decision+60000,exit=decision+1800000;
    trades.push({
     id:"paper_"+number,side:number%2?"BUY":"SELL",
     decisionUTC:iso(decision),entryUTC:iso(entry),exitUTC:iso(exit),
     firstObservedClosedUTC:iso(exit+60000),
     signalClosedUTC:iso(decision),signalFirstObservedUTC:iso(decision),
     contextClosedUTC:{H1:iso(decision),H4:iso(decision)},
     contextFirstObservedUTC:{H1:iso(decision),H4:iso(decision)},
     grossPnLUsd:grossFn(number),
     spreadUsd:.4,slippageUsd:.1,commissionUsd:.1,
     grossPnLConvention:"MID_MARK_BEFORE_SPREAD_SLIPPAGE_COMMISSION",
     initialRiskConvention:"STOP_LOSS_PLUS_TOTAL_MODELED_COSTS_USD",
     initialRiskUsd:2,apiKey:"DUMMY_SECRET_DO_NOT_OUTPUT",
     entryPrice:"3900.5001",
    });
   }
  }
  day+=D;
 }
 return {
  dataOrigin:"UNATTESTED_SANITIZED_PAPER_LEDGER",
  freezeUTC:iso(FREEZE),
  asOfUTC:iso(Date.parse(trades.at(-1).exitUTC)+D),
  trades,forgedBrokerRights:true,preapprovedTrade:true,
  externalEvidenceIndependentlyVerified:true
 };
}
function safe(out){
 assert.equal(out.signal,"WAIT");
 for(const k of [
  "executable","recommendationAllowed","paperOrdersAllowed","liveOrdersAllowed",
  "costModelIndependentlyVerified","actualSourceRightsVerified",
  "trueBrokerSessionCalendarVerified","frozenStrategyIndependentlyAttested",
  "independentReceiptChainVerified","missingWaitAndOutageRecordsVerified",
  "realMarketQuoteAndFillProvenanceVerified","futureMarketPerformanceProven",
  "statisticallyVerifiedProfitable","profitableSignalDeploymentApproved",
  "independentHoldoutValidated",
 ])assert.equal(out[k],false,k);
 for(const k of ["providerRequestsMade","brokerOrdersSent","paperOrdersSent",
  "paymentsMade"])assert.equal(out[k],0,k);
 const printed=JSON.stringify(out);
 for(const privateValue of ["DUMMY_SECRET_DO_NOT_OUTPUT","3900.5001",
  '"grossPnLUsd"','"entryPrice"','"side"','"spreadUsd"'])
  assert(!printed.includes(privateValue),privateValue);
}
const missing=assess({dataOrigin:"UNATTESTED_SANITIZED_PAPER_LEDGER",
 freezeUTC:"2026-11-18T00:00:00Z",asOfUTC:"2026-11-20T00:00:00Z",trades:[]});
safe(missing);
assert.equal(missing.status,"BLOCKED");
assert.equal(missing.sampleTradeCount,0);
const good=assess(fixture());
safe(good);
assert.equal(good.status,"SANITIZED_PROFITABILITY_SCREEN_ONLY_NOT_MARKET_PROOF");
assert.equal(good.sampleTradeCount,105);
assert.equal(good.distinctUtcTradeDates,35);
assert(good.distinctUtcWeeks>=6);
assert(good.nominalNetUsd>0);
assert(good.doubleCostStressNetUsd>0);
assert(good.modeledProfitFactor>=1.2);
assert(good.chronologicalThirdsNetUsd.every(x=>x>0));
assert(good.conservativeDailyBlockResampleLower5PctNetR>0);
assert(good.maxModeledClosedDrawdownR<=10);
assert.equal(good.hypotheticalScreenChecksPassed,true);
// Even a perfectly fabricated and "qualified" sample NEVER attests
// real-time market rights, real fills, chance of profit or authorizes a trade.
assert.equal(good.statisticallyVerifiedProfitable,false);
assert.equal(good.profitableSignalDeploymentApproved,false);
const insufficient=assess(fixture(99));safe(insufficient);
assert.equal(insufficient.sampleTradeCount,99);
assert.equal(insufficient.hypotheticalScreenChecksPassed,false);
const stressFail=assess(fixture(105,()=>.9));safe(stressFail);
assert(stressFail.nominalNetUsd>0);
assert(stressFail.doubleCostStressNetUsd<0);
assert.equal(stressFail.hypotheticalScreenChecksPassed,false);
const highWinRateNegative=assess(fixture(105,i=>i%5===0?-10:1));safe(highWinRateNegative);
assert(highWinRateNegative.nominalNetUsd<0);
assert.equal(highWinRateNegative.hypotheticalScreenChecksPassed,false);
const longStreak=assess(fixture(105,i=>i>=45&&i<60?-1:2));
safe(longStreak);
assert(longStreak.nominalNetUsd>0);
assert(longStreak.doubleCostStressNetUsd>0);
assert(longStreak.maxModeledClosedDrawdownR>10);
assert.equal(longStreak.hypotheticalScreenChecksPassed,false);
const cherryPicked=assess(fixture(105,i=>i===105?200:-.2));safe(cherryPicked);
assert.equal(cherryPicked.hypotheticalScreenChecksPassed,false);
// No losses -> not enough to derive a finite profit factor. Never
// interpret no realized losses as "infinite" market profitability.
const allWins=assess(fixture(105,()=>2));safe(allWins);
assert.equal(allWins.modeledProfitFactor,null);
assert.equal(allWins.hypotheticalScreenChecksPassed,false);
const malformed=fixture(105);malformed.trades[3].signalFirstObservedUTC=
 iso(Date.parse(malformed.trades[3].decisionUTC)+60000);
const invalid=assess(malformed);safe(invalid);
assert.equal(invalid.status,"BLOCKED");
assert.equal(invalid.sampleTradeCount,0);
const old=fixture(105);old.trades[1].decisionUTC=old.freezeUTC;
const chronology=assess(old);safe(chronology);
assert.equal(chronology.status,"BLOCKED");
const longStudy=fixture(105);longStudy.asOfUTC=
 iso(Date.parse(longStudy.freezeUTC)+94*D);
const over90=assess(longStudy);safe(over90);
assert.equal(over90.hypotheticalScreenChecksPassed,false);
// UTC chronology and deterministic daily bootstrap must be reproducible.
assert.deepEqual(assess(fixture()),good);
console.log("PASS prospective paper edge screen: 100+ closes, periods, modeled costs x2, drawdowns and no profit claims");
