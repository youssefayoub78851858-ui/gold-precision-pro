"use strict";
/**
 * Diagnoses timestamps of real CLOSED BiQuote OHLC gaps, never market access.
 * General Nov-2026 reference: 22-23 UTC daily, Fri 22 -> Sun 23 weekend.
 * Does NOT identify underlying MT5 broker; no holidays, no licence proof,
 * no backfill and no permission to join bars across even a likely pause.
 */
const WIDTHS=Object.freeze({M15:900000,H1:3600000,H4:14400000});
const FROM=Date.parse("2026-11-01T00:00:00Z");
const TO=Date.parse("2027-03-14T00:00:00Z");
function candidateTime(slotMs,tf){
 const width=WIDTHS[tf];
 if(!Number.isSafeInteger(slotMs)||slotMs<FROM||slotMs+width>TO)return null;
 // A reference closed slot must be entirely inside an assumed pause.
 for(let t=slotMs;t<slotMs+width;t+=900000){
  const d=new Date(t),weekday=d.getUTCDay(),hour=d.getUTCHours();
  const weekend=(weekday===5)||(weekday===0&&hour<23)||
    (weekday===6&&hour>=22);
  const daily=weekday>=1&&weekday<=4&&hour===22;
  if(!weekend&&!daily)return false;
 }
 return true;
}
function auditRows(rows,tf){
 const empty={classification:"REFERENCE_ONLY_UNVERIFIED_BROKER",
  referenceWindowUTC:"2026-11-01..2027-03-14",
  sessionCalendarVerified:false,brokerCalendarVerified:false,
  bridgeBarsAllowed:false,signal:"WAIT",executable:false,
  timeframe:tf,gapCount:0,missingSlots:0,referencePauseCandidates:0,
  missingDuringReferenceTradingHours:0,outsideReference:0,examples:[]};
 const width=WIDTHS[tf];
 if(!width||!Array.isArray(rows)||rows.length<2||rows.length>200)
   return {...empty,error:"INVALID_INPUT"};
 let prev=null;
 for(const row of rows){
  const t=Date.parse(row?.time);
  if(!Number.isFinite(t)||t%width!==0||t<=prev)
   return {...empty,error:"INVALID_OR_UNSORTED_CANDLE_OPEN"};
  if(prev!==null){
   const difference=t-prev;
   if(difference%width!==0)return {...empty,error:"MISALIGNED_CANDLE_GAP"};
   const missing=difference/width-1;
   if(missing>0){
    empty.gapCount++;
    empty.missingSlots+=missing;
    let ref=0,trading=0,unknown=0;
    if(missing>1100){
      unknown=missing;
    }else for(let i=1;i<=missing;i++){
      const status=candidateTime(prev+i*width,tf);
      if(status===true)ref++;
      else if(status===false)trading++;
      else unknown++;
    }
    empty.referencePauseCandidates+=ref;
    empty.missingDuringReferenceTradingHours+=trading;
    empty.outsideReference+=unknown;
    if(empty.examples.length<8){
      empty.examples.push({
        previousBarUTC:new Date(prev).toISOString(),
        nextBarUTC:new Date(t).toISOString(),
        missingSlots:missing,
        referencePauseCandidateSlots:ref,
        unexplainedTradingSlots:trading,
        outsideReferenceSlots:unknown,
        label:ref===missing?"REFERENCE_PAUSE_CANDIDATE_NOT_BROKER_VERIFIED":
          trading>0?"MISSING_IN_REFERENCE_TRADING_HOURS":
          "REFERENCE_RANGE_UNKNOWN"
      });
    }
   }
  }
  prev=t;
 }
 return empty;
}
module.exports={candidateTime,auditRows};
