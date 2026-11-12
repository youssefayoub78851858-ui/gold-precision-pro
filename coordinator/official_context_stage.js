"use strict";
// Explicitly opt-in official-source fetch, safe summary for private research UI.
// Fed monetary RSS, BLS calendar and H.15 are NOT comprehensive news/real-time DXY.
const {getOfficialMacroReview}=require("./official_macro_review");
const {readAutoDailyContext}=require("./h15_official_rss");
const iso=x=>typeof x==="string"&&Number.isFinite(Date.parse(x))&&/Z$/.test(x);
function stageOfficialContext(macro,h15,asOfUTC){
 const now=Date.parse(asOfUTC);
 if(!iso(asOfUTC)||!Number.isFinite(now))throw Error("Explicit UTC asOf required");
 const base={
  mode:"OFFICIAL_PARTIAL_CONTEXT_REVIEW",signal:"WAIT",executable:false,
  researchEligible:false,automaticTrading:false,directionalVote:false,
  sourceRequestsMadeHere:0,quoteSource:"NONE",xauPrice:null,
  newsCoverage:"PARTIAL_US_OFFICIAL_ONLY",politicalWorldNewsCoverage:false,
  geopoliticalWorldNewsCoverage:false,completeUsdCalendarCoverage:false,
  dxyAvailable:false,gcOrderFlowAvailable:false,
  ultimateLayerAdmission:{US02Y:false,US10Y:false,calendar:false,headlines:false,DXY:false,GC:false,orderFlow:false},
  alerts:[],headlines:[],calendar:[],rates:[],
  sourceStatus:{fed:"UNAVAILABLE",bls:"UNAVAILABLE",h15:"UNAVAILABLE"},
  blockingReasons:[],
 };
 if(!macro||typeof macro!=="object"||macro.mode!=="OFFICIAL_MACRO_REVIEW"||
    macro.signal!=="WAIT"||macro.executable!==false||
    !h15||typeof h15!=="object"||h15.signal!=="WAIT"||h15.executable!==false)
  return {...base,blockingReasons:["OFFICIAL_CONTEXT_CONTRACT_INVALID"]};
 const checked=macro.checkedUTC;
 const fresh=iso(checked)&&Date.parse(checked)<=now+60000&&now-Date.parse(checked)<=30*60000;
 const fed=fresh&&macro.feeds?.fed==="OFFICIAL_REFRESHED";
 const bls=fresh&&macro.feeds?.bls==="OFFICIAL_REFRESHED";
 const verifiedH15=h15.mode==="OFFICIAL_RECORDED_DAILY_CONTEXT"&&
                     h15.sourceStatus==="OFFICIAL_FED_RSS_REFRESHED"&&
                     h15.allowedRole==="MACRO_DAILY_CONTEXT_ONLY";
 const reasons=[];
 if(!fed)reasons.push("FED_MONETARY_RSS_UNAVAILABLE_OR_STALE");
 if(!bls)reasons.push("BLS_CALENDAR_UNAVAILABLE_OR_STALE");
 if(!verifiedH15)reasons.push("H15_DAILY_CONTEXT_UNAVAILABLE_OR_FALLBACK");
 const alerts=[],events=[],headlines=[],rates=[];
 if(bls&&Array.isArray(macro.calendar)){
  const seen=new Set();
  for(const e of macro.calendar.slice(0,50)){
   if(!e||e.source!=="U.S. Bureau of Labor Statistics"||
      e.eventType!=="SCHEDULED_NOT_RELEASED"||!iso(e.scheduledUTC)||
      !["CPI","PPI","JOBS","JOLTS","ECI","IMPORT_EXPORT","PRODUCTIVITY","REAL_EARNINGS"].includes(e.kind))
    continue;
   const t=Date.parse(e.scheduledUTC),id=e.kind+"|"+e.scheduledUTC;
   if(seen.has(id)||!Number.isFinite(t)||t<now-30*60000||t>now+7*86400000)continue;
   seen.add(id);
   const near=Math.abs(t-now)<=30*60000;
   const item={kind:e.kind,scheduledUTC:e.scheduledUTC,source:e.source,
               isWithinThirtyMinutes:near};
   events.push(item);
   if(near)alerts.push({code:"OFFICIAL_BLS_EVENT_WINDOW",severity:"RESEARCH_VETO",
                        source:"BLS",kind:e.kind,scheduledUTC:e.scheduledUTC});
  }
 }
 if(fed&&macro.headlineReview?.status==="RESEARCH_ONLY"&&Array.isArray(macro.headlineReview.items)){
  const seen=new Set();
  for(const x of macro.headlineReview.items.slice(0,20)){
   if(!x||!iso(x.publishedUTC)||!iso(x.availableUTC)||
      Date.parse(x.availableUTC)>now||Date.parse(x.publishedUTC)>Date.parse(x.availableUTC)||
      typeof x.id!=="string"||seen.has(x.id))continue;
   seen.add(x.id);
   headlines.push({id:x.id,publishedUTC:x.publishedUTC,
      category:x.category||"UNKNOWN",goldPressure:x.goldPressure||"UNDETERMINED",
      confidence:x.confidence==="LOW"?"LOW":"NONE",
      status:x.status||"UNCLASSIFIED",source:"Federal Reserve"});
  }
 }
 if(verifiedH15&&Array.isArray(h15.rates)){
  for(const x of h15.rates){
   if(!x||!["DGS2","DGS10"].includes(x.series)||
      !Number.isFinite(x.latestYieldPct)||x.latestYieldPct<0||x.latestYieldPct>30)continue;
   rates.push({series:x.series,dailyYieldPct:x.latestYieldPct,
               observationDate:h15.observedDate,
               frequency:"DAILY_NOT_INTRADAY",intradayVote:false});
  }
 }
 return {...base,sourceStatus:{fed:fed?"OFFICIAL_PARTIAL_ONLY":"UNAVAILABLE",
    bls:bls?"OFFICIAL_PARTIAL_ONLY":"UNAVAILABLE",
    h15:verifiedH15?"DAILY_REFERENCE_ONLY":"UNAVAILABLE"},
    calendar:events,headlines,rates,alerts,
    knownEventWindowVeto:alerts.length>0,
    blockingReasons:[...reasons,"WORLD_NEWS_AND_COMPLETE_CALENDAR_NOT_VERIFIED",
                     "INTRADAY_DXY_GC_AND_ORDER_FLOW_NOT_AVAILABLE"],
    note:"Government sources are partial context, not world geopolitical coverage, a surprise model or intraday trading authority"};
}
async function collectOfficialContext({nowMs=Date.now(),offline=true,fetchFn}={}){
 if(!Number.isFinite(nowMs))throw Error("Invalid clock");
 // Offline is intentionally the default: no network calls unless explicitly asked.
 const [macro,h15]=await Promise.all([
  getOfficialMacroReview({nowMs,offline,fetchFn}),
  readAutoDailyContext({nowMs,offline,fetchFn})
 ]);
 return stageOfficialContext(macro,h15,new Date(nowMs).toISOString());
}
module.exports={stageOfficialContext,collectOfficialContext};
