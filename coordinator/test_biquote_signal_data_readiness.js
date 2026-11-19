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
a.equal(early.warmupCrossFrameMatchedH4,0);
a.equal(early.warmupCrossFrameFullyVerified,false);
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
a.equal(good.warmupCrossFrameMatchedH4,21);
a.equal(good.warmupCrossFrameFullyVerified,true);
for(const tf of Object.keys(WIDTH))
 a.equal(good.storedClosedCounts[tf],
  good.observedAtDecision[tf]+good.firstSeenAfterDecision[tf]+
  good.legacyWithoutFirstSeen[tf]);
a(good.blockers.includes("UPSTREAM_BROKER_DATA_RIGHTS_UNVERIFIED"));
// Critical H4/H1 case: an older bar can be inside stale-age limits
// and still have enough contiguous history when the newest CLOSED bar
// has never been received. Do not mislabel that old bar "latest".
const longMature=fixture(384),longBase=assess(longMature);
safe(longBase);
a.equal(longBase.localGeometryObserved,true);
for(const tf of Object.keys(WIDTH))
 a.equal(longBase.latestEligibleClosedObservedAtDecision[tf],true);
const missingNewestH4=structuredClone(longMature);
delete missingNewestH4.firstObservedClosedUTC.H4[
 missingNewestH4.frames.H4.at(-1).datetime];
const missingNewestH4Result=assess(missingNewestH4);
safe(missingNewestH4Result);
a.equal(missingNewestH4Result.technicalWarmupMissing.H4,0);
a.equal(missingNewestH4Result.latestEligibleClosedObservedAtDecision.H4,false);
a.equal(missingNewestH4Result.localGeometryObserved,false);
a.equal(missingNewestH4Result.localTimingAndParityCheck,"NOT_PROVEN");
a(missingNewestH4Result.blockers.includes(
 "H4_LATEST_ELIGIBLE_CLOSED_BAR_NOT_OBSERVED_AT_DECISION"));
const missingNewestH1=structuredClone(longMature);
delete missingNewestH1.firstObservedClosedUTC.H1[
 missingNewestH1.frames.H1.at(-1).datetime];
const missingNewestH1Result=assess(missingNewestH1);
safe(missingNewestH1Result);
a.equal(missingNewestH1Result.technicalWarmupMissing.H1,0);
a.equal(missingNewestH1Result.latestEligibleClosedObservedAtDecision.H1,false);
a.equal(missingNewestH1Result.localGeometryObserved,false);
a(missingNewestH1Result.blockers.includes(
 "H1_LATEST_ELIGIBLE_CLOSED_BAR_NOT_OBSERVED_AT_DECISION"));
const delayedNewestH4=structuredClone(longMature);
delayedNewestH4.firstObservedClosedUTC.H4[
 delayedNewestH4.frames.H4.at(-1).datetime]=
 iso(Date.parse(delayedNewestH4.asOfUTC)+300000);
const delayedNewestH4Result=assess(delayedNewestH4);
safe(delayedNewestH4Result);
a.equal(delayedNewestH4Result.firstSeenAfterDecision.H4,1);
a.equal(delayedNewestH4Result.latestEligibleClosedObservedAtDecision.H4,false);
a.equal(delayedNewestH4Result.localGeometryObserved,false);
// Missing the entire latest closed H4 is more dangerous than an unknown
// receipt: the previous H4 remains <5h old, 21 closed H4s remain and
// M15-to-that-old-H4 OHLC can match, but the expected 4-hour slot is absent.
const grid=fixture(352),gridOK=assess(grid);
safe(gridOK);a.equal(gridOK.localGeometryObserved,true);
a.equal(gridOK.latestExpectedUTCGridClosedObservedAtDecision.H4,true);
const missingFullH4=structuredClone(grid);
const removedH4=missingFullH4.frames.H4.pop();
delete missingFullH4.firstObservedClosedUTC.H4[removedH4.datetime];
const missingFullH4Result=assess(missingFullH4);
safe(missingFullH4Result);
a.equal(missingFullH4Result.technicalWarmupMissing.H4,0);
a.equal(missingFullH4Result.latestEligibleClosedObservedAtDecision.H4,true);
a.equal(missingFullH4Result.latestExpectedUTCGridClosedObservedAtDecision.H4,false);
a.equal(missingFullH4Result.localGeometryObserved,false);
a(missingFullH4Result.blockers.includes("H4_EXPECTED_UTC_CLOSED_SLOT_NOT_OBSERVED"));
// Same issue on H1: the previous hour still satisfies the 75-minute age
// allowance, and its OHLC can match all retained M15 constituents.
const missingFullH1=structuredClone(grid);
const removedH1=missingFullH1.frames.H1.pop();
delete missingFullH1.firstObservedClosedUTC.H1[removedH1.datetime];
const missingFullH1Result=assess(missingFullH1);
safe(missingFullH1Result);
a.equal(missingFullH1Result.technicalWarmupMissing.H1,0);
a.equal(missingFullH1Result.latestEligibleClosedObservedAtDecision.H1,true);
a.equal(missingFullH1Result.latestExpectedUTCGridClosedObservedAtDecision.H1,false);
a.equal(missingFullH1Result.localGeometryObserved,false);
a(missingFullH1Result.blockers.includes("H1_EXPECTED_UTC_CLOSED_SLOT_NOT_OBSERVED"));
// A paused market does not authorize synthesizing candles to pass the
// clock grid. The lack of authenticated broker session means WAIT.
const paused=structuredClone(grid);
paused.asOfUTC=iso(Date.parse(grid.asOfUTC)+4*WIDTH.H1);
const pausedReport=assess(paused);
safe(pausedReport);
a.equal(pausedReport.latestExpectedUTCGridClosedObservedAtDecision.H4,false);
a(pausedReport.blockers.includes("H4_EXPECTED_UTC_CLOSED_SLOT_NOT_OBSERVED"));
// IMPORTANT: a matching *latest* H4 is not enough for 21-H4 warmup.
// An old constituent may have an unknown local receipt while the last
// 21 M15 and H1 bars are still contiguous and fresh.
const backfillFixture=fixture(384);
const backfillGood=assess(backfillFixture);
safe(backfillGood);
a.equal(backfillGood.warmupCrossFrameMatchedH4,21);
a.equal(backfillGood.localGeometryObserved,true);
const olderM15ReceiptMissing=structuredClone(backfillFixture);
const historicalM15=olderM15ReceiptMissing.frames.M15[16*10].datetime;
delete olderM15ReceiptMissing.firstObservedClosedUTC.M15[historicalM15];
const oldMissingResult=assess(olderM15ReceiptMissing);safe(oldMissingResult);
a.equal(oldMissingResult.technicalWarmupMissing.M15,0);
a.equal(oldMissingResult.technicalWarmupMissing.H4,0);
a.equal(oldMissingResult.warmupCrossFrameMatchedH4,20);
a.equal(oldMissingResult.warmupCrossFrameFullyVerified,false);
a.equal(oldMissingResult.localGeometryObserved,false);
a(oldMissingResult.blockers.includes(
 "H4_21_CLOSED_BARS_M15_H1_CROSS_FRAME_PARITY_UNPROVEN"));
// All local receipt times can exist while an older H4/H1 candle is
// inconsistent with its M15 constituents. Neither old mismatch can
// be hidden by the newest H4 still matching perfectly.
const historicalH4Mismatch=structuredClone(backfillFixture);
historicalH4Mismatch.frames.H4[14].high+=10;
const oldH4Result=assess(historicalH4Mismatch);safe(oldH4Result);
a.equal(oldH4Result.technicalWarmupMissing.H4,0);
a.equal(oldH4Result.warmupCrossFrameMatchedH4,20);
a.equal(oldH4Result.localGeometryObserved,false);
a(oldH4Result.blockers.includes(
 "H4_21_CLOSED_BARS_M15_H1_CROSS_FRAME_PARITY_UNPROVEN"));
const historicalH1Mismatch=structuredClone(backfillFixture);
historicalH1Mismatch.frames.H1[4*14].high+=10;
const oldH1Result=assess(historicalH1Mismatch);safe(oldH1Result);
a.equal(oldH1Result.warmupCrossFrameMatchedH4,20);
a.equal(oldH1Result.localGeometryObserved,false);
a(oldH1Result.blockers.includes(
 "H4_21_CLOSED_BARS_M15_H1_CROSS_FRAME_PARITY_UNPROVEN"));
// Future receipt of ONE older M15 candle must not be used to prove
// prior-decision 21-H4 integrity.
const olderFutureReceipt=structuredClone(backfillFixture);
olderFutureReceipt.firstObservedClosedUTC.M15[historicalM15]=
 iso(Date.parse(olderFutureReceipt.asOfUTC)+600000);
const oldFutureResult=assess(olderFutureReceipt);safe(oldFutureResult);
a.equal(oldFutureResult.firstSeenAfterDecision.M15,1);
a.equal(oldFutureResult.warmupCrossFrameFullyVerified,false);
a.equal(oldFutureResult.localGeometryObserved,false);
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
