'use strict';
// Offline FCLite historical BID/ASK getter-shape audit only. No SDK, network or orders.
// Documentation: https://www.fxcm.com/public-docs/fclite/trading/prices/get_historical_prices_for_an_instrument.html
const FRAMES=Object.freeze({M15:900000,H1:3600000,H4:14400000});
const FIELDS=['Open','High','Low','Close'];
const REQUIRED=['getCount','getDate','isBar',...FIELDS.flatMap(x=>['getBid'+x,'getAsk'+x])];
function utc(v){
 if(v instanceof Date){const t=v.getTime();if(!Number.isFinite(t))throw Error('INVALID_UTC_TIME');return t;}

 if(typeof v!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$/.test(v))throw Error('UTC_ISO_Z_REQUIRED');
 const t=Date.parse(v);if(!Number.isFinite(t)||new Date(t).toISOString().slice(0,19)!==v.slice(0,19))throw Error('INVALID_UTC_TIME');
 return t;
}
function responseResult(count,issues){
 return {provider:'FXCM',source:'FCLITE_NODE_HISTORICAL_GETTERS',status:'WAIT_FXCM_FCLITE_EVIDENCE',
  signal:'WAIT',executable:false,researchEligible:false,paperOrdersAllowed:false,engineStatus:'NOT_INVOKED',
  structurallyValid:issues.length===0,closedCandlesInspected:count,sourceRequestsMade:0,ordersSent:0,
  sdkLoaded:false,credentialsRead:false,sourceRightsVerified:false,independentCalendarVerified:false,
  finalBarStatusVerified:false,liveQuoteHistoryParityVerified:false,
  blockingReasons:[...issues,'FXCM_CLOUD_EULA_AND_DEMO_READ_ONLY_ENTITLEMENT_NOT_VERIFIED',
   'FXCM_REAL_XAUUSD_BID_ASK_HISTORY_AND_LIVE_QUOTES_NOT_TESTED',
   'FXCM_INDEPENDENT_SESSION_FINALITY_AND_CLOCK_NOT_VERIFIED',
   'FXCM_FCLITE_NODE_SDK_INSTALL_ON_REVIEW_IMAGE_NOT_TESTED']};
}
function auditFcliteHistory(history,{interval='M15',asOfUTC,symbol='XAU/USD'}={}){
 const issues=[];let count=0;
 try {
  if(symbol!=='XAU/USD')throw Error('WRONG_INSTRUMENT');
  const width=FRAMES[interval];if(!width)throw Error('UNSUPPORTED_INTERVAL');
  const now=utc(asOfUTC);
  if(!history||REQUIRED.some(k=>typeof history[k]!=='function'))throw Error('BID_ASK_HISTORY_GETTERS_MISSING');
  if(history.isBar()!==true)throw Error('TICK_HISTORY_IS_NOT_CANDLE_HISTORY');
 const n=history.getCount();if(!Number.isInteger(n)||n<1||n>2048)throw Error('INVALID_HISTORY_COUNT');
  let previous=-Infinity;
  for(let i=0;i<n;i++){
   const t=utc(history.getDate(i));
   if(t<=previous||t%width)throw Error('DUPLICATE_UNORDERED_OR_UNALIGNED');
   if(t+width>now)throw Error('INCOMPLETE_OR_FUTURE_CANDLE');
   const sides={bid:{},ask:{}};
   for(const k of FIELDS){
    const bid=history['getBid'+k](i),ask=history['getAsk'+k](i);
    if(typeof bid!=='number'||typeof ask!=='number'||!Number.isFinite(bid)||!Number.isFinite(ask)||bid<=0||ask<bid)throw Error('INVALID_OR_CROSSED_BID_ASK');
    sides.bid[k.toLowerCase()]=bid;sides.ask[k.toLowerCase()]=ask;
   }
   for(const x of Object.values(sides))if(x.high<Math.max(x.open,x.close,x.low)||x.low>Math.min(x.open,x.close,x.high))throw Error('INVALID_OHLC_EXTREMA');
   count++;previous=t;
  }
 }catch(e){issues.push(e.message||'MALFORMED_LOCAL_HISTORY');}
 return responseResult(count,issues);
}

function extractValidatedRows(history,interval,asOfUTC,symbol){
 const result=auditFcliteHistory(history,{interval,asOfUTC,symbol});
 if(!result.structurallyValid)throw Error(result.blockingReasons[0]);
 const bars=[];
 for(let i=0;i<history.getCount();i++){
  const raw=history.getDate(i),stamp=raw instanceof Date?raw.getTime():Date.parse(raw);
  const bid={},ask={};
  for(const k of FIELDS){
   bid[k.toLowerCase()]=history['getBid'+k](i);
   ask[k.toLowerCase()]=history['getAsk'+k](i);
  }
  bars.push({openTime:new Date(stamp).toISOString(),bid,ask});
 }
 return bars;
}
function closeTo(a,b){return Math.abs(a-b)<=Math.max(1e-5,Math.abs(a)*1e-8,Math.abs(b)*1e-8);}
function compareBidAskAggregates(m15,higher,width){
 const count=width/FRAMES.M15;
 const indexed=new Map(m15.map(bar=>[Date.parse(bar.openTime),bar]));
 const supplied=new Map(higher.map(bar=>[Date.parse(bar.openTime),bar]));
 const complete=new Map();
 for(const stamp of indexed.keys()){
  const start=Math.floor(stamp/width)*width;
  if(complete.has(start))continue;
  const group=Array.from({length:count},(_,k)=>indexed.get(start+k*FRAMES.M15));
  if(group.some(x=>x===undefined))continue;
  complete.set(start,group);
 }
 for(const [stamp] of supplied){
  const members=Array.from({length:count},(_,k)=>indexed.get(stamp+k*FRAMES.M15));
  if(members.some(x=>x!==undefined)&&members.some(x=>x===undefined))throw Error('PARTIAL_CROSS_TIMEFRAME_COVERAGE');
 }
 for(const [stamp,group] of complete){
  const actual=supplied.get(stamp);
  if(!actual)throw Error('MISSING_CROSS_TIMEFRAME_AGGREGATE');
  for(const side of ['bid','ask']){
   const expected={
    open:group[0][side].open,
    high:Math.max(...group.map(x=>x[side].high)),
    low:Math.min(...group.map(x=>x[side].low)),
    close:group.at(-1)[side].close
   };
   for(const key of ['open','high','low','close'])
    if(!closeTo(actual[side][key],expected[key]))throw Error('CROSS_TIMEFRAME_BID_ASK_OHLC_MISMATCH');
  }
 }
}
function stageFcliteBundle(histories,{asOfUTC,symbol='XAU/USD'}={}){
 const issues=[],counts={M15:0,H1:0,H4:0};let frames={};
 try {
  if(symbol!=='XAU/USD')throw Error('WRONG_INSTRUMENT');
  if(!histories||typeof histories!=='object'||Array.isArray(histories)||Object.keys(histories).sort().join(',')!=='H1,H4,M15')throw Error('THREE_FRAMES_REQUIRED');
  for(const frame of Object.keys(FRAMES)){
   frames[frame]=extractValidatedRows(histories[frame],frame,asOfUTC,symbol);
   counts[frame]=frames[frame].length;
  }
  compareBidAskAggregates(frames.M15,frames.H1,FRAMES.H1);
  compareBidAskAggregates(frames.M15,frames.H4,FRAMES.H4);
 }catch(e){issues.push(e.message||'INVALID_MULTIFRAME_HISTORY');frames={};}
 return {
  ...responseResult(counts.M15,issues),
  closedBarCounts:counts,
  geometricWarmupOnly:Object.values(counts).every(n=>n>=50),
  dataOrigin:'UNVERIFIED_FXCM_FCLITE_OFFLINE_SAMPLE',
  quarantinedBidAskFrames:frames,
  approvedForResearch:false,readyForPaper:false,
 };
}

module.exports={auditFcliteHistory,stageFcliteBundle};
if(require.main===module)console.log(JSON.stringify(responseResult(0,['NO_CAPTURE_SUPPLIED']),null,2));
