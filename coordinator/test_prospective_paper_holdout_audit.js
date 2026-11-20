"use strict";
const a=require("node:assert/strict");
const {evaluate}=require("./prospective_paper_holdout_audit");
const ORIGIN="UNATTESTED_SANITIZED_PAPER_LEDGER";
const start=Date.parse("2026-11-18T00:00:00Z");
const iso=x=>new Date(x).toISOString().replace(".000Z","Z");
function safe(x){
 a.equal(x.signal,"WAIT");
 for(const k of ["executable","recommendationAllowed","tradeEligible",
  "paperOrdersAllowed","liveOrdersAllowed","sourceRightsVerified",
  "independentBrokerFillCostsVerified","independentHoldoutValidated",
  "freezeIndependentlyAttested","profitabilityProven"])a.equal(x[k],false,k);
 a.equal(x.brokerOrdersSent,0);a.equal(x.paperOrdersSent,0);
 a.equal(x.providerRequestsMade,0);
 const raw=JSON.stringify(x);
 a(!raw.includes("SECRET_PRICE")&&!raw.includes("PRIVATE_KEY"));
 a(!raw.includes('"entryUSD"')&&!raw.includes('"entryPrice"'));
}
const trade=(i,gross=2)=>({
 id:"t"+i,side:i%2?"SELL":"BUY",
 decisionUTC:iso(start+3600000*i),
 entryUTC:iso(start+3600000*i+60000),
 exitUTC:iso(start+3600000*i+1800000),
 firstObservedClosedUTC:iso(start+3600000*i+1860000),
 // M15 candle closed BEFORE decision; receipt is after that close.
 signalClosedUTC:iso(start+3600000*i),
 signalFirstObservedUTC:iso(start+3600000*i),
 // H1/H4 need independently closed and first-seen BEFORE decision too.
 contextClosedUTC:{H1:iso(start+3600000*i),H4:iso(start+Math.floor(i/4)*14400000)},
 contextFirstObservedUTC:{H1:iso(start+3600000*i),H4:iso(start+Math.floor(i/4)*14400000)},
 grossPnLUsd:gross,spreadUsd:.4,slippageUsd:.1,commissionUsd:.1,
 initialRiskUsd:2,entryPrice:"SECRET_PRICE"
});
const packet=trades=>({dataOrigin:ORIGIN,freezeUTC:iso(start),
 asOfUTC:iso(start+90000000),trades,allowTrade:true,
 providerAuthorizes:true,sourceRightsVerified:true,token:"PRIVATE_KEY"});
let noTrades=evaluate(packet([]));safe(noTrades);
a.equal(noTrades.status,"NO_CLOSED_PAPER_TRADES");
a.equal(noTrades.statistics,null);
const good=evaluate(packet([trade(1,2),trade(2,-3)]));safe(good);
a.equal(good.status,"UNATTESTED_PAPER_ARITHMETIC_ONLY");
a.equal(good.statistics.totalGrossMinusModeledCostsUsd,-2.2);
a.equal(good.statistics.modeledCostsUsd,1.2);
a.equal(good.statistics.averageNetR,-.55);
a.equal(good.statistics.winRate,.5);
a.equal(good.statistics.maxRealizedDrawdownUsd,3.6);
a.equal(good.statistics.sampleSizeAtLeast30,false);
const allWins=evaluate({
 ...packet(Array.from({length:32},(_,i)=>trade(i+1))),
 asOfUTC:iso(start+40*3600000)
});safe(allWins);
a.equal(allWins.closedTrades,32);
a.equal(allWins.statistics.sampleSizeAtLeast30,true);
a.equal(allWins.statistics.profitFactor,null);
a.equal(allWins.statistics.inference,"DESCRIPTIVE_ONLY_NOT_STATISTICAL_PROOF");
a.equal(allWins.profitabilityProven,false);
for(const data of [
 {...packet([trade(1)]),dataOrigin:"VERIFIED_REAL_BROKER_FILLED"},
 {...packet([trade(1)]),asOfUTC:iso(start)},
 {...packet([trade(1)]),freezeUTC:iso(start-1000)},
 {...packet([trade(1)]),trades:[trade(1),trade(1)]},
 {...packet([trade(2),trade(1)])},
 {...packet([trade(1)]),trades:[{...trade(1),firstObservedClosedUTC:iso(start+3600000)}]},
 {...packet([trade(1)]),trades:[{...trade(1),signalClosedUTC:iso(start+3600000+900000)}]},
 {...packet([trade(1)]),trades:[{...trade(1),signalFirstObservedUTC:iso(start+3600000+900000)}]},
 {...packet([trade(1)]),trades:[{...trade(1),signalClosedUTC:"2026-11-18T01:05:00Z"}]},
 {...packet([trade(1)]),trades:[{...trade(1),signalFirstObservedUTC:undefined}]},
 {...packet([trade(1)]),trades:[{...trade(1),contextClosedUTC:undefined}]},
 {...packet([trade(1)]),trades:[{...trade(1),contextClosedUTC:{H1:iso(start+3600000)}}]},
 {...packet([trade(1)]),trades:[{...trade(1),contextFirstObservedUTC:{H1:iso(start+3600000),H4:"not-a-time"}}]},
 {...packet([trade(1)]),trades:[{...trade(1),contextClosedUTC:{H1:iso(start+3600000+900000),H4:iso(start)}}]},
 {...packet([trade(1)]),trades:[{...trade(1),contextClosedUTC:{H1:iso(start+3600000),H4:iso(start+14400000)}}]},
 {...packet([trade(1)]),trades:[{...trade(1),contextFirstObservedUTC:{H1:iso(start+3600000+60000),H4:iso(start)}}]},
 {...packet([trade(1)]),trades:[{...trade(1),contextFirstObservedUTC:{H1:iso(start+3600000),H4:iso(start+3600000+60000)}}]},
 {...packet([trade(1)]),trades:[{...trade(1),decisionUTC:iso(start+3600000+120000)}]},
 {...packet([trade(1)]),trades:[{...trade(1),spreadUsd:-1}]},
 {...packet([trade(1)]),trades:[{...trade(1),commissionUsd:NaN}]},
 {...packet([trade(1)]),trades:[{...trade(1),initialRiskUsd:0}]},
 {...packet([trade(1)]),trades:[{...trade(1),initialRiskUsd:0.00001}]},
 {...packet([trade(1)]),trades:[{...trade(1),initialRiskUsd:Number.MIN_VALUE}]},
 // A stale M15 closed candle must not be used to justify a fresh order.
 {...packet([trade(1)]),trades:[{...trade(1),signalClosedUTC:iso(start),
    signalFirstObservedUTC:iso(start)}]},
 // H1 or H4 must also be sufficiently recent for the decision.
 {...packet([trade(2)]),trades:[{...trade(2),
    contextClosedUTC:{H1:iso(start),H4:iso(start)},
    contextFirstObservedUTC:{H1:iso(start),H4:iso(start)}}]},
 {...packet([trade(5)]),trades:[{...trade(5),
    contextClosedUTC:{H1:iso(start+5*3600000),H4:iso(start)},
    contextFirstObservedUTC:{H1:iso(start+5*3600000),H4:iso(start)}}]},
 {...packet([trade(1)]),trades:[{...trade(1),side:"WAIT"}]},
 {...packet([trade(1)]),trades:[{...trade(1),grossPnLUsd:"2"}]},
 {...packet([trade(1)]),trades:Array.from({length:2001},()=>trade(1))}
 ]){
  const x=evaluate(data);safe(x);
  a.equal(x.status,"BLOCKED");
}
// Trade 2 cannot claim a completed past result when it made its
// decision BEFORE the independent first-observed close of trade 1.
const second={...trade(2),
 decisionUTC:iso(start+3600000+1800000+30000),
 signalClosedUTC:iso(start+3600000+1800000),
 signalFirstObservedUTC:iso(start+3600000+1800000),
 contextClosedUTC:{H1:iso(start+3600000),H4:iso(start)},
 contextFirstObservedUTC:{H1:iso(start+3600000),H4:iso(start)}
};
const pastOutcomeNotYetKnown=evaluate(packet([trade(1),second]));
safe(pastOutcomeNotYetKnown);
a.equal(pastOutcomeNotYetKnown.status,"BLOCKED");
a.equal(pastOutcomeNotYetKnown.reason,"LOOKAHEAD_OR_NONCHRONOLOGICAL_PAPER_TRADE");
const pennyRisk=evaluate(packet([{...trade(1),initialRiskUsd:0.01}]));
safe(pennyRisk);
a.equal(pennyRisk.status,"UNATTESTED_PAPER_ARITHMETIC_ONLY");
a(Number.isFinite(pennyRisk.statistics.averageNetR));
const missingContext=evaluate({...packet([trade(1)]),trades:[{
 ...trade(1),contextFirstObservedUTC:{H1:iso(start+3600000),H4:iso(start+3600000+60000)}
}]});
a.equal(missingContext.reason,"MULTITIMEFRAME_CONTEXT_NOT_KNOWN_AT_DECISION");
console.log("PASS sanitized prospective paper arithmetic: costs, net R, drawdown, chronology, no source/trading authorization");
