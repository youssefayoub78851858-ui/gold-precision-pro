"use strict";
// Offline safety regression tests. Run: node --test coordinator/tests/review_dashboard_safety.test.js
// No provider requests, credentials, orders or external dependencies.
const test=require("node:test");
const assert=require("node:assert/strict");
const {validateChart,validateSnapshot,localLatestParity,researchWatch,technicalObservations}=
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

test("latest parity refuses missing M15 constituents even with plausible higher frames",()=>{
 const source=chart(now);
 // Remove one required M15 candle; chart validator accepts bounded historical gaps,
 // but the parity guard must never treat a gap as matching higher frames.
 source.M15.splice(20,1);
 const checked=validateChart(source,now);
 assert.ok(checked);
 assert.equal(localLatestParity(checked),false);
 const {localCoveredParityAudit}=require("../../review-dashboard.js");
 const audit=localCoveredParityAudit(checked);
 assert.ok(audit.H1.fullyCovered<6);
});
test("snapshot rejects absent rights and research safety fields",()=>{
 const packet={signal:"WAIT",executable:false,researchEligible:true,
  tradePlanExecutable:false,paperOrdersAllowed:false,orderEndpointsCalled:false,
  status:"OBSERVED_READONLY_UNVERIFIED"};
 assert.equal(validateSnapshot(packet,now),null);
});

test("private V3 technical watch blocks unauthenticated and unlicensed observations",()=>{
 const {observe}=require("../biquote_private_v3_watch");
 const anonymous=observe({origin:"PUBLIC",chart:chart(now)});
 assert.equal(anonymous.signal,"WAIT");
 assert.equal(anonymous.executable,false);
 assert.equal(anonymous.entry,null);
 assert.equal(anonymous.stopLoss,null);
 assert.equal(anonymous.takeProfit,null);
 assert.equal(anonymous.reason,"NOT_AUTHENTICATED_PERSONAL_CHART");
 const noRights=observe({origin:"AUTHENTICATED_PERSONAL_BIQUOTE_PRIVATE_CHART",
  priceBasis:"UNKNOWN",chart:chart(now)});
 assert.equal(noRights.signal,"WAIT");
 assert.equal(noRights.reason,"MIXED_OR_UNVERIFIED_PRICE_BASIS");
 assert.equal(noRights.liveOrdersAllowed,false);
});
test("private V3 watch refuses unsupported cross-frame evidence",()=>{
 const {observe}=require("../biquote_private_v3_watch");
 const x=observe({origin:"AUTHENTICATED_PERSONAL_BIQUOTE_PRIVATE_CHART",
  priceBasis:"MID_WITH_POSSIBLE_BID_SEED",sourceSnapshotStatus:"WAIT_CROSS_FRAME_GAPS",
  chart:chart(now),asOfUTC:new Date(now).toISOString()});
 assert.equal(x.signal,"WAIT");
 assert.equal(x.status,"WAIT_CROSS_FRAME_EVIDENCE");
 assert.equal(x.reason,"SOURCE_HAS_UNRESOLVED_CROSS_FRAME_GAPS");
 assert.equal(x.brokerOrdersSent,0);
});

test("research-only MTF alignment cannot authorize orders",()=>{
 const {makeMtfReadiness}=require("../biquote_mtf_readiness");
 const frame=(close,ema20)=>({state:"OBSERVATION_ONLY",sessionCalendarVerified:false,
  executable:false,tradeEligible:false,validForEntry:false,signal:"WAIT",
  contiguousBars:24,unclassifiedGapsInChart:0,ema20,lastClosed:close});
 const analysis={frames:{M15:frame(3001,3000),H1:frame(3001,3000),H4:frame(3001,3000)}};
 const comparison={H1:{completeMatches:2,completeMismatches:0,incompleteM15Groups:0},
  H4:{completeMatches:1,completeMismatches:0,incompleteM15Groups:0}};
 const x=makeMtfReadiness(analysis,comparison);
 assert.equal(x.alignment,"OBSERVATION_ALL_ABOVE_EMA20");
 assert.equal(x.signal,"WAIT");
 assert.equal(x.tradeEligible,false);
 assert.equal(x.executable,false);
 assert.equal(x.researchEligible,false);
 assert.ok(x.blockerCodes.includes("PROFITABILITY_NOT_INDEPENDENTLY_VALIDATED"));
 assert.ok(x.blockerCodes.includes("UNDERLYING_MT5_DATA_RIGHTS_UNVERIFIED"));
});
test("MTF readiness refuses invalid or partial higher-frame evidence",()=>{
 const {makeMtfReadiness}=require("../biquote_mtf_readiness");
 const x=makeMtfReadiness({frames:{}},{});
 assert.equal(x.state,"INVALID_INPUT_BLOCKED");
 assert.equal(x.alignment,"NOT_ASSESSABLE");
 assert.equal(x.signal,"WAIT");
 assert.equal(x.executable,false);
});

test("MTF OHLC mismatch stays WAIT and records a blocker",()=>{
 const {makeMtfReadiness}=require("../biquote_mtf_readiness");
 const frame=()=>({state:"OBSERVATION_ONLY",sessionCalendarVerified:false,
  executable:false,tradeEligible:false,validForEntry:false,signal:"WAIT",
  contiguousBars:24,unclassifiedGapsInChart:0,ema20:3000,lastClosed:3001});
 const analysis={frames:{M15:frame(),H1:frame(),H4:frame()}};
 const comparisons={H1:{completeMatches:1,completeMismatches:1,incompleteM15Groups:0},
  H4:{completeMatches:1,completeMismatches:0,incompleteM15Groups:0}};
 const x=makeMtfReadiness(analysis,comparisons);
 assert.equal(x.quality,"OHLC_MISMATCH");
 assert.ok(x.blockerCodes.includes("CROSS_FRAME_OHLC_MISMATCH"));
 assert.equal(x.signal,"WAIT");
 assert.equal(x.tradeEligible,false);
 assert.equal(x.executable,false);
});
test("MTF missing constituent M15 bars stays WAIT",()=>{
 const {makeMtfReadiness}=require("../biquote_mtf_readiness");
 const frame=()=>({state:"OBSERVATION_ONLY",sessionCalendarVerified:false,
  executable:false,tradeEligible:false,validForEntry:false,signal:"WAIT",
  contiguousBars:24,unclassifiedGapsInChart:0,ema20:3000,lastClosed:3001});
 const analysis={frames:{M15:frame(),H1:frame(),H4:frame()}};
 const comparisons={H1:{completeMatches:1,completeMismatches:0,incompleteM15Groups:2},
  H4:{completeMatches:1,completeMismatches:0,incompleteM15Groups:0}};
 const x=makeMtfReadiness(analysis,comparisons);
 assert.equal(x.quality,"PARTIAL_M15_CONSTITUENTS");
 assert.ok(x.blockerCodes.includes("INCOMPLETE_M15_CONSTITUENTS"));
 assert.equal(x.signal,"WAIT");
 assert.equal(x.executable,false);
});

test("21-H4 audit cannot be certified by one truncated provider snapshot",()=>{
 const {assess}=require("../biquote_snapshot_capacity_gate");
 const x=assess();
 assert.equal(x.signal,"WAIT");
 assert.equal(x.executable,false);
 assert.equal(x.requiredContiguousH4,21);
 assert.equal(x.requiredM15Constituents,336);
 assert.equal(x.requiredH1Constituents,84);
 assert.equal(x.singleSnapshotCanProve21H4M15Parity,false);
 assert.equal(x.archiveRequiredForFullWindow,true);
 assert.equal(x.archiveCurrentlyVerified,false);
});

test("closed UTC source candles support descriptive EMA RSI ATR only",()=>{
 const series=technicalObservations(validateChart(chart(now),now));
 for(const tf of Object.keys(W)){
  assert.equal(series[tf].status,"LOCAL_CLOSED_MID_ONLY");
  assert.equal(series[tf].count,24);
  assert.equal(series[tf].ema20,3001);
  assert.equal(series[tf].rsi14,50);
  assert.ok(series[tf].atr14>0);
  assert.equal(series[tf].closeVsEma,"EQUAL");
 }
 assert.ok(!JSON.stringify(series).includes("BUY"));
 assert.ok(!JSON.stringify(series).includes("SELL"));
});
test("gap in a recent H4 candle blocks H4 indicator but not M15",()=>{
 const x=chart(now);x.H4.splice(16,1);
 const series=technicalObservations(validateChart(x,now));
 assert.equal(series.H4.status,"INSUFFICIENT");
 assert.equal(series.H4.count,7);
 assert.equal(series.H4.ema20,undefined);
 assert.equal(series.M15.status,"LOCAL_CLOSED_MID_ONLY");
});
test("malformed or absent chart never fabricates indicators",()=>{
 const result=technicalObservations({M15:[null],H1:[],H4:null});
 for(const tf of Object.keys(W))assert.notEqual(result[tf]?.status,"LOCAL_CLOSED_MID_ONLY");
});
test("main Render review UI folds indicators and clears private metrics",()=>{
 const fs=require("node:fs"),path=require("node:path");
 const html=fs.readFileSync(path.resolve(__dirname,"../../review-dashboard.html"),"utf8");
 const js=fs.readFileSync(path.resolve(__dirname,"../../review-dashboard.js"),"utf8");
 assert.match(html,/<details id="technical" class="panel technical-panel">/);
 assert.ok(!html.includes('<details id="technical" open'));
 for(const tf of ["m15","h1","h4"])
  for(const suffix of ["technical","ema","rsi","atr","technical-quality"])
   assert.ok(html.includes('id="'+tf+'-'+suffix+'"'));
 assert.ok(js.includes("resetTechnical();"));
 assert.ok(js.includes("renderTechnical(verified.chart);"));
 assert.ok(js.includes("if(Date.now()>expiry)"));
 assert.ok(!js.includes("order_send("));
});
