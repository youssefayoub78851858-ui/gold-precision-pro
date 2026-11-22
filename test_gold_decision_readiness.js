"use strict";
/**
 * Offline Android Decision Center checks: static 9-layer metadata cannot be
 * presented as live market readiness, and no private archive is fetched.
 * No network, vendor key, real BID/ASK, paper or live trade calls.
 */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const html=fs.readFileSync("ultimate.html","utf8");
const head="<script>\n(function(){\n const btn=document.getElementById('multi-source-check');";
const from=html.indexOf(head);
assert(from>0,"Existing static source checklist must still exist");
const end=html.indexOf("</script>",from);
assert(end>from,"Source checklist must be self-contained");
const js=html.slice(from+8,end); // strip <script>
const names=["XAUUSD_BBO","GC_TRADES","GC_DEPTH","DXY","US02Y","US10Y","CALENDAR","HEADLINES","RISK_COSTS"];
const labels={};
let state="good",calls=[],events={};
const make=()=>({
 textContent:"",disabled:false,children:[],addEventListener(k,f){this["on"+k]=f;},
 appendChild(x){this.children.push(x)},replaceChildren(...x){this.children=x},
});
const nodes=new Map();
for(const id of ["multi-source-check","multi-source-state","multi-source-grid","gdc-source-proof","capital-kyc-handoff"])
 nodes.set(id,make());
const document={
 getElementById:id=>nodes.get(id)||null,
 createElement:()=>make(),
 createTextNode:text=>({textContent:text})
};
const window={addEventListener:(k,f)=>{events[k]=f}};
// Use the actual offline registry contract; the legacy JSON key is kept
// only for compatibility, never a claim about a private user's KYC.
const normal=require("./coordinator/multi_source_public_readiness").snapshot();
assert.equal(normal.capitalDemoPreKyc.kycRequestedNow,false);
assert.equal(normal.capitalDemoPreKyc.connected,false);
assert.equal(normal.capitalDemoPreKyc.signal,"WAIT");
async function fetch(url,opts){
 calls.push({url,opts});
 assert.equal(url,"/api/v3/ultimate/multi-source-readiness");
 assert.equal(opts.credentials,"omit");
 assert.equal(opts.cache,"no-store");
 assert.equal(opts.redirect,"error");
 if(state==="offline")throw Error("offline");
 if(state==="forged")return {ok:true,async json(){return {...normal,verifiedLiveLayerCount:3}}};
 return {ok:true,async json(){return normal}};
}
vm.runInNewContext(js,{document,window,fetch,AbortSignal:{timeout:()=>null},
 Object,Array,String,Number,Error},{timeout:3000});
const button=nodes.get("multi-source-check");
const proof=nodes.get("gdc-source-proof");
const status=nodes.get("multi-source-state");
(async()=>{
 assert.equal(typeof button.onclick,"function");
 await button.onclick();
 assert.match(proof.textContent,/0 \/ 9 مكتملة/);
 assert.match(proof.textContent,/الثابت فقط/);
 assert.match(status.textContent,/0 من 9 مصادر حقيقية/);
 assert.equal(nodes.get("multi-source-grid").children.length,9);
 assert.match(nodes.get("capital-kyc-handoff").textContent,/بانتظار موافقة مكتوبة/);
 assert.match(nodes.get("capital-kyc-handoff").textContent,/حالة توثيق الحساب لا تفحصها هذه الشاشة/);
 assert.doesNotMatch(nodes.get("capital-kyc-handoff").textContent,/توثيق الهوية مؤجّل/);
 assert.match(nodes.get("capital-kyc-handoff").textContent,/WAIT/);
 state="forged";
 await button.onclick();
 assert.match(proof.textContent,/العدد غير معروف/);
 assert.match(status.textContent,/WAIT/);
 state="offline";
 await button.onclick();
 assert.match(proof.textContent,/تعذّر التحقق/);
 assert.doesNotMatch(proof.textContent,/0 \/ 9 مكتملة/);
 assert.equal(button.disabled,false);
 assert.equal(calls.length,3);
 assert.equal(calls.every(x=>x.url==="/api/v3/ultimate/multi-source-readiness"),true);
 assert(html.includes('id="gdc-archive-proof"'));
 assert(html.includes('أرشيف BiQuote الخاص: غير مؤكد على الشاشة العامة'));
 assert(html.includes('href="/private-monitor#biquote-forward-panel"'));
 assert(!js.includes("MONITOR_READONLY_TOKEN"));
 assert(!js.includes("/api/v3/monitor/status"));
 assert(!js.includes("paper-buy")&&!js.includes("paper-sell"));
 console.log("PASS Decision Center: honest static 0/9, fail-closed forged/unavailable metadata, protected vault, no provider or trades");
})().catch(e=>{console.error(e);process.exitCode=1});
