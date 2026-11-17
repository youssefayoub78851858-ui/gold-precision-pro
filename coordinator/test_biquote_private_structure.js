"use strict";
// Pure offline synthetic checks; no provider requests, tokens or orders.
const assert=require("node:assert/strict");
const {analyzeChart,analyzeFrame}=require("./biquote_private_structure");
const MS={M15:900000,H1:3600000,H4:14400000},NOW=Date.parse("2026-11-17T08:00:00Z");
function rows(tf,n=48){
 const step=MS[tf],end=Math.floor(NOW/step)*step;
 return Array.from({length:n},(_,i)=>{
  const t=end-(n-i)*step;
  const p=4000+Math.sin(i/3)*2+i/20;
  return {time:new Date(t).toISOString(),
   open:p,high:p+1,low:p-1,close:p+0.15};
 });
}
const close=(a,b)=>Math.abs(a-b)<0.000001;
for(const tf of ["M15","H1","H4"]){
 const x=analyzeFrame(rows(tf),tf,NOW);
 assert.equal(x.signal,"WAIT");assert.equal(x.executable,false);
 assert.equal(x.researchEligible,false);assert.equal(x.tradeEligible,false);
 assert.equal(x.paperOrdersAllowed,false);assert.equal(x.validForEntry,false);
 assert.equal(x.sessionCalendarVerified,false);
 assert.equal(x.referenceOnlyGapAudit.brokerCalendarVerified,false);
 assert.equal(x.referenceOnlyGapAudit.bridgeBarsAllowed,false);
 assert.equal(x.referenceOnlyGapAudit.signal,"WAIT");
 assert.equal(x.referenceOnlyGapAudit.executable,false);
 assert.equal(x.state,"OBSERVATION_ONLY");
 assert.equal(x.contiguousBars,48);
 assert.equal(x.unclassifiedGapsInChart,0);
 assert.ok(x.ema20>0&&x.atr14>0);
 assert.ok(x.recentRangeHigh20>x.recentRangeLow20);
 assert.ok(Array.isArray(x.lastClosedEvents));
 assert.ok(x.confirmedSwingHigh===null||x.confirmedSwingHigh>0);
 assert.ok(x.confirmedSwingLow===null||x.confirmedSwingLow>0);
 const fresh=rows(tf);
 const stale=analyzeFrame(fresh,tf,NOW-3*step(tf));
 assert.equal(stale.state,"INSUFFICIENT_VERIFIED_STRUCTURE");
 assert.equal(stale.reason,"INVALID_CLOSED_BARS");
}
// Historical data gaps must be detected. An internal gap may remain, but
// the verified structure only analyzes the most recent continuous tail.
function step(tf){return MS[tf]}
const m15=rows("M15");
const broken=m15.map(x=>({...x}));
const missing=broken.splice(42,1)[0];
const gated=analyzeFrame(broken,"M15",NOW);
assert.equal(gated.state,"INSUFFICIENT_VERIFIED_STRUCTURE");
assert.equal(gated.reason,"LESS_THAN_7_CONTIGUOUS_CLOSED_BARS");
assert.equal(gated.unclassifiedGapsInChart,1);
assert.equal(gated.contiguousBars,5);
assert.equal(gated.confirmedSwingHigh,undefined);
assert.equal(gated.ema20,undefined);
// Only post-gap CLOSED bars may inform pivots, BOS/sweep and FVG.
// A partial segment can be described, but never make a trade or
// falsely report EMA20/ATR14 that need more than its confirmed bars.
for(const tail of [7,8,11,14,15,19,20]){
 const source=rows("H1");
 const shortened=source.filter((_,i)=>i!==source.length-tail-1);
 const analysis=analyzeFrame(shortened,"H1",NOW);
 assert.equal(analysis.signal,"WAIT");
 assert.equal(analysis.executable,false);
 assert.equal(analysis.validForEntry,false);
 assert.equal(analysis.sessionCalendarVerified,false);
 assert.equal(analysis.contiguousBars,tail);
 assert.equal(analysis.state,tail>=20?"OBSERVATION_ONLY":
   "PARTIAL_OBSERVATION_UNVERIFIED_SESSION");
 assert.equal(analysis.ema20===null,tail<20);
 assert.equal(analysis.atr14===null,tail<15);
 assert.equal(analysis.recentRangeBars,Math.min(tail,20));
 assert.equal(analysis.technicalCoverage,"CONTIGUOUS_POST_GAP_ONLY");
 assert.equal(analysis.unclassifiedGapsRemainBlocked,true);
 for(const event of analysis.lastClosedEvents)
  assert.ok(["BOS_UP","BOS_DOWN","SWEEP_HIGH","SWEEP_LOW","FVG_BULL","FVG_BEAR"].includes(event));
}
for(const tf of ["H1","H4"]){
 const partial=rows(tf), gapAt=partial.length-11;
 partial.splice(gapAt,1);
 const x=analyzeFrame(partial,tf,NOW);
 assert.equal(x.state,"PARTIAL_OBSERVATION_UNVERIFIED_SESSION");
 assert.equal(x.unclassifiedGapsInChart,1);
 assert.equal(x.referenceOnlyGapAudit.gapCount,1);
 assert.equal(x.referenceOnlyGapAudit.sessionCalendarVerified,false);
 assert.equal(x.referenceOnlyGapAudit.bridgeBarsAllowed,false);
 assert.equal(x.contiguousBars,10);
 assert.equal(x.ema20,null);
 assert.equal(x.atr14,null);
 assert.ok(x.recentRangeLow20<x.recentRangeHigh20);
 assert.equal(x.signal,"WAIT");
 // Pre-gap prices can change arbitrarily (within OHLC validity)
 // without changing ANY private pivot/last-bar event.
 const alternate=partial.map((r,i)=>i<gapAt?{
  ...r,open:r.open+300,high:r.high+300,low:r.low+300,close:r.close+300}:r);
 const y=analyzeFrame(alternate,tf,NOW);
 assert.deepEqual(x,y);
 // Disallow a 6-bar tail from claiming any structure.
 const six=rows(tf).slice(-6);
 const z=analyzeFrame(six,tf,NOW);
 assert.equal(z.reason,"INVALID_CLOSED_BARS"); // no source warmup
}

// A pre-gap prefix must have zero effect on a post-gap run of 30 bars.
const gapped=rows("M15");
gapped.splice(12,1);
const seen=analyzeFrame(gapped,"M15",NOW);
const suffix=analyzeFrame(gapped.slice(12),"M15",NOW);
assert.equal(seen.contiguousBars,35);
assert.equal(seen.unclassifiedGapsInChart,1);
assert.equal(seen.ema20,suffix.ema20);
assert.deepEqual(seen.lastClosedEvents,suffix.lastClosedEvents);
// Future/open candles must never become pivot confirmations.
const forming=rows("M15");
forming.at(-1).time=new Date(NOW).toISOString();
assert.equal(analyzeFrame(forming,"M15",NOW).state,"INSUFFICIENT_VERIFIED_STRUCTURE");
const impossible=rows("M15");impossible.at(-1).high=0;
assert.equal(analyzeFrame(impossible,"M15",NOW).reason,"INVALID_CLOSED_BARS");
const unaligned=rows("M15");unaligned[0].time="2026-11-16T18:13:00Z";
assert.equal(analyzeFrame(unaligned,"M15",NOW).reason,"INVALID_CLOSED_BARS");
// No future bar changes the prior prefix result: running evaluation for
// a past as-of time on the same as-of-constrained prefix is deterministic.
const prefix=rows("M15").slice(0,-1);
const before=analyzeFrame(prefix,"M15",NOW);
const after=analyzeFrame(rows("M15"),"M15",NOW);
assert.equal(before.state,"OBSERVATION_ONLY");
assert.equal(before.lastClosedOpenUTC,prefix.at(-1).time);
assert.notEqual(before.lastClosedOpenUTC,after.lastClosedOpenUTC);
assert.deepEqual(before,analyzeFrame(prefix,"M15",NOW));
// Data is returned as private derived-only observations, not a recommendation.
const everything=analyzeChart(Object.fromEntries(["M15","H1","H4"].map(tf=>[tf,rows(tf)])),NOW);
assert.equal(everything.signal,"WAIT");
assert.equal(everything.executable,false);
assert.equal(everything.newsAndMacroIncluded,false);
assert.equal(everything.orderFlowIncluded,false);
assert.equal(everything.priceBasis,"MID_WITH_POSSIBLE_BID_SEED");
assert.deepEqual(Object.keys(everything.frames),["M15","H1","H4"]);
assert.ok(!JSON.stringify(everything).includes('"bars"'));
console.log("PASS BiQuote private technical: 3 timeframes confirmed pivots/ranges/EMA/ATR, session gaps fail closed, no trading or lookahead");
