"use strict";
// Offline safety regression tests. Run: node --test coordinator/tests/review_dashboard_safety.test.js
// No provider requests, credentials, orders or external dependencies.
const test=require("node:test");
const assert=require("node:assert/strict");
const {validateChart,validateSnapshot,localLatestParity,researchWatch,technicalObservations,continuityReport,validateDailyH15,validateOfficialMacro,validatePreapproval}=
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
 assert.ok(js.includes("if(Date.now()>expiry&&!markStale"));
 assert.ok(!js.includes("order_send("));
});

test("six internal offline modules appear on mobile without accepting forged live approvals",()=>{
 const {validateInternalHandoff}=require("../../review-dashboard.js");
 const {inspect}=require("../internal_offline_handoff");
 const packet=inspect();
 assert.equal(packet.status,"OFFLINE_INTERFACES_CHECKED_EXTERNAL_EVIDENCE_PENDING");
 assert.deepEqual(validateInternalHandoff(packet),{
  internalOfflineContractsChecked:true,signal:"WAIT",tradeReady:false
 });
 for(const fake of [
  {...packet,executable:true},
  {...packet,signal:"BUY"},
  {...packet,paperOrdersAllowed:true},
  {...packet,providerConnectionEnabled:true},
  {...packet,independentSourceRightsVerified:true},
  {...packet,externalProviderDecisionDeferredToLastStage:false},
  {...packet,providerRequestsMade:1},
  {...packet,paymentsMade:1},
  {...packet,entry:4000},
  {...packet,historicalArchiveAudit:{...packet.historicalArchiveAudit,
    independentAccuracyPct:99.8}},
  {...packet,historicalArchiveAudit:{...packet.historicalArchiveAudit,
    archiveUsedAsIndependentHoldout:true}},
  {...packet,historicalArchiveAudit:{...packet.historicalArchiveAudit,
    statisticallyValidated:true}},
  {...packet,historicalArchiveAudit:{...packet.historicalArchiveAudit,
    providerRequestsMade:1}},
  {...packet,checks:{...packet.checks,sourceRequirements:"LIVE"}},
  {...packet,stageStatus:{...packet.stageStatus,finalProvider:"CONNECTED"}}
 ]) assert.equal(validateInternalHandoff(fake),null);
 const fs=require("node:fs"),path=require("node:path");
 const html=fs.readFileSync(path.resolve(__dirname,"../../review-dashboard.html"),"utf8");
 const js=fs.readFileSync(path.resolve(__dirname,"../../review-dashboard.js"),"utf8");
 assert.ok(html.includes('id="internal-handoff"'));
 assert.ok(html.includes('id="historical-archive-audit"'));
 for(const field of ["src","candles","analysis","macro","paper","provider","note"])
  assert.ok(html.includes('id="internal-gate-'+field+'"'));
 assert.ok(js.includes('"/api/v3/ultimate/internal-handoff"'));
 assert.ok(js.includes('validateInternalHandoff(await r.json())'));
 assert.ok(js.includes('void loadInternalHandoff()'));
 assert.ok(js.includes('"WAIT — ربط داخلي غير متحقق حالياً"'));
 assert.ok(js.includes("report.historicalArchiveAudit.developmentM15Bars"));
});

test("session-checked foreground auto refresh preserves stale history but not tradability",()=>{
 const fs=require("node:fs"),path=require("node:path");
 const js=fs.readFileSync(path.resolve(__dirname,"../../review-dashboard.js"),"utf8");
 const ui=fs.readFileSync(path.resolve(__dirname,"../../review-dashboard.html"),"utf8");
 const server=fs.readFileSync(path.resolve(__dirname,"../../server.js"),"utf8");
 assert.ok(js.includes("const AUTO_POLL_MS=10000, SOURCE_ERROR_BACKOFF_MS=10000, MAX_STALE_MS=600000"));
 assert.ok(js.includes('document.addEventListener("DOMContentLoaded"'));
 assert.ok(js.includes('"/api/v3/ultimate/biquote-viewer-status"'));
 assert.ok(js.includes('packet?.viewerSessionReady!==true'));
 assert.ok(js.includes("function markStale("));
 assert.ok(js.includes('$("decision").textContent="WAIT"'));
 assert.ok(js.includes('document.visibilityState==="hidden"'));
 assert.ok(server.includes("const ready=session.authenticated(req.headers);"));
 assert.ok(server.includes("marketDataRequested:false,ordersSent:0"));
 assert.ok(ui.includes('id="auto-state"'));
 assert.ok(!js.includes("localStorage"));
 assert.ok(!js.includes("sessionStorage"));
});

test("automatic mobile display shows a countdown but never implies a live quote",()=>{
 const fs=require("node:fs"),path=require("node:path");
 const js=fs.readFileSync(path.resolve(__dirname,"../../review-dashboard.js"),"utf8");
 assert.match(js,/function updateAutoLabel\(/);
 assert.match(js,/Number\.isFinite\(nextPollAt\)/);
 assert.match(js,/const old=state&&Date\.now\(\)>expiry\?"بيانات قديمة · ":""/);
 assert.match(js,/updateAutoLabel\(\)/);
 assert.ok(js.includes('viewerReady?"فحص السعر":"محاولة اتصال"'));
 // A temporary 503/data failure must NOT silently switch the 10s UI
 // cadence to 30s. HTTP 429 is an explicit 3-minute exception to avoid
 // provider quota abuse; 30s quote freshness stays an independent gate.
 assert.ok(js.includes('nextPollAt=Date.now()+(error.message==="RATE_LIMITED"?180000:SOURCE_ERROR_BACKOFF_MS)'));
 assert.ok(js.includes('"تلقائي · إعادة فحص خلال 10 ثوانٍ"'));
 assert.ok(js.includes('"تلقائي · حد الطلبات: إعادة بعد 3 دقائق"'));
 assert.ok(js.includes('d.quoteAgeSeconds>30'));
 assert.ok(js.includes('$("decision").textContent="WAIT"'));
 assert.ok(!js.includes("localStorage"));
 assert.ok(!js.includes("executable:true"));
});

test("UTC continuity reports private CLOSED bars without fabricating gaps",()=>{
 const clean=continuityReport(validateChart(chart(now),now));
 for(const tf of Object.keys(W)){
  assert.equal(clean[tf].observed,24);
  assert.equal(clean[tf].utcTail,24);
  assert.equal(clean[tf].utcGapPairs,0);
 }
 const missing=chart(now);
 missing.H1.splice(3,1);missing.H4.splice(16,1);
 const result=continuityReport(validateChart(missing,now));
 assert.equal(result.H1.utcTail,20);
 assert.equal(result.H1.meets21Utc,false);
 assert.equal(result.H1.utcGapPairs,1);
 assert.equal(result.H1.unobservedUtcSlots,1);
 assert.equal(result.H4.utcTail,7);
 assert.equal(result.M15.utcGapPairs,0);
});
test("UTC continuity fails closed on malformed inputs and UI clears private results",()=>{
 const c=validateChart(chart(now),now);c.H1[5].t=c.H1[4].t;
 assert.equal(continuityReport(c),null);
 const fs=require("node:fs"),path=require("node:path");
 const html=fs.readFileSync(path.resolve(__dirname,"../../review-dashboard.html"),"utf8");
 const script=fs.readFileSync(path.resolve(__dirname,"../../review-dashboard.js"),"utf8");
 assert.ok(html.includes('id="continuity-details"'));
 assert.ok(!html.includes('id="continuity-details" open'));
 assert.ok(script.includes("resetContinuity();"));
 assert.ok(script.includes("renderContinuity(verified);"));
 assert.ok(!script.includes("localStorage"));
});

test("official DAILY H15 safety requires matching source, recent date and both rate series",()=>{
 const pkt={
  mode:"OFFICIAL_RECORDED_DAILY_CONTEXT",signal:"WAIT",executable:false,
  liveData:false,dataFresh:false,readyForFiveMinuteGate:false,
  readyForUltimateTrading:false,allowedRole:"MACRO_DAILY_CONTEXT_ONLY",
  dataStatus:"DAILY_REFERENCE_ONLY",sourceURL:"https://www.federalreserve.gov/releases/h15/",
  sourceStatus:"OFFICIAL_FED_RSS_REFRESHED",observedDate:"2026-11-19",
  rates:[{series:"DGS2",maturityYears:2,latestYieldPct:4.67},
    {series:"DGS10",maturityYears:10,latestYieldPct:5.11}]
 };
 const at=Date.parse("2026-11-21T10:00:00Z");
 assert.equal(validateDailyH15(pkt,at).DGS2,4.67);
 assert.equal(validateDailyH15(pkt,at).DGS10,5.11);
 assert.equal(validateDailyH15({...pkt,sourceStatus:"STORED_FALLBACK"},at).historical,true);
 for(const bad of [
   {...pkt,signal:"BUY"},{...pkt,executable:true},
   {...pkt,liveData:true},{...pkt,readyForFiveMinuteGate:true},
   {...pkt,sourceURL:"https://evil.example"},{...pkt,observedDate:"2026-11-22"},
   {...pkt,observedDate:"2026-11-09"},
   {...pkt,rates:[pkt.rates[0],pkt.rates[0]]},
   {...pkt,rates:[{...pkt.rates[0],latestYieldPct:Infinity},pkt.rates[1]]}
 ])assert.equal(validateDailyH15(bad,at),null);
});
test("mobile H15 display is decoupled from private prices and trading votes",()=>{
 const fs=require("node:fs"),p=require("node:path");
 const script=fs.readFileSync(p.resolve(__dirname,"../../review-dashboard.js"),"utf8");
 const html=fs.readFileSync(p.resolve(__dirname,"../../review-dashboard.html"),"utf8");
 assert.ok(script.includes('fetch("/api/v3/ultimate/free-context"'));
 assert.ok(script.includes('credentials:"omit"'));
 assert.ok(script.includes("nextH15At=Date.now()+3600000"));
 assert.ok(script.includes("h15Epoch++"));
 for(const id of ["us02y-daily","us10y-daily","h15-daily-note"])
  assert.ok(html.includes('id="'+id+'"'));
 assert.ok(!script.includes("order_send("));
});

test("official Fed and BLS metadata are bounded, authentic and cannot enable signals",()=>{
 const at=Date.parse("2026-11-21T08:30:00Z");
 const a={mode:"OFFICIAL_MACRO_REVIEW",signal:"WAIT",executable:false,
  liveData:false,trading:"disabled",automaticTrading:false,
  firstAvailabilityVerified:false,marketDataRequests:0,
  fedSource:"https://www.federalreserve.gov/feeds/press_monetary.xml",
  blsSource:"https://www.bls.gov/schedule/news_release/bls.ics",
  checkedUTC:"2026-11-21T08:29:00.000Z",
  feeds:{fed:"OFFICIAL_REFRESHED",bls:"OFFICIAL_REFRESHED"},
  headlines:[{title:"Fed statement",source:"Federal Reserve",
   eventType:"RELEASED_POLICY_HEADLINE",publishedUTC:"2026-11-20T18:00:00.000Z",
   url:"https://www.federalreserve.gov/newsevents/pressreleases/monetary20261120a.htm"}],
  calendar:[{kind:"CPI",scheduledUTC:"2026-11-25T13:30:00.000Z",
   localTimezone:"America/New_York",source:"U.S. Bureau of Labor Statistics",
   eventType:"SCHEDULED_NOT_RELEASED"}]};
 const v=validateOfficialMacro(a,at);
 assert.equal(v.signal,"WAIT");assert.equal(v.executable,false);
 assert.equal(v.latestFed.title,"Fed statement");assert.equal(v.nextBls.kind,"CPI");
 for(const bad of [
  {...a,signal:"BUY"},{...a,executable:true},{...a,automaticTrading:true},
  {...a,checkedUTC:"2026-11-21T09:00:00.000Z"},
  {...a,checkedUTC:"2026-11-20T00:00:00.000Z"},
  {...a,headlines:[{...a.headlines[0],url:"https://evil.example/x"}]},
  {...a,calendar:[{...a.calendar[0],scheduledUTC:"2026-11-20T13:30:00.000Z"}]},
  {...a,headlines:[{...a.headlines[0],publishedUTC:"2026-11-21T09:00:00.000Z"}]}
 ])assert.equal(validateOfficialMacro(bad,at),null);
 const partial=validateOfficialMacro({...a,feeds:{fed:"UNAVAILABLE",bls:"UNAVAILABLE"},
  headlines:[],calendar:[]},at);
 assert.equal(partial.latestFed,null);assert.equal(partial.nextBls,null);
});

test("four-stage preapproval view cannot promote fabricated ready sources",()=>{
 const {inspect}=require("../preapproval_four_tracks_status");
 const data=inspect();
 assert.equal(validatePreapproval(data).signal,"WAIT");
 assert.equal(validatePreapproval({...data,executable:true}),null);
 assert.equal(validatePreapproval({...data,verifiedLiveLayerCount:1}),null);
 assert.equal(validatePreapproval({...data,steps:{...data.steps,
  capitalDemo:{...data.steps.capitalDemo,connected:true}}}),null);
 const fs=require("node:fs"),p=require("node:path");
 const html=fs.readFileSync(p.resolve(__dirname,"../../review-dashboard.html"),"utf8");
 for(const id of ["preapproval","stage-official","stage-independent","stage-paper","stage-capital","stage-note"])
  assert.ok(html.includes('id="'+id+'"'));
 assert.ok(!html.includes('id="preapproval" open'));
});
