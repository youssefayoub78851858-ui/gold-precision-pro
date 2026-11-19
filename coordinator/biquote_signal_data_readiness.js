"use strict";
/*
 * Offline point-in-time XAUUSD signal DATA readiness, not a trading engine.
 * Runs only on caller-supplied sealed-archive snapshots. Never polls providers,
 * accesses a vault, changes V3, creates paper orders, or authorizes BUY/SELL.
 * First-seen timestamps are LOCAL receipts, never authenticated vendor times.
 */
const WIDTH=Object.freeze({M15:900000,H1:3600000,H4:14400000});
const WARMUP=21,PAPER=50,MAX_BARS=45000;
const MAX_AGE=Object.freeze({M15:1200000,H1:4500000,H4:18000000});
const START=Date.parse("2026-11-18T00:00:00Z");
const FIXED=Object.freeze([
 "UPSTREAM_BROKER_DATA_RIGHTS_UNVERIFIED",
 "BROKER_SESSION_CALENDAR_UNVERIFIED",
 "HISTORICAL_EXECUTION_BID_ASK_AND_COSTS_UNVERIFIED",
 "MACRO_ORDERFLOW_AND_NEWS_AVAILABILITY_UNVERIFIED",
 "UNTOUCHED_AFTER_COST_HOLDOUT_NOT_VALIDATED"
]);
const TIME=/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/;
const ZERO=()=>({M15:0,H1:0,H4:0});
function utc(s){
 if(typeof s!=="string"||!TIME.test(s))return NaN;
 const n=Date.parse(s);
 return Number.isFinite(n)&&new Date(n).toISOString().slice(0,19)===s.slice(0,19)?n:NaN;
}
function base(status,extra={}){
 return {mode:"BIQUOTE_LOCAL_POINT_IN_TIME_DATA_GATE_V1",
  status,signal:"WAIT",researchCandidate:"NONE",executable:false,
  tradeEligible:false,paperOrdersAllowed:false,liveOrdersAllowed:false,
  brokerOrdersSent:0,providerRequestsMade:0,sourceRightsVerified:false,
  brokerSessionCalendarVerified:false,independentAvailabilityVerified:false,
  brokerCostsVerified:false,profitabilityProven:false,
  minTechnicalBarsPerFrame:WARMUP,minPaperBarsPerFrame:PAPER,
  blockers:[...FIXED],storedClosedCounts:ZERO(),observedAtDecision:ZERO(),
  legacyWithoutFirstSeen:ZERO(),contiguousObservedClosed:ZERO(),
  technicalWarmupMissing:{M15:WARMUP,H1:WARMUP,H4:WARMUP},
  paperHistoryMissing:{M15:PAPER,H1:PAPER,H4:PAPER},
  localTimingAndParityCheck:"NOT_PROVEN",...extra};
}
function parseRows(rows,tf){
 const width=WIDTH[tf];
 if(!Array.isArray(rows)||rows.length>MAX_BARS)throw Error("BAD_FRAME");
 let prev=-Infinity;
 return rows.map(bar=>{
  const t=utc(bar?.datetime);
  if(!Number.isFinite(t)||t<START||t%width!==0||t<=prev)
   throw Error("BAD_CLOSED_BAR_TIME");
  prev=t;
  const {open,high,low,close}=bar;
  if(![open,high,low,close].every(v=>typeof v==="number"&&Number.isFinite(v)&&v>0&&v<1e8)||
     low>Math.min(open,close)||high<Math.max(open,close))
   throw Error("BAD_PRICE_GEOMETRY");
  return {t,open,high,low,close,datetime:bar.datetime};
 });
}
function contiguous(rows,tf){
 const w=WIDTH[tf];
 if(!rows.length)return [];
 let first=rows.length-1;
 while(first>0&&rows[first].t-rows[first-1].t===w)first--;
 return rows.slice(first);
}
function equalPrice(a,b){
 return Math.abs(a-b)<=Math.max(0.00001,Math.abs(b)*1e-8);
}
function latestParity(frames){
 const map=new Map(frames.M15.map(b=>[b.t,b]));
 for(const [tf,n] of [["H1",4],["H4",16]]){
  const last=frames[tf].at(-1);
  if(!last)return false;
  const parts=Array.from({length:n},(_,i)=>map.get(last.t+i*WIDTH.M15));
  if(parts.some(v=>!v))return false;
  if(!equalPrice(parts[0].open,last.open)||
     !equalPrice(Math.max(...parts.map(b=>b.high)),last.high)||
     !equalPrice(Math.min(...parts.map(b=>b.low)),last.low)||
     !equalPrice(parts.at(-1).close,last.close))return false;
 }
 return true;
}
function assess(input){
 const origin=input?.dataOrigin;
 if(!["BIQUOTE_ARCHIVED_UNVERIFIED_NO_PAPER","SYNTHETIC_TEST_ONLY"].includes(origin))
  return base("BLOCKED",{blockers:[...FIXED,"UNKNOWN_ARCHIVE_ORIGIN"]});
 const asOf=utc(input?.asOfUTC);
 if(!Number.isFinite(asOf)||asOf<START)
  return base("BLOCKED",{blockers:[...FIXED,"INVALID_DECISION_TIME"]});
 let frames;
 try{
  frames=Object.fromEntries(Object.keys(WIDTH).map(tf=>
   [tf,parseRows(input?.frames?.[tf],tf)]));
 }catch(_){
  return base("BLOCKED",{blockers:[...FIXED,"INVALID_SEALED_CANDLES"]});
 }
 const counts=Object.fromEntries(Object.keys(WIDTH).map(tf=>[tf,frames[tf].length]));
 const receipts=input?.firstObservedClosedUTC;
 if(receipts===undefined){
  return base("RECEIPTS_UNAVAILABLE",{storedClosedCounts:counts,
   legacyWithoutFirstSeen:counts,blockers:[...FIXED,"LEGACY_FIRST_SEEN_TIMES_UNKNOWN"]});
 }
 if(!receipts||typeof receipts!=="object"||Array.isArray(receipts)||
   Object.keys(receipts).sort().join(",")!=="H1,H4,M15")
  return base("BLOCKED",{storedClosedCounts:counts,
   blockers:[...FIXED,"INVALID_RECEIPT_MAP"]});
 const available={},observed={},unknown={},tail={},warm={},paper={},lastAge={};
 for(const tf of Object.keys(WIDTH)){
  const map=receipts[tf],bars=frames[tf],width=WIDTH[tf];
  if(!map||typeof map!=="object"||Array.isArray(map))
   return base("BLOCKED",{storedClosedCounts:counts,
    blockers:[...FIXED,"INVALID_"+tf+"_RECEIPTS"]});
  const validKeys=new Set(bars.map(b=>b.datetime));
  if(Object.keys(map).some(k=>!validKeys.has(k)))
   return base("BLOCKED",{storedClosedCounts:counts,
    blockers:[...FIXED,"RECEIPT_UNKNOWN_"+tf+"_BAR"]});
  const known=[];
  let previous=-Infinity,knownCount=0;
  for(const bar of bars){
   const raw=map[bar.datetime];
   if(raw===undefined)continue;
   const t=utc(raw);
   if(!Number.isFinite(t)||t<bar.t+width||t<previous)
    return base("BLOCKED",{storedClosedCounts:counts,
     blockers:[...FIXED,"INVALID_OR_NONMONOTONIC_"+tf+"_RECEIPT"]});
   previous=t;knownCount++;
   if(t<=asOf&&bar.t+width<=asOf)known.push(bar);
  }
  available[tf]=known;
  observed[tf]=known.length;
  unknown[tf]=bars.length-knownCount;
  tail[tf]=contiguous(known,tf).length;
  warm[tf]=Math.max(0,WARMUP-tail[tf]);
  paper[tf]=Math.max(0,PAPER-tail[tf]);
  const last=known.at(-1);
  lastAge[tf]=last?asOf-(last.t+width):null;
 }
 const blockers=[...FIXED];
 for(const tf of Object.keys(WIDTH)){
  if(warm[tf]>0)blockers.push(tf+"_INSUFFICIENT_POINT_IN_TIME_WARMUP");
  if(paper[tf]>0)blockers.push(tf+"_INSUFFICIENT_PAPER_HISTORY");
  if(lastAge[tf]===null||lastAge[tf]>MAX_AGE[tf])
   blockers.push(tf+"_CLOSED_CANDLE_STALE_OR_UNOBSERVED");
  if(unknown[tf]>0)blockers.push(tf+"_LEGACY_UNTIMED_BARS_EXCLUDED");
 }
 const parity=latestParity(available);
 if(!parity)blockers.push("LATEST_CLOSED_M15_H1_H4_OHLC_PARITY_UNPROVEN");
 const localReady=Object.values(warm).every(n=>n===0)&&
  Object.values(lastAge).every((n,i)=>Number.isFinite(n)&&
   n>=0&&n<=MAX_AGE[Object.keys(WIDTH)[i]])&&parity;
 return base(localReady?"LOCAL_GEOMETRY_ONLY_NOT_TRADE_READY":"INSUFFICIENT_EVIDENCE",{
  asOfUTC:new Date(asOf).toISOString().replace(".000Z","Z"),
  storedClosedCounts:counts,observedAtDecision:observed,
  legacyWithoutFirstSeen:unknown,contiguousObservedClosed:tail,
  technicalWarmupMissing:warm,paperHistoryMissing:paper,
  localTimingAndParityCheck:localReady?"LOCAL_ONLY_NOT_INDEPENDENT":"NOT_PROVEN",
  blockers,
  // This is never a signal-admission flag: independent upstream evidence is missing.
  localGeometryObserved:localReady});
}
module.exports={assess,utc};
if(require.main===module){
 try{
  let raw="";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data",v=>{raw+=v;if(raw.length>18000000)throw Error("TOO_LARGE");});
  process.stdin.on("end",()=>{
   try{process.stdout.write(JSON.stringify(assess(JSON.parse(raw)))+"\n");}
   catch(_){process.stdout.write(JSON.stringify(base("BLOCKED"))+"\n");}
  });
 }catch(_){process.stdout.write(JSON.stringify(base("BLOCKED"))+"\n");}
}
