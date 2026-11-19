"use strict";
/*
 * RETROSPECTIVE diagnostics of sealed archive candle snapshots only.
 * This is NOT a prospective point-in-time test: schema v1 does not record
 * when each historical OHLC candle first became available to the collector.
 * No network, orders, broker fills, simulated equity or price-bearing output.
 */
const {reviewFourStages}=require("./ultimate_four_stage_review");
const WIDTH=Object.freeze({M15:900000,H1:3600000,H4:14400000});
const MIN=21,MAX_BARS=45000,MAX_REPLAY=256;
const START=Date.parse("2026-11-18T00:00:00Z");
const safe=Object.freeze({mode:"BIQUOTE_V3_CHRONOLOGICAL_RECONSTRUCTION_ONLY",
 signal:"WAIT",executable:false,paperOrdersAllowed:false,
 liveOrdersAllowed:false,tradeEligible:false,
 brokerOrdersSent:0,providerRequestsMade:0,brokerFillsModeled:false,
 individualCandleFirstAvailableUTCVerified:false,
 executionBidAskHistoryVerified:false,brokerCostsVerified:false,
 sourceRightsVerified:false,brokerCalendarVerified:false,
 independentHoldoutPerformanceProven:false,
 hypotheticalNetPnL:null,netExpectancy:null,winRate:null});
function stamp(value){
 if(typeof value!=="string"||!/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(value))return NaN;
 const t=Date.parse(value);
 return Number.isFinite(t)&&new Date(t).toISOString().replace(".000Z","Z")===value?t:NaN;
}
function parseRows(rows,width){
 if(!Array.isArray(rows)||rows.length>MAX_BARS)throw Error("INVALID_ARCHIVE_FRAME");
 let last=-Infinity;
 return rows.map(row=>{
  if(!row||typeof row!=="object"||Array.isArray(row)||
     !["datetime","open","high","low","close"].every(k=>Object.hasOwn(row,k)))
   throw Error("INVALID_ARCHIVE_BAR");
  const t=stamp(row.datetime);
  if(!Number.isFinite(t)||t<START||t%width!==0||t<=last)
   throw Error("INVALID_ARCHIVE_TIME");
  last=t;
  const {open,high,low,close}=row;
  if(![open,high,low,close].every(v=>typeof v==="number"&&Number.isFinite(v)&&v>0&&v<1e8)||
      low>Math.min(open,close)||high<Math.max(open,close))
   throw Error("INVALID_ARCHIVE_OHLC");
  return {...row,_t:t};
 });
}
function suffix(rows,width,asOf){
 const completed=rows.filter(b=>b._t+width<=asOf);
 if(!completed.length)return [];
 let start=completed.length-1;
 while(start>0&&completed[start]._t-completed[start-1]._t===width)start--;
 return completed.slice(Math.max(start,completed.length-128)).map(({_t,...b})=>b);
}
function parity(frames){
 const map=new Map(frames.M15.map(x=>[stamp(x.datetime),x]));
 let checked={H1:0,H4:0};
 for(const [tf,n] of [["H1",4],["H4",16]]){
  for(const bar of frames[tf]){
   const t=stamp(bar.datetime);
   const group=Array.from({length:n},(_,i)=>map.get(t+i*WIDTH.M15));
   if(group.some(x=>!x))continue;
   const expected={open:group[0].open,high:Math.max(...group.map(b=>b.high)),
    low:Math.min(...group.map(b=>b.low)),close:group.at(-1).close};
   // Strictly same price basis ONLY; a mismatch is never "fixed".
   if(Object.keys(expected).some(k=>
      Math.abs(expected[k]-bar[k])>Math.max(0.00001,Math.abs(bar[k])*1e-8)))
     return false;
   checked[tf]++;
  }
 }
 return checked.H1>0&&checked.H4>0;
}
function blocked(code,totals={M15:0,H1:0,H4:0}){
 return {...safe,status:"BLOCKED",blocker:code,
  storedClosedCounts:totals,retrospectiveDecisionCount:0,
  technicalWatchCounts:{BUY:0,SELL:0,NONE:0},
  noFutureCandlesUsed:true,replayOnlyNotPointInTime:true};
}
function inspect(input){
 const origin=input?.dataOrigin;
 if(!["SYNTHETIC_TEST_ONLY","BIQUOTE_ARCHIVED_UNVERIFIED_NO_PAPER"].includes(origin))
  return blocked("UNVERIFIED_ARCHIVE_ORIGIN");
 const cutoff=input?.decisionCutoffUTC===undefined?Infinity:stamp(input.decisionCutoffUTC);
 if(Number.isNaN(cutoff)||cutoff<START)return blocked("INVALID_DECISION_CUTOFF");
 let parsed;
 try{parsed=Object.fromEntries(Object.entries(WIDTH).map(([tf,width])=>
  [tf,parseRows(input.frames?.[tf],width)]));}
 catch{return blocked("UNSAFE_OR_MALFORMED_CLOSED_ARCHIVE");}
 const counts=Object.fromEntries(Object.keys(WIDTH).map(tf=>[tf,parsed[tf].length]));
 const m15=parsed.M15.filter(x=>x._t+WIDTH.M15<=cutoff);
 let checked=0, skipped=0;
 const observations={BUY:0,SELL:0,NONE:0};
 // A fixed cutoff is applied BEFORE choosing the replay window. Adding
 // future candles cannot move its start or change any prior observation.
 for(const bar of m15.slice(-MAX_REPLAY)){
  const asOf=bar._t+WIDTH.M15;
  const frames=Object.fromEntries(Object.entries(WIDTH).map(([tf,width])=>
    [tf,suffix(parsed[tf],width,asOf)]));
  if(Object.values(frames).some(x=>x.length<MIN)||
     !parity(frames)){
   skipped++;continue;
  }
  const candidate=reviewFourStages({
   dataOrigin:"BIQUOTE_ARCHIVED_UNVERIFIED_NO_PAPER",
   snapshot:{asOfUTC:new Date(asOf).toISOString().replace(".000Z","Z"),
    frames,feeds:{},spread:null,risk:{killSwitch:true,activeTrades:0}}
  });
  if(candidate.signal!=="WAIT"||candidate.executable!==false||
     candidate.paperOrdersAllowed!==false||
     candidate.liveOrdersAllowed!==false||
     candidate.hypotheticalSyntheticPlan!==null||
     candidate.stages?.data?.status!=="GEOMETRY_ONLY"||
     candidate.stages?.analysis?.status!=="FROZEN_ENGINE_EVALUATED"){
   skipped++;continue;
  }
  const side=candidate.stages.analysis.technicalCandidate;
  if(!Object.hasOwn(observations,side)){skipped++;continue;}
  checked++;observations[side]++;
 }
 return {...safe,status:checked?"RETROSPECTIVE_WATCH_COUNTS_ONLY":"BLOCKED",
  blocker:checked?null:"NO_21_BAR_CONTIGUOUS_POINT_GEOMETRY",
  storedClosedCounts:counts,
  retrospectiveDecisionCount:checked,skippedDecisionCount:skipped,
  technicalWatchCounts:observations,
  noFutureCandlesUsed:true,replayOnlyNotPointInTime:true,
  explanation:"Final OHLC archive is retrospectively filtered by close time. Per-bar FIRST-SEEN times, broker quotes, rights and costs are missing; do not call this an untouched prospective test."};
}
module.exports={inspect,stamp,parseRows,suffix,parity};
if(require.main===module){
 try{
  let raw="";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data",chunk=>{raw+=chunk;if(raw.length>18000000){
   process.stderr.write("INPUT_TOO_LARGE\n");process.exit(2);}});
  process.stdin.on("end",()=>{
   const out=inspect(JSON.parse(raw));
   process.stdout.write(JSON.stringify(out)+"\n");
  });
 }catch(_){process.stdout.write(JSON.stringify(blocked("INVALID_REPLAY_INPUT"))+"\n");}
}
