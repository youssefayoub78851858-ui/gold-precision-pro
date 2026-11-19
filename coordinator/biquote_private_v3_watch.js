"use strict";
/**
 * Authenticated PERSONAL screen only: reuse the frozen V3 market-structure
 * candidate as a retrospective technical WATCH on observed, CLOSED BiQuote
 * candles. Never a market recommendation, paper order, risk plan or license.
 * Input is the already-read in-memory private chart. Zero network/disk.
 */
const {assess}=require("./v3_multitimeframe");
const WIDTH=Object.freeze({M15:900000,H1:3600000,H4:14400000});
const TF=["M15","H1","H4"],MIN=21;
const safe=(status,reason,extra={})=>({
 mode:"PRIVATE_FROZEN_V3_TECHNICAL_WATCH_ONLY",
 status,reason,signal:"WAIT",executable:false,tradeEligible:false,
 paperOrdersAllowed:false,liveOrdersAllowed:false,
 sourceRightsVerified:false,independentBrokerCalendarVerified:false,
 firstSeenAtDecisionVerified:false,brokerBidAskCostsVerified:false,
 independentMacroNewsGcOrderFlowVerified:false,
 forwardPerformanceProven:false,technicalCandidate:"NONE",
 watchLabel:"WAIT",entry:null,stopLoss:null,takeProfit:null,
 providerRequestsMade:0,brokerOrdersSent:0,paperOrdersSent:0,
 noHistoricalBackfillAssumed:true,retrospectiveOnly:true,
 ...extra
});
function parseTail(rows,width,asOf){
 if(!Array.isArray(rows)||rows.length<MIN||rows.length>48)
  return {rows:[],reason:"INSUFFICIENT_CLOSED_HISTORY"};
 let last=-Infinity,valid=[];
 for(const x of rows){
  const t=Date.parse(x?.time);
  if(typeof x?.time!=="string"||!Number.isFinite(t)||
     t%width!==0||t<=last||t+width>asOf)
   return {rows:[],reason:"INVALID_OR_UNCLOSED_CANDLE_TIME"};
  if(["open","high","low","close"].some(k=>
    typeof x[k]!=="number"||!Number.isFinite(x[k])||
    x[k]<=0||x[k]>=100000000)||
    x.low>Math.min(x.open,x.close)||
    x.high<Math.max(x.open,x.close))
   return {rows:[],reason:"INVALID_CLOSED_OHLC"};
  valid.push({datetime:x.time,open:x.open,high:x.high,low:x.low,close:x.close,t});
  last=t;
 }
 let start=valid.length-1;
 while(start>0&&valid[start].t-valid[start-1].t===width)start--;
 const tail=valid.slice(start);
 if(tail.length<MIN)return {rows:[],reason:"NOT_21_STRICTLY_CONTIGUOUS_CLOSED"};
 if(asOf-(last+width)>width)return {rows:[],reason:"LATEST_CLOSED_CANDLE_STALE"};
 return {rows:tail,reason:null};
}
function parity(whole,parts){
 if(parts.some(x=>!x))return false;
 const near=(a,b)=>Math.abs(a-b)<=Math.max(.00001,Math.abs(b)*1e-8);
 return near(whole.open,parts[0].open)&&
  near(whole.high,Math.max(...parts.map(x=>x.high)))&&
  near(whole.low,Math.min(...parts.map(x=>x.low)))&&
  near(whole.close,parts.at(-1).close);
}
function observe(input){
 if(input?.origin!=="AUTHENTICATED_PERSONAL_BIQUOTE_PRIVATE_CHART")
  return safe("BLOCKED","NOT_AUTHENTICATED_PERSONAL_CHART");
 if(input.priceBasis!=="MID_WITH_POSSIBLE_BID_SEED")
  return safe("BLOCKED","MIXED_OR_UNVERIFIED_PRICE_BASIS");
 const asOf=Date.parse(input.asOfUTC);
 if(typeof input.asOfUTC!=="string"||!Number.isFinite(asOf)||
    !input.asOfUTC.endsWith("Z"))
  return safe("BLOCKED","INVALID_AS_OF_UTC");
 const parsed={};
 for(const tf of TF){
  const x=parseTail(input.chart?.[tf],WIDTH[tf],asOf);
  if(x.reason)return safe("WAIT_DATA_INCOMPLETE",tf+"_"+x.reason);
  parsed[tf]=x.rows;
 }
 // The last closed H4, last closed H1, and H1's four M15 candles must
 // have been fully retained at the SAME observation; gaps and vendor
 // declared breaks CANNOT be bridged. Not all historical bars are proven
 // parity/first-seen by this check, so output stays research-only.
 const m15=new Map(parsed.M15.map(x=>[x.t,x]));
 const h1=new Map(parsed.H1.map(x=>[x.t,x]));
 const recentH1=parsed.H1.at(-1),recentH4=parsed.H4.at(-1);
 const partsH1=Array.from({length:4},(_,i)=>
  m15.get(recentH1.t+i*WIDTH.M15));
 const partsH4=Array.from({length:16},(_,i)=>
  m15.get(recentH4.t+i*WIDTH.M15));
 const hoursH4=Array.from({length:4},(_,i)=>
  h1.get(recentH4.t+i*WIDTH.H1));
 if(!parity(recentH1,partsH1)||!parity(recentH4,partsH4)||
    !parity(recentH4,hoursH4))
  return safe("WAIT_CROSS_FRAME_EVIDENCE","LAST_CLOSED_H1_H4_M15_PARITY_NOT_PROVEN");
 let x;
 try{x=assess(Object.fromEntries(TF.map(tf=>
  [tf,parsed[tf].map(({t,...bar})=>bar)])),input.asOfUTC);}
 catch{return safe("BLOCKED","FROZEN_RESEARCH_ENGINE_ERROR");}
 if(x?.signal!=="WAIT"||x?.executable!==false||
    !["BUY","SELL","NONE"].includes(x.candidate))
  return safe("BLOCKED","FROZEN_ENGINE_CONTRACT_UNEXPECTED");
 const candidate=x.candidate;
 return safe("TECHNICAL_WATCH_ONLY_NOT_TRADE_READY",
  candidate==="NONE"?"NO_ALIGNED_CLOSED_BAR_BOS":
    "FROZEN_V3_ALIGNED_CLOSED_BAR_BOS_NO_INDEPENDENT_CONFIRMATION",{
  technicalCandidate:candidate,
  watchLabel:candidate==="NONE"?"WAIT":"WATCH_"+candidate,
  eachFrameMinimumClosed:MIN,
  lastCrossFrameParityObserved:true
 });
}
module.exports={observe};
