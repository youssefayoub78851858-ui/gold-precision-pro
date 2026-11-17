"use strict";
/**
 * RESEARCH-ONLY EMA20 over ACTUAL observed CLOSED candles across a generic
 * winter market-pause reference. Never fill, insert, reindex, backfill,
 * convert MID to BID/ASK, assert broker session legality, or trade.
 *
 * Important: the existing gap-strict EMA20 in biquote_private_structure.js
 * remains authoritative for the descriptive chart; this separate candidate
 * cannot authorize the MTF trade engine or the alignment gate.
 */
const {auditRows}=require("./biquote_session_reference");
const WIDTH=Object.freeze({M15:900000,H1:3600000,H4:14400000});
const NAMES=Object.freeze(["M15","H1","H4"]);
const WAIT=Object.freeze({signal:"WAIT",executable:false,tradeEligible:false,
 researchEligible:false,paperOrdersAllowed:false,validForEntry:false});
function reject(reason,count=0){
 return {...WAIT,status:"NOT_ASSESSABLE",reason,observedBars:count,
  ema20:null,lastClose:null,relation:"NOT_ASSESSABLE",
  brokerSessionVerified:false,upstreamRightsVerified:false,
  observationOnly:true,gapsAssumedClosed:false};
}
function frameCandidate(rows,tf,asOfMs){
 const width=WIDTH[tf];
 if(!width||!Array.isArray(rows)||rows.length<20||rows.length>48||
    !Number.isFinite(asOfMs))return reject("INSUFFICIENT_CLOSED_BARS");
 let previous=-1;
 for(const row of rows){
  if(!row||typeof row.time!=="string"||!/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(row.time)||
     !["open","high","low","close"].every(k=>typeof row[k]==="number"&&
       Number.isFinite(row[k])&&row[k]>0))return reject("INVALID_OHLC_OR_TIME");
  const t=Date.parse(row.time);
  if(!Number.isFinite(t)||t<=previous||t%width!==0||
     t+width>asOfMs||row.high<Math.max(row.open,row.close,row.low)||
     row.low>Math.min(row.open,row.close,row.high))
     return reject("INVALID_OHLC_OR_TIME");
  previous=t;
 }
 const gap=auditRows(rows,tf);
 if(gap.error||gap.brokerCalendarVerified!==false||
    gap.sessionCalendarVerified!==false||
    gap.bridgeBarsAllowed!==false||
    gap.missingDuringReferenceTradingHours>0||
    gap.outsideReference>0||
    gap.referencePauseCandidates!==gap.missingSlots)
   return reject("UNCLASSIFIED_OR_TRADING_TIME_GAP",rows.length);
 if(gap.gapCount===0)
   return reject("NO_REFERENCE_PAUSE_TO_RESEARCH_USE_STRICT_EMA",rows.length);
 // Last twenty actual candles are *observed*, NEVER imagined scheduled bars.
 // SMA-20 seed followed by EMA recursion across actual observations.
 let value=rows.slice(0,20).reduce((a,x)=>a+x.close,0)/20;
 for(let i=20;i<rows.length;i++)
   value=value*(19/21)+rows[i].close*(2/21);
 const lastClose=rows.at(-1).close;
 const relation=lastClose>value?"ABOVE_REFERENCE_EMA20":
  lastClose<value?"BELOW_REFERENCE_EMA20":"AT_REFERENCE_EMA20";
 return {...WAIT,status:"REFERENCE_PAUSE_CANDIDATE_ONLY",
  basis:"OBSERVED_CLOSED_MID_POSSIBLE_BID_SEED",
  timeframe:tf,observedBars:rows.length,
  lastObservedOpenUTC:rows.at(-1).time,
  ema20:Number(value.toFixed(3)),
  lastClose:Number(lastClose.toFixed(3)),
  relation,
  referencePauseCandidateSlots:gap.referencePauseCandidates,
  missingDuringReferenceTradingHours:0,missingOutsideReference:0,
  brokerSessionVerified:false,upstreamRightsVerified:false,
  observationOnly:true,gapsAssumedClosed:false,
  notForTrading:true,
  reason:"REFERENCE_CALENDAR_NOT_UNDERLYING_BROKER_VERIFIED"};
}
function examine(chart,asOfMs){
 const frames={};
 for(const tf of NAMES)frames[tf]=frameCandidate(chart?.[tf],tf,asOfMs);
 return {...WAIT,mode:"PRIVATE_MID_OBSERVED_EMA_REFERENCE_ONLY",
  brokerSessionVerified:false,upstreamRightsVerified:false,
  decisionReady:false,alignmentForTrading:"NOT_ASSESSABLE",
  sourceClock:"UTC_CLOSED_BARS_ONLY",
  frames};
}
module.exports={examine,frameCandidate};
