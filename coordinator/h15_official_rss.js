"use strict";
// Optional public H.15 RSS reference; never a market execution source.
const {readH15DailyContext}=require("./h15_daily_context");
const SERIES=[
 {series:"DGS2",years:2,url:"https://www.federalreserve.gov/feeds/Data/H15_H15_RIFLGFCY02_N.B.XML"},
 {series:"DGS10",years:10,url:"https://www.federalreserve.gov/feeds/Data/H15_H15_RIFLGFCY10_N.B.XML"}
];
let cached=null,until=0,inflight=null;
const fullDay=/^\d{4}-\d{2}-\d{2}$/;
function getTag(xml,tag){
 const m=xml.match(new RegExp("<"+tag+"(?:\\s[^>]*)?>([\\s\\S]*?)<\\/"+tag+">","i"));
 if(!m)return null;
 return m[1].replace(/^<!\[CDATA\[|\]\]>$/g,"").trim();
}
function parseFeed(xml,years){
 if(typeof xml!=="string"||xml.length>500000||!xml.includes("<item"))throw Error("H15 RSS format invalid");
 const items=[...xml.matchAll(/<item(?:\s[^>]*)?>([\s\S]*?)<\/item>/gi)];
 const rows=[];
 for(const item of items){
   const title=getTag(item[1],"title");
   const match=title&&title.match(/^US:\s*H15\s+([0-9]+(?:\.[0-9]+)?)\s+(\d{4}-\d{2}-\d{2})\s+FRB\s+(2|10)-year Treasury constant maturity$/i);
   if(!match||Number(match[3])!==years)continue;
   const pct=Number(match[1]),date=match[2];
   if(!(pct>=0&&pct<=30)||!fullDay.test(date)||new Date(date+"T00:00:00Z").toISOString().slice(0,10)!==date)continue;
   const pub=getTag(item[1],"pubDate");
   const publishedUTC=pub&&!Number.isNaN(Date.parse(pub))?new Date(pub).toISOString():null;
   rows.push({date,pct,publishedUTC});
 }
 rows.sort((a,b)=>b.date.localeCompare(a.date));
 const unique=[];
 for(const row of rows){
  const prior=unique.find(x=>x.date===row.date);
  if(prior){if(prior.pct!==row.pct)throw Error("Conflicting H15 values");continue;}
  unique.push(row);
 }
 if(unique.length<2)throw Error("Not enough official H15 observations");
 return {latest:unique[0],previous:unique[1]};
}
function buildOfficialDailyContext(xmls,now=new Date()){
 if(!Array.isArray(xmls)||xmls.length!==2)throw Error("Missing official RSS");
 const parsed=SERIES.map((s,i)=>parseFeed(xmls[i],s.years));
 const first=parsed[0];
 if(parsed.some(x=>x.latest.date!==first.latest.date||x.previous.date!==first.previous.date))
  throw Error("Official H15 source dates are not aligned");
 const observed=Date.parse(first.latest.date+"T00:00:00Z");
 const nowMS=now.getTime();
 if(!Number.isFinite(nowMS)||nowMS<observed||nowMS-observed>10*86400000)throw Error("Stale or future H15 observation");
 const dates=parsed.map(x=>x.latest.publishedUTC).filter(Boolean);
 for(const t of dates){
  if(Date.parse(t)>nowMS+3600000||Date.parse(t)<observed-86400000)throw Error("Invalid RSS publication timestamp");
 }
 return {
  mode:"OFFICIAL_RECORDED_DAILY_CONTEXT",signal:"WAIT",executable:false,
  dataStatus:"DAILY_REFERENCE_ONLY",dataFresh:false,liveData:false,
  providerRequests:0,marketVendorRequests:0,officialFeedRequests:2,
  networkEnabled:true,trading:"disabled",automaticallyRefreshed:true,
  sourceStatus:"OFFICIAL_FED_RSS_REFRESHED",
  sourceName:"Board of Governors of the Federal Reserve System — H.15",
  sourceURL:"https://www.federalreserve.gov/releases/h15/",
  sourceFeeds:SERIES.map(s=>s.url),observedDate:first.latest.date,
  previousObservedDate:first.previous.date,
  publicationTimestampRecorded:dates.length===2,
  publicationTimestampsUTC:parsed.map(x=>x.latest.publishedUTC),
  firstAvailabilityVerified:false,allowedRole:"MACRO_DAILY_CONTEXT_ONLY",
  readyForFiveMinuteGate:false,readyForUltimateTrading:false,
  rates:SERIES.map((s,i)=>({
   series:s.series,maturityYears:s.years,
   latestYieldPct:parsed[i].latest.pct,previousYieldPct:parsed[i].previous.pct,
   changePercentagePoints:Number((parsed[i].latest.pct-parsed[i].previous.pct).toFixed(3))
  })),
  warning:"Official RSS yields are daily published observations, not live Treasury quotes. Publication timestamps do not prove first market availability; M15 yield confirmation stays blocked."
 };
}
async function readAutoDailyContext({fetchFn=fetch,nowMs=Date.now(),offline=false}={}){
 const fallback=reason=>({
  ...readH15DailyContext(),sourceStatus:"STORED_FALLBACK",
  automaticallyRefreshed:false,officialFeedRequests:0,marketVendorRequests:0,
  refreshWarning:reason
 });
 if(offline)return fallback("Official network deliberately disabled in offline test");
 if(cached&&nowMs<until)return cached;
 if(inflight)return inflight;
 inflight=(async()=>{
  try{
   const xmls=await Promise.all(SERIES.map(async s=>{
    const response=await fetchFn(s.url,{
     signal:AbortSignal.timeout(7000),
     headers:{"Accept":"application/rss+xml,application/xml,text/xml","User-Agent":"GoldPrecisionPro-Research-Review/1.0"}
    });
    if(!response.ok)throw Error("H15 official HTTP unavailable");
    const body=await response.text();
    if(body.length>500000)throw Error("H15 response too large");
    return body;
   }));
   const result=buildOfficialDailyContext(xmls,new Date(nowMs));
   cached=result;until=nowMs+60*60*1000;
   return result;
  }catch(err){
   const message=String(err&&err.message||"");
   const diagnostic=message==="H15 official HTTP unavailable"?"FED_RSS_HTTP_ERROR":
     message==="H15 response too large"?"FED_RSS_OVERSIZE":
     message==="Not enough official H15 observations"?"FED_RSS_NO_MATCHING_OBSERVATIONS":
     message==="Official H15 source dates are not aligned"?"FED_RSS_SERIES_DATES_MISMATCH":
     message==="H15 RSS format invalid"?"FED_RSS_FORMAT_UNEXPECTED":
     message==="Invalid RSS publication timestamp"?"FED_RSS_PUBLICATION_DATE_INVALID":
     message==="Stale or future H15 observation"?"FED_RSS_STALE_OR_FUTURE":
     err&&err.name==="TimeoutError"?"FED_RSS_TIMEOUT":
     err&&err.name==="AbortError"?"FED_RSS_TIMEOUT":
     message.startsWith("Conflicting H15")?"FED_RSS_CONFLICT":
     message.includes("fetch")?"FED_RSS_NETWORK_FAILURE":
     "FED_RSS_UNCLASSIFIED_FAILURE";
   // Only a stable diagnostic code; never log provider payloads or credentials.
   console.warn("H15 daily RSS fallback: "+diagnostic);
   const result={...fallback("Official RSS refresh unavailable. Showing stored daily reference, not current market data."),
     refreshDiagnosticCode:diagnostic};
   cached=result;until=nowMs+10*60*1000;
   return result;
  }finally{inflight=null;}
 })();
 return inflight;
}
module.exports={SERIES,parseFeed,buildOfficialDailyContext,readAutoDailyContext};
