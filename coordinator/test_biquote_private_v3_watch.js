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
