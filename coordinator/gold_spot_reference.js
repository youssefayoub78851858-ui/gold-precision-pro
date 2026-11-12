"use strict";
// Unauthenticated XAUS reference quote for REVIEW DISPLAY ONLY.
// Not an XAU/USD broker quote, not GC futures, and NOT an OHLC provider.
const SOURCE="https://xaus.com/api/v1/spot?compact=1";
const CACHE_MS=60000;
const MAX_AGE_MS=120000;
let cached=null,expires=0,inflight=null;
const frameNames=["M15","H1","H4"];
function frameReadiness(){
 return Object.fromEntries(frameNames.map(name=>[name,{
  status:"NOT_CONNECTED",closedCandles:0,readyForTrading:false,
  reason:"No verified closed OHLC candles for this timeframe; spot snapshot cannot be turned into an historical bar."
 }]));
}
function base(nowMs,status,errorCode){
 return {mode:"FREE_XAU_SPOT_REFERENCE",signal:"WAIT",executable:false,
  trading:"disabled",researchOnly:true,readyForUltimateTrading:false,
  spotReferenceOnly:true,brokerEquivalent:false,
  goldPriceForSignals:null,liveCandlesAvailable:false,realOHLC:false,
  symbol:"XAU",currency:"USD",unit:"USD per troy ounce",
  provider:"XAUS.com (indicative mid-market spot reference, not CFI or GC)",
  sourceURL:SOURCE,checkedUTC:new Date(nowMs).toISOString(),
  price:null,updatedAtUTC:null,ageSeconds:null,
  dataStatus:status,fetchStatus:errorCode,
  frames:frameReadiness(),
  historicalArchiveAvailable:true,archiveUsage:"Past recorded BID research only; no authenticated live M15/H1/H4",
  disclaimer:"Only a timestamped indicative spot snapshot. Not CFI XAUUSD, not executable, no volume, spread, bid/ask, OHLC, futures or order flow."
 };
}
function validateResponse(payload,nowMs){
 if(!payload||typeof payload!=="object"||Array.isArray(payload)||
   (payload.source!=="xaus.com"&&payload.price_source!=="xaus.com"))
   throw Error("SOURCE_IDENTITY_MISMATCH");
 const state=payload.data_state;
 if(!state||typeof state!=="object"||!['fresh','stale','unavailable'].includes(state.status))
   throw Error("INVALID_SPOT_STATE");
 if(state.status==='unavailable')
   return {price:null,fresh:false,sourceTime:null,ageSeconds:null,state:state.status};
 const price=payload.spot_usd_oz;
 if(typeof price!=="number"||!Number.isFinite(price)||price<100||price>20000)
   throw Error("INVALID_SPOT_PRICE");
 const generatedAt=payload.updated_at;
 if(typeof generatedAt!=="string"||
   !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$/.test(generatedAt))
   throw Error("INVALID_SPOT_TIMESTAMP");
 const generatedMs=Date.parse(generatedAt);
 if(!Number.isFinite(generatedMs))throw Error("INVALID_SPOT_TIMESTAMP");
 const asOf=payload.price_as_of||state.as_of||generatedAt;
 if(typeof asOf!=="string"||
   !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$/.test(asOf))
   throw Error("INVALID_SPOT_TIMESTAMP");
 const timestamp=Date.parse(asOf);
 if(!Number.isFinite(timestamp))throw Error("INVALID_SPOT_TIMESTAMP");
 const generationAge=nowMs-generatedMs;
 if(generationAge< -15000)throw Error("FUTURE_SPOT_TIMESTAMP");
 if(generationAge>MAX_AGE_MS)throw Error("STALE_SPOT_RESPONSE");
 const age=nowMs-timestamp;
 if(age< -15000)throw Error("FUTURE_SPOT_TIMESTAMP");
 const reportedAge=state.age_seconds;
 if(reportedAge!==undefined&&(!Number.isFinite(reportedAge)||reportedAge<0))
   throw Error("INVALID_SPOT_STATE");
 const fresh=state.status==='fresh'&&payload.stale!==true&&age<=MAX_AGE_MS&&
   (reportedAge===undefined||reportedAge<=MAX_AGE_MS/1000);
 return {price,fresh,sourceTime:new Date(timestamp).toISOString(),
  ageSeconds:Math.max(0,Math.round(age/1000)),state:state.status};
}
async function getGoldSpotReference({fetchFn=fetch,nowMs=Date.now(),offline=false}={}){
 if(!Number.isFinite(nowMs))throw Error("INVALID_CLOCK");
 if(offline)return base(nowMs,"DISABLED_OFFLINE","OFFLINE_TEST");
 if(cached&&nowMs<expires)return cached;
 if(inflight)return inflight;
 inflight=(async()=>{
  let result=base(nowMs,"SOURCE_UNAVAILABLE","NO_DATA");
  try{
   const response=await fetchFn(SOURCE,{signal:AbortSignal.timeout(7500),
    headers:{Accept:"application/json"}});
   if(!response.ok)throw Error("XAUS_HTTP_ERROR");
   const type=response.headers?.get?.("content-type");
   if(type&&!type.toLowerCase().includes("json"))throw Error("XAUS_NON_JSON");
   const body=await response.text();
   if(body.length>20000)throw Error("XAUS_OVERSIZE");
   const payload=JSON.parse(body);
   const parsed=validateResponse(payload,nowMs);
   if(parsed.fresh){
    result={...result,dataStatus:"SPOT_REFERENCE_FRESH",fetchStatus:"OK",
      price:parsed.price,updatedAtUTC:parsed.sourceTime,ageSeconds:parsed.ageSeconds};
   }else{
    result={...result,dataStatus:parsed.state==="unavailable"?"SOURCE_UNAVAILABLE":"SPOT_REFERENCE_STALE",
      fetchStatus:parsed.state==="unavailable"?"UNAVAILABLE":"STALE_TIMESTAMP",
      updatedAtUTC:parsed.sourceTime,ageSeconds:parsed.ageSeconds};
   }
  }catch(e){
   const code=["XAUS_HTTP_ERROR","XAUS_NON_JSON","XAUS_OVERSIZE",
     "SOURCE_IDENTITY_MISMATCH","INVALID_SPOT_PRICE","INVALID_SPOT_STATE",
     "INVALID_SPOT_TIMESTAMP","STALE_SPOT_RESPONSE","FUTURE_SPOT_TIMESTAMP"].includes(e.message)?e.message:
      e.name==="TimeoutError"?"XAUS_TIMEOUT":"XAUS_NETWORK_OR_FORMAT_ERROR";
   result={...result,fetchStatus:code};
  }
  cached=result;
  expires=nowMs+(result.dataStatus==="SPOT_REFERENCE_FRESH"?CACHE_MS:15000);
  return result;
 })();
 try{return await inflight;}finally{inflight=null;}
}
module.exports={SOURCE,CACHE_MS,MAX_AGE_MS,frameReadiness,validateResponse,getGoldSpotReference};
