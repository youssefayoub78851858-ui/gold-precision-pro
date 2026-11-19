"use strict";
/** Static UI contract test, no browser/network/vendor credentials/orders. */
const a=require("node:assert/strict");
const fs=require("node:fs"),path=require("node:path"),vm=require("node:vm");
const src=fs.readFileSync(path.resolve(__dirname,"../biquote-mobile-ui.js"),"utf8");
const begin=src.indexOf("function renderFrozenV3ResearchWatch(v,comparisons,sourceStatus){");
const end=src.indexOf(" // This is a PRIVATE, already validated observation.",begin);
a(begin>0&&end>begin,"Exact V3 watch panel must exist");
const output={textContent:""};
const env={$:id=>id==="gdc-v3-watch"?output:null};
vm.runInNewContext(src.slice(begin,end),env,{timeout:2000});
const render=(v,c,sourceStatus="OBSERVED_READONLY_UNVERIFIED")=>{
 env.renderFrozenV3ResearchWatch(v,c,sourceStatus);
 return output.textContent;
};
const safe={
 mode:"PRIVATE_FROZEN_V3_TECHNICAL_WATCH_ONLY",
 status:"WAIT_CROSS_FRAME_EVIDENCE",
 signal:"WAIT",executable:false,tradeEligible:false,
 paperOrdersAllowed:false,liveOrdersAllowed:false,
 sourceRightsVerified:false,firstSeenAtDecisionVerified:false,
 independentMacroNewsGcOrderFlowVerified:false,
 brokerBidAskCostsVerified:false,retrospectiveOnly:true,
 entry:null,stopLoss:null,takeProfit:null,
 providerRequestsMade:0,brokerOrdersSent:0,
 technicalCandidate:"NONE",watchLabel:"WAIT",
 reason:"SOURCE_HAS_UNRESOLVED_CROSS_FRAME_GAPS",
 privateToken:"DO_NOT_PRINT_TOKEN",priceSecret:948382
};
const c={
 H1:{completeMatches:11,completeMismatches:1,
     incompleteM15Groups:3,outsideRetentionWindow:17},
 H4:{completeMatches:2,completeMismatches:0,
     incompleteM15Groups:7,outsideRetentionWindow:8}
};
let got=render(safe,c);
a.match(got,/^WAIT/);
a.match(got,/H1: مطابق 11، مختلف 1، M15 ناقص 3/);
a.match(got,/H4: مطابق 2، مختلف 0، M15 ناقص 7/);
a.match(got,/خارج نطاق M15 8/);
a(!got.includes("DO_NOT_PRINT_TOKEN"));
a(!got.includes("948382"));
a(!got.includes("BUY"));
for(const k of ["completeMatches","completeMismatches",
                "incompleteM15Groups","outsideRetentionWindow"]){
 const tampered=structuredClone(c);
 tampered.H4[k]="PRIVATE_SECRET_UNTRUSTED";
 got=render(safe,tampered);
 a.match(got,/^WAIT/);
 a(!got.includes("PRIVATE_SECRET_UNTRUSTED"));
 a(!got.includes("H4: مطابق"));
}
const gone=render(safe,null);
a.match(gone,/^WAIT/);
a(!gone.includes("H1: مطابق"));
const gap=render({...safe,status:"WAIT_DATA_INCOMPLETE",
 reason:"H4_NOT_21_STRICTLY_CONTIGUOUS_CLOSED"},c);
a.match(gap,/أقل من 21 شمعة H4 متتالية/);
a(!gap.includes("H1: مطابق"));
const clear={
 H1:{completeMatches:12,completeMismatches:0,
     incompleteM15Groups:0,outsideRetentionWindow:12},
 H4:{completeMatches:2,completeMismatches:0,
     incompleteM15Groups:0,outsideRetentionWindow:25}
};
const watchPayload={...safe,status:"TECHNICAL_WATCH_ONLY_NOT_TRADE_READY",
 technicalCandidate:"BUY",watchLabel:"WATCH_BUY",lastCrossFrameParityObserved:true,
 reason:"FROZEN_V3_ALIGNED_CLOSED_BAR_BOS_NO_INDEPENDENT_CONFIRMATION"};
const watch=render(watchPayload,clear);
a.match(watch,/^WAIT · WATCH_BUY/);
a.match(watch,/ليست توصية دخول/);
// A valid-looking WATCH payload must not override contradictory live
// source status, an old H1 mismatch, missing H4 constituents, or a
// malformed overlap report. These conditions must show plain WAIT.
for(const item of [
 {c,status:"WAIT_CROSS_FRAME_GAPS"},
 {c,status:"OBSERVED_READONLY_UNVERIFIED"},
 {c:null,status:"OBSERVED_READONLY_UNVERIFIED"},
 {c:{...clear,H4:{...clear.H4,incompleteM15Groups:1}},
  status:"OBSERVED_READONLY_UNVERIFIED"},
 {c:{...clear,H1:{...clear.H1,completeMatches:0}},
  status:"OBSERVED_READONLY_UNVERIFIED"},
 {c:{...clear,H1:{...clear.H1,completeMismatches:1}},
  status:"OBSERVED_READONLY_UNVERIFIED"},
 {c:clear,status:"UNVERIFIED_UNKNOWN_STATUS"}
]){
 const veto=render(watchPayload,item.c,item.status);
 a.match(veto,/^WAIT — نتيجة WATCH تعارض/);
 a(!veto.includes("WATCH_BUY"));
}

for(const patch of [
 {executable:true},{paperOrdersAllowed:true},{sourceRightsVerified:true},
 {firstSeenAtDecisionVerified:true},{brokerBidAskCostsVerified:true},
 {entry:4420},{providerRequestsMade:1},{brokerOrdersSent:1}
]){
 got=render({...safe,status:"TECHNICAL_WATCH_ONLY_NOT_TRADE_READY",
 technicalCandidate:"BUY",watchLabel:"WATCH_BUY",lastCrossFrameParityObserved:true,
 ...patch},clear);
 a.match(got,/^WAIT — نتيجة محرك V3 غير متاحة/);
 a(!got.includes("WATCH_BUY"));
}
a(src.includes("renderFrozenV3ResearchWatch(data.privateTechnicalWatch,\n     data.crossFrameComparisons,data.status)"));
console.log("PASS owner-only V3 WAIT: exact sanitized H1/H4 vs M15 counts, no raw private data, forged trade fields vetoed");
