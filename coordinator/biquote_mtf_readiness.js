"use strict";
/**
 * BiQuote multi-timeframe readiness panel, PERSONAL READ-ONLY.
 *
 * Combines only already-verified CLOSED MID candle technical observations.
 * Never supplies BUY/SELL, entries, SL/TP, paper orders or execution authority.
 * Does not invent a broker MT5 schedule from generic gold hours.
 */
const FRAMES=Object.freeze(["H4","H1","M15"]);
const WAIT=Object.freeze({signal:"WAIT",executable:false,tradeEligible:false,
 researchEligible:false,paperOrdersAllowed:false,validForEntry:false});
const FIXED_BLOCKERS=Object.freeze([
 "BROKER_SESSION_CALENDAR_UNVERIFIED",
 "UNDERLYING_MT5_DATA_RIGHTS_UNVERIFIED",
 "HISTORICAL_BID_ASK_NOT_AVAILABLE",
 "MACRO_NEWS_AND_ORDERFLOW_NOT_INTEGRATED",
 "PROFITABILITY_NOT_INDEPENDENTLY_VALIDATED"
]);
const ALLOWED_STATES=new Set([
 "OBSERVATION_ONLY","PARTIAL_OBSERVATION_UNVERIFIED_SESSION",
 "INSUFFICIENT_VERIFIED_STRUCTURE"
]);
const BIAS=new Set(["ABOVE_EMA20","BELOW_EMA20","AT_EMA20","UNDETERMINED"]);
function frameEvidence(frame,tf){
 if(!frame||!ALLOWED_STATES.has(frame.state)||frame.sessionCalendarVerified!==false||
    frame.executable!==false||frame.tradeEligible!==false||
    frame.validForEntry!==false||frame.signal!=="WAIT")return null;
 const bars=frame.contiguousBars;
 if(!Number.isInteger(bars)||bars<0||bars>48)return null;
 const gaps=frame.unclassifiedGapsInChart;
 // Valid incomplete frame does not currently carry a gap counter; never
 // manufacture the missing-gaps metric.
 if(gaps!==undefined&&(!Number.isInteger(gaps)||gaps<0))return null;
 const ema20=typeof frame.ema20==="number"&&Number.isFinite(frame.ema20)&&frame.ema20>0;
 const close=typeof frame.lastClosed==="number"&&Number.isFinite(frame.lastClosed)&&frame.lastClosed>0;
 const full=frame.state==="OBSERVATION_ONLY"&&bars>=20&&ema20&&close;
 const partial=frame.state==="PARTIAL_OBSERVATION_UNVERIFIED_SESSION";
 const direction=full
  ?frame.lastClosed>frame.ema20?"ABOVE_EMA20":
   frame.lastClosed<frame.ema20?"BELOW_EMA20":"AT_EMA20"
  :"UNDETERMINED";
 if(!BIAS.has(direction))return null;
 return {timeframe:tf,coverage:full?"FULL_CONTIGUOUS_TECHNICAL":
   partial?"PARTIAL_POST_GAP":"INSUFFICIENT_OR_INVALID",
   contiguousBars:bars,unclassifiedGaps:gaps===undefined?null:gaps,
   ema20Available:full,direction,
   lastClosedUTC:typeof frame.lastClosedOpenUTC==="string"?frame.lastClosedOpenUTC:null,
   sessionCalendarVerified:false,tradeEligible:false,executable:false};
}
function makeMtfReadiness(analysis,comparisons){
 const frames={};
 for(const tf of FRAMES){
  const item=frameEvidence(analysis?.frames?.[tf],tf);
  if(!item) return {...WAIT,mode:"PRIVATE_READONLY_MTF_READINESS",
     state:"INVALID_INPUT_BLOCKED",blockerCodes:["INVALID_FRAME_EVIDENCE"],
     frameSummaries:{},alignment:"NOT_ASSESSABLE",quality:"UNVERIFIED"};
  frames[tf]=item;
 }
 const blockers=[...FIXED_BLOCKERS];
 const complete=FRAMES.every(tf=>frames[tf].ema20Available===true);
 if(!complete)blockers.push("LESS_THAN_20_CONTIGUOUS_BARS_IN_HIGHER_FRAME");
 const gaps=FRAMES.some(tf=>frames[tf].unclassifiedGaps===null||
                                      frames[tf].unclassifiedGaps>0);
 if(gaps)blockers.push("SESSION_GAPS_UNCLASSIFIED");
 let quality="UNVERIFIED";
 if(comparisons&&typeof comparisons==="object"){
  const x=comparisons.H1,y=comparisons.H4;
  const entries=[x,y];
  if(entries.every(o=>o&&["completeMatches","completeMismatches",
    "incompleteM15Groups"].every(k=>Number.isInteger(o[k])&&o[k]>=0))){
   quality=entries.some(o=>o.completeMismatches>0)
     ?"OHLC_MISMATCH":entries.some(o=>o.incompleteM15Groups>0)
       ?"PARTIAL_M15_CONSTITUENTS":"MATCHED_COMPARED_WINDOWS_ONLY";
  }
 }
 if(quality==="UNVERIFIED")blockers.push("CROSS_FRAME_QUALITY_NOT_PROVEN");
 if(quality==="OHLC_MISMATCH")blockers.push("CROSS_FRAME_OHLC_MISMATCH");
 if(quality==="PARTIAL_M15_CONSTITUENTS")blockers.push("INCOMPLETE_M15_CONSTITUENTS");
 // A price-vs-EMA20 direction is NOT a trade recommendation. The
 // readiness/alignment is not assessable without ALL three full frames,
 // even though individual partial observations can still be displayed.
 const values=FRAMES.map(tf=>frames[tf].direction);
 const alignment=complete
  ?values.every(v=>v==="ABOVE_EMA20")?"OBSERVATION_ALL_ABOVE_EMA20":
   values.every(v=>v==="BELOW_EMA20")?"OBSERVATION_ALL_BELOW_EMA20":
   "OBSERVATION_MIXED_OR_AT_EMA20":"NOT_ASSESSABLE";
 return {...WAIT,mode:"PRIVATE_READONLY_MTF_READINESS",
   state:"NO_TRADE_RESEARCH_ONLY",
   alignment,quality,
   sessionCalendarVerified:false,
   underlyingBrokerRightsVerified:false,
   macroAndNewsIntegrated:false,orderFlowIntegrated:false,
   framesRequired:[...FRAMES],frameSummaries:frames,
   blockerCodes:blockers};
}
module.exports={makeMtfReadiness};
