"use strict";
/**
 * Private-only read-only check against BiQuote SUPPORT-DECLARED MT5
 * XAUUSD schedule (reply dated 2026-11-16).
 * Sunday 23:00 UTC -> Friday 22:00 UTC; daily break 22-23 UTC.
 * Provider warns the UTC schedule can shift around DST.
 *
 * The original broker is unnamed, independently verified holidays/DST
 * and upstream usage rights are unknown. NEVER bridge missing OHLC,
 * fill bars, authorize technical entries, or mark a signal tradeable.
 *
 * Bounded to 2026-11-02..2026-11-30 UTC, safely away from 2026 DST
 * transition. Outside that range classify UNKNOWN. The public
 * generic-reference audit remains unchanged and separately labeled.
 */
const WIDTHS=Object.freeze({M15:900000,H1:3600000,H4:14400000});
const FROM=Date.parse("2026-11-02T00:00:00Z");
const UNTIL=Date.parse("2026-11-30T00:00:00Z");
const BASE=Object.freeze({
 mode:"BIQUOTE_VENDOR_DECLARED_SESSION_EVIDENCE_ONLY",
 sourceRecord:"BIQUOTE_SUPPORT_REPLY_2026_11_16",
 scheduleSource:"PROVIDER_SUPPORT_NOT_ORIGINAL_BROKER_DOCUMENT",
 coveredUtc:"2026-11-02 through 2026-11-29 inclusive",
 providerSaysPrivateRenderResearchAllowed:true,
 providerSaysSingleMT5Feed:true,
 originalBrokerIdentified:false,
 originalBrokerUpstreamRightsWarranted:false,
 brokerIndependentScheduleVerified:false,
 dstChangesIndependentlyVerified:false,
 allowsGapBridging:false,canIssueTradePlan:false,
 signal:"WAIT",executable:false,tradeEligible:false,paperOrdersAllowed:false
});
function slotClosed(openMs,width){
 if(!Number.isSafeInteger(openMs)||!Number.isInteger(width)||
    openMs<FROM||openMs+width>UNTIL)return null;
 for(let t=openMs;t<openMs+width;t+=900000){
  const d=new Date(t),day=d.getUTCDay(),hour=d.getUTCHours();
  const weekend=(day===5&&hour>=22)||day===6||(day===0&&hour<23);
  const daily=(day>=1&&day<=4&&hour===22);
  if(!(weekend||daily))return false;
 }
 return true;
}
function evaluateGap(rows,tf){
 const width=WIDTHS[tf];
 const result={...BASE,timeframe:tf,
  status:"NOT_INDEPENDENTLY_VERIFIED",
  gapGroups:0,missingSlots:0,providerDeclaredPauseSlots:0,
  missingDuringProviderTradingSlots:0,outsideDeclaredDateWindowSlots:0,
  examples:[]};
 if(!width||!Array.isArray(rows)||rows.length<2||rows.length>1000){
  result.error="INVALID_FRAME_OR_HISTORY";return result;
 }
 let previous=-1;
 for(const row of rows){
  const stamp=row?.time;
  if(typeof stamp!=="string"||
     !/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(stamp)){
   result.error="INVALID_TIMESTAMP";return result;
  }
  const t=Date.parse(stamp);
  if(!Number.isSafeInteger(t)||t%width!==0||t<=previous){
   result.error="BAD_BAR_ORDER_OR_GRID";return result;
  }
  if(previous>=0){
   const missing=(t-previous)/width-1;
   if(!Number.isSafeInteger(missing)||missing<0){
     result.error="NONINTEGER_CANDLE_GAP";return result;
   }
   if(missing>0){
     result.gapGroups++;result.missingSlots+=missing;
     let closed=0,trading=0,unknown=0;
     if(missing>3000)unknown=missing;
     else{
       for(let i=1;i<=missing;i++){
         const v=slotClosed(previous+i*width,width);
         if(v===true)closed++;
         else if(v===false)trading++;
         else unknown++;
       }
     }
     result.providerDeclaredPauseSlots+=closed;
     result.missingDuringProviderTradingSlots+=trading;
     result.outsideDeclaredDateWindowSlots+=unknown;
     const type=closed===missing?"MATCHES_PROVIDER_DECLARED_CLOSURE_NOT_PROVEN":
       trading>0?"MISSING_WHEN_PROVIDER_DECLARES_MARKET_OPEN":
       "OUTSIDE_VERIFIABLE_DECLARATION_WINDOW";
     if(result.examples.length<8)result.examples.push({
       previousOpenUTC:new Date(previous).toISOString(),
       nextOpenUTC:new Date(t).toISOString(),
       missingSlots:missing,providerPauseSlots:closed,
       providerOpenMissingSlots:trading,unknownSlots:unknown,
       classification:type
     });
   }
  }
  previous=t;
 }
 return result;
}
function evaluateFrames(chart){
 const frames={};
 for(const tf of ["M15","H1","H4"])frames[tf]=evaluateGap(chart?.[tf],tf);
 return {...BASE,frames};
}
module.exports={evaluateFrames,evaluateGap,slotClosed};
