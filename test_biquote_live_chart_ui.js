"use strict";
// BiQuote private live candle UI smoke: mocked network, no market/order calls.
const assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm"),path=require("node:path");
const NOW=Date.now();
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
const ids=["biquote-refresh","biquote-viewer-secret","biquote-live-canvas",
"biquote-live-caption","biquote-status","biquote-private-quote",
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
   return [tf,Array.from({length:48},(_,i)=>{
     const value=3900+i*0.2;
     return {time:new Date(end-(48-i)*w).toISOString(),
       open:value,high:value+0.6,low:value-0.4,close:value+0.1};
   })];
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
let networkMode="anonymous",requests=[];
async function fetch(url,opts){
 requests.push({url,opts});
 assert.equal(url,"/api/v3/ultimate/biquote-observation");
 assert.equal(opts.method,"GET");
 assert.equal(opts.credentials,"omit");
 if(networkMode==="offline")return {ok:false,status:503,
   async json(){return {status:"WAIT_BIQUOTE_DATA_UNAVAILABLE",signal:"WAIT",
    executable:false,researchEligible:false,rawQuoteShown:false,
    blockerCodes:["PUBLIC_HTTP_UNAVAILABLE"]}}};
 const allowed=networkMode==="authorized";
 assert.equal("Authorization" in opts.headers,allowed);
 return {ok:true,status:200,async json(){return {...base,rawQuoteShown:allowed,
   ...(allowed?{bid:3910,ask:3910.2,privateChartReadOnly:true,
    privateChartDataBasis:"MID_WITH_POSSIBLE_BID_SEED",
    privateChart:chart()}:{}),
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
 const before=candleDraws;
 makeNode("biquote-viewer-secret").value="a".repeat(40);
 networkMode="authorized";
 await makeNode("biquote-refresh").click();
 assert.ok(candleDraws>before+20,"Authenticated closed MID candles must draw");
 assert.match(makeNode("biquote-live-caption").textContent,/READ-ONLY/);
 assert.match(makeNode("biquote-live-caption").textContent,/تغطية M15/);
 const newBefore=candleDraws;await tabs[1].click();
 assert.ok(candleDraws>newBefore+20,"H1 selected frame must redraw real candles");
 assert.equal(tabs[1]["aria-pressed"],"true");
 networkMode="offline";
 await makeNode("biquote-refresh").click();
 assert.match(makeNode("biquote-live-caption").textContent,/WAIT/);
 assert.ok(blankMessages>=2,"Offline feed must clear live chart immediately");
 assert.equal(requests.length,3);
 assert.equal(requests.every(r=>!r.opts.headers["X-Broker-Order"]),true);
 console.log("PASS PRIVATE BiQuote chart: no anonymous raw data, 3 real MID frames after viewer auth, stale cleared; WAIT and paper isolated");
}
main().catch(err=>{console.error(err);process.exitCode=1;});
