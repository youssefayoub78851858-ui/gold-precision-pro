"use strict";
/**
 * Private read-only market structure on actual BiQuote CLOSED MID candles.
 * Windowed so that a missing candle or weekend is NEVER bridged as a
 * continuous sequence for BOS/sweep/FVG/EMA/ATR. Uses existing V3 research
 * pivots; no orders, forecast, source authorization or strategy admission.
 */
const {structure}=require("./v3_market_structure");
const {auditRows}=require("./biquote_session_reference");
const WIDTHS=Object.freeze({M15:900000,H1:3600000,H4:14400000});
const ORDER=Object.freeze(["M15","H1","H4"]);
const MIN_CONFIRMED_PIVOT_WINDOW=7; // V3 left2/right2 + one last CLOSED candle
const WAIT=Object.freeze({signal:"WAIT",executable:false,researchEligible:false,
  tradeEligible:false,paperOrdersAllowed:false});
function price(x){return typeof x==="number"&&Number.isFinite(x)&&x>0}
function valid(rows,tf,asOfMs){
 if(!Array.isArray(rows)||rows.length<20||rows.length>48)return false;
 let prev=-1;
 for(const row of rows){
  if(!row||typeof row.time!=="string"||
    !/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(row.time))return false;
  const t=Date.parse(row.time);
  if(!Number.isFinite(t)||t<=prev||t%WIDTHS[tf]!==0||t+WIDTHS[tf]>asOfMs)return false;
  if(!["open","high","low","close"].every(k=>price(row[k])))return false;
  if(row.high<Math.max(row.open,row.close,row.low)||
     row.low>Math.min(row.open,row.close,row.high))return false;
  prev=t;
 }
 return true;
}
const rounded=x=>Number(x.toFixed(3));
function ema20(rows){
 let result=rows.slice(0,20).reduce((a,b)=>a+b.close,0)/20;
 for(let i=20;i<rows.length;i++)result=result*(19/21)+rows[i].close*(2/21);
 return rounded(result);
}
function atr14(rows){
 if(rows.length<15)return null;
 const tr=[];
 for(let i=1;i<rows.length;i++){
  const current=rows[i],prev=rows[i-1];
  tr.push(Math.max(current.high-current.low,
    Math.abs(current.high-prev.close),Math.abs(current.low-prev.close)));
 }
 let a=tr.slice(0,14).reduce((p,n)=>p+n,0)/14;
 for(let i=14;i<tr.length;i++)a=(a*13+tr[i])/14;
 return rounded(a);
}
function empty(reason,gaps,used){
 return {...WAIT,state:"INSUFFICIENT_VERIFIED_STRUCTURE",reason,
   contiguousBars:used,unclassifiedGapsInChart:gaps,
   sessionCalendarVerified:false,validForEntry:false,
   priceBasis:"MID_WITH_POSSIBLE_BID_SEED"};
}
function analyzeFrame(rows,tf,asOfMs){
 if(!valid(rows,tf,asOfMs))return empty("INVALID_CLOSED_BARS",0,0);
 let breaks=0;
 for(let i=1;i<rows.length;i++)
  if(Date.parse(rows[i].time)-Date.parse(rows[i-1].time)!==WIDTHS[tf])breaks++;
 let first=rows.length-1;
 while(first>0 &&
       Date.parse(rows[first].time)-Date.parse(rows[first-1].time)===WIDTHS[tf])
  first--;
 const contiguous=rows.slice(first);
 // Historical BiQuote bars can span broker day/week pauses. NEVER call
 // such pauses verified without the actual broker's session calendar.
 // Permit 7+ bars only for within-segment confirmed pivot observations.
 // ATR14 requires 15 connected candles, EMA20 requires 20; do not
 // compute either indicator by jumping an unclassified gap.
 if(contiguous.length<MIN_CONFIRMED_PIVOT_WINDOW)
  return empty("LESS_THAN_7_CONTIGUOUS_CLOSED_BARS",breaks,contiguous.length);
 // Label only whether missing UTC slots resemble a GENERAL winter pause.
 // This may help an operator request the exact broker session calendar,
 // but never joins bars or changes trading admission.
 const referenceOnlyGapAudit=auditRows(rows,tf);
 const observed=structure(contiguous,{left:2,right:2});
 const last=contiguous.at(-1);
 if(observed.signal!=="WAIT"||observed.executable!==false)
  return empty("STRUCTURE_GATE_NOT_WAIT",breaks,contiguous.length);
 const recent=contiguous.slice(-20);
 const events=[
  observed.bosUp?"BOS_UP":null,observed.bosDown?"BOS_DOWN":null,
  observed.sweepHigh?"SWEEP_HIGH":null,observed.sweepLow?"SWEEP_LOW":null,
  observed.fvgBull?"FVG_BULL":null,observed.fvgBear?"FVG_BEAR":null
 ].filter(Boolean);
 const full=contiguous.length>=20;
 return {...WAIT,state:full?"OBSERVATION_ONLY":"PARTIAL_OBSERVATION_UNVERIFIED_SESSION",
   timeframe:tf,contiguousBars:contiguous.length,
   unclassifiedGapsInChart:breaks,
   referenceOnlyGapAudit,
   sessionCalendarVerified:false,validForEntry:false,
   priceBasis:"MID_WITH_POSSIBLE_BID_SEED",
   lastClosedOpenUTC:contiguous.at(-1).time,
   lastClosed:rounded(last.close),
   ema20:full?ema20(contiguous):null,
   atr14:contiguous.length>=15?atr14(contiguous):null,
   recentRangeBars:recent.length,
   recentRangeHigh20:rounded(Math.max(...recent.map(x=>x.high))),
   recentRangeLow20:rounded(Math.min(...recent.map(x=>x.low))),
   technicalCoverage:"CONTIGUOUS_POST_GAP_ONLY",
   unclassifiedGapsRemainBlocked:true,
   confirmedSwingHigh:observed.high?rounded(observed.high.price):null,
   confirmedSwingLow:observed.low?rounded(observed.low.price):null,
   lastClosedEvents:events,
   // Price zones are observational only. Missing upstream licence/session
   // checks and MID/BID seed prohibit any execution interpretation.
   demandSupplyUnverified:true};
}
function analyzeChart(chart,asOfMs){
 const results={};
 for(const tf of ORDER)results[tf]=analyzeFrame(chart?.[tf],tf,asOfMs);
 return {...WAIT,mode:"PRIVATE_READONLY_TECHNICAL_OBSERVATIONS",
  priceBasis:"MID_WITH_POSSIBLE_BID_SEED",
  sessionCalendarVerified:false,upstreamRightsWarranted:false,
  orderFlowIncluded:false,newsAndMacroIncluded:false,
  frames:results};
}
module.exports={analyzeChart,analyzeFrame};
