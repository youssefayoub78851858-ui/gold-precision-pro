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
 assert.equal(localLatestParity(c),false);
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
