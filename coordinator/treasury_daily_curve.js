'use strict';
// Official Treasury DAILY published par yields. Never M15/GC/DXY or a price feed.
// Strict calendar/date validation and zero point-in-time backtest authority.
const BASE='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml';
const SOURCE='U.S. Department of the Treasury';
const blocked=reason=>({
 mode:'OFFICIAL_TREASURY_2Y10Y_DAILY',status:'BLOCKED',signal:'WAIT',
 executable:false,researchEligible:false,paperOrdersAllowed:false,
 eligibleForIntradayConfirmation:false,pointInTimeBacktestEligible:false,
 source:SOURCE,sourceRequestsMadeHere:0,reasonCode:reason});
const dateMs=s=>{
 if(typeof s!=='string'||! /^\d{4}-\d{2}-\d{2}T00:00:00(?:\.000)?$/.test(s))return NaN;
 const d=Date.parse(s.slice(0,10)+'T00:00:00Z');
 return Number.isFinite(d)&&new Date(d).toISOString().slice(0,10)===s.slice(0,10)?d:NaN;
};
function pull(entry,key){
 const m=entry.match(new RegExp('<d:'+key+'(?:\\s[^>]*)?>([\\s\\S]*?)<\\/d:'+key+'>','i'));
 return m?.[1]?.trim()??null;
}
function reviewTreasuryXML(xml,asOfUTC,requestedMonth){
 const now=Date.parse(asOfUTC);
 if(typeof asOfUTC!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(asOfUTC)||!Number.isFinite(now))
  return blocked('INDEPENDENT_CLOCK_REQUIRED');
 if(typeof requestedMonth!=='string'||!/^\d{6}$/.test(requestedMonth))
  return blocked('MONTH_PARAMETER_INVALID');
 if(typeof xml!=='string'||xml.length<100||xml.length>350000||
    !xml.includes('DailyTreasuryYieldCurveRate')||!xml.includes('http://www.w3.org/2005/Atom'))
  return blocked('UNRECOGNIZED_TREASURY_XML');
 const entries=[...xml.matchAll(/<entry(?:\s[^>]*)?>[\s\S]*?<\/entry>/gi)];
 if(entries.length<1||entries.length>35)return blocked('TREASURY_MONTHLY_ROWS_MISSING_OR_EXCESS');
 const rows=[],seen=new Set();
 for(const hit of entries){
  const d=pull(hit[0],'NEW_DATE'),t=dateMs(d);
  const two=pull(hit[0],'BC_2YEAR'),ten=pull(hit[0],'BC_10YEAR');
  const a=two===null?NaN:Number(two),z=ten===null?NaN:Number(ten);
  if(!Number.isFinite(t)||t>now||seen.has(t)||
     d.slice(0,7).replace('-','')!==requestedMonth||
     !/^\d{1,2}\.\d{1,4}$/.test(two??'')||
     !/^\d{1,2}\.\d{1,4}$/.test(ten??'')||
     !(a>0&&a<30&&z>0&&z<30))
   return blocked('TREASURY_ROW_DATE_YIELD_OR_DUPLICATE_INVALID');
  seen.add(t);
  rows.push({observationDate:d.slice(0,10),time:t,twoYearPct:a,tenYearPct:z});
 }
 rows.sort((x,y)=>y.time-x.time);
 const latest=rows[0],age=(now-latest.time)/86400000;
 if(age>10)return blocked('TREASURY_DAILY_REFERENCE_STALE');
 const previous=rows[1]??null;
 return {mode:'OFFICIAL_TREASURY_2Y10Y_DAILY',status:'DAILY_REFERENCE_ONLY',
   signal:'WAIT',executable:false,researchEligible:false,paperOrdersAllowed:false,
   eligibleForIntradayConfirmation:false,pointInTimeBacktestEligible:false,
   firstAvailabilityVerified:false,quoteLive:false,
   source:SOURCE,sourceURL:BASE,sourceRequestsMadeHere:0,
   observedDate:latest.observationDate,ageDays:Math.floor(age),
   twoYearYieldPct:latest.twoYearPct,tenYearYieldPct:latest.tenYearPct,
   twoTenSpreadPct:Number((latest.tenYearPct-latest.twoYearPct).toFixed(4)),
   previousObservedDate:previous?.observationDate??null,
   twoYearDailyChangePct:previous?Number((latest.twoYearPct-previous.twoYearPct).toFixed(4)):null,
   tenYearDailyChangePct:previous?Number((latest.tenYearPct-previous.tenYearPct).toFixed(4)):null,
   recordsValidated:rows.length,
   historicalAvailabilityTimeVerified:false,
   allowedRole:'SLOW_DAILY_MACRO_REFERENCE_ONLY',
   warning:'Official published daily Treasury observations only, not trading-session intraday US02Y/US10Y confirmation. Observation day is NOT the first public availability timestamp; historical backtests must not look ahead.'};
}
let cached=null,expires=0,inflight=null;
async function getTreasuryDaily({nowMs=Date.now(),fetchFn=fetch,offline=true}={}){
 if(offline)return blocked('TREASURY_PUBLIC_FETCH_NOT_APPROVED');
 if(!Number.isFinite(nowMs))return blocked('INDEPENDENT_CLOCK_REQUIRED');
 if(cached&&nowMs<expires)return cached;
 if(inflight)return inflight;
 inflight=(async()=>{
  const month=new Date(nowMs).toISOString().slice(0,7).replace('-','');
  const url=new URL(BASE);url.searchParams.set('data','daily_treasury_yield_curve');
  url.searchParams.set('field_tdr_date_value_month',month);
  try{
   const res=await fetchFn(url.toString(),{headers:{Accept:'application/xml,text/xml',
    'User-Agent':'GoldPrecisionPro-Treasury-Daily-Research/1.0'},
    redirect:'error',signal:AbortSignal.timeout(11000)});
   if(!res.ok)return {...blocked('TREASURY_HTTP_'+res.status),sourceRequestsMadeHere:1};
   const text=await res.text();
   if(text.length>350000)return {...blocked('TREASURY_XML_TOO_LARGE'),sourceRequestsMadeHere:1};
   const out={...reviewTreasuryXML(text,new Date(nowMs).toISOString(),month),sourceRequestsMadeHere:1};
   cached=out;expires=nowMs+(out.status==='DAILY_REFERENCE_ONLY'?3600000:600000);
   return out;
  }catch{return {...blocked('TREASURY_REQUEST_UNAVAILABLE'),sourceRequestsMadeHere:1};}
 })();
 try{return await inflight;}finally{inflight=null;}
}
module.exports={BASE,SOURCE,reviewTreasuryXML,getTreasuryDaily};
