"use strict";
// Official/public SOURCE INVENTORY only. No fetches, keys, prices or orders.
// Source identity and public availability NEVER prove entitlement to automated
// cloud analysis, complete coverage, timeliness or exchange-data licensing.
const PROVIDERS=Object.freeze({
 fed:"https://www.federalreserve.gov/feeds/press_monetary.xml",
 bls:"https://www.bls.gov/schedule/news_release/bls.ics",
 h15:"https://www.federalreserve.gov/releases/h15/",
 dxy:"https://developer.ice.com/fixed-income-data-services/catalog/ice-data-indices-currency-indices",
 gc:"https://www.cmegroup.com/market-data.html"
});
const CONSTRAINTS=Object.freeze([
 "PUBLIC_PAGE_DOES_NOT_VERIFY_CLOUD_AUTOMATION_RIGHTS",
 "OFFICIAL_MACRO_FEEDS_ARE_NOT_A_FULL_MARKET_NEWS_FEED",
 "NO_PUBLIC_SOURCE_CONFERS_LIVE_DXY_OR_GC_TRADE_ENTITLEMENT",
 "LIVE_TRADING_AND_PAPER_ADMISSION_REMAIN_DISABLED"
]);
function inventoryForOfficialContext(stage){
 const status=stage&&typeof stage==="object"&&!Array.isArray(stage)?stage:{};
 const sources=status.sourceStatus&&typeof status.sourceStatus==="object"?status.sourceStatus:{};
 const has=(id,value)=>sources[id]===value;
 const fed=has("fed","OFFICIAL_PARTIAL_ONLY");
 const bls=has("bls","OFFICIAL_PARTIAL_ONLY");
 const daily=has("h15","DAILY_REFERENCE_ONLY");
 const rates=Array.isArray(status.rates)?status.rates:[];
 const rate=(series)=>daily&&rates.some(r=>r&&r.series===series&&
              r.frequency==="DAILY_NOT_INTRADAY"&&r.intradayVote===false&&
              Number.isFinite(r.dailyYieldPct));
 const rows=[
  {id:"FED_POLICY_RELEASES",name:"Federal Reserve monetary policy RSS",url:PROVIDERS.fed,
   channel:"OFFICIAL_PUBLIC_RSS",frequency:"EVENT_METADATA_ONLY",
   status:fed?"PARTIAL_OFFICIAL_CONTEXT_OBSERVED":"NOT_OBSERVED_OR_STALE",
   purpose:"Policy release timestamps/headlines; no measured gold response",
   fullCoverage:false,liveMarketFeed:false},
  {id:"BLS_RELEASE_SCHEDULE",name:"BLS official release schedule",url:PROVIDERS.bls,
   channel:"OFFICIAL_PUBLIC_CALENDAR",frequency:"SCHEDULED_EVENTS_ONLY",
   status:bls?"PARTIAL_OFFICIAL_CONTEXT_OBSERVED":"NOT_OBSERVED_OR_STALE",
   purpose:"Known CPI/PPI/jobs release windows only, not actual-vs-consensus",
   fullCoverage:false,liveMarketFeed:false},
  ...["DGS2","DGS10"].map(series=>({
   id:series,name:series==="DGS2"?"US two-year Treasury H.15":"US ten-year Treasury H.15",
   url:PROVIDERS.h15,channel:"OFFICIAL_PUBLIC_H15",
   frequency:"DAILY_NOT_INTRADAY",
   status:rate(series)?"DAILY_REFERENCE_OBSERVED":"NOT_OBSERVED_OR_STALE",
   purpose:"Daily yield context; not US02Y/US10Y intraday price confirmation",
   fullCoverage:false,liveMarketFeed:false
  })),
  {id:"DXY",name:"ICE U.S. Dollar Index",url:PROVIDERS.dxy,
   channel:"EXCHANGE_INDEX_MARKET_DATA",frequency:"INTRADAY_RIGHTS_UNVERIFIED",
   status:"NO_APPROVED_LIVE_SOURCE",purpose:"Intraday dollar confirmation; separate entitlement and API needed",
   fullCoverage:false,liveMarketFeed:false},
  {id:"GC",name:"CME COMEX gold futures",url:PROVIDERS.gc,
   channel:"EXCHANGE_FUTURES_MARKET_DATA",frequency:"INTRADAY_RIGHTS_UNVERIFIED",
   status:"NO_APPROVED_LIVE_SOURCE",purpose:"Independent contract-specific gold confirmation",
   fullCoverage:false,liveMarketFeed:false},
  {id:"GC_ORDER_FLOW",name:"GC trades / footprint / DOM",url:PROVIDERS.gc,
   channel:"EXCHANGE_LEVEL2_TRADE_DATA",frequency:"INTRADAY_RIGHTS_UNVERIFIED",
   status:"NO_APPROVED_LIVE_SOURCE",purpose:"Real aggressor trades, sequence continuity, depth and separate licensing",
   fullCoverage:false,liveMarketFeed:false},
  {id:"GLOBAL_GEO_NEWS",name:"Global political/geopolitical headlines",url:null,
   channel:"NOT_CONNECTED",frequency:"FULL_COVERAGE_NOT_VERIFIED",
   status:"MISSING_COVERAGE",purpose:"World-news coverage and publication latency remain unverified",
   fullCoverage:false,liveMarketFeed:false},
  {id:"USD_COMPLETE_CALENDAR",name:"Full USD economic calendar with actual and consensus",url:null,
   channel:"NOT_CONNECTED",frequency:"FULL_COVERAGE_NOT_VERIFIED",
   status:"MISSING_COVERAGE",purpose:"BLS schedule alone does not supply forecasts or all market events",
   fullCoverage:false,liveMarketFeed:false}
 ];
 const inventory=rows.map(r=>({
  ...r,usageRightsForCloudResearch:"NOT_SEPARATELY_VERIFIED",
  contextOnly:r.status==="PARTIAL_OFFICIAL_CONTEXT_OBSERVED"||r.status==="DAILY_REFERENCE_OBSERVED",
  ultimateLayerAdmitted:false,
  executable:false
 }));
 return {
  mode:"OFFLINE_SOURCE_COVERAGE_INVENTORY",signal:"WAIT",executable:false,
  sourceRequestsMade:0,liveDataTested:false,liveTradingAuthorized:false,
  accountOrPaymentRequiredForThisAudit:false,
  freePublicOfficialReferenceCount:inventory.filter(r=>r.contextOnly).length,
  fullNewsCoverageVerified:false,completeUsdCalendarVerified:false,
  realTimeDxyVerified:false,realTimeGcVerified:false,orderFlowVerified:false,
  completeUltimateStackVerified:false,
  sources:inventory,guardrails:[...CONSTRAINTS]
 };
}
module.exports={inventoryForOfficialContext,PROVIDERS};
