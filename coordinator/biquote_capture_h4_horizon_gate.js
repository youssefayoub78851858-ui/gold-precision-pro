"use strict";
/*
 * Conservative count-only upper bound for the EXISTING bounded private
 * BiQuote observation window. It cannot prolong consent or grant trading.
 * Even an uninterrupted collector cannot produce more than ONE UTC-aligned
 * closed candle per future timeframe slot. Broker breaks can only reduce
 * this upper bound, and no historical/backfilled bars are invented.
 */
const WIDTH=Object.freeze({M15:15*60000,H1:60*60000,H4:4*60*60000});
const {slotClosed}=require("./biquote_vendor_declared_session");
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
 maxPossibleContiguousH4:null,rawStoredH4CountReachableByWindowEnd:null,
 // Optional conditional projection based ONLY on BiQuote support's
 // November 2026 pause declaration; not the actual unnamed broker calendar.
 providerDeclaredH4Projection:null,
 paperH4HistoryReachableByWindowEnd:null,
 theoreticalWarmupH4ReachableByWindowEnd:null,
 upperBoundFutureClosedSlots:empty(),maximumPossiblePersistedClosed:empty(),
 maximumPossibleContiguousClosed:empty(),
 blockers:["HYPOTHETICAL_COUNTS_NOT_TRADING_PROOF",
           "H4_FIRST_SEEN_FOR_DEPLOYED_LEGACY_ARCHIVE_UNKNOWN",
           "BROKER_SESSIONS_AND_DATA_RIGHTS_UNVERIFIED",
           ...(reason?[reason]:[])],...more
});
function declaredH4Projection(now,end,tailH4){
 // Every counted interval ends at an H4 UTC boundary. An H4 bar whose
 // entire four-hour interval lies inside the provider-declared weekend
 // closure cannot exist *if* that declaration applies to the broker.
 // In contrast, H4 intervals that are PARTLY open may have a real bar:
 // count them in the generous upper bound; never synthesize any bar.
 // Both endpoints are within the bounded existing capture, and this
 // calculation performs no requests, archive reads or deployment.
 const from=Math.floor(now/WIDTH.H4)+1,to=Math.floor(end/WIDTH.H4);
 let observedFullBreaks=0,otherSlots=0,unknownSlots=0;
 let current=tailH4,best=tailH4;
 for(let boundary=from;boundary<=to;boundary++){
  const classification=slotClosed((boundary-1)*WIDTH.H4,WIDTH.H4);
  if(classification===null){unknownSlots++;current=0;continue;}
  if(classification===true){observedFullBreaks++;current=0;continue;}
  otherSlots++;
  current++;
  best=Math.max(best,current);
 }
 if(unknownSlots)return {
  mode:"BIQUOTE_SUPPORT_DECLARED_NOVEMBER_2026_SCENARIO_ONLY",
  status:"OUTSIDE_PROVIDER_DECLARED_DATE_RANGE",
  originalBrokerScheduleVerified:false,
  consentExtended:false,providerDeclaredFullPauseH4Slots:null,
  maxPossibleClosedH4FutureSlotsUnderDeclaration:null,
  maxPossibleContiguousH4AtAnyTimeUnderDeclaration:null,
  maxPossibleContiguousH4AtCaptureEndUnderDeclaration:null,
  technicalWarmup21ReachableUnderDeclaration:null,
  paperHistory50ReachableUnderDeclaration:null
 };
 return {
  mode:"BIQUOTE_SUPPORT_DECLARED_NOVEMBER_2026_SCENARIO_ONLY",
  status:"HYPOTHETICAL_VENDOR_SCHEDULE_NOT_BROKER_VERIFIED",
  originalBrokerScheduleVerified:false,
  consentExtended:false,providerDeclaredFullPauseH4Slots:observedFullBreaks,
  maxPossibleClosedH4FutureSlotsUnderDeclaration:otherSlots,
  maxPossibleContiguousH4AtAnyTimeUnderDeclaration:best,
  maxPossibleContiguousH4AtCaptureEndUnderDeclaration:current,
  technicalWarmup21ReachableUnderDeclaration:best>=WARMUP,
  paperHistory50ReachableUnderDeclaration:best>=PAPER
 };
}
function assessWindow(input){
 if(input?.origin!=="UNATTESTED_RENDER_COUNTS_NO_PRIVATE_ARCHIVE")
  return result("BLOCKED","INVALID_UNATTESTED_METADATA_ORIGIN");
 const start=stamp(input.startUTC),now=stamp(input.asOfUTC),
       end=stamp(input.endUTC),c=input.persistedClosedCounts,
       tail=input.contiguousClosedCounts;
 if(!Number.isFinite(start)||!Number.isFinite(now)||!Number.isFinite(end)||
    !(start<=now&&now<end&&end-start<=7*86400000)||
    !c||typeof c!=="object"||Array.isArray(c)||
    Object.keys(c).sort().join(",")!=="H1,H4,M15"||
    Object.values(c).some(n=>!integer(n))||
    !tail||typeof tail!=="object"||Array.isArray(tail)||
    Object.keys(tail).sort().join(",")!=="H1,H4,M15"||
    Object.keys(WIDTH).some(tf=>!integer(tail[tf])||tail[tf]>c[tf]))
  return result("BLOCKED","INVALID_BOUNDED_WINDOW_OR_COUNTS");
 const remaining={},ceiling={},contiguousCeiling={};
 for(const tf of Object.keys(WIDTH)){
  // End inclusively is intentionally generous. A last-close exactly
  // at stop time may not get recorded, making this only an upper bound.
  remaining[tf]=Math.max(0,Math.floor(end/WIDTH[tf])-
                           Math.floor(now/WIDTH[tf]));
  ceiling[tf]=c[tf]+remaining[tf];
  contiguousCeiling[tf]=tail[tf]+remaining[tf];
 }
 // Paper/technical history needs a contiguous recent H4 sequence; 50
 // stored bars with older gaps is NOT 50 eligible history bars. Even the
 // optimistic future horizon remains count-only and not an availability seal.
 const paperPossible=contiguousCeiling.H4>=PAPER,
       warmupPossible=contiguousCeiling.H4>=WARMUP;
 const vendorScenario=declaredH4Projection(now,end,tail.H4);
 const blockers=[
  "HYPOTHETICAL_COUNTS_NOT_TRADING_PROOF",
  "H4_FIRST_SEEN_FOR_DEPLOYED_LEGACY_ARCHIVE_UNKNOWN",
  "BROKER_SESSIONS_AND_DATA_RIGHTS_UNVERIFIED"
 ];
 if(!paperPossible)blockers.push("H4_50_BAR_PAPER_HISTORY_MATHEMATICALLY_UNREACHABLE");
 if(ceiling.H4>=PAPER&&!paperPossible)
  blockers.push("RAW_H4_COUNT_CANNOT_REPLACE_CONTIGUOUS_HISTORY");
 if(!warmupPossible)blockers.push("H4_21_BAR_WARMUP_MATHEMATICALLY_UNREACHABLE");
 // Conditional planning advice, NOT a mathematical statement about the
 // unnamed real broker or independently authenticated market sessions.
 if(vendorScenario.status==="HYPOTHETICAL_VENDOR_SCHEDULE_NOT_BROKER_VERIFIED"){
  if(!vendorScenario.technicalWarmup21ReachableUnderDeclaration)
   blockers.push("H4_21_WARMUP_UNREACHABLE_WITHIN_PROVIDER_DECLARED_WEEKEND_SCENARIO");
  if(!vendorScenario.paperHistory50ReachableUnderDeclaration)
   blockers.push("H4_50_PAPER_UNREACHABLE_WITHIN_PROVIDER_DECLARED_WEEKEND_SCENARIO");
 }
 return result("THEORETICAL_COUNT_CEILING_NOT_READINESS",null,{
  asOfUTC:input.asOfUTC,captureEndUTC:input.endUTC,
  persistedClosedCounts:{...c},contiguousClosedCounts:{...tail},
  upperBoundFutureClosedSlots:remaining,
  maximumPossiblePersistedClosed:ceiling,
  maximumPossibleContiguousClosed:contiguousCeiling,
  hypotheticalFutureH4Closures:remaining.H4,
  maxPossibleStoredH4:ceiling.H4,
  maxPossibleContiguousH4:contiguousCeiling.H4,
  rawStoredH4CountReachableByWindowEnd:ceiling.H4>=PAPER,
  providerDeclaredH4Projection:vendorScenario,
  theoreticalWarmupH4ReachableByWindowEnd:warmupPossible,
  paperH4HistoryReachableByWindowEnd:paperPossible,
  minWarmupH4:WARMUP,minPaperHistoryH4:PAPER,
  blockers
 });
}
module.exports={assessWindow,declaredH4Projection};
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
