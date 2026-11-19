"use strict";
// Offline safety regression tests. Run: node --test coordinator/tests/review_dashboard_safety.test.js
// No provider requests, credentials, orders or external dependencies.
const test=require("node:test");
const assert=require("node:assert/strict");
const {validateChart,validateSnapshot,localLatestParity,researchWatch}=
 require("../../review-dashboard.js");
const W={M15:900000,H1:3600000,H4:14400000};
function chart(at){
 const result={};
 for(const [tf,width] of Object.entries(W)){
  const last=Math.floor((at-width)/width)*width;
  result[tf]=Array.from({length:24},(_,i)=>{
   const t=last-(23-i)*width;
   return {time:new Date(t).toISOString(),open:3000,high:3002,low:2998,close:3001};
  });
 }
 return result;
}
const now=Date.UTC(2026,10,19,12,0,0);
test("valid closed candles are observational, not automatically signals",()=>{
 const c=validateChart(chart(now),now);
 assert.ok(c);
 // These fabricated but internally consistent CLOSED bars match locally.
 // Matching OHLC alone is observational and must never authorize a trade.
 assert.equal(localLatestParity(c),true);
 assert.equal(researchWatch({d:{privateTechnicalWatch:{signal:"BUY"}},comparisons:{},chart:c}),
  "WAIT — فحص V3 غير مؤكد");
});
test("reject open or future candles in every timeframe",()=>{
 for(const tf of Object.keys(W)){
  const c=chart(now);c[tf][23].time=new Date(now).toISOString();
  assert.equal(validateChart(c,now),null,tf);
 }
});
test("reject malformed OHLC, duplicates and unsorted bars",()=>{
 const c=chart(now);c.M15[2].low=3100;
 assert.equal(validateChart(c,now),null);
 const d=chart(now);d.H1[2].time=d.H1[1].time;
 assert.equal(validateChart(d,now),null);
});
test("reject synthetic or executable recommendations",()=>{
 assert.equal(validateSnapshot({signal:"BUY",executable:true},now),null);
 assert.equal(validateSnapshot({signal:"SELL",executable:false},now),null);
 assert.equal(researchWatch({d:{privateTechnicalWatch:{signal:"BUY"}},comparisons:{},chart:chart(now)}),
  "WAIT — فحص V3 غير مؤكد");
});
test("never accept invalid chart geometry",()=>{
 const c=chart(now);c.H4[0].high=2990;
 assert.equal(validateChart(c,now),null);
});

test("21 H4 candles cannot be independently proven by the current single snapshot",()=>{
 const {assess}=require("../biquote_snapshot_capacity_gate");
 const x=assess();
 assert.equal(x.signal,"WAIT");
 assert.equal(x.executable,false);
 assert.equal(x.sufficientForTradeRecommendations,false);
 assert.equal(x.requiredM15Constituents,336);
 assert.equal(x.requiredH1Constituents,84);
 assert.equal(x.configuredProviderMaxM15Bars,200);
 assert.equal(x.providerM15CapacityShortfall,136);
 assert.equal(x.singleSnapshotCanProve21H4M15Parity,false);
 assert.equal(x.archiveRequiredForFullWindow,true);
 assert.equal(x.archiveCurrentlyVerified,false);
});

test("latest timeframe parity rejects a corrupted M15 constituent",()=>{
 const source=chart(now);
 // Change one constituent's high while preserving valid OHLC geometry.
 source.M15[20].high=3003;
 const checked=validateChart(source,now);
 assert.ok(checked);
 assert.equal(localLatestParity(checked),false);
 assert.equal(researchWatch({d:{privateTechnicalWatch:{signal:"BUY"}},comparisons:{},chart:checked}),
  "WAIT — فحص V3 غير مؤكد");
});
test("historical cross-frame audit counts a mismatched fully covered H1 bar",()=>{
 const {localCoveredParityAudit}=require("../../review-dashboard.js");
 const source=chart(now);
 const baseline=localCoveredParityAudit(validateChart(source,now));
 assert.ok(baseline.H1.fullyCovered>=1);
 assert.equal(baseline.H1.disagreed,0);
 source.M15[20].high=3003;
 const result=localCoveredParityAudit(validateChart(source,now));
 assert.ok(result.H1.disagreed>=1);
});
