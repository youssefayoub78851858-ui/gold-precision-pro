"use strict";
const assert=require("node:assert/strict");
const {SOURCE,CACHE_MS,MAX_AGE_MS,validateResponse,getGoldSpotReference,frameReadiness}=require("./gold_spot_reference");
async function main(){
 const t=Date.parse("2026-11-11T15:51:27Z");
const payload={source:"xaus.com",price_source:"xaus.com",spot_usd_oz:4003.5,
 updated_at:"2026-11-11T15:51:27Z",price_as_of:"2026-11-11T15:51:00Z",
 data_state:{status:"fresh",as_of:"2026-11-11T15:51:00Z",source:"upstream",age_seconds:27},stale:false};
assert.equal(MAX_AGE_MS,120000);
assert.equal(CACHE_MS,60000);
 assert.equal(validateResponse(payload,t).fresh,true);
 assert.equal(validateResponse(payload,t).ageSeconds,27);
assert.throws(()=>validateResponse({...payload,source:"unknown",price_source:"unknown"},t),/SOURCE_IDENTITY_MISMATCH/);
assert.throws(()=>validateResponse({...payload,spot_usd_oz:null},t),/INVALID_SPOT_PRICE/);
assert.throws(()=>validateResponse({...payload,updated_at:"2026-11-11T16:01:00Z"},t),/FUTURE_SPOT_TIMESTAMP/);
assert.equal(validateResponse({...payload,data_state:{...payload.data_state,status:"stale"},stale:true},t).fresh,false);
assert.throws(()=>validateResponse({...payload,updated_at:"2026-11-11T15:40:00Z"},t),/STALE_SPOT_RESPONSE/);
assert.throws(()=>validateResponse({...payload,data_state:{status:"unknown"}},t),/INVALID_SPOT_STATE/);
assert.equal(validateResponse({...payload,spot_usd_oz:null,data_state:{status:"unavailable"}},t).state,"unavailable");
assert.equal(validateResponse({...payload,updated_at:new Date(t+900000).toISOString(),
 data_state:{status:"stale",as_of:payload.price_as_of,source:"cache",age_seconds:900},stale:true},t+900000).fresh,false);
 assert.deepEqual(Object.keys(frameReadiness()),["M15","H1","H4"]);
 const calls=[];
 const fake=async(url)=>{calls.push(url);return {ok:true,headers:{get:()=> "application/json"},text:async()=>JSON.stringify(payload)};};
 const res=await getGoldSpotReference({fetchFn:fake,nowMs:t});
 assert.equal(calls.length,1);
assert.equal(calls[0],SOURCE);
 assert.equal(res.mode,"FREE_XAU_SPOT_REFERENCE");
 assert.equal(res.dataStatus,"SPOT_REFERENCE_FRESH");
 assert.equal(res.price,4003.5);
 assert.equal(res.executable,false);
 assert.equal(res.signal,"WAIT");
 assert.equal(res.readyForUltimateTrading,false);
 assert.equal(res.realOHLC,false);
 assert.equal(res.liveCandlesAvailable,false);
 assert.equal(res.goldPriceForSignals,null);
 assert.ok(["M15","H1","H4"].every(tf=>res.frames[tf].readyForTrading===false&&res.frames[tf].closedCandles===0));
 const cache=await getGoldSpotReference({fetchFn:()=>{throw Error("unexpected duplicate API call");},nowMs:t+1000});
 assert.equal(cache.price,4003.5);
const stalePayload={...payload,updated_at:new Date(t+500000).toISOString(),
 data_state:{status:"stale",as_of:payload.price_as_of,source:"cache",age_seconds:527},stale:true};
const old=await getGoldSpotReference({fetchFn:async()=>({ok:true,headers:{get:()=>"application/json"},text:async()=>JSON.stringify(stalePayload)}),nowMs:t+500000});
 assert.equal(old.dataStatus,"SPOT_REFERENCE_STALE");
 assert.equal(old.price,null);
 assert.equal(old.signal,"WAIT");
assert.equal(old.updatedAtUTC,payload.price_as_of.replace(".000Z","Z").replace("Z",".000Z"));
 const unavailableBody={source:"xaus.com",spot_usd_oz:null,updated_at:new Date(t+520000).toISOString(),
  data_state:{status:"unavailable",as_of:null,source:"unavailable",age_seconds:null}};
 const unavailable=await getGoldSpotReference({fetchFn:async()=>({ok:true,headers:{get:()=>"application/json"},text:async()=>JSON.stringify(unavailableBody)}),nowMs:t+520000});
 assert.equal(unavailable.dataStatus,"SOURCE_UNAVAILABLE");
 assert.equal(unavailable.price,null);
 assert.equal(unavailable.fetchStatus,"UNAVAILABLE");
 const rateLimited=await getGoldSpotReference({fetchFn:async()=>({ok:false,status:429}),nowMs:t+540000});
 assert.equal(rateLimited.fetchStatus,"XAUS_HTTP_ERROR");
 const offline=await getGoldSpotReference({offline:true,nowMs:t});
 assert.equal(offline.dataStatus,"DISABLED_OFFLINE");
 assert.equal(offline.price,null);
 assert.equal(offline.readyForUltimateTrading,false);
console.log("PASS XAUS indicative reference: provenance, canonical data_state, freshness, cache, outage and M15/H1/H4 no-OHLC WAIT gates");
}
main().catch(e=>{console.error(e);process.exitCode=1;});
