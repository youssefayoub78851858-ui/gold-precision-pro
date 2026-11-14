'use strict';
// The CFTC's public weekly COT report describes positions as of Tuesday.
// Display/research context only: NOT GC tape, footprints, real-time positioning
// or evidence that would have been public before its actual release.
const DATASET='https://publicreporting.cftc.gov/resource/72hh-3qpy.json';
const CODE='088691';
const MARKET='GOLD - COMMODITY EXCHANGE INC.';
const FIELDS=['market_and_exchange_names','cftc_contract_market_code',
 'report_date_as_yyyy_mm_dd','open_interest_all',
 'm_money_positions_long_all','m_money_positions_short_all'];
function blocked(reason,requests=0){
 return {mode:'CFTC_GOLD_WEEKLY_CONTEXT',status:'BLOCKED',signal:'WAIT',
 executable:false,paperOrdersAllowed:false,researchEligible:false,
 intradayVote:false,orderFlowAvailable:false,gcMarketDataAvailable:false,
 requestCount:requests,reasonCode:reason,source:DATASET};
}
function dateUTC(value){
 if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}(?:T00:00:00(?:\.\d{3})?)?$/.test(value))
  return NaN;
 const stamp=Date.parse(value.slice(0,10)+'T00:00:00.000Z');
 return Number.isFinite(stamp)&&new Date(stamp).toISOString().slice(0,10)===value.slice(0,10)?stamp:NaN;
}
function integer(value){
 if(typeof value!=='string'&&!Number.isSafeInteger(value))return null;
 if(!/^\d+$/.test(String(value)))return null;
 const n=Number(value);return Number.isSafeInteger(n)?n:null;
}
function reviewCFTC(rows,asOfUTC){
 const now=Date.parse(asOfUTC);
 if(typeof asOfUTC!=='string'||!asOfUTC.endsWith('Z')||!Number.isFinite(now))
  return blocked('CHECK_TIME_INVALID');
 if(!Array.isArray(rows)||rows.length<1||rows.length>8)return blocked('CFTC_DATASET_EMPTY_OR_OVERSIZE');
 const normalized=[],dates=new Set();
 for(const item of rows){
  if(!item||typeof item!=='object'||Array.isArray(item)||
     FIELDS.some(key=>!Object.hasOwn(item,key))||
     item.cftc_contract_market_code!==CODE||
     item.market_and_exchange_names!==MARKET)
   return blocked('CFTC_GOLD_CONTRACT_OR_SCHEMA_MISMATCH');
  const stamp=dateUTC(item.report_date_as_yyyy_mm_dd);
  const oi=integer(item.open_interest_all);
  const longs=integer(item.m_money_positions_long_all);
  const shorts=integer(item.m_money_positions_short_all);
  if(!Number.isFinite(stamp)||stamp>now||dates.has(stamp)||
     oi===null||oi<=0||longs===null||shorts===null||
     longs>oi||shorts>oi)return blocked('CFTC_REPORT_DATE_OR_POSITIONS_INVALID');
  dates.add(stamp);
  normalized.push({day:new Date(stamp).toISOString().slice(0,10),stamp,openInterest:oi,
   managedMoneyLong:longs,managedMoneyShort:shorts,managedMoneyNet:longs-shorts});
 }
 normalized.sort((a,b)=>b.stamp-a.stamp);
 const latest=normalized[0],ageDays=(now-latest.stamp)/86400000;
 if(ageDays>28)return blocked('CFTC_WEEKLY_REPORT_STALE');
 return {mode:'CFTC_GOLD_WEEKLY_CONTEXT',status:'WEEKLY_REFERENCE_ONLY',
  signal:'WAIT',executable:false,researchEligible:false,paperOrdersAllowed:false,
  intradayVote:false,orderFlowAvailable:false,gcMarketDataAvailable:false,
  source:DATASET,contractMarketCode:CODE,contractMarketName:MARKET,
  observationDate:latest.day,ageSinceTuesdayDays:Math.floor(ageDays),
  openInterestContracts:latest.openInterest,
  managedMoneyLongContracts:latest.managedMoneyLong,
  managedMoneyShortContracts:latest.managedMoneyShort,
  managedMoneyNetContracts:latest.managedMoneyNet,
  previousNetContracts:normalized[1]?.managedMoneyNet??null,
  historicalReleaseTimingProven:false,
  backtestAsOfAdmission:false,
  snapshotUse:'CURRENT_WEEKLY_CONTEXT_ONLY',
  sourceRequestsMadeHere:0,
  warning:'COT positions as of Tuesday, usually made public later. No point-in-time release timestamps: never import this observation into historical decisions without independently verified publication time. Not real-time GC or Order Flow.'};
}
let cached=null,expiry=0,inFlight=null;
async function getCFTCGoldWeekly({fetchFn=fetch,nowMs=Date.now(),offline=true}={}){
 if(offline)return blocked('PUBLIC_CFTC_FETCH_NOT_APPROVED');
 if(!Number.isFinite(nowMs))return blocked('CHECK_TIME_INVALID');
 if(cached&&nowMs<expiry)return cached;
 if(inFlight)return inFlight;
 inFlight=(async()=>{
  const url=new URL(DATASET);
  url.searchParams.set('$select',FIELDS.join(','));
  url.searchParams.set('$where',"cftc_contract_market_code='088691'");
  url.searchParams.set('$order','report_date_as_yyyy_mm_dd DESC');
  url.searchParams.set('$limit','2');
  try{
   const res=await fetchFn(url.toString(),{
    headers:{Accept:'application/json','User-Agent':'GoldPrecisionPro-Official-Weekly-Review/1.0'},
    redirect:'error',signal:AbortSignal.timeout(9000)});
   if(!res.ok)return blocked('CFTC_HTTP_'+res.status,1);
   const raw=await res.text();if(raw.length>12000)return blocked('CFTC_RESPONSE_OVERSIZE',1);
   let rows;try{rows=JSON.parse(raw)}catch{return blocked('CFTC_INVALID_JSON',1);}
   const out={...reviewCFTC(rows,new Date(nowMs).toISOString()),requestCount:1};
   cached=out;expiry=nowMs+(out.status==='WEEKLY_REFERENCE_ONLY'?6*3600000:600000);
   return out;
  }catch{return blocked('CFTC_TRANSPORT_UNAVAILABLE',1);}
 })();
 try{return await inFlight;}finally{inFlight=null;}
}
module.exports={DATASET,CODE,MARKET,FIELDS,reviewCFTC,getCFTCGoldWeekly};
