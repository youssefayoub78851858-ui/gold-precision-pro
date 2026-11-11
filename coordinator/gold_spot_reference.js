"use strict";
// Unauthenticated free XAU spot price for REVIEW DISPLAY ONLY.
// Not an XAU/USD broker quote, not GC futures, and NOT an OHLC provider.
const SOURCE="https://api.gold-api.com/price/XAU";
const CACHE_MS=30000;
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
  provider:"Gold API (independent indicative spot price, not CFI)",
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
   payload.symbol!=="XAU"||payload.currency!=="USD")
   throw Error("SOURCE_IDENTITY_MISMATCH");
 const price=payload.price;
 if(typeof price!=="number"||!Number.isFinite(price)||price<100||price>20000)
   throw Error("INVALID_SPOT_PRICE");
 if(typeof payload.updatedAt!=="string"||
   !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(payload.updatedAt))
   throw Error("INVALID_SPOT_TIMESTAMP");
 const timestamp=Date.parse(payload.updatedAt);
 if(!Number.isFinite(timestamp))throw Error("INVALID_SPOT_TIMESTAMP");
 const age=nowMs-timestamp;
 if(age< -15000)throw Error("FUTURE_SPOT_TIMESTAMP");
 const fresh=age<=MAX_AGE_MS;
 return {price,fresh,sourceTime:new Date(timestamp).toISOString(),ageSeconds:Math.max(0,Math.round(age/1000))};
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
   if(!response.ok)throw Error("GOLD_API_HTTP_ERROR");
   const type=response.headers?.get?.("content-type");
   if(type&&!type.toLowerCase().includes("json"))throw Error("GOLD_API_NON_JSON");
   const body=await response.text();
   if(body.length>20000)throw Error("GOLD_API_OVERSIZE");
   const payload=JSON.parse(body);
   const parsed=validateResponse(payload,nowMs);
   if(parsed.fresh){
    result={...result,dataStatus:"SPOT_REFERENCE_FRESH",fetchStatus:"OK",
      price:parsed.price,updatedAtUTC:parsed.sourceTime,ageSeconds:parsed.ageSeconds};
   }else{
    result={...result,dataStatus:"SPOT_REFERENCE_STALE",fetchStatus:"STALE_TIMESTAMP",
      updatedAtUTC:parsed.sourceTime,ageSeconds:parsed.ageSeconds};
   }
  }catch(e){
   const code=["GOLD_API_HTTP_ERROR","GOLD_API_NON_JSON","GOLD_API_OVERSIZE",
     "SOURCE_IDENTITY_MISMATCH","INVALID_SPOT_PRICE","INVALID_SPOT_TIMESTAMP",
     "FUTURE_SPOT_TIMESTAMP"].includes(e.message)?e.message:
      e.name==="TimeoutError"?"GOLD_API_TIMEOUT":"GOLD_API_NETWORK_OR_FORMAT_ERROR";
   result={...result,fetchStatus:code};
  }
  cached=result;
  expires=nowMs+(result.dataStatus==="SPOT_REFERENCE_FRESH"?CACHE_MS:15000);
  return result;
 })();
 try{return await inflight;}finally{inflight=null;}
}
module.exports={SOURCE,CACHE_MS,MAX_AGE_MS,frameReadiness,validateResponse,getGoldSpotReference};
