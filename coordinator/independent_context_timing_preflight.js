"use strict";
/**
 * OFFLINE / SANITIZED pre-decision temporal preflight for the seven external
 * context families used by the frozen XAUUSD research engine.
 * NEVER fetches prices, accepts entitlement claims, runs V3, or issues trades.
 * Even plausible clocks are untrusted assertions, not source/native receipts.
 */
const MODE="GOLD_EXTERNAL_CONTEXT_TIMING_PREFLIGHT_OFFLINE_V1";
const REQUIRED=Object.freeze({
 DXY:{kind:"INDEX_QUOTE_NOT_EXCHANGE_DXY",maxAgeMs:300000},
 GC_TRADES:{kind:"COMEX_GC_EXCHANGE_TRADES_NOT_CFD",maxAgeMs:120000},
 GC_DEPTH:{kind:"COMEX_GC_MBP_OR_MBO_NOT_CFD",maxAgeMs:120000},
 US02Y:{kind:"OFFICIAL_PUBLISHED_DAILY_YIELD",maxAgeMs:72*3600000},
 US10Y:{kind:"OFFICIAL_PUBLISHED_DAILY_YIELD",maxAgeMs:72*3600000},
 CALENDAR:{kind:"PUBLISHED_US_MACRO_CALENDAR",maxAgeMs:24*3600000},
 HEADLINES:{kind:"PUBLISHED_NEWS_HEADLINE",maxAgeMs:60*60000}
});
const KEYS=Object.keys(REQUIRED);
const GC_CONTRACT=/^GC[FGHJKMNQUVXZ][0-9]{1,4}$/;
const ISO=/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/;
function at(s){
 if(typeof s!=="string"||!ISO.test(s))return NaN;
 const t=Date.parse(s);
 return Number.isFinite(t)&&new Date(t).toISOString().slice(0,19)===s.slice(0,19)?t:NaN;
}
const base=(status,reason)=>({
 mode:MODE,status,reason,signal:"WAIT",executable:false,
 researchEligible:false,recommendationAllowed:false,tradeEligible:false,
 paperOrdersAllowed:false,liveOrdersAllowed:false,
 providerRequestsMade:0,brokerOrdersSent:0,paperOrdersSent:0,
 sourceRightsVerified:false,independentFeedIdentityVerified:false,
 brokerSessionVerified:false,comexOrderFlowLicensed:false,
 macroPublicationIndependentlyVerified:false,allLayersQualified:false,
 independentHoldoutValidated:false,
 requiredLayerCount:KEYS.length,verifiedLiveLayerCount:0,
 perLayer:{},summary:null
});
function inspect(input){
 if(input?.origin!=="UNATTESTED_SANITIZED_CONTEXT_TIMES_ONLY")
  return base("BLOCKED","UNTRUSTED_CONTEXT_ORIGIN");
 const decision=at(input.decisionUTC),asOf=at(input.asOfUTC);
 if(!Number.isFinite(decision)||!Number.isFinite(asOf)||decision>asOf||
    decision<Date.parse("2026-11-18T00:00:00Z"))
  return base("BLOCKED","INVALID_DECISION_OR_AUDIT_CLOCK");
 const evidence=input.items;
 if(!evidence||typeof evidence!=="object"||Array.isArray(evidence)||
    Object.keys(evidence).some(k=>!Object.hasOwn(REQUIRED,k)))
  return base("BLOCKED","UNSUPPORTED_OR_INVALID_CONTEXT_ITEMS");
 const perLayer={},counts={recent:0,daily:0,scheduled:0,missing:0,blocked:0};
 for(const name of KEYS){
  const item=evidence[name];
  if(item===undefined){
   perLayer[name]={status:"MISSING",timeSuitable:false,sourceQualified:false};
   counts.missing++;continue;
  }
  // Reject extra fields (prices, source/license claims, trust switches,
  // arbitrary user names, credentials). Never reflect unknown data.
  const isGC=name==="GC_TRADES"||name==="GC_DEPTH";
  const keys=isGC?
    "contract,firstAvailableUTC,kind,observedUTC,receivedUTC":
    "firstAvailableUTC,kind,observedUTC,receivedUTC";
  if(!item||typeof item!=="object"||Array.isArray(item)||
     Object.keys(item).sort().join(",")!==keys||
     (isGC&&(!GC_CONTRACT.test(item.contract)||typeof item.contract!=="string")))
  {
   perLayer[name]={status:"INVALID_METADATA",timeSuitable:false,sourceQualified:false};
   counts.blocked++;continue;
  }
  const kind=REQUIRED[name].kind,
        event=at(item.observedUTC),
        available=at(item.firstAvailableUTC),
        received=at(item.receivedUTC);
  if(item.kind!==kind||![event,available,received].every(Number.isFinite)||
     available>received||received>decision||received<0){
   perLayer[name]={status:"INVALID_OR_LATE_RECEIPT",timeSuitable:false,sourceQualified:false};
   counts.blocked++;continue;
  }
  if(name==="CALENDAR"&&event>decision){
   // An advance calendar ANNOUNCEMENT can be known before the release.
   // Its future actual or surprise cannot be known; never call it real.
   perLayer[name]={status:"FUTURE_EVENT_SCHEDULE_ONLY",timeSuitable:false,sourceQualified:false};
   counts.scheduled++;continue;
  }
  if(event>available||event>decision||decision-event>REQUIRED[name].maxAgeMs){
   perLayer[name]={status:"STALE_OR_PREPUBLICATION_EVENT",timeSuitable:false,sourceQualified:false};
   counts.blocked++;continue;
  }
  if(name==="US02Y"||name==="US10Y"){
   // Free official yields are prior published DAILY context, not ticks.
   perLayer[name]={status:"DAILY_REFERENCE_ONLY_NOT_INTRADAY",timeSuitable:false,sourceQualified:false};
   counts.daily++;continue;
  }
  perLayer[name]={status:"PLAUSIBLE_UNATTESTED_CLOCK_ONLY",
    timeSuitable:true,sourceQualified:false};
  counts.recent++;
 }
 // Exchange-trade timestamps and order-book updates from DIFFERENT GC
 // contracts, or snapshots separated by too much time, cannot confirm
 // the same futures flow. Both labels are still caller-asserted, not
 // exchange/Databento entitlements or independent clock evidence.
 let gcPairStatus="GC_PAIR_UNAVAILABLE_OR_NOT_TIME_SUITABLE";
 if(perLayer.GC_TRADES?.timeSuitable===true&&
    perLayer.GC_DEPTH?.timeSuitable===true){
   const trades=evidence.GC_TRADES,depth=evidence.GC_DEPTH;
   const skew=Math.abs(at(trades.observedUTC)-at(depth.observedUTC));
   if(trades.contract!==depth.contract||skew>60000){
     gcPairStatus=trades.contract!==depth.contract?
       "GC_CONTRACT_MISMATCH":"GC_TRADE_DEPTH_CLOCK_SKEW";
     for(const key of ["GC_TRADES","GC_DEPTH"]){
       perLayer[key]={status:gcPairStatus,timeSuitable:false,
         sourceQualified:false};
     }
     counts.recent-=2;counts.blocked+=2;
   }else gcPairStatus="MATCHED_UNATTESTED_GC_LABELS_AND_CLOCKS_ONLY";
 }
 const status=counts.blocked?"CONTEXT_TIMING_CONFLICTS":
  counts.missing?"INCOMPLETE_CONTEXT":
  "ONLY_UNATTESTED_CLOCKS_NOT_TRADING_PROOF";
 return {...base(status,"NO_INDEPENDENT_SOURCE_ENTITLEMENT_OR_RECEIPT_ATTESTATION"),
  perLayer,summary:counts,gcTradeDepthCrossCheck:{
    status:gcPairStatus,exchangeProven:false,
    contractRollVerified:false,providerCredentialsAccessed:false
  }};
}
module.exports={inspect};
if(require.main===module){
 let raw="";
 process.stdin.setEncoding("utf8");
 process.stdin.on("data",chunk=>{
  raw+=chunk;if(raw.length>262144){process.stderr.write("CONTEXT_INPUT_TOO_LARGE\n");process.exit(2);}
 });
 process.stdin.on("end",()=>{
  try{process.stdout.write(JSON.stringify(inspect(JSON.parse(raw)))+"\n");}
  catch{process.stdout.write(JSON.stringify(base("BLOCKED","INVALID_CONTEXT_INPUT"))+"\n");}
 });
}
