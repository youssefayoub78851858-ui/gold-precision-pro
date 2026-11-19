"use strict";
// Whole-inline-script offline test, synthetic metadata only. No browser,
// network, credentials, cloud calls or trading stack.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const source=fs.readFileSync(path.join(__dirname,"..","private-monitor.html"),"utf8");
const script=source.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert(script);
const nodes=new Map();
const fakeDocument={
 getElementById(id){
  if(!nodes.has(id))nodes.set(id,{textContent:"",value:"",
   disabled:false,children:[],replaceChildren(){this.children=[];},
   addEventListener(){},append(x){this.children.push(x);}});
  return nodes.get(id);
 },
 createElement(){return{textContent:"",className:""};}
};
const sandbox={document:fakeDocument,console,AbortController,
  location:{protocol:"https:",hostname:"test.invalid"}};
vm.runInNewContext(script,sandbox,{timeout:1500});
const text=id=>fakeDocument.getElementById(id).textContent;
vm.runInNewContext("renderSignalRoadmap(null,'BUY')",sandbox,{timeout:1500});
assert.match(text("signal-roadmap-status"),/WAIT/);
assert.doesNotMatch(text("signal-roadmap-status"),/BUY/);
assert.match(text("signal-roadmap-history"),/غير مثبت/);
const data={
 mode:"PRIVATE_FORWARD_BIQUOTE_CAPTURE_NOT_TRADING_ADMISSIBLE",
 status:"PRIVATE_FORWARD_VAULT_METADATA_ONLY",signal:"WAIT",
 executable:false,paperOrdersAllowed:false,tradeSignalReady:false,
 brokerRightsVerified:false,
 counts:{M15:130,H1:32,H4:8},
 forwardCoverage:{
  M15:{latestContiguousBars:42},
  H1:{latestContiguousBars:10},
  H4:{latestContiguousBars:8}
 },
 privateToken:"DO_NOT_PRINT_ME",
 bid:4279.12,
};
sandbox.sample=data;
vm.runInNewContext("renderSignalRoadmap(sample,'BUY')",sandbox,{timeout:1500});
assert.match(text("signal-roadmap-status"),/WAIT.*BUY.*ممنوع/);
assert.match(text("signal-roadmap-history"),/H4 8\/21/);
assert.match(text("signal-roadmap-paper"),/H4 8\/50/);
assert.match(text("signal-roadmap-rights"),/غير مثبتة/);
assert.match(text("signal-roadmap-costs"),/غير مثبتين/);
assert.match(text("signal-roadmap-performance"),/غير مثبت/);
const render=Array.from(nodes.values()).map(x=>x.textContent).join(" ");
assert(!render.includes("DO_NOT_PRINT_ME"));
assert(!render.includes("4279.12"));
// A forged readiness flag and malformed data are never displayed as
// qualified observations, BUY or live trade.
sandbox.sample={...data,brokerRightsVerified:true};
vm.runInNewContext("renderSignalRoadmap(sample,'NONE')",sandbox,{timeout:1500});
assert.match(text("signal-roadmap-history"),/غير مثبت/);
assert.match(text("signal-roadmap-status"),/^WAIT/);
vm.runInNewContext("clearSignalRoadmap()",sandbox,{timeout:1500});
assert.match(text("signal-roadmap-status"),/^WAIT/);
assert(!source.includes('localStorage.setItem("MONITOR_READONLY_TOKEN"'));
console.log("PASS price-free mobile trade-readiness roadmap; WAIT despite technical WATCH; no provider calls");
