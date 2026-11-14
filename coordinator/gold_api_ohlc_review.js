'use strict';
// Gold API Premium pre-purchase audit ONLY. No API key, HTTP client, subscription,
// broker equivalence, trade or self-attested session calendar.
const {aggregate}=require('./eodhd_ws_bridge');
const WIDTH=900000;
const finite=x=>typeof x==='number'&&Number.isFinite(x)&&x>0;
const reason=(code)=>({status:'BLOCKED',signal:'WAIT',executable:false,
  paperOrdersAllowed:false,researchEligible:false,source:'Gold API XAU',
  quoteBasis:'UNKNOWN_INDICATIVE',realBidAsk:false,
  providerRequestsMade:0,reasonCodes:[code],
  counts:{M15:0,H1:0,H4:0},finalizedSeriesVerified:false});
function staticStatus(){
 return {...reason('NO_AUTHORIZED_XAUUSD_OHLC_HISTORY'),
   mode:'GOLD_API_PREMIUM_PREPURCHASE_ONLY',monthlyUsd:10,
   freeSpotAvailable:true,priceEndpointDisplayOnly:true,
   premiumKeyConfigured:false,subscriptionPurchased:false,
   liveOHLCVerified:false,licensedBrokerBidAsk:false,
   sessionAndHistoryVerified:false,
   documentation:{
     ohlc:'https://gold-api.com/llms.txt',
     pricing:'https://gold-api.com/pricing',
     terms:'https://gold-api.com/terms'
   },
   blockingReasons:[
     'PREMIUM_API_KEY_NOT_CONFIGURED',
     'OHLC_IS_ONE_RANGE_NOT_A_NATIVE_SERIES',
     'HISTORICAL_INTERVAL_CONTINUITY_UNTESTED',
     'PRICE_BASIS_AND_BROKER_SPREAD_UNKNOWN',
     'RENDER_RESEARCH_AND_STORAGE_PERMISSION_NOT_INDEPENDENTLY_ATTESTED'
   ]};
}
const utcMs=value=>{
 if(typeof value!=='string'||!/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{3})?Z$/.test(value))return NaN;
 const n=Date.parse(value);
 return Number.isFinite(n)&&new Date(n).toISOString().slice(0,19)===value.slice(0,19)?n:NaN;
};
function inspectRanges(records,opts={}){
 const asOf=utcMs(opts.asOfUTC), expected=opts.independentExpectedOpenTimes;
 if(!Number.isFinite(asOf))return reason('INDEPENDENT_ASOF_INVALID');
 if(typeof opts.independentScheduleReference!=='string'||!opts.independentScheduleReference.trim()||
    !Array.isArray(expected)||expected.length<1||expected.length>2048)
  return reason('INDEPENDENT_SESSION_CALENDAR_REQUIRED');
 if(!Array.isArray(records)||records.length!==expected.length)return reason('RANGE_COUNT_OR_SESSION_GAP');
 const bars=[];
 let last=-Infinity;
 for(let i=0;i<expected.length;i++){
  const wanted=utcMs(expected[i]),r=records[i],v=r?.response;
  if(!Number.isFinite(wanted)||wanted%WIDTH!==0||wanted<=last)
   return reason('UNVERIFIED_EXPECTED_BAR_ORDER');
  last=wanted;
  if(!r||r.httpStatus!==200||!v||typeof v!=='object'||Array.isArray(v))
   return reason('PREMIUM_OHLC_HTTP_OR_JSON_REJECTED');
  if(!Number.isSafeInteger(r.requestStartTimestamp)||!Number.isSafeInteger(r.requestEndTimestamp)||
     r.requestStartTimestamp*1000!==wanted||
     r.requestEndTimestamp*1000!==wanted+WIDTH||
     v.startTimestamp!==r.requestStartTimestamp||v.endTimestamp!==r.requestEndTimestamp)
   return reason('RANGE_BOUNDARY_OR_PROVIDER_TIMESTAMP_MISMATCH');
  // Do not use the forming M15 bar. A small time buffer allows finalization.
  if(wanted+WIDTH+30000>asOf)return reason('UNCLOSED_OR_UNSETTLED_M15');
  const {open,high,low,close}=v;
  if(![open,high,low,close].every(finite)||low>Math.min(open,close)||
     high<Math.max(open,close)||high<low)
   return reason('INVALID_OHLC_VALUES');
  bars.push({openTime:new Date(wanted).toISOString(),open,high,low,close});
 }
 const h1=aggregate(bars,4),h4=aggregate(bars,16);
 const count={M15:bars.length,H1:h1.length,H4:h4.length};
 const age=(asOf-(last+WIDTH))/1000;
 const reasons=['PRICE_BASIS_NOT_BID_ASK',
   'SINGLE_RANGE_API_NOT_YET_VALIDATED_AS_BROKER_MARKET_CANDLES',
   'NO_INDEPENDENT_BROKER_PARITY_OR_EXECUTION_COST',
   'NO_VERIFIED_LIVE_SUBSCRIPTION_OR_PRIVATE_SOURCE_RIGHTS'];
 if(age>1200)reasons.unshift('LATEST_CLOSED_M15_STALE');
 if(h4.length<50)reasons.unshift('INDICATOR_H4_WARMUP_INSUFFICIENT');
 return {
   mode:'GOLD_API_PREMIUM_OFFLINE_RANGE_AUDIT',
   status:'GEOMETRY_VALID_BUT_SOURCE_UNVERIFIED',
   source:'Gold API XAU',quoteBasis:'UNKNOWN_INDICATIVE',
   signal:'WAIT',executable:false,paperOrdersAllowed:false,
   researchEligible:false,sourceRequestsMade:0,
   finalizedSeriesVerified:false,completeM15Ranges:count.M15,
   counts:count,latestClosedUTC:new Date(last+WIDTH).toISOString(),
   closedAgeSeconds:age,independentSessionReferencePresent:true,
   geometryCheckPassed:true,derivedFrameCountsOnly:true,
   brokerBidAskAvailable:false,reasonCodes:reasons
 };
}
module.exports={inspectRanges,staticStatus};
