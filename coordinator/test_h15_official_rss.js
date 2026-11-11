"use strict";
const assert=require("node:assert/strict");
const {SERIES,parseFeed,buildOfficialDailyContext,readAutoDailyContext}=require("./h15_official_rss");
function xml(years,latest,prev,latestDate="2026-11-09",prevDate="2026-11-06"){
 const entry=(pct,day)=>'<item><title>US: H15 '+pct+' '+day+' FRB '+years+'-year Treasury constant maturity</title><pubDate>Tue, 10 Nov 2026 21:15:00 GMT</pubDate></item>';
 return '<rss version="2.0"><channel><title>Federal Reserve H15</title>'+entry(latest,latestDate)+entry(prev,prevDate)+'</channel></rss>';
}
async function run(){
 const a=xml(2,4.56,4.51),b=xml(10,4.88,4.86);
 assert.deepEqual(parseFeed(a,2).latest.date,"2026-11-09");
 assert.equal(parseFeed(a,2).previous.pct,4.51);
 const result=buildOfficialDailyContext([a,b],new Date("2026-11-11T14:30:00Z"));
 assert.equal(result.mode,"OFFICIAL_RECORDED_DAILY_CONTEXT");
 assert.equal(result.signal,"WAIT");
 assert.equal(result.executable,false);
 assert.equal(result.readyForFiveMinuteGate,false);
 assert.equal(result.readyForUltimateTrading,false);
 assert.equal(result.liveData,false);
 assert.equal(result.providerRequests,0);
 assert.equal(result.officialFeedRequests,2);
 assert.equal(result.rates[0].changePercentagePoints,0.05);
 assert.equal(result.rates[1].changePercentagePoints,0.02);
 assert.throws(()=>buildOfficialDailyContext([a,xml(10,4.88,4.86,"2026-11-10")],new Date("2026-11-11T14:30:00Z")),/not aligned/);
 assert.throws(()=>buildOfficialDailyContext([a,b],new Date("2026-11-08T14:30:00Z")),/future/);
 assert.throws(()=>buildOfficialDailyContext([a,b],new Date("2026-12-10T14:30:00Z")),/Stale/);
 assert.throws(()=>parseFeed(xml(2,49,4.51),2),/Not enough/);
 assert.throws(()=>parseFeed('<rss><channel></channel></rss>',2),/format invalid/);
 const requested=[];
 const fakeFetch=async url=>{
  requested.push(url);
  const i=SERIES.findIndex(s=>s.url===url);
  assert.ok(i>=0,"No untrusted URL");
  return {ok:true,text:async()=>i===0?a:b};
 };
 const actual=await readAutoDailyContext({fetchFn:fakeFetch,nowMs:Date.parse("2026-11-11T14:30:00Z")});
 assert.equal(requested.length,2);
 assert.equal(actual.observedDate,"2026-11-09");
 assert.equal(actual.sourceStatus,"OFFICIAL_FED_RSS_REFRESHED");
 assert.equal(actual.readyForUltimateTrading,false);
 const cached=await readAutoDailyContext({fetchFn:()=>{throw Error("No double fetch");},nowMs:Date.parse("2026-11-11T14:31:00Z")});
 assert.equal(cached.rates[0].latestYieldPct,4.56);
 const offline=await readAutoDailyContext({offline:true});
 assert.equal(offline.sourceStatus,"STORED_FALLBACK");
 assert.equal(offline.readyForFiveMinuteGate,false);
 assert.equal(offline.officialFeedRequests,0);
 const failed=await readAutoDailyContext({
  fetchFn:async()=>({ok:false,status:403}),
  nowMs:Date.parse("2026-11-12T17:00:00Z")
 });
 assert.equal(failed.sourceStatus,"STORED_FALLBACK");
 assert.equal(failed.refreshDiagnosticCode,"FED_RSS_HTTP_ERROR");
 assert.equal(failed.signal,"WAIT");
 assert.equal(failed.readyForUltimateTrading,false);
 assert.equal(failed.readyForFiveMinuteGate,false);
 console.log("PASS official H15 RSS: validate series/dates, no market vendor calls, cache, safe fallback, WAIT and gate isolation");
}
run().catch(e=>{console.error(e);process.exitCode=1;});
