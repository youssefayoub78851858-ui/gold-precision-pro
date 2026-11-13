'use strict';
// Offline FCLite historical BID/ASK getter-shape audit only. No SDK, network or orders.
// Documentation: https://www.fxcm.com/public-docs/fclite/trading/prices/get_historical_prices_for_an_instrument.html
const FRAMES=Object.freeze({M15:900000,H1:3600000,H4:14400000});
const FIELDS=['Open','High','Low','Close'];
const REQUIRED=['getCount','getDate',...FIELDS.flatMap(x=>['getBid'+x,'getAsk'+x])];
function utc(v){
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
module.exports={auditFcliteHistory};
if(require.main===module)console.log(JSON.stringify(responseResult(0,['NO_CAPTURE_SUPPLIED']),null,2));
