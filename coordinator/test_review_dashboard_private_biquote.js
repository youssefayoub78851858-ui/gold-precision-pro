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
 // 48 M15 bars contain 11 full H1 and 2 full H4 windows.
 // Source-wide summaries may cover more than the private display window.
 const h1={completeMatches:11,completeMismatches:0,
   incompleteM15Groups:0,outsideRetentionWindow:54};
 const h4={completeMatches:2,completeMismatches:0,
   incompleteM15Groups:0,outsideRetentionWindow:63};
 return {signal:"WAIT",executable:false,researchEligible:false,
  tradePlanExecutable:false,paperOrdersAllowed:false,
  orderEndpointsCalled:false,status:"OBSERVED_READONLY_UNVERIFIED",
  rawQuoteShown:true,privateChartReadOnly:true,
  privateChartDataBasis:"MID_WITH_POSSIBLE_BID_SEED",
  bid:1999.9,ask:2000.2,spread:0.3,
  quoteAgeSeconds:1.5,observedUTC:new Date(NOW).toISOString(),
  quoteUTC:new Date(NOW-1500).toISOString(),privateChart:chart,
  frameSummary:summary,
  crossFrameComparisons:{H1:{...h1},H4:{...h4}},
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
const completeAudit=mod.localCoveredParityAudit(good.chart);
a.deepEqual(completeAudit,{
 H1:{fullyCovered:11,disagreed:0},
 H4:{fullyCovered:2,disagreed:0}
});
a.match(mod.researchWatch(good),/^WAIT · WATCH_BUY/);
// Vendor-declared H4 closure count can be shown descriptively ONLY;
// unverified broker-calendar/rights assertions must not be reflected.
const h4Times=[
 "2026-11-20T16:00:00Z","2026-11-20T20:00:00Z",
 "2026-11-22T20:00:00Z","2026-11-23T00:00:00Z",
 "2026-11-23T04:00:00Z"
].map(t=>({t:Date.parse(t)}));
const vendorBase={
 mode:"BIQUOTE_VENDOR_DECLARED_H4_ADJACENCY_RESEARCH_ONLY",
 status:"PROVIDER_DECLARED_PAUSE_SCENARIO_NOT_TRADING_PROOF",
 signal:"WAIT",executable:false,
 originalBrokerIdentified:false,originalBrokerCalendarVerified:false,
 brokerMarketDataRightsVerified:false,all21H4M15ParityVerified:false,
 perBarFirstSeenVerified:false,researchWarmupApproved:false,
 paperOrdersAllowed:false,liveOrdersAllowed:false,
 brokerOrdersSent:0,paperOrdersSent:0,providerRequestsMade:0,
 missingCandlesSynthesized:0,
 observedClosedH4Bars:5,strictUtcH4Tail:3,
 providerDeclaredSessionAdjacentH4Tail:5,
 providerDeclaredPauseGapPairs:1,providerDeclaredPauseMissingH4Slots:11,
 unexplainedGapPairs:0,unknownCalendarGapPairs:0,
 providerScenarioReached21H4:false,
 token:"H4_PRIVATE_DO_NOT_RENDER"
};
const label=mod.vendorH4SessionLabel({
 chart:{H4:h4Times},d:{privateVendorH4Tail:vendorBase}
});
a.match(label,/UTC متتالية: 3/);
a.match(label,/حسب استراحات BiQuote: 5/);
a.match(label,/حقوق المصدر غير مثبتين/);
a(!label.includes("H4_PRIVATE_DO_NOT_RENDER"));
for(const mutate of [
 v=>{v.signal="BUY";},
 v=>{v.executable=true;},
 v=>{v.originalBrokerCalendarVerified=true;},
 v=>{v.brokerMarketDataRightsVerified=true;},
 v=>{v.researchWarmupApproved=true;},
 v=>{v.providerScenarioReached21H4=true;},
 v=>{v.strictUtcH4Tail=4;},
 v=>{v.providerDeclaredSessionAdjacentH4Tail=100;},
 v=>{v.observedClosedH4Bars=50;},
 v=>{v.missingCandlesSynthesized=1;}
]){
 const v=structuredClone(vendorBase);mutate(v);
 a.match(mod.vendorH4SessionLabel({chart:{H4:h4Times},
  d:{privateVendorH4Tail:v}}),/جدول وسيط MT5 غير مثبت/);
}
a.match(mod.vendorH4SessionLabel(good),/جدول وسيط MT5 غير مثبت/);

// Even an older fully covered H1 or H4 disagreement, outside the last
// H1/H4 but inside the private M15 snapshot, MUST suppress WATCH.
for(const mutate of [
 x=>{x.privateChart.H1[41].high=2004;},
 x=>{x.privateChart.H4[46].high=2004;},
 x=>{x.privateChart.M15[25].high=2004;}
]){
 const x=packet();mutate(x);
 const checked=mod.validateSnapshot(x,NOW);
 a(checked);a.equal(mod.localLatestParity(checked.chart),true);
 const audit=mod.localCoveredParityAudit(checked.chart);
 a(audit.H1.disagreed+audit.H4.disagreed>0);
 a(!mod.researchWatch(checked).includes("WATCH_BUY"));
}
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
 x=>{x.spread=5;},
 x=>{x.spread="0.3";},
 x=>{x.crossFrameComparisons.H4.outsideRetentionWindow=62;},
 x=>{x.frameSummary.H1.closedCount=66;},
 x=>{x.status="WAIT_CROSS_FRAME_GAPS";},
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
 x=>{x.status="WAIT_CROSS_FRAME_GAPS";
       x.crossFrameComparisons.H1.incompleteM15Groups=1;
       x.crossFrameComparisons.H1.outsideRetentionWindow=53;},
 x=>{x.status="WAIT_CROSS_FRAME_GAPS";
       x.crossFrameComparisons.H4.completeMismatches=1;
       x.crossFrameComparisons.H4.outsideRetentionWindow=62;},
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
 "reason","decision","quality-status","chart-status","refresh",
 "data-state","trend-status","watch-status","parity-status",
 "vendor-h4-session","technical-short","technical-note","auto-state",
 ...["m15","h1","h4"].flatMap(tf=>
   ["technical","ema","rsi","atr","technical-quality"].map(s=>tf+"-"+s))
 ].map(k=>[k,new Node()]));
const tabs=["15min","1h","4h"].map(tf=>{
 const n=new Node();n.dataset.frame=tf;return n;
});
const documentEvents={};
const windowEvents={};
const document={
 visibilityState:"visible",
 getElementById:id=>nodes[id]||null,
 querySelectorAll:x=>x==="[data-frame]"?tabs:[],
 createElementNS:()=>new Node(),
 addEventListener:(n,fn)=>{documentEvents[n]=fn;}
};
const window={addEventListener:(n,fn)=>{windowEvents[n]=fn;}};
const script=fs.readFileSync("review-dashboard.js","utf8");
const NativeDate=Date;
let timeNow=NOW;
class Clock extends NativeDate {static now(){return timeNow;}}
let calls=[];
let intervalCallback=null;
const context={document,window,Date:Clock,Intl,console,
 setInterval:(fn)=>{intervalCallback=fn;return 1;},
 AbortSignal:{timeout:()=>({})},
 fetch:async(url,options)=>{
  calls.push({url,options});
  return {status:200,headers:{get:key=>key==="content-type"?
     "application/json; charset=utf-8":null},json:async()=>packet()};
 }};
vm.runInNewContext(script,context,{timeout:3000});
a.equal(calls.length,0,"NO background market calls");
a.equal(nodes.decision.textContent,"WAIT");
a.equal(nodes.price.textContent,"غير متاح");
a.match(nodes["vendor-h4-session"].textContent,/جدول وسيط MT5 غير مثبت/);
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
 a.equal(nodes["technical-short"].textContent,"3/3 مرصودة");
 a.notEqual(nodes["m15-ema"].textContent,"—");
 a.notEqual(nodes["h1-rsi"].textContent,"—");
 a.notEqual(nodes["h4-atr"].textContent,"—");
 a(nodes.reason.textContent.includes("WATCH_BUY"));
 a.match(nodes["vendor-h4-session"].textContent,/جدول وسيط MT5 غير مثبت/);
 a(!JSON.stringify(nodes).includes("NOT_FOR_UI"));
 tabs[1].handlers.click();
 a(nodes["chart-status"].textContent.startsWith("H1"));
 // Stage 3: Android throttles timers in the background. A user
 // selecting a timeframe after expiry must synchronously wipe ALL
 // private prices and WATCH, without any new upstream request.
 timeNow=NOW+20000;
 tabs[0].handlers.click();
 a(nodes.price.textContent.includes("2,000"),"Old historical close remains visible");
 a.equal(nodes["technical-short"].textContent,"3/3 مرصودة");
 a.notEqual(nodes["m15-ema"].textContent,"—");
 a.match(nodes["data-state"].textContent,/قديمة/);
 a.equal(nodes["watch-status"].textContent,"WAIT · لا فرصة صالحة");
 a(!nodes.reason.textContent.includes("WATCH_BUY"));
 a.match(nodes["vendor-h4-session"].textContent,/جدول وسيط MT5 غير مثبت/);
 a.equal(calls.length,1,"No background refresh on tab switch");
 timeNow=NOW;
 await nodes.refresh.handlers.click();
 a(nodes.price.textContent.includes("2,000"));
 document.visibilityState="hidden";
 documentEvents.visibilitychange();
 a.equal(nodes.price.textContent,"غير متاح");
 a(!nodes.reason.textContent.includes("WATCH_BUY"));
 a.equal(calls.length,2);
 document.visibilityState="visible";
 await nodes.refresh.handlers.click();
 a(nodes.price.textContent.includes("2,000"));
 windowEvents.pagehide();
 a.equal(nodes.price.textContent,"غير متاح");
 a.equal(calls.length,3);
 await nodes.refresh.handlers.click();
 a(nodes.price.textContent.includes("2,000"));
 timeNow=NOW+20000;
 windowEvents.focus();
 a(nodes.price.textContent.includes("2,000"));
 a.match(nodes["data-state"].textContent,/قديمة/);
 a(!nodes.reason.textContent.includes("WATCH_BUY"));
 a.equal(calls.length,4);
 a.equal(typeof intervalCallback,"function");
 intervalCallback();
 a.equal(calls.length,4);
 timeNow=NOW;
 // New browser session lacking a valid viewer cookie cannot reveal prices.
 context.fetch=async()=>({status:200,
  headers:{get:()=> "application/json; charset=utf-8"},json:async()=>({
  signal:"WAIT",executable:false,rawQuoteShown:false})});
 await nodes.refresh.handlers.click();
 a.equal(nodes.price.textContent,"غير متاح");
 a.equal(nodes.decision.textContent,"WAIT");
 a(!nodes.reason.textContent.includes("WATCH_BUY"));
 // STAGE 2: Android BFCache/pagehide during the network fetch. The late
 // success is discarded even if the response was fully valid at request time.
 let finishFetch;let delayedRequests=0;
 context.fetch=()=>{delayedRequests++;
   return new Promise(resolve=>{finishFetch=resolve;});};
 const pendingPagehide=nodes.refresh.handlers.click();
 a.equal(typeof finishFetch,"function");
 windowEvents.pagehide();
 finishFetch({status:200,
  headers:{get:()=> "application/json; charset=utf-8"},
  json:async()=>packet()});
 await pendingPagehide;
 a.equal(nodes.price.textContent,"غير متاح");
 a.equal(nodes["watch-status"].textContent,"WAIT");
 a(!nodes.reason.textContent.includes("WATCH_BUY"));
 a.equal(delayedRequests,1);
 // STAGE 3: the fetch completes, but the JSON body is still resolving
 // when a user hides then shows the app again. The old generation may
 // never fill the private chart or WATCH, even if the tab is now visible.
 let finishJSON;
 context.fetch=()=>{delayedRequests++;
   return Promise.resolve({status:200,
    headers:{get:()=> "application/json; charset=utf-8"},
    json:()=>new Promise(resolve=>{finishJSON=resolve;})});
 };
 const pendingHidden=nodes.refresh.handlers.click();
 for(let i=0;i<6&&!finishJSON;i++)await Promise.resolve();
 a.equal(typeof finishJSON,"function");
 document.visibilityState="hidden";
 documentEvents.visibilitychange();
 document.visibilityState="visible";
 finishJSON(packet());
 await pendingHidden;
 a.equal(nodes.price.textContent,"غير متاح");
 a.equal(nodes.decision.textContent,"WAIT");
 a(!nodes.reason.textContent.includes("WATCH_BUY"));
 a.equal(delayedRequests,2);
 // A NEW user click can still fetch; old replies never linger after it.
 context.fetch=async()=>({status:200,
  headers:{get:()=> "application/json; charset=utf-8"},
  json:async()=>packet()});
 await nodes.refresh.handlers.click();
 a(nodes.price.textContent.includes("2,000"));
 a(nodes.reason.textContent.startsWith("WAIT"));
 a.equal(nodes.decision.textContent,"WAIT");
 windowEvents.pagehide();
 a.equal(nodes.price.textContent,"غير متاح");

 // Auto-start must check HttpOnly viewer session first, then poll read-only
 // observations every minute only while the page is visible.
 timeNow=NOW;
 const autoCalls=[];
 context.fetch=async(url,options)=>{
  autoCalls.push({url,options});
  if(url==="/api/v3/ultimate/biquote-viewer-status")
   return {status:200,json:async()=>({signal:"WAIT",executable:false,
      viewerSessionReady:true,marketDataRequested:false,ordersSent:0})};
  const x=packet();
  x.observedUTC=new Date(timeNow).toISOString();
  x.quoteUTC=new Date(timeNow-1500).toISOString();
  return {status:200,headers:{get:k=>k==="content-type"?
     "application/json; charset=utf-8":null},json:async()=>x};
 };
 documentEvents.DOMContentLoaded();
 for(let i=0;i<25;i++)await Promise.resolve();
 a.equal(autoCalls[0]?.url,"/api/v3/ultimate/biquote-viewer-status");
 a.equal(autoCalls[0]?.options.credentials,"same-origin");
 a.equal(autoCalls.filter(x=>x.url==="/api/v3/ultimate/biquote-observation").length,1);
 a(nodes.price.textContent.includes("2,000"),"Auto startup displays closed bars");
 timeNow=NOW+61000;
 intervalCallback();
 for(let i=0;i<25;i++)await Promise.resolve();
 a.equal(autoCalls.filter(x=>x.url==="/api/v3/ultimate/biquote-observation").length,2);
 a.equal(nodes.decision.textContent,"WAIT");
 document.visibilityState="hidden";
 documentEvents.visibilitychange();
 const n=autoCalls.length;
 timeNow=NOW+122000;intervalCallback();
 a.equal(autoCalls.length,n,"No polling while tab hidden");
 a.equal(nodes.price.textContent,"غير متاح","Hidden privacy wipe");
 document.visibilityState="visible";
 documentEvents.visibilitychange();
 for(let i=0;i<25;i++)await Promise.resolve();
 a.equal(autoCalls.filter(x=>x.url==="/api/v3/ultimate/biquote-viewer-status").length,2);
 a.equal(autoCalls.filter(x=>x.url==="/api/v3/ultimate/biquote-observation").length,3);
 a.equal(nodes.decision.textContent,"WAIT");
 windowEvents.pagehide();
 console.log("PASS private mobile candle data gates, older H4 parity, Android BFCache/in-flight cancellation, no background requests and zero orders");
})().catch(e=>{console.error(e);process.exitCode=1;});
