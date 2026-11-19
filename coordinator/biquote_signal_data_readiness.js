"use strict";
/*
 * Offline point-in-time XAUUSD signal DATA readiness, not a trading engine.
 * Runs only on caller-supplied sealed-archive snapshots. Never polls providers,
 * accesses a vault, changes V3, creates paper orders, or authorizes BUY/SELL.
 * First-seen timestamps are LOCAL receipts, never authenticated vendor times.
 */
const WIDTH=Object.freeze({M15:900000,H1:3600000,H4:14400000});
const {slotClosed:providerDeclaredClosedSlot}=require("./biquote_vendor_declared_session");
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
const FALSE=()=>({M15:false,H1:false,H4:false});
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
  legacyWithoutFirstSeen:ZERO(),firstSeenAfterDecision:ZERO(),
  contiguousObservedClosed:ZERO(),
  latestEligibleClosedObservedAtDecision:FALSE(),
  latestExpectedUTCGridClosedObservedAtDecision:FALSE(),
  technicalWarmupMissing:{M15:WARMUP,H1:WARMUP,H4:WARMUP},
  paperHistoryMissing:{M15:PAPER,H1:PAPER,H4:PAPER},
  warmupCrossFrameRequiredH4:WARMUP,warmupCrossFrameMatchedH4:0,
  warmupCrossFrameFullyVerified:false,
  warmupCrossFrameProviderPauseAffectedH4:0,
  warmupCrossFrameUnexplainedCoverageH4:0,
  warmupCrossFramePriceMismatchH4:0,
  warmupCrossFrameProviderPauseNotBrokerVerified:true,
  localTimingAndParityCheck:"NOT_PROVEN",localGeometryObserved:false,...extra};
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
// The latest H4 alone is insufficient: EMA/RSI warmup can consume older
// H4 bars whose H1/M15 constituents were missing or revised. For the
// last 21 locally-received consecutive H4 candles, prove that all 16
// M15 and four H1 members were RECEIVED before decision and OHLC agree.
// This remains local equality, not independent vendor/execution evidence.
function warmupCrossFrameParity(frames){
 const h4=contiguous(frames.H4,"H4").slice(-WARMUP);
 if(h4.length!==WARMUP)return {matched:0,proven:false,
   declaredPauseAffected:0,unexplainedCoverage:0,priceMismatch:0};
 const m15=new Map(frames.M15.map(b=>[b.t,b]));
 const h1=new Map(frames.H1.map(b=>[b.t,b]));
 const matches=(whole,members)=>{
  if(members.some(x=>!x))return false;
  return equalPrice(whole.open,members[0].open)&&
   equalPrice(whole.high,Math.max(...members.map(x=>x.high)))&&
   equalPrice(whole.low,Math.min(...members.map(x=>x.low)))&&
   equalPrice(whole.close,members.at(-1).close);
 };
 let matched=0,declaredPauseAffected=0,unexplainedCoverage=0,
     priceMismatch=0;
 for(const bar of h4){
  const quarters=Array.from({length:16},(_,i)=>
   m15.get(bar.t+i*WIDTH.M15));
  const hours=Array.from({length:4},(_,i)=>
   h1.get(bar.t+i*WIDTH.H1));
  const missingSlots=[];
  quarters.forEach((q,i)=>{
   if(!q)missingSlots.push({t:bar.t+i*WIDTH.M15,width:WIDTH.M15});
  });
  hours.forEach((h,i)=>{
   if(!h)missingSlots.push({t:bar.t+i*WIDTH.H1,width:WIDTH.H1});
  });
  if(missingSlots.length){
   // A support-declared November trading break can explain missing
   // constituents. It NEVER justifies bridging or claiming OHLC parity.
   // A missing slot outside that exact bounded declaration remains unknown.
   if(missingSlots.every(x=>providerDeclaredClosedSlot(x.t,x.width)===true))
    declaredPauseAffected++;
   else unexplainedCoverage++;
   continue;
  }
  if(!matches(bar,quarters)||!matches(bar,hours)){
   priceMismatch++;
   continue;
  }
  let hoursMatch=true;
  for(const hour of hours){
   const hourMembers=Array.from({length:4},(_,i)=>
    m15.get(hour.t+i*WIDTH.M15));
   if(!matches(hour,hourMembers)){hoursMatch=false;break;}
  }
  if(hoursMatch)matched++;
  else priceMismatch++;
 }
 return {matched,declaredPauseAffected,unexplainedCoverage,
         priceMismatch,proven:matched===WARMUP};
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
 const available={},observed={},unknown={},afterDecision={},tail={},warm={},paper={},lastAge={};
 const latestEligibleObserved={},latestGridObserved={};
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
  let previous=-Infinity,knownCount=0,lateCount=0;
  for(const bar of bars){
   const raw=map[bar.datetime];
   if(raw===undefined)continue;
   const t=utc(raw);
   if(!Number.isFinite(t)||t<bar.t+width||t<previous)
    return base("BLOCKED",{storedClosedCounts:counts,
     blockers:[...FIXED,"INVALID_OR_NONMONOTONIC_"+tf+"_RECEIPT"]});
   previous=t;knownCount++;
   if(t<=asOf&&bar.t+width<=asOf)known.push(bar);
   else lateCount++;
  }
  available[tf]=known;
  observed[tf]=known.length;
  unknown[tf]=bars.length-knownCount;
  afterDecision[tf]=lateCount;
  tail[tf]=contiguous(known,tf).length;
  warm[tf]=Math.max(0,WARMUP-tail[tf]);
  paper[tf]=Math.max(0,PAPER-tail[tf]);
  const last=known.at(-1);
  // An older H4 can be fresh enough (<5h) and satisfy 21-bar warmup
  // while a *newer already closed* H4 has an UNKNOWN/FUTURE receipt.
  // Never present that earlier H4 as the latest closed at decision time.
  const latestClosed=bars.filter(b=>b.t+width<=asOf).at(-1);
  latestEligibleObserved[tf]=!!latestClosed&&!!last&&
   latestClosed.t===last.t;
  // UTC aligned EXPECTED time slot is a conservative safeguard only.
  // When a closed slot is absent at the decision time, older H4 can still
  // look fresh (<5h) and pass 21-bar warmup. We must not grant local
  // geometry readiness from that stale slot. During legitimate broker
  // breaks/DST uncertainty, fail closed to WAIT, never invent a flat bar.
  const expectedUTCSlot=Math.floor(asOf/width)*width-width;
  latestGridObserved[tf]=!!last&&last.t===expectedUTCSlot;
  lastAge[tf]=last?asOf-(last.t+width):null;
 }
 const blockers=[...FIXED];
 for(const tf of Object.keys(WIDTH)){
  if(warm[tf]>0)blockers.push(tf+"_INSUFFICIENT_POINT_IN_TIME_WARMUP");
  if(paper[tf]>0)blockers.push(tf+"_INSUFFICIENT_PAPER_HISTORY");
  if(lastAge[tf]===null||lastAge[tf]>MAX_AGE[tf])
   blockers.push(tf+"_CLOSED_CANDLE_STALE_OR_UNOBSERVED");
  if(unknown[tf]>0)blockers.push(tf+"_LEGACY_UNTIMED_BARS_EXCLUDED");
  if(afterDecision[tf]>0)blockers.push(tf+"_FUTURE_RECEIPTS_EXCLUDED_FROM_DECISION");
  if(!latestEligibleObserved[tf])
   blockers.push(tf+"_LATEST_ELIGIBLE_CLOSED_BAR_NOT_OBSERVED_AT_DECISION");
  if(!latestGridObserved[tf])
   blockers.push(tf+"_EXPECTED_UTC_CLOSED_SLOT_NOT_OBSERVED");
 }
 const parity=latestParity(available);
 const warmupParity=warmupCrossFrameParity(available);
 if(!parity)blockers.push("LATEST_CLOSED_M15_H1_H4_OHLC_PARITY_UNPROVEN");
 if(!warmupParity.proven)
  blockers.push("H4_21_CLOSED_BARS_M15_H1_CROSS_FRAME_PARITY_UNPROVEN");
 if(warmupParity.declaredPauseAffected>0)
  blockers.push("H4_M15_COVERAGE_ABSENT_WITHIN_BIQUOTE_DECLARED_PAUSE_NOT_PROVEN");
 if(warmupParity.unexplainedCoverage>0)
  blockers.push("H4_M15_COVERAGE_MISSING_OUTSIDE_DECLARED_PAUSE");
 if(warmupParity.priceMismatch>0)
  blockers.push("H4_M15_H1_WARMUP_OHLC_PRICE_CONFLICT");
 const localReady=Object.values(warm).every(n=>n===0)&&
  Object.values(latestEligibleObserved).every(Boolean)&&
  Object.values(latestGridObserved).every(Boolean)&&
  Object.values(lastAge).every((n,i)=>Number.isFinite(n)&&
   n>=0&&n<=MAX_AGE[Object.keys(WIDTH)[i]])&&parity&&warmupParity.proven;
 return base(localReady?"LOCAL_GEOMETRY_ONLY_NOT_TRADE_READY":"INSUFFICIENT_EVIDENCE",{
  asOfUTC:new Date(asOf).toISOString().replace(".000Z","Z"),
  storedClosedCounts:counts,observedAtDecision:observed,
  legacyWithoutFirstSeen:unknown,firstSeenAfterDecision:afterDecision,
  contiguousObservedClosed:tail,
  latestEligibleClosedObservedAtDecision:latestEligibleObserved,
  latestExpectedUTCGridClosedObservedAtDecision:latestGridObserved,
  technicalWarmupMissing:warm,paperHistoryMissing:paper,
  warmupCrossFrameMatchedH4:warmupParity.matched,
  warmupCrossFrameFullyVerified:warmupParity.proven,
  warmupCrossFrameProviderPauseAffectedH4:warmupParity.declaredPauseAffected,
  warmupCrossFrameUnexplainedCoverageH4:warmupParity.unexplainedCoverage,
  warmupCrossFramePriceMismatchH4:warmupParity.priceMismatch,
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
