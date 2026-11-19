"use strict";
/*
 * Conservative count-only upper bound for the EXISTING bounded private
 * BiQuote observation window. It cannot prolong consent or grant trading.
 * Even an uninterrupted collector cannot produce more than ONE UTC-aligned
 * closed candle per future timeframe slot. Broker breaks can only reduce
 * this upper bound, and no historical/backfilled bars are invented.
 */
const WIDTH=Object.freeze({M15:15*60000,H1:60*60000,H4:4*60*60000});
const WARMUP=21,PAPER=50;
const ISO=/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/;
const stamp=s=>{
 if(typeof s!=="string"||!ISO.test(s))return NaN;
 const n=Date.parse(s);
 return Number.isFinite(n)&&new Date(n).toISOString().slice(0,19)===s.slice(0,19)?n:NaN;
};
const integer=x=>Number.isSafeInteger(x)&&x>=0&&x<100000;
const empty=()=>({M15:null,H1:null,H4:null});
const result=(status,reason,more={})=>({
 mode:"BIQUOTE_BOUNDED_COLLECTOR_COUNT_CEILING_ONLY",
 status,signal:"WAIT",executable:false,tradeEligible:false,
 paperOrdersAllowed:false,liveOrdersAllowed:false,brokerOrdersSent:0,
 sourceRequestsMade:0,brokerRightsVerified:false,
 brokerSessionCalendarVerified:false,firstSeenVerified:false,
 backupVerified:false,independentHoldoutValidated:false,
 captureExtended:false,collectorRestarted:false,
 hypotheticalFutureH4Closures:null,maxPossibleStoredH4:null,
 paperH4HistoryReachableByWindowEnd:null,
 theoreticalWarmupH4ReachableByWindowEnd:null,
 upperBoundFutureClosedSlots:empty(),maximumPossiblePersistedClosed:empty(),
 blockers:["HYPOTHETICAL_COUNTS_NOT_TRADING_PROOF",
           "H4_FIRST_SEEN_FOR_DEPLOYED_LEGACY_ARCHIVE_UNKNOWN",
           "BROKER_SESSIONS_AND_DATA_RIGHTS_UNVERIFIED",
           ...(reason?[reason]:[])],...more
});
function assessWindow(input){
 if(input?.origin!=="UNATTESTED_RENDER_COUNTS_NO_PRIVATE_ARCHIVE")
  return result("BLOCKED","INVALID_UNATTESTED_METADATA_ORIGIN");
 const start=stamp(input.startUTC),now=stamp(input.asOfUTC),
       end=stamp(input.endUTC),c=input.persistedClosedCounts;
 if(!Number.isFinite(start)||!Number.isFinite(now)||!Number.isFinite(end)||
    !(start<=now&&now<end&&end-start<=7*86400000)||
    !c||typeof c!=="object"||Array.isArray(c)||
    Object.keys(c).sort().join(",")!=="H1,H4,M15"||
    Object.values(c).some(n=>!integer(n)))
  return result("BLOCKED","INVALID_BOUNDED_WINDOW_OR_COUNTS");
 const remaining={},ceiling={};
 for(const tf of Object.keys(WIDTH)){
  // End inclusively is intentionally generous. A last-close exactly
  // at stop time may not get recorded, making this only an upper bound.
  remaining[tf]=Math.max(0,Math.floor(end/WIDTH[tf])-
                           Math.floor(now/WIDTH[tf]));
  ceiling[tf]=c[tf]+remaining[tf];
 }
 const paperPossible=ceiling.H4>=PAPER,warmupPossible=ceiling.H4>=WARMUP;
 const blockers=[
  "HYPOTHETICAL_COUNTS_NOT_TRADING_PROOF",
  "H4_FIRST_SEEN_FOR_DEPLOYED_LEGACY_ARCHIVE_UNKNOWN",
  "BROKER_SESSIONS_AND_DATA_RIGHTS_UNVERIFIED"
 ];
 if(!paperPossible)blockers.push("H4_50_BAR_PAPER_HISTORY_MATHEMATICALLY_UNREACHABLE");
 if(!warmupPossible)blockers.push("H4_21_BAR_WARMUP_MATHEMATICALLY_UNREACHABLE");
 return result("THEORETICAL_COUNT_CEILING_NOT_READINESS",null,{
  asOfUTC:input.asOfUTC,captureEndUTC:input.endUTC,
  persistedClosedCounts:{...c},
  upperBoundFutureClosedSlots:remaining,
  maximumPossiblePersistedClosed:ceiling,
  hypotheticalFutureH4Closures:remaining.H4,
  maxPossibleStoredH4:ceiling.H4,
  theoreticalWarmupH4ReachableByWindowEnd:warmupPossible,
  paperH4HistoryReachableByWindowEnd:paperPossible,
  minWarmupH4:WARMUP,minPaperHistoryH4:PAPER,
  blockers
 });
}
module.exports={assessWindow};
if(require.main===module){
 let data="";
 process.stdin.setEncoding("utf8");
 process.stdin.on("data",chunk=>{
  data+=chunk;if(data.length>65536){process.stderr.write("TOO_LARGE\n");process.exit(2);}
 });
 process.stdin.on("end",()=>{
  try{process.stdout.write(JSON.stringify(assessWindow(JSON.parse(data)))+"\n");}
  catch{process.stdout.write(JSON.stringify(result("BLOCKED","INVALID_INPUT"))+"\n");}
 });
}
