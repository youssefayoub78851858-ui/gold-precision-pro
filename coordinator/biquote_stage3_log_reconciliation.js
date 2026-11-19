"use strict";
/**
 * Read-only reconciliation of already-sanitized Render Stage-3 metadata.
 * This does NOT access Render, a private vault, market data or execution.
 * It proves ONLY that untrusted COUNT logs agree with each other.
 */
const TYPES=Object.freeze([
 "BIQUOTE_STAGE3_CLOSED_BAR_PROGRESS",
 "BIQUOTE_STAGE3_VENDOR_REFERENCE_GAPS",
 "BIQUOTE_STAGE3_ARCHIVE_OHLC_OVERLAP",
 "BIQUOTE_STAGE3_QUOTE_RECEIPT_CADENCE"
]);
const BIN_KEYS=Object.freeze([
 "GT_150_LE_300_SECONDS","GT_300_LE_600_SECONDS","GT_3600_SECONDS",
 "GT_600_LE_3600_SECONDS","LE_150_SECONDS"
]);
const TIME=/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z$/;
const FRAMES=["M15","H1","H4"];
const ints=x=>Number.isSafeInteger(x)&&x>=0&&x<=20000000;
const time=s=>{
 if(typeof s!=="string"||!TIME.test(s))return NaN;
 const n=Date.parse(s);
 return Number.isFinite(n)&&new Date(n).toISOString().slice(0,19)===s.slice(0,19)?n:NaN;
};
const FRAMEZERO=()=>({M15:null,H1:null,H4:null});
function fail(status,why,extra={}){
 return {
  mode:"BIQUOTE_STAGE3_LOG_RECONCILIATION_COUNTS_ONLY",
  status,signal:"WAIT",executable:false,tradeEligible:false,
  researchEligible:false,paperOrdersAllowed:false,liveOrdersAllowed:false,
  brokerOrdersSent:0,providerRequestsMade:0,
  firstObservedClosedUTCVerified:false,brokerRightsVerified:false,
  brokerSessionCalendarVerified:false,independentPriceParityVerified:false,
  executionBidAskVerified:false,independentTradeProfitabilityProven:false,
  matchedEventCount:0,checkedProgressEvents:0,sourceQuoteSamples:null,
  persistedClosed:FRAMEZERO(),unclassifiedMissingSlots:FRAMEZERO(),
  comparedClosed:{H1:0,H4:0},fullyCoveredDisagreements:{H1:null,H4:null},
  blockers:["LEGACY_COLLECTOR_FIRST_SEEN_UNKNOWN",
            "SOURCE_RIGHTS_AND_BROKER_CALENDAR_UNVERIFIED",
            "SPARSE_QUOTES_NOT_EXECUTION_EVIDENCE",
            ...(why?[why]:[])],...extra
 };
}
function checkFrames(obj,keys){
 return obj&&typeof obj==="object"&&!Array.isArray(obj)&&
        Object.keys(obj).sort().join(",")===keys.slice().sort().join(",");
}
function reconcile({records}={}){
 if(!Array.isArray(records)||records.length>1200)
  return fail("BLOCKED","INVALID_STAGE3_LOG_INPUT");
 if(!records.length)return fail("INCOMPLETE","NO_STAGE3_PROGRESS_OBSERVED");
 const normalized=[];
 for(const x of records){
  if(!x||!TYPES.includes(x.event)||!Number.isFinite(time(x.atUTC))||
     x.signal!=="WAIT"||x.executable!==false||
     x.paperOrdersAllowed!==false||x.brokerOrdersSent!==0||
     !ints(x.dayIndex)||x.dayIndex<1||x.dayIndex>7)
   return fail("BLOCKED","UNSAFE_OR_MALFORMED_STAGE3_LOG_EVENT");
  normalized.push({...x,epoch:time(x.atUTC)});
 }
 normalized.sort((a,b)=>a.epoch-b.epoch);
 const progresses=normalized.filter(x=>x.event===TYPES[0]);
 if(!progresses.length)return fail("INCOMPLETE","NO_STAGE3_PROGRESS_OBSERVED");
 let previous=null;
 for(const p of progresses){
  if(!checkFrames(p.frames,FRAMES))return fail("BLOCKED","INVALID_PROGRESS_FRAME_SET");
  for(const tf of FRAMES){
   const v=p.frames[tf];
   if(!v||!ints(v.persistedClosed)||!ints(v.contiguousClosed)||
      !ints(v.unclassifiedMissingSlots)||
      v.contiguousClosed>v.persistedClosed||
      (previous&&v.persistedClosed<previous.frames[tf].persistedClosed))
    return fail("BLOCKED","INVALID_OR_REGRESSING_STAGE3_COUNTS");
  }
  if(previous&&(p.dayIndex<previous.dayIndex||p.epoch<=previous.epoch))
   return fail("BLOCKED","NONMONOTONIC_STAGE3_PROGRESS");
  previous=p;
 }
 const latest=progresses.at(-1),matches={};
 for(const type of TYPES.slice(1)){
  const eligible=normalized.filter(x=>x.event===type&&
   x.dayIndex===latest.dayIndex&&
   Math.abs(x.epoch-latest.epoch)<=30000);
  if(eligible.length>1)return fail("BLOCKED","DUPLICATE_STAGE3_SAME_CYCLE");
  if(eligible.length===1)matches[type]=eligible[0];
 }
 const counts=Object.fromEntries(FRAMES.map(tf=>[tf,latest.frames[tf].persistedClosed]));
 const missing=Object.fromEntries(FRAMES.map(tf=>[tf,latest.frames[tf].unclassifiedMissingSlots]));
 if(Object.keys(matches).length<3)
  return fail("INCOMPLETE","STAGE3_LOG_EVENT_BUNDLE_INCOMPLETE",{
   checkedProgressEvents:progresses.length,
   matchedEventCount:Object.keys(matches).length+1,
   persistedClosed:counts,unclassifiedMissingSlots:missing
  });
 const gap=matches[TYPES[1]],over=matches[TYPES[2]],quote=matches[TYPES[3]];
 if(!checkFrames(gap.frames,FRAMES)||!checkFrames(over.frames,["H1","H4"])||
    !quote.intervalBins||typeof quote.intervalBins!=="object"||
    Array.isArray(quote.intervalBins)||
    Object.keys(quote.intervalBins).sort().join(",")!==
      BIN_KEYS.slice().sort().join(",")||
    !ints(quote.sourceQuoteSamples)||quote.sourceQuoteSamples<1||
    !ints(quote.observedIntervals)||quote.observedIntervals!==quote.sourceQuoteSamples-1)
  return fail("BLOCKED","STAGE3_CROSS_EVENT_STRUCTURE_CONTRADICTORY");
 for(const tf of FRAMES){
  if(!gap.frames[tf]||
     !ints(gap.frames[tf].unclassifiedMissingSlots)||
     gap.frames[tf].unclassifiedMissingSlots!==missing[tf])
   return fail("BLOCKED","STAGE3_REFERENCE_AND_PROGRESS_GAP_MISMATCH");
 }
 const disagreements={},compared={};
 for(const tf of ["H1","H4"]){
  const x=over.frames[tf];
  if(!x||!ints(x.fullyCoveredCompared)||
     !ints(x.fullyCoveredDisagreed)||
     !ints(x.higherClosedExamined)||!ints(x.notFullyCovered)||
     x.fullyCoveredCompared+x.notFullyCovered!==x.higherClosedExamined||
     x.higherClosedExamined>counts[tf]||
     x.fullyCoveredDisagreed>x.fullyCoveredCompared)
   return fail("BLOCKED","STAGE3_OHLC_COVERAGE_COUNTERS_CONTRADICTORY");
  disagreements[tf]=x.fullyCoveredDisagreed;
  compared[tf]=x.fullyCoveredCompared;
 }
 if(BIN_KEYS.some(k=>!ints(quote.intervalBins[k]))||
    BIN_KEYS.reduce((sum,k)=>sum+quote.intervalBins[k],0)!==quote.observedIntervals)
  return fail("BLOCKED","STAGE3_QUOTE_INTERVAL_COUNTS_CONTRADICTORY");
 const blockers=["LEGACY_COLLECTOR_FIRST_SEEN_UNKNOWN",
   "SOURCE_RIGHTS_AND_BROKER_CALENDAR_UNVERIFIED",
   "SPARSE_QUOTES_NOT_EXECUTION_EVIDENCE"];
 if(FRAMES.some(tf=>missing[tf]>0))blockers.push("UNCLASSIFIED_CLOSED_CANDLE_GAPS");
 if(disagreements.H1||disagreements.H4)blockers.push("OBSERVED_CROSS_FRAME_OHLC_MISMATCH");
 if(["H1","H4"].some(tf=>over.frames[tf].notFullyCovered>0))
  blockers.push("PARTIAL_M15_OVERLAP_NOT_VERIFIED");
 return fail("CONSISTENT_COUNTS_ONLY_NOT_MARKET_PROOF",null,{
  checkedProgressEvents:progresses.length,matchedEventCount:4,
  sourceQuoteSamples:quote.sourceQuoteSamples,
  persistedClosed:counts,unclassifiedMissingSlots:missing,
  fullyCoveredDisagreements:disagreements,comparedClosed:compared,
  blockers
 });
}
module.exports={reconcile};
