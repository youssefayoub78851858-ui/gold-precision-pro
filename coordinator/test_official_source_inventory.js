"use strict";
const assert=require("node:assert/strict");
const {inventoryForOfficialContext,PROVIDERS}=require("./official_source_inventory");
const {stageOfficialContext,collectOfficialContext}=require("./official_context_stage");
const at="2026-11-13T13:00:00.000Z";
const fake=Object.freeze({
 sourceStatus:{fed:"OFFICIAL_PARTIAL_ONLY",bls:"OFFICIAL_PARTIAL_ONLY",h15:"DAILY_REFERENCE_ONLY"},
 rates:[
  {series:"DGS2",frequency:"DAILY_NOT_INTRADAY",intradayVote:false,dailyYieldPct:3.7},
  {series:"DGS10",frequency:"DAILY_NOT_INTRADAY",intradayVote:false,dailyYieldPct:4.2}
 ]
});
function proveBlocked(v){
 assert.equal(v.signal,"WAIT");assert.equal(v.executable,false);
 assert.equal(v.liveDataTested,false);assert.equal(v.completeUltimateStackVerified,false);
 assert.equal(v.liveTradingAuthorized,false);assert.equal(v.fullNewsCoverageVerified,false);
 assert.equal(v.completeUsdCalendarVerified,false);assert.equal(v.sourceRequestsMade,0);
 assert.equal(v.sources.length,9);
 assert.ok(v.sources.every(r=>r.executable===false&&r.ultimateLayerAdmitted===false));
 assert.ok(v.sources.every(r=>r.usageRightsForCloudResearch==="NOT_SEPARATELY_VERIFIED"));
 assert.ok(v.sources.filter(r=>["DXY","GC","GC_ORDER_FLOW"].includes(r.id))
  .every(r=>r.status==="NO_APPROVED_LIVE_SOURCE"&&!r.liveMarketFeed));
}
(async()=>{
 assert.equal(PROVIDERS.bls,"https://www.bls.gov/schedule/news_release/bls.ics");
 assert.equal(PROVIDERS.fed,"https://www.federalreserve.gov/feeds/press_monetary.xml");
 let report=inventoryForOfficialContext(fake);proveBlocked(report);
 assert.equal(report.freePublicOfficialReferenceCount,4);
 assert.equal(report.sources.find(r=>r.id==="DGS2").frequency,"DAILY_NOT_INTRADAY");
 assert.equal(report.sources.find(r=>r.id==="DXY").url,PROVIDERS.dxy);
 const forged={sourceStatus:{fed:"OFFICIAL_PARTIAL_ONLY",bls:"OFFICIAL_PARTIAL_ONLY",h15:"DAILY_REFERENCE_ONLY"},
  rates:[{series:"DGS2",dailyYieldPct:4.1,frequency:"INTRADAY",intradayVote:true}]};
 report=inventoryForOfficialContext(forged);proveBlocked(report);
 assert.equal(report.sources.find(r=>r.id==="DGS2").status,"NOT_OBSERVED_OR_STALE");
 proveBlocked(inventoryForOfficialContext(null));
 const macro={mode:"OFFICIAL_MACRO_REVIEW",signal:"WAIT",executable:false,checkedUTC:at,
  feeds:{fed:"OFFICIAL_REFRESHED",bls:"OFFICIAL_REFRESHED"},calendar:[],headlineReview:{status:"RESEARCH_ONLY",items:[]}};
 const h15={mode:"OFFICIAL_RECORDED_DAILY_CONTEXT",signal:"WAIT",executable:false,
  sourceStatus:"OFFICIAL_FED_RSS_REFRESHED",allowedRole:"MACRO_DAILY_CONTEXT_ONLY",
  observedDate:"2026-11-12",rates:[
   {series:"DGS2",latestYieldPct:3.7},{series:"DGS10",latestYieldPct:4.2}]};
 const stage=stageOfficialContext(macro,h15,at);
 proveBlocked(stage.sourceInventory);
 assert.equal(stage.sourceInventory.freePublicOfficialReferenceCount,4);
 assert.equal(stage.ultimateLayerAdmission.DXY,false);
 const mismatch=stageOfficialContext({...macro,signal:"BUY"},h15,at);
 proveBlocked(mismatch.sourceInventory);
 assert.equal(mismatch.sourceInventory.freePublicOfficialReferenceCount,0);
 // Offline collection must not invoke fetch despite a passed malicious callback.
 const offline=await collectOfficialContext({offline:true,nowMs:Date.parse(at),
  fetchFn:()=>{throw Error("UNEXPECTED_NETWORK");}});
 proveBlocked(offline.sourceInventory);
 assert.equal(offline.sourceInventory.freePublicOfficialReferenceCount,0);
 console.log("PASS source inventory: public partial only, rights unverified, zero market calls, WAIT");
})().catch(e=>{console.error(e);process.exitCode=1});
