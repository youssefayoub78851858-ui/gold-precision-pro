"use strict";
// BiQuote private live candle UI smoke: mocked network, no market/order calls.
const assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm"),path=require("node:path");
const NOW=Date.now();
const {analyzeChart}=require("./coordinator/biquote_private_structure");
const {examine}=require("./coordinator/biquote_observed_ema_reference");
const {evaluateFrames}=require("./coordinator/biquote_vendor_declared_session");
const {makeMtfReadiness}=require("./coordinator/biquote_mtf_readiness");
const widths={M15:900000,H1:3600000,H4:14400000};
let candleDraws=0,blankMessages=0;
function makeCanvas(){
 const ctx={
   setTransform(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},
   fillRect(){candleDraws++;},fillText(t){if(t.includes("لا توجد شموع"))blankMessages++;},
   set fillStyle(_v){},set strokeStyle(_v){},set font(_v){},set textAlign(_v){}
 };
 return {clientWidth:360,clientHeight:285,width:0,height:0,getContext:()=>ctx};
}
const elements=new Map();
function makeNode(id){
 if(elements.has(id))return elements.get(id);
 const handlers={};
 const node={id,value:"",disabled:false,textContent:"",dataset:{},setAttribute(k,v){this[k]=v},
   addEventListener(e,fn){handlers[e]=fn},click(){return handlers.click?.()},
   ...id==="biquote-live-canvas"?makeCanvas():{}};
 elements.set(id,node);return node;
}
const ids=["biquote-refresh","biquote-viewer-secret","biquote-viewer-logout","biquote-viewer-session-state","biquote-live-canvas",
"biquote-live-caption","biquote-structure-summary","biquote-mtf-readiness","biquote-observed-ema","biquote-vendor-session","biquote-status","biquote-private-quote",
"biquote-private-spread","biquote-observed","biquote-m15","biquote-h1",
"biquote-h4","biquote-overlap"];
ids.forEach(makeNode);
const tabs=["M15","H1","H4"].map(tf=>{
 const t=makeNode("tab-"+tf);t.dataset.biqFrame=tf;return t;
});
const frameSummary=Object.fromEntries(Object.entries(widths).map(([tf,w])=>[tf,{
 closedCount:60,lastClosedUTC:new Date(Math.floor(NOW/w)*w).toISOString(),
 descriptiveTrend:"DOWN",unclassifiedCalendarGaps:0
}]));
function chart(){
 return Object.fromEntries(Object.entries(widths).map(([tf,w])=>{
   const end=Math.floor(NOW/w)*w;
   const rows=Array.from({length:48},(_,i)=>{
     const value=3900+i*0.2;
     return {time:new Date(end-(48-i)*w).toISOString(),
       open:value,high:value+0.6,low:value-0.4,close:value+0.1};
   });
   if(networkMode==="authorized-gapped" && tf!=="M15"){
     // Unknown session pause. A gap before the last 10 CLOSED bars
     // may not be silently bridged by technical indicators.
     for(let i=0;i<38;i++)rows[i].time=
       new Date(Date.parse(rows[i].time)-w).toISOString();
   }
   return [tf,rows];
 }));
}
const base={status:"WAIT_CROSS_FRAME_GAPS",signal:"WAIT",executable:false,
 researchEligible:false,tradePlanExecutable:false,paperOrdersAllowed:false,
 orderEndpointsCalled:false,observedUTC:new Date(NOW).toISOString(),
 quoteAgeSeconds:1,frameSummary,
 crossFrameComparisons:{
   H1:{completeMatches:40,completeMismatches:0,incompleteM15Groups:0},
   H4:{completeMatches:8,completeMismatches:0,incompleteM15Groups:3}
 }};
let networkMode="anonymous",requests=[],sessionActive=false,sessionLogins=0;
async function fetch(url,opts){
 requests.push({url,opts});
 if(url==="/api/v3/ultimate/biquote-viewer-session"){
   assert.equal(opts.credentials,"same-origin");
   if(opts.method==="POST"){
     assert.equal(opts.headers.Authorization,"Bearer "+("a".repeat(40)));
     sessionActive=true;sessionLogins++;
     return {ok:true,status:200,async json(){return {
       status:"VIEWER_SESSION_READY",signal:"WAIT",executable:false};}};
   }
   assert.equal(opts.method,"DELETE");
   sessionActive=false;
   return {ok:true,status:200,async json(){return {status:"VIEWER_SESSION_CLEARED"};}};
 }
 assert.equal(url,"/api/v3/ultimate/biquote-observation");
 assert.equal(opts.method,"GET");
 assert.equal(opts.credentials,"same-origin");
 assert.equal(opts.headers.Authorization,undefined,"Viewer token must not be sent on every chart request");
 if(networkMode==="offline")return {ok:false,status:503,
   async json(){return {status:"WAIT_BIQUOTE_DATA_UNAVAILABLE",signal:"WAIT",
    executable:false,researchEligible:false,rawQuoteShown:false,
    blockerCodes:["PUBLIC_HTTP_UNAVAILABLE"]}}};
 const allowed=sessionActive&&(networkMode==="authorized"||networkMode==="authorized-gapped");
 return {ok:true,status:200,async json(){return {...base,rawQuoteShown:allowed,
   ...(allowed?{bid:3910,ask:3910.2,privateChartReadOnly:true,
    privateChartDataBasis:"MID_WITH_POSSIBLE_BID_SEED",
    privateChart:chart(),privateStructure:(()=>{
      const s=analyzeChart(chart(),NOW);
      s.multiFrame=makeMtfReadiness(s,base.crossFrameComparisons);
      s.referenceEmaResearch=examine(chart(),NOW);
      s.vendorDeclaredSession=evaluateFrames(chart());
      return s;
    })()}:{}),
   }}};
}
const document={getElementById:makeNode,querySelectorAll:sel=>{
 assert.equal(sel,"button[data-biq-frame]");return tabs;
}};
const window={devicePixelRatio:1,addEventListener(){}};
const context={window,document,Date,Number,Math,Object,Array,JSON,String,Boolean,
 AbortSignal:{timeout:()=>null},fetch,setInterval:()=>0,console};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,"biquote-mobile-ui.js"),"utf8"),context,{timeout:2000});
async function main(){
 assert.ok(blankMessages>=1,"Default real chart is blank, never a fabricated sample");
 await makeNode("biquote-refresh").click();
 assert.match(makeNode("biquote-live-caption").textContent,/رمز مشاهدة/);
 assert.match(makeNode("biquote-structure-summary").textContent,/WAIT/);
 assert.match(makeNode("biquote-mtf-readiness").textContent,/WAIT/);
 assert.match(makeNode("biquote-observed-ema").textContent,/WAIT/);
 assert.match(makeNode("biquote-vendor-session").textContent,/WAIT/);
 const before=candleDraws;
 makeNode("biquote-viewer-secret").value="a".repeat(40);
 networkMode="authorized";
 await makeNode("biquote-refresh").click();
 assert.ok(candleDraws>before+20,"Authenticated closed MID candles must draw");
 assert.equal(sessionLogins,1,"Exactly one token exchange");
 assert.equal(makeNode("biquote-viewer-secret").value,"","Original viewer token cleared immediately");
 const firstCookies=requests.length;
 await makeNode("biquote-refresh").click();
 assert.equal(sessionLogins,1,"Later refresh must use cookie, never resend token");
 assert.equal(requests.length,firstCookies+1);
 assert.match(makeNode("biquote-viewer-session-state").textContent,/7 أيام/);
 assert.match(makeNode("biquote-live-caption").textContent,/READ-ONLY/);
 assert.match(makeNode("biquote-live-caption").textContent,/تغطية M15/);
 assert.match(makeNode("biquote-structure-summary").textContent,/EMA20/);
 assert.match(makeNode("biquote-structure-summary").textContent,/ATR14/);
 assert.match(makeNode("biquote-structure-summary").textContent,/القرار WAIT/);
 assert.match(makeNode("biquote-mtf-readiness").textContent,/الفواصل الثلاثة فوق EMA20/);
 assert.match(makeNode("biquote-mtf-readiness").textContent,/H4/);
 assert.match(makeNode("biquote-mtf-readiness").textContent,/H1/);
 assert.match(makeNode("biquote-mtf-readiness").textContent,/M15/);
 assert.match(makeNode("biquote-mtf-readiness").textContent,/لا صفقات/);
 assert.match(makeNode("biquote-observed-ema").textContent,/غير قابل للاحتساب/);
 assert.match(makeNode("biquote-observed-ema").textContent,/قرار التداول WAIT/);
 assert.match(makeNode("biquote-vendor-session").textContent,/الأحد 23:00/);
 assert.match(makeNode("biquote-vendor-session").textContent,/القرار WAIT/);
 const newBefore=candleDraws;await tabs[1].click();
 assert.ok(candleDraws>newBefore+20,"H1 selected frame must redraw real candles");
 assert.equal(tabs[1]["aria-pressed"],"true");
 assert.match(makeNode("biquote-structure-summary").textContent,/قراءة H1/);
 // Actual after-gap candles can support 7-bar confirmed swing *patterns*
 // without pretending to have 20 contiguous H1/H4 candles for EMA20.
 networkMode="authorized-gapped";
 await makeNode("biquote-refresh").click();
 await tabs[1].click();
 assert.match(makeNode("biquote-structure-summary").textContent,/تحليل جزئي/);
 assert.match(makeNode("biquote-mtf-readiness").textContent,/غير قابل للتقييم/);
 assert.match(makeNode("biquote-mtf-readiness").textContent,/تغطية M15 ناقصة/);
 assert.match(makeNode("biquote-structure-summary").textContent,/جدول جلسات وسيط BiQuote الأصلي غير موثّق/);
 assert.match(makeNode("biquote-structure-summary").textContent,/أمثلة أوقات الفجوات/);
 assert.match(makeNode("biquote-structure-summary").textContent,/غير متاح \(<20 شمعة متصلة\)/);
 assert.match(makeNode("biquote-structure-summary").textContent,/ATR14: غير متاح/);
 assert.match(makeNode("biquote-structure-summary").textContent,/10/);
 await tabs[2].click();
 assert.match(makeNode("biquote-structure-summary").textContent,/قراءة H4/);
 assert.match(makeNode("biquote-structure-summary").textContent,/تحليل جزئي/);
 assert.match(makeNode("biquote-structure-summary").textContent,/WAIT/);
 networkMode="offline";
 await makeNode("biquote-refresh").click();
 assert.match(makeNode("biquote-live-caption").textContent,/WAIT/);
 assert.ok(blankMessages>=2,"Offline feed must clear live chart immediately");
 assert.match(makeNode("biquote-structure-summary").textContent,/WAIT/);
 assert.match(makeNode("biquote-mtf-readiness").textContent,/WAIT/);
 assert.match(makeNode("biquote-mtf-readiness").textContent,/محجوب/);
 assert.match(makeNode("biquote-observed-ema").textContent,/محجوبة/);
 assert.match(makeNode("biquote-vendor-session").textContent,/غير متاح/);
 assert.equal(requests.length,6);
 assert.equal(requests.every(r=>!r.opts.headers["X-Broker-Order"]),true);
 await makeNode("biquote-viewer-logout").click();
 assert.equal(sessionActive,false,"Explicit logout clears browser cookie");
 assert.match(makeNode("biquote-viewer-session-state").textContent,/تسجيل الخروج/);
 networkMode="authorized";
 await makeNode("biquote-refresh").click();
 assert.match(makeNode("biquote-live-caption").textContent,/رمز مشاهدة/);
 assert.equal(sessionLogins,1,"After logout no covert reauthentication");
 console.log("PASS PRIVATE BiQuote chart: no anonymous raw data, 3 real MID frames after viewer auth, stale cleared; WAIT and paper isolated");
}
main().catch(err=>{console.error(err);process.exitCode=1;});
