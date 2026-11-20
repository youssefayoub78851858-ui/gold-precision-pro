"use strict";
/**
 * OFFLINE research-only H4 sequence diagnostic for the November 2026
 * BiQuote SUPPORT-DECLARED schedule. An FX/CFD broker can pause over
 * weekends: raw 4h-gap continuity differs from session-aware continuity.
 *
 * The vendor schedule is NOT a verified unnamed MT5 broker calendar.
 * This module cannot certify broker session entitlement, make candles,
 * infer first-seen times, change a collector, or authorize trades.
 */
const {slotClosed}=require("./biquote_vendor_declared_session");
const WIDTH=14400000;
const MAX=250;
const KIND="UNATTESTED_VENDOR_NOV2026_H4_OPEN_AND_RECEIPT_TIMES_ONLY";
const ISO=/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/;
function stamp(x){
 if(typeof x!=="string"||!ISO.test(x))return NaN;
 const v=Date.parse(x);
 return Number.isFinite(v)&&new Date(v).toISOString().slice(0,19)===x.slice(0,19)?v:NaN;
}
function base(status,reason,extra={}){
 return {
  mode:"BIQUOTE_VENDOR_SESSION_H4_OFFLINE_DIAGNOSTIC_V1",
  status,reason,signal:"WAIT",executable:false,tradeEligible:false,
  recommendationAllowed:false,paperOrdersAllowed:false,liveOrdersAllowed:false,
  brokerOrdersSent:0,paperOrdersSent:0,providerRequestsMade:0,
  sourceRightsVerified:false,originalBrokerIdentified:false,
  originalBrokerSessionCalendarVerified:false,marketCalendarIndependentlyVerified:false,
  firstSeenVendorAuthenticated:false,independentOHLCParityVerified:false,
  brokerBidAskCostsVerified:false,forwardHoldoutProven:false,
  providerDeclaredScheduleOnly:true,tradeAdmissionPossible:false,
  barsWithLocalReceipt:0,rawUtcGridTail:0,
  vendorConditionalSessionTail:0,
  providerDeclaredFullyClosedH4SlotsBridged:0,
  missingProviderOpenH4Slots:0,unknownScheduleSlots:0,
  conditional21H4Reached:false,conditional50H4Reached:false,
  ...extra
 };
}
function inspect(input){
 if(input?.origin!==KIND)
  return base("BLOCKED","INVALID_UNATTESTED_ORIGIN");
 const now=stamp(input.asOfUTC),bars=input.bars;
 if(!Number.isFinite(now)||!Array.isArray(bars)||bars.length>MAX)
  return base("BLOCKED","INVALID_TIME_OR_BAR_SET");
 // Empty input is a valid safe observation, not a promise of availability.
 if(!bars.length)
  return base("NO_OBSERVED_H4","NO_RECEIPTED_BARS");
 let prevOpen=-Infinity,prevReceipt=-Infinity,raw=0,session=0;
 let bridged=0,missingOpen=0,unknown=0;
 for(const item of bars){
  if(!item||typeof item!=="object"||Array.isArray(item)||
     Object.keys(item).sort().join(",")!=="firstSeenClosedUTC,openUTC")
   return base("BLOCKED","UNSAFE_OR_MISSING_BAR_METADATA");
  const t=stamp(item.openUTC),receipt=stamp(item.firstSeenClosedUTC);
  if(!Number.isFinite(t)||!Number.isFinite(receipt)||t%WIDTH!==0||
     t<=prevOpen||t+WIDTH>receipt||receipt>now||receipt<prevReceipt)
   return base("BLOCKED","INVALID_H4_GRID_ORDER_OR_FIRST_RECEIPT");
  const thisSlot=slotClosed(t,WIDTH);
  if(thisSlot===null)
   return base("BLOCKED","OUTSIDE_VENDOR_DECLARED_DATE_WINDOW");
  if(thisSlot===true)
   return base("BLOCKED","H4_BAR_CLAIMED_INSIDE_VENDOR_FULL_CLOSURE");
  if(prevOpen===-Infinity){raw=1;session=1;}
  else {
   const widthCount=(t-prevOpen)/WIDTH;
   if(!Number.isSafeInteger(widthCount)||widthCount<1)
    return base("BLOCKED","INVALID_H4_GRID_INTERVAL");
   raw=widthCount===1?raw+1:1;
   let gapAllClosed=true;
   for(let at=prevOpen+WIDTH;at<t;at+=WIDTH){
    const closed=slotClosed(at,WIDTH);
    if(closed===null){unknown++;gapAllClosed=false;}
    else if(closed===true){bridged++;}
    else{missingOpen++;gapAllClosed=false;}
   }
   session=gapAllClosed?session+1:1;
  }
  prevOpen=t;prevReceipt=receipt;
 }
 return base("VENDOR_CONDITIONAL_COUNTS_ONLY_NOT_TRADE_READY",
  "ORIGINAL_BROKER_CALENDAR_AND_SOURCE_RIGHTS_UNVERIFIED",{
   barsWithLocalReceipt:bars.length,rawUtcGridTail:raw,
   vendorConditionalSessionTail:session,
   providerDeclaredFullyClosedH4SlotsBridged:bridged,
   missingProviderOpenH4Slots:missingOpen,
   unknownScheduleSlots:unknown,
   conditional21H4Reached:session>=21,
   conditional50H4Reached:session>=50
  });
}
module.exports={inspect};
if(require.main===module){
 let raw="";
 process.stdin.setEncoding("utf8");
 process.stdin.on("data",part=>{
  raw+=part;
  if(raw.length>300000){process.stderr.write("H4_SESSION_AUDIT_TOO_LARGE\n");process.exit(2);}
 });
 process.stdin.on("end",()=>{
  try{process.stdout.write(JSON.stringify(inspect(JSON.parse(raw)))+"\n");}
  catch{process.stdout.write(JSON.stringify(base("BLOCKED","INVALID_JSON_INPUT"))+"\n");}
 });
}
