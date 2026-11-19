"use strict";
const a=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const mod=require("../review-dashboard.js");
const W={M15:900000,H1:3600000,H4:14400000};
const NOW=Date.parse("2026-11-19T20:59:50.000Z");
function packet(){
 const chart={};
 const summary={};
 for(const [tf,width] of Object.entries(W)){
  const latestOpen=Math.floor(NOW/width)*width-width;
  chart[tf]=Array.from({length:48},(_,i)=>({
   time:new Date(latestOpen-(47-i)*width).toISOString(),
   open:2000,high:2001,low:1999,close:2000
  }));
  summary[tf]={closedCount:65,
   lastClosedUTC:new Date(latestOpen+width).toISOString(),
   priceBasis:"MID_WITH_POSSIBLE_BID_SEED"};
 }
 const c={completeMatches:4,completeMismatches:0,
   incompleteM15Groups:0,outsideRetentionWindow:50};
 return {signal:"WAIT",executable:false,researchEligible:false,
  tradePlanExecutable:false,paperOrdersAllowed:false,
  orderEndpointsCalled:false,status:"OBSERVED_READONLY_UNVERIFIED",
  rawQuoteShown:true,privateChartReadOnly:true,
  privateChartDataBasis:"MID_WITH_POSSIBLE_BID_SEED",
  bid:1999.9,ask:2000.2,
  quoteAgeSeconds:1.5,observedUTC:new Date(NOW).toISOString(),
  quoteUTC:new Date(NOW-1500).toISOString(),privateChart:chart,
  frameSummary:summary,
  crossFrameComparisons:{H1:{...c},H4:{...c}},
  privateTechnicalWatch:{
   mode:"PRIVATE_FROZEN_V3_TECHNICAL_WATCH_ONLY",
   status:"TECHNICAL_WATCH_ONLY_NOT_TRADE_READY",
   signal:"WAIT",executable:false,tradeEligible:false,
   paperOrdersAllowed:false,liveOrdersAllowed:false,
   sourceRightsVerified:false,firstSeenAtDecisionVerified:false,
   independentMacroNewsGcOrderFlowVerified:false,
   brokerBidAskCostsVerified:false,retrospectiveOnly:true,
   entry:null,stopLoss:null,takeProfit:null,
   brokerOrdersSent:0,providerRequestsMade:0,
   requiredM15ToReconcile21H4:336,requiredH1ToReconcile21H4:84,
   privateChartMaxBarsPerFrame:48,
   full21H4CrossFrameAuditPossibleFromPrivateSnapshot:false,
   technicalCandidate:"BUY",watchLabel:"WATCH_BUY",
   lastCrossFrameParityObserved:true
  },
  secret:"NOT_FOR_UI"
 };
}
const good=mod.validateSnapshot(packet(),NOW);
a(good,"full private valid snapshot");
a.equal(good.chart.M15.length,48);
a.equal(mod.localLatestParity(good.chart),true);
a.match(mod.researchWatch(good),/^WAIT · WATCH_BUY/);
// Even perfectly clean (but forged) source-wide overlap counters must
// not override a price conflict in the latest closed H1, last H4, or
// one of the H1 constituents of the last H4 in the private local chart.
for(const mutate of [
 x=>{x.privateChart.H1[47].high=2004;},
 x=>{x.privateChart.H4[47].high=2004;},
 x=>{x.privateChart.H1[44].close=2000.4;},
 x=>{x.privateChart.M15[42].high=2004;},
 x=>{x.privateChart.M15[44].close=2000.4;}
]){
 const x=packet();mutate(x);
 const checked=mod.validateSnapshot(x,NOW);
 a(checked,"Row geometry is valid; discrepancy only emerges from cross-frame parity");
 a.equal(mod.localLatestParity(checked.chart),false);
 const veto=mod.researchWatch(checked);
 a.match(veto,/^WAIT/);
 a(!veto.includes("WATCH_BUY"),"Contradictory closed OHLC must veto technical WATCH");
}

// Modifying only an internal M15 *close*, without changing the first
// open, final close, maximum high or minimum low, cannot be detected by
// OHLC parity alone. No independent tick-level validity is claimed.
const hiddenInterior=packet();
hiddenInterior.privateChart.M15[42].close=2000.4;
const interior=mod.validateSnapshot(hiddenInterior,NOW);
a(interior);
a.equal(mod.localLatestParity(interior.chart),true);
// This is still never a real trade: the WATCH label remains retrospective.
a.equal(interior.d.signal,"WAIT");a.equal(interior.d.executable,false);
for(const mutate of [
 x=>{x.signal="BUY";},x=>{x.executable=true;},
 x=>{x.tradePlanExecutable=true;},x=>{x.rawQuoteShown=false;},
 x=>{x.privateChartReadOnly=false;},x=>{x.ask=x.bid-1;},
 x=>{x.quoteAgeSeconds=31;},
 x=>{x.observedUTC=new Date(NOW-61000).toISOString();},
 x=>{x.quoteUTC=new Date(NOW+3000).toISOString();},
 x=>{x.privateChart.M15[47].time=x.privateChart.M15[46].time;},
 x=>{x.privateChart.M15[47].close=NaN;},
 x=>{x.privateChart.M15[47].low=3000;},
 x=>{x.privateChart.H4[47].time=new Date(NOW).toISOString();},
 x=>{x.frameSummary.H4.lastClosedUTC="2026-11-10T00:00:00.000Z";},
 x=>{x.frameSummary.H4.closedCount=1;},
 x=>{x.privateChart.M15.push(x.privateChart.M15[47]);},
 x=>{delete x.privateChart.H1;},
 x=>{x.crossFrameComparisons.H1.completeMatches="not_a_number";},
 x=>{x.crossFrameComparisons.H4.completeMismatches=-1;}
]){
 const x=packet();mutate(x);
 a.equal(mod.validateSnapshot(x,NOW),null);
}
for(const mutate of [
 x=>{x.status="WAIT_CROSS_FRAME_GAPS";},
 x=>{x.crossFrameComparisons.H1.incompleteM15Groups=1;},
 x=>{x.crossFrameComparisons.H4.completeMismatches=1;},
 x=>{x.privateTechnicalWatch.entry=2000;},
 x=>{x.privateTechnicalWatch.paperOrdersAllowed=true;},
 x=>{x.privateTechnicalWatch.requiredM15ToReconcile21H4=48;}
]){
 const x=packet();mutate(x);
 const r=mod.validateSnapshot(x,NOW);
 a(r);const display=mod.researchWatch(r);
 a.match(display,/^WAIT/);a(!display.includes("WATCH_BUY"));
}
// Simulated DOM: no fetch or token on page init; ONE existing read-only
// same-origin request on user click, owner candles only, never BUY order.
class Node {
 constructor(){this.textContent="";this.nodes=[];this.handlers={};this.dataset={};this.attrs={};this.disabled=false;}
 addEventListener(n,fn){this.handlers[n]=fn;}
 setAttribute(k,v){this.attrs[k]=v;}
 appendChild(n){this.nodes.push(n);}
 replaceChildren(){this.nodes=[];}
}
const nodes=Object.fromEntries(["candles","price","timestamp","source",
 "reason","decision","quality-status","chart-status","refresh"].map(k=>[k,new Node()]));
const tabs=["15min","1h","4h"].map(tf=>{
 const n=new Node();n.dataset.frame=tf;return n;
});
const document={
 getElementById:id=>nodes[id]||null,
 querySelectorAll:x=>x==="[data-frame]"?tabs:[],
 createElementNS:()=>new Node()
};
const script=fs.readFileSync("review-dashboard.js","utf8");
const NativeDate=Date;
class Clock extends NativeDate {static now(){return NOW;}}
let calls=[];
const context={document,Date:Clock,Intl,console,
 setInterval:()=>null,
 AbortSignal:{timeout:()=>({})},
 fetch:async(url,options)=>{
  calls.push({url,options});
  return {status:200,json:async()=>packet()};
 }};
vm.runInNewContext(script,context,{timeout:3000});
a.equal(calls.length,0,"NO background market calls");
a.equal(nodes.decision.textContent,"WAIT");
a.equal(nodes.price.textContent,"غير متاح");
(async()=>{
 await nodes.refresh.handlers.click();
 a.equal(calls.length,1);
 a.equal(calls[0].url,"/api/v3/ultimate/biquote-observation");
 a.equal(calls[0].options.credentials,"same-origin");
 a.equal(calls[0].options.method,"GET");
 a.equal(calls[0].options.cache,"no-store");
 a(!JSON.stringify(calls).includes("Authorization"));
 a.equal(nodes.decision.textContent,"WAIT");
 a(nodes.price.textContent.includes("2,000"));
 a(nodes.reason.textContent.includes("WATCH_BUY"));
 a(!JSON.stringify(nodes).includes("NOT_FOR_UI"));
 tabs[1].handlers.click();
 a(nodes["chart-status"].textContent.startsWith("H1"));
 // New browser session lacking a valid viewer cookie cannot reveal prices.
 context.fetch=async()=>({status:200,json:async()=>({
  signal:"WAIT",executable:false,rawQuoteShown:false})});
 await nodes.refresh.handlers.click();
 a.equal(nodes.price.textContent,"غير متاح");
 a.equal(nodes.decision.textContent,"WAIT");
 a(!nodes.reason.textContent.includes("WATCH_BUY"));
 console.log("PASS secure on-demand private mobile candles; anonymous, stale, forged data WAIT; no background fetch, token, paper or broker orders");
})().catch(e=>{console.error(e);process.exitCode=1;});
