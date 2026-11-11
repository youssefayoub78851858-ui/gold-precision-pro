"use strict";
const fs=require("node:fs");
const path=require("node:path");
const SNAPSHOT=path.join(__dirname,"..","research","official","h15-daily-context-2026-11-10.json");
function isoDay(day){
 return typeof day==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(day)&&!Number.isNaN(Date.parse(day+"T00:00:00Z"));
}
function readH15DailyContext(){
 const data=JSON.parse(fs.readFileSync(SNAPSHOT,"utf8"));
 if(data.kind!=="OFFICIAL_DAILY_CONTEXT_SNAPSHOT"||
    data.sourceURL!=="https://www.federalreserve.gov/releases/h15/"||
    data.frequency!=="DAILY"||data.isLive!==false||
    data.isAutomaticallyUpdated!==false||data.forDisplayOnly!==true||
    data.eligibleForIntradayConfirmation!==false||
    data.eligibleForUltimateTrading!==false||
    data.observationAvailabilityTimestamp!==null||
    !isoDay(data.latestObservedDate)||!isoDay(data.previousObservedDate)||
    !isoDay(data.publishedReleaseDate)||
    data.previousObservedDate>=data.latestObservedDate||
    data.latestObservedDate>=data.publishedReleaseDate||
    !Array.isArray(data.data)||data.data.length!==2) throw Error("Official daily context contract invalid");
 const expected={DGS2:2,DGS10:10};
 const seen=new Set();
 const rates=data.data.map(row=>{
   if(!Object.hasOwn(expected,row.series)||seen.has(row.series)||
      row.maturityYears!==expected[row.series]||
      !Number.isFinite(row.latest)||!Number.isFinite(row.previous)||
      row.latest<0||row.latest>30||row.previous<0||row.previous>30)
      throw Error("Official H15 rates invalid");
   seen.add(row.series);
   return {series:row.series,maturityYears:row.maturityYears,
     latestYieldPct:row.latest,previousYieldPct:row.previous,
     changePercentagePoints:Number((row.latest-row.previous).toFixed(3))};
 });
 if(seen.size!==2)throw Error("Missing H15 series");
 return {
   mode:"OFFICIAL_RECORDED_DAILY_CONTEXT",signal:"WAIT",executable:false,
   dataStatus:"DAILY_REFERENCE_ONLY",dataFresh:false,liveData:false,
   providerRequests:0,networkEnabled:false,trading:"disabled",
   sourceName:data.sourceName,sourceURL:data.sourceURL,
   publicationDate:data.publishedReleaseDate,
   observedDate:data.latestObservedDate,
   previousObservedDate:data.previousObservedDate,
   reviewedDate:data.snapshotReviewedDate,
   firstAvailabilityVerified:false,
   lastUpdateType:"MANUALLY_RECORDED_OFFICIAL_SNAPSHOT",
   allowedRole:"MACRO_DAILY_CONTEXT_ONLY",
   readyForFiveMinuteGate:false,
   readyForUltimateTrading:false,
   rates,
   warning:"Official H.15 daily yield reference, not intraday US02Y/US10Y quotes. Last known official observations only; timestamp of first availability was not independently verified. This is not live data or a trade signal."
 };
}
module.exports={readH15DailyContext};
