"use strict";
const a=require("node:assert/strict");
const {observe}=require("./biquote_private_v3_watch");
const ASOF="2026-11-10T12:00:00Z", T=Date.parse(ASOF);
const W={M15:900000,H1:3600000,H4:14400000};
function fixture(){
 const chart=Object.fromEntries(Object.entries(W).map(([tf,width])=>
  [tf,Array.from({length:30},(_,i)=>{
   const bar={time:new Date(T-(30-i)*width).toISOString(),
    open:100,high:101,low:99,close:100};
   if(i===22)bar.high=103;
   if(i===29){bar.high=105;bar.close=104;}
   return bar;
  })]));
 return {origin:"AUTHENTICATED_PERSONAL_BIQUOTE_PRIVATE_CHART",
  priceBasis:"MID_WITH_POSSIBLE_BID_SEED",asOfUTC:ASOF,chart,
  sourceSnapshotStatus:"OBSERVED_READONLY_UNVERIFIED",
  sourceCrossFrameComparisons:{
   H1:{completeMatches:12,completeMismatches:0,
       incompleteM15Groups:0,outsideRetentionWindow:12},
   H4:{completeMatches:2,completeMismatches:0,
       incompleteM15Groups:0,outsideRetentionWindow:25}
  },
  secret:"DO_NOT_LEAK",brokerSignal:"BUY",riskApproved:true};
}
function secure(x){
 a.equal(x.signal,"WAIT");a.equal(x.executable,false);
 a.equal(x.tradeEligible,false);a.equal(x.paperOrdersAllowed,false);
 a.equal(x.liveOrdersAllowed,false);a.equal(x.brokerOrdersSent,0);
 a.equal(x.paperOrdersSent,0);a.equal(x.providerRequestsMade,0);
 a.equal(x.sourceRightsVerified,false);
 a.equal(x.firstSeenAtDecisionVerified,false);
 a.equal(x.independentBrokerCalendarVerified,false);
 a.equal(x.brokerBidAskCostsVerified,false);
 a.equal(x.forwardPerformanceProven,false);
 a.equal(x.retrospectiveOnly,true);
 for(const p of ["entry","stopLoss","takeProfit"])a.equal(x[p],null);
 const encoded=JSON.stringify(x);
 for(const privateData of ['"open"','"high"','"low"','"close"','"bid"',
  '"ask"','"secret"','DO_NOT_LEAK'])
  a(!encoded.includes(privateData));
}
const yes=observe(fixture());secure(yes);
a.equal(yes.status,"TECHNICAL_WATCH_ONLY_NOT_TRADE_READY");
a.equal(yes.technicalCandidate,"BUY");
a.equal(yes.watchLabel,"WATCH_BUY");
a.equal(yes.lastCrossFrameParityObserved,true);
// An OLD H4 or H1 mismatch discovered by the whole source window must
// veto WATCH even if the latest 16 M15 bars and the last H4 agree.
for(const tf of ["H1","H4"]){
 const earlierBad=fixture();
 earlierBad.sourceSnapshotStatus="WAIT_CROSS_FRAME_GAPS";
 earlierBad.sourceCrossFrameComparisons[tf].completeMismatches=1;
 earlierBad.sourceCrossFrameComparisons[tf].completeMatches=1;
 const veto=observe(earlierBad);secure(veto);
 a.equal(veto.technicalCandidate,"NONE");
 a.equal(veto.watchLabel,"WAIT");
 a.equal(veto.status,"WAIT_CROSS_FRAME_EVIDENCE");
 a.equal(veto.reason,"SOURCE_HAS_UNRESOLVED_CROSS_FRAME_GAPS");
 const forgedClear=fixture();
 forgedClear.sourceCrossFrameComparisons[tf].completeMismatches=1;
 const vetoSource=observe(forgedClear);secure(vetoSource);
 a.equal(vetoSource.watchLabel,"WAIT");
 a.equal(vetoSource.reason,"HISTORICAL_CROSS_FRAME_GAPS_OR_PRICE_MISMATCH");
}
const missingOld=fixture();
missingOld.sourceCrossFrameComparisons.H4.incompleteM15Groups=1;
const missingOldResult=observe(missingOld);secure(missingOldResult);
a.equal(missingOldResult.watchLabel,"WAIT");
a.equal(missingOldResult.reason,"HISTORICAL_CROSS_FRAME_GAPS_OR_PRICE_MISMATCH");
for(const mutated of [
 x=>{delete x.sourceCrossFrameComparisons;},
 x=>{x.sourceCrossFrameComparisons.H1.completeMatches=-1;},
 x=>{x.sourceCrossFrameComparisons.H4.completeMismatches="0";},
 x=>{x.sourceCrossFrameComparisons.H4.extra=999;},
 x=>{x.sourceCrossFrameComparisons.H4.completeMatches=0;}
]){
 const v=fixture();mutated(v);const blocked=observe(v);secure(blocked);
 a.equal(blocked.watchLabel,"WAIT");
}

const down=fixture();
for(const tf of Object.keys(W)){
 const row=down.chart[tf];
 row[22].low=97;
 row[22].high=101;
 row[29].high=101;row[29].low=95;row[29].close=96;
}
const sell=observe(down);secure(sell);
a.equal(sell.watchLabel,"WATCH_SELL");
a.equal(sell.technicalCandidate,"SELL");
const neutral=fixture();
for(const tf of Object.keys(W)){
 neutral.chart[tf][22].high=101;
 neutral.chart[tf][29].high=101;
 neutral.chart[tf][29].close=100;
}
const flat=observe(neutral);secure(flat);
a.equal(flat.watchLabel,"WAIT");
a.equal(flat.technicalCandidate,"NONE");
// Invalid gap or stale quote MUST NEVER yield BUY or SELL.
const attack=[
 x=>{x.origin="ANONYMOUS_PUBLIC_VISITOR";},
 x=>{x.priceBasis="YAHOO_SYNTHETIC";},
 x=>{x.asOfUTC="BAD";},
 x=>{x.chart.M15.pop();},
 x=>{x.chart.M15.splice(19,1);},
 x=>{x.chart.H4.splice(15,1);},
 x=>{x.chart.M15.at(-1).high=200;},
 x=>{x.chart.H1.at(-1).high=200;},
 x=>{x.chart.H4.at(-1).high=200;},
 x=>{x.chart.M15.at(-1).time=ASOF;},
 x=>{x.chart.M15.at(-1).close=NaN;},
 x=>{x.chart.M15[0].low=200;},
 x=>{x.asOfUTC="2026-11-10T13:05:00Z";},
 x=>{delete x.chart.H4;},
];
for(const mutate of attack){
 const sample=fixture();mutate(sample);
 const rejected=observe(sample);secure(rejected);
 a.equal(rejected.technicalCandidate,"NONE");
 a.equal(rejected.watchLabel,"WAIT");
}
const invalid=observe(null);secure(invalid);
a.equal(invalid.status,"BLOCKED");
console.log("PASS authenticated-only frozen V3 BUY/SELL WATCH and strict WAIT malformed, gaps, OHLC mismatch, stale; no orders or levels");
