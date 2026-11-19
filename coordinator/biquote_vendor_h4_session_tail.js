"use strict";
/*
 * H4 closed-bar research tail across a *provider-declared* market break.
 *
 * The original MT5 broker session/holiday/DST schedule is NOT independently
 * known. An H4 gap is "declared pause adjacent" ONLY when every missing
 * H4 interval is entirely closed by the bounded Nov-2026 BiQuote support
 * statement. No OHLC synthesis, clock bridging, V3 input mutation or
 * admission to BUY/SELL/paper/live orders is possible here.
 *
 * Consumes only already-fetched OWNER-ONLY, validated in-memory OHLC.
 * Does not access the private collector, network or any credential.
 */
const {slotClosed}=require("./biquote_vendor_declared_session");
const H4=4*3600000, MIN=21;
const iso=/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/;
function base(status,reason,extra={}){
 return {
  mode:"BIQUOTE_VENDOR_DECLARED_H4_ADJACENCY_RESEARCH_ONLY",
  status,reason,
  sourceRecord:"BIQUOTE_SUPPORT_REPLY_2026_11_16",
  originalBrokerIdentified:false,
  originalBrokerCalendarVerified:false,
  brokerMarketDataRightsVerified:false,
  strictUtcH4Tail:0,
  providerDeclaredSessionAdjacentH4Tail:0,
  providerDeclaredPauseGapPairs:0,
  providerDeclaredPauseMissingH4Slots:0,
  unexplainedGapPairs:0,
  unknownCalendarGapPairs:0,
  providerScenarioReached21H4:false,
  all21H4M15ParityVerified:false,
  perBarFirstSeenVerified:false,
  researchWarmupApproved:false,
  signal:"WAIT",technicalCandidate:"NONE",executable:false,
  paperOrdersAllowed:false,liveOrdersAllowed:false,
  brokerOrdersSent:0,paperOrdersSent:0,providerRequestsMade:0,
  missingCandlesSynthesized:0,
  ...extra
 };
}
function observe(input){
 if(input?.origin!=="AUTHENTICATED_PERSONAL_BIQUOTE_PRIVATE_CHART")
  return base("BLOCKED","UNAUTHENTICATED_ORIGIN");
 const asOfText=input?.asOfUTC;
 if(typeof asOfText!=="string"||!iso.test(asOfText))
  return base("BLOCKED","INVALID_ASOF");
 const asOf=Date.parse(asOfText),bars=input?.h4;
 if(!Number.isFinite(asOf)||new Date(asOf).toISOString().slice(0,19)!==
    asOfText.slice(0,19)||!Array.isArray(bars)||bars.length<2||
    bars.length>48)return base("BLOCKED","INVALID_BAR_WINDOW");
 let prev=null,strict=0,adjacent=0,pairs=0,pauses=0,
     unexplained=0,unknown=0;
 for(const row of bars){
  if(!row||typeof row.time!=="string"||!iso.test(row.time))
   return base("BLOCKED","INVALID_BAR_TIMESTAMP");
  const t=Date.parse(row.time);
  if(!Number.isFinite(t)||new Date(t).toISOString().slice(0,19)!==
       row.time.slice(0,19)||t%H4!==0||t+H4>asOf||
       (prev!==null&&t<=prev))
   return base("BLOCKED","INVALID_OR_UNCLOSED_H4_TIME");
  const vals=["open","high","low","close"].map(k=>row[k]);
  if(vals.some(v=>typeof v!=="number"||!Number.isFinite(v)||
     v<=0||v>=1e8)||row.high<Math.max(row.open,row.close)||
     row.low>Math.min(row.open,row.close))
   return base("BLOCKED","INVALID_CLOSED_H4_PRICE_GEOMETRY");
  if(prev===null){strict=1;adjacent=1;}
  else{
   const missing=(t-prev)/H4-1;
   if(!Number.isSafeInteger(missing)||missing<0||missing>1000)
    return base("BLOCKED","INVALID_H4_GRID_DELTA");
   if(missing===0){strict++;adjacent++;}
   else{
    strict=1;
    let allDeclared=true,hasUnknown=false;
    for(let k=1;k<=missing;k++){
     const classification=slotClosed(prev+k*H4,H4);
     if(classification!==true)allDeclared=false;
     if(classification===null)hasUnknown=true;
    }
    if(allDeclared){
     adjacent++;
     pairs++;
     pauses+=missing;
    }else{
     adjacent=1;
     if(hasUnknown)unknown++;
     else unexplained++;
    }
   }
  }
  prev=t;
 }
 const scenarioReached=adjacent>=MIN;
 return base("PROVIDER_DECLARED_PAUSE_SCENARIO_NOT_TRADING_PROOF",
   scenarioReached?"21_OBSERVED_H4_POSSIBLE_UNDER_UNVERIFIED_BROKER_SCHEDULE":
     "INSUFFICIENT_SESSION_ADJACENT_H4_OBSERVATIONS",{
   observedClosedH4Bars:bars.length,
   lastH4ClosedUTC:new Date(prev+H4).toISOString(),
   strictUtcH4Tail:strict,
   providerDeclaredSessionAdjacentH4Tail:adjacent,
   providerDeclaredPauseGapPairs:pairs,
   providerDeclaredPauseMissingH4Slots:pauses,
   unexplainedGapPairs:unexplained,
   unknownCalendarGapPairs:unknown,
   providerScenarioReached21H4:scenarioReached
  });
}
module.exports={observe};
