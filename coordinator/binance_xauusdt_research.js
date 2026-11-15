'use strict';
// Research-only Binance USD-M XAUUSDT aggregated-trades intake. PURE and OFFLINE:
// no WebSocket, REST, credentials, persistence, orders, or upstream signal integration.
// XAUUSDT perpetual trades are NOT XAUUSD OTC/CFI prices or COMEX GC order flow.
const SYMBOL='XAUUSDT';
const MARKET_STREAM='wss://fstream.binance.com/market/ws/xauusdt@aggTrade';
const MAX_FUTURE_MS=10_000;
const MINUTE_MS=60_000;
const NY_CLOCK=new Intl.DateTimeFormat('en-US',{
 timeZone:'America/New_York',weekday:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});

function referenceHoursEstimate(timestampMs){
 if(!Number.isSafeInteger(timestampMs)||timestampMs<0)throw Error('INVALID_UTC_TIMESTAMP');
 const parts=Object.fromEntries(NY_CLOCK.formatToParts(timestampMs).filter(p=>p.type!=='literal').map(p=>[p.type,p.value]));
 const hour=Number(parts.hour),weekday=parts.weekday;
 if(weekday==='Sat'||(weekday==='Fri'&&hour>=17)||(weekday==='Sun'&&hour<18))return false;
 if(['Mon','Tue','Wed','Thu'].includes(weekday)&&hour===17)return false;
 // Only normal OTC reference hours; broker closures, holidays & maintenance NOT verified.
 return true;
}
function newState(){return {
 schemaVersion:1,source:'BINANCE_USDM_XAUUSDT_RESEARCH',symbol:SYMBOL,
 lastAggregateId:null,lastTimestampMs:null,firstTimestampMs:null,
 seen:0,duplicateCount:0,suspectMissingAggregates:0,invalidCount:0,
 onHoursVolumeBuy:0,onHoursVolumeSell:0,offHoursCount:0,
 minute:null,minuteSummaries:[],
 dataContinuityVerified:false,sourceRightsVerified:false,referenceCalendarVerified:false,
 blockers:['NO_INDEPENDENT_FEED_VERIFICATION','CONTINUITY_NOT_ANCHORED','REFERENCE_MARKET_CALENDAR_UNVERIFIED'],
 signal:'WAIT',executable:false,canTrade:false,paperOrdersAllowed:false,
 };}
function reject(state,reason){
 state.invalidCount++;
 if(!state.blockers.includes(reason))state.blockers.push(reason);
 state.dataContinuityVerified=false;
 return {accepted:false,reason,signal:'WAIT',executable:false};
}
function sumMinute(state){
 if(state.minute){
  // Keep bounded local summaries for inspection only; no durable storage here.
  state.minuteSummaries.push({...state.minute});
  if(state.minuteSummaries.length>120)state.minuteSummaries.shift();
 }
}
function intake(state,input,observedAtMs){
 if(!state||state.source!=='BINANCE_USDM_XAUUSDT_RESEARCH')throw Error('INVALID_RESEARCH_STATE');
 if(!Number.isSafeInteger(observedAtMs)||observedAtMs<0)return reject(state,'INVALID_OBSERVATION_TIME');
 let value;
 try{value=typeof input==='string'?JSON.parse(input):input;}catch{return reject(state,'INVALID_JSON');}
 const item=value?.data??value;
 if(!item||item.e!=='aggTrade'||item.s!==SYMBOL)return reject(state,'WRONG_EVENT_OR_SYMBOL');
 const id=item.a,tradeTime=item.T;
 if(!Number.isSafeInteger(id)||id<0||!Number.isSafeInteger(tradeTime)||tradeTime<0||
    tradeTime>observedAtMs+MAX_FUTURE_MS)return reject(state,'INVALID_EVENT_ID_OR_TIMESTAMP');
 const price=Number(item.p),qty=Number(item.q);
 if(!Number.isFinite(price)||price<=0||!Number.isFinite(qty)||qty<=0||typeof item.m!=='boolean')
  return reject(state,'INVALID_PRICE_QUANTITY_OR_SIDE');
 if(state.lastAggregateId!==null){
  if(id===state.lastAggregateId){state.duplicateCount++;return {accepted:false,reason:'DUPLICATE_AGGREGATE',signal:'WAIT',executable:false};}
  if(id<state.lastAggregateId)return reject(state,'OUT_OF_ORDER_AGGREGATE');
  if(id>state.lastAggregateId+1){
   // Aggregate IDs are indicative of possible missing events, not a proof of full trade coverage.
   state.suspectMissingAggregates+=id-state.lastAggregateId-1;
   if(!state.blockers.includes('POSSIBLE_AGGREGATE_GAP'))state.blockers.push('POSSIBLE_AGGREGATE_GAP');
  }
  if(tradeTime<state.lastTimestampMs)return reject(state,'TRADE_TIMESTAMP_REVERSED');
 }
 // Never claim a complete CVD just because a connection or first trade exists.
 if(state.firstTimestampMs===null)state.firstTimestampMs=tradeTime;
 state.lastAggregateId=id;state.lastTimestampMs=tradeTime;state.seen++;
 const withinReferenceHours=referenceHoursEstimate(tradeTime);
 if(!withinReferenceHours){state.offHoursCount++;return {accepted:true,referenceHours:false,signal:'WAIT',executable:false};}
 const minuteStart=Math.floor(tradeTime/MINUTE_MS)*MINUTE_MS;
 if(state.minute && minuteStart<state.minute.startMs)return reject(state,'MINUTE_TIME_REVERSED');
 if(!state.minute||state.minute.startMs!==minuteStart){sumMinute(state);state.minute={startMs:minuteStart,open:price,high:price,low:price,close:price,buyQty:0,sellQty:0,delta:0,count:0};}
 const m=state.minute;
 m.high=Math.max(m.high,price);m.low=Math.min(m.low,price);m.close=price;m.count++;
 if(item.m){m.sellQty+=qty;state.onHoursVolumeSell+=qty;}
 else{m.buyQty+=qty;state.onHoursVolumeBuy+=qty;}
 m.delta=m.buyQty-m.sellQty;
 return {accepted:true,referenceHours:true,signal:'WAIT',executable:false};
}
function status(state,observedAtMs){
 const last=state.lastTimestampMs;
 const fresh=Number.isSafeInteger(observedAtMs)&&last!==null&&observedAtMs>=last&&observedAtMs-last<=30_000;
 return {
 source:state.source,priceSource:'BINANCE_PERPETUAL_NOT_SPOT_XAUUSD',
 transport:'NOT_CONNECTED_BY_THIS_MODULE',observedAggregates:state.seen,
 duplicateCount:state.duplicateCount,suspectMissingAggregates:state.suspectMissingAggregates,
 offHoursCount:state.offHoursCount,lastTradeTimestampMs:last,feedFreshnessObserved:fresh,
 onHoursDeltaObserved:state.onHoursVolumeBuy-state.onHoursVolumeSell,
 minuteCount:state.minuteSummaries.length,
 // Fail closed pending LICENSE + independent calendar + seeded gap-free continuity.
 reliable:false,reason:state.blockers,
 signal:'WAIT',executable:false,researchEligible:false,paperOrdersAllowed:false,providerRequestsMade:0,
 };
}
module.exports={SYMBOL,MARKET_STREAM,referenceHoursEstimate,newState,intake,status};
