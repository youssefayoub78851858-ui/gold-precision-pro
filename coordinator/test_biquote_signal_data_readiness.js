"use strict";
const a=require("node:assert/strict");
const {assess}=require("./biquote_signal_data_readiness");
const START=Date.parse("2026-11-18T00:00:00Z");
const WIDTH={M15:900000,H1:3600000,H4:14400000};
const iso=t=>new Date(t).toISOString().replace(".000Z","Z");
function frames(n){
 const M15=Array.from({length:n},(_,i)=>{
  const p=2000+i*.05;
  return {datetime:iso(START+i*WIDTH.M15),open:p,high:p+.4,low:p-.2,close:p+.1};
 });
 function grouped(k){
  return Array.from({length:Math.floor(n/k)},(_,i)=>{
   const x=M15.slice(i*k,i*k+k);
   return {datetime:x[0].datetime,open:x[0].open,
    high:Math.max(...x.map(b=>b.high)),low:Math.min(...x.map(b=>b.low)),
    close:x.at(-1).close};
  });
 }
 return {M15,H1:grouped(4),H4:grouped(16)};
}
function receipts(fr){
 return Object.fromEntries(Object.entries(fr).map(([tf,rows])=>
  [tf,Object.fromEntries(rows.map(r=>[r.datetime,iso(Date.parse(r.datetime)+WIDTH[tf]+1000)]))]));
}
function fixture(n){
 const f=frames(n);
 return {dataOrigin:"BIQUOTE_ARCHIVED_UNVERIFIED_NO_PAPER",frames:f,
  firstObservedClosedUTC:receipts(f),asOfUTC:iso(START+n*WIDTH.M15+60000)};
}
function safe(x){
 a.equal(x.signal,"WAIT");a.equal(x.executable,false);
 a.equal(x.tradeEligible,false);a.equal(x.paperOrdersAllowed,false);
 a.equal(x.liveOrdersAllowed,false);a.equal(x.researchCandidate,"NONE");
 a.equal(x.brokerOrdersSent,0);a.equal(x.providerRequestsMade,0);
 a.equal(x.sourceRightsVerified,false);
 a.equal(x.brokerCostsVerified,false);
 a.equal(x.profitabilityProven,false);
 a.equal(JSON.stringify(x).includes('"open":'),false);
 a.equal(JSON.stringify(x).includes('"close":'),false);
}
const early=assess(fixture(131));
safe(early);
a.equal(early.storedClosedCounts.M15,131);
a.equal(early.storedClosedCounts.H1,32);
a.equal(early.storedClosedCounts.H4,8);
a.equal(early.contiguousObservedClosed.H4,8);
a.equal(early.firstSeenAfterDecision.H4,0);
a.equal(early.technicalWarmupMissing.H4,13);
a.equal(early.paperHistoryMissing.H4,42);
a.equal(early.localGeometryObserved,false);
a(early.blockers.includes("H4_INSUFFICIENT_POINT_IN_TIME_WARMUP"));
// Reaching a research-only technical warm-up never enables a trade.
const mature=fixture(336),good=assess(mature);
safe(good);
a.equal(good.technicalWarmupMissing.H4,0);
a.equal(good.paperHistoryMissing.H4,29);
a.equal(good.status,"LOCAL_GEOMETRY_ONLY_NOT_TRADE_READY");
a.equal(good.localTimingAndParityCheck,"LOCAL_ONLY_NOT_INDEPENDENT");
a.equal(good.localGeometryObserved,true);
for(const tf of Object.keys(WIDTH))
 a.equal(good.storedClosedCounts[tf],
  good.observedAtDecision[tf]+good.firstSeenAfterDecision[tf]+
  good.legacyWithoutFirstSeen[tf]);
a(good.blockers.includes("UPSTREAM_BROKER_DATA_RIGHTS_UNVERIFIED"));
// Legacy bars are unknown, NOT automatically assigned a receipt.
const legacy=structuredClone(mature);
delete legacy.firstObservedClosedUTC;
const unknown=assess(legacy);
safe(unknown);
a.equal(unknown.status,"RECEIPTS_UNAVAILABLE");
a.equal(unknown.legacyWithoutFirstSeen.H4,21);
a.equal(unknown.firstSeenAfterDecision.H4,0);
a.equal(unknown.contiguousObservedClosed.H4,0);
// Missing or delayed last H4 first-seen makes coverage insufficient.
const missing=structuredClone(mature);
delete missing.firstObservedClosedUTC.H4[missing.frames.H4.at(-1).datetime];
const missingReport=assess(missing);
safe(missingReport);
a.equal(missingReport.legacyWithoutFirstSeen.H4,1);
a.equal(missingReport.localGeometryObserved,false);
const late=structuredClone(mature);
late.firstObservedClosedUTC.H4[late.frames.H4.at(-1).datetime]=
 iso(Date.parse(mature.asOfUTC)+300000);
const lateReport=assess(late);
safe(lateReport);
a.equal(lateReport.observedAtDecision.H4,20);
a.equal(lateReport.firstSeenAfterDecision.H4,1);
a.equal(lateReport.legacyWithoutFirstSeen.H4,0);
a(lateReport.blockers.includes("H4_FUTURE_RECEIPTS_EXCLUDED_FROM_DECISION"));
a.equal(lateReport.localGeometryObserved,false);
// Partial M15 group and a differing H4 bar cannot pass price parity.
const absent=structuredClone(mature);
delete absent.firstObservedClosedUTC.M15[absent.frames.M15.at(-1).datetime];
a.equal(assess(absent).localGeometryObserved,false);
const mismatch=structuredClone(mature);
mismatch.frames.H4.at(-1).high+=12;
const mismatchResult=assess(mismatch);
safe(mismatchResult);
a(mismatchResult.blockers.includes("LATEST_CLOSED_M15_H1_H4_OHLC_PARITY_UNPROVEN"));
// A future correction must never affect prior as-of geometry.
const future=structuredClone(mature);
const bar=future.frames.M15.at(-1);
future.frames.M15.push({...bar,datetime:iso(Date.parse(bar.datetime)+WIDTH.M15),
 open:9999,high:10000,low:9998,close:9999});
future.firstObservedClosedUTC.M15[future.frames.M15.at(-1).datetime]=
 iso(Date.parse(future.frames.M15.at(-1).datetime)+WIDTH.M15+1000);
a.equal(assess(future).localGeometryObserved,good.localGeometryObserved);
a.equal(assess(future).observedAtDecision.M15,good.observedAtDecision.M15);
a.equal(assess(future).firstSeenAfterDecision.M15,1);
a.equal(assess(future).legacyWithoutFirstSeen.M15,0);
a.equal(assess(future).storedClosedCounts.M15,337);
// Untrusted packet assertions cannot override hard-coded no-trading.
const forged=assess({...mature,sourceRightsVerified:true,
 brokerCostsVerified:true,canTrade:true,signal:"BUY",paperOrdersAllowed:true});
safe(forged);
// Malformed timestamps, duplicate OHLC and impossible receipts fail closed.
for(const bad of [
 {...mature,asOfUTC:"2026-11-19T00:00:00+00:00"},
 {...mature,dataOrigin:"LIVE_ENTITLED"},
 {...mature,frames:{...mature.frames,M15:[...mature.frames.M15,mature.frames.M15.at(-1)]}},
 {...mature,firstObservedClosedUTC:{...mature.firstObservedClosedUTC,
  H4:{...mature.firstObservedClosedUTC.H4,
   [mature.frames.H4.at(-1).datetime]:"2026-11-18T00:00:00Z"}}},
 {...mature,firstObservedClosedUTC:{...mature.firstObservedClosedUTC,H1:{
  ...mature.firstObservedClosedUTC.H1,UNKNOWN:"2026-11-19T00:00:00Z"}}}
]){
 const x=assess(bad);safe(x);a.equal(x.status,"BLOCKED");
}
console.log("PASS BiQuote point-in-time closed-frame readiness, 131/32/8 warm-up, first-seen, stale/gap, parity, no lookahead, no orders");
