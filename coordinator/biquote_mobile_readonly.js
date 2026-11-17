"use strict";
/**
 * BiQuote personal REVIEW screen observation (no trading).
 * Public response contains DERIVED quality & directional descriptions only.
 * Raw BID/ASK is available only after an independent private coordinator viewer
 * authentication succeeds; no raw candle list is ever returned.
 * No vendor keys, sessions, orders, broker endpoints, persisted history,
 * hidden retries, interval loops or permission inferred from upstream JSON.
 */
const {analyzeChart}=require("./biquote_private_structure");
const URLS=Object.freeze({
 quote:"https://biquote.io/api/XAUUSD?allowStale=false",
 M15:"https://biquote.io/api/XAUUSD/ohlc?interval=15m&limit=200",
 H1:"https://biquote.io/api/XAUUSD/ohlc?interval=1h&limit=180",
 H4:"https://biquote.io/api/XAUUSD/ohlc?interval=4h&limit=180"
});
const META=Object.freeze({M15:{name:"15m",width:900000},H1:{name:"1h",width:3600000},H4:{name:"4h",width:14400000}});
const FRAMES=Object.freeze(["M15","H1","H4"]);
const MAX_BYTES=1000000;
const MAX_AGE_MS=30000;
const CACHE_MS=90000;
// A 90-second successful-response cache must NEVER override the independent
// 30-second market-quote freshness gate. Refresh at 20s, leaving headroom
// for HTTP latency; still fail closed if the new quote cannot be verified.
const MAX_REUSABLE_QUOTE_AGE_MS=20000;
const WAIT=Object.freeze({signal:"WAIT",executable:false,researchEligible:false,orderEndpointsCalled:false,paperOrdersAllowed:false,tradePlanExecutable:false});
let cache=null,expires=0,pending=null;

function utcMs(value){
 if(typeof value!=="string"||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value))throw Error("INVALID_UTC");
 const ms=Date.parse(value);if(!Number.isFinite(ms))throw Error("INVALID_UTC");
 return ms;
}
function price(n){return typeof n==="number"&&Number.isFinite(n)&&n>0}
function finite(n){return typeof n==="number"&&Number.isFinite(n)}
function ema(rows,period){
 const values=rows.map(x=>x.close);
 if(values.length<period)return null;
 let current=values.slice(0,period).reduce((a,b)=>a+b,0)/period;
 for(let i=period;i<values.length;i++)current=current*(1-2/(period+1))+values[i]*2/(period+1);
 return current;
}
function frame(envelope,tf,asOf){
 const {width,name}=META[tf];
 if(!envelope||envelope.symbol!=="XAUUSD"||envelope.interval!==name
   ||!Array.isArray(envelope.bars)||!envelope.bars.length||envelope.bars.length>1000)
  throw Error(tf+"_BAD_ENVELOPE");
 const closed=[],byTime=new Map();let prev=Infinity;
 for(let i=0;i<envelope.bars.length;i++){
  const b=envelope.bars[i];
  if(!b||typeof b.isOpen!=="boolean")throw Error(tf+"_OPEN_FLAG_INVALID");
  const stamp=utcMs(b.openTime);
  if(stamp>=prev||stamp%width!==0||stamp>asOf)throw Error(tf+"_TIME_INVALID");
  prev=stamp;
  if(!["open","high","low","close"].every(k=>price(b[k]))
   ||b.high<Math.max(b.open,b.low,b.close)
   ||b.low>Math.min(b.open,b.high,b.close)
   ||!Number.isInteger(b.tickVolume)||b.tickVolume<0||!finite(b.volume)||b.volume<0)
   throw Error(tf+"_OHLC_INVALID");
  if(b.isOpen){
   if(i!==0)throw Error(tf+"_OPEN_CANDLE_NOT_FIRST");
   continue;
  }
  if(stamp+width>asOf)throw Error(tf+"_UNCLOSED_CANDLE");
  const row={t:stamp,open:b.open,high:b.high,low:b.low,close:b.close};
  closed.push(row);byTime.set(stamp,row);
 }
 if(closed.length<50)throw Error(tf+"_INSUFFICIENT_CLOSED");
 closed.reverse();
 const e20=ema(closed,20),e50=ema(closed,50);
 const last=closed[closed.length-1],prevClose=closed[closed.length-2];
 const direction=e20>e50&&last.close>e20?"UP":e20<e50&&last.close<e20?"DOWN":"MIXED";
 let gridGaps=0;
 for(let i=1;i<closed.length;i++)if(closed[i].t-closed[i-1].t!==width)gridGaps++;
 return {all:closed,map:byTime,view:{closedCount:closed.length,
    lastClosedUTC:new Date(last.t+width).toISOString(),priceBasis:"MID_WITH_POSSIBLE_BID_SEED",
    descriptiveTrend:direction,ema20AboveEma50:e20>e50,
    latestClosedChange:prevClose?last.close-prevClose.close:null,
    unclassifiedCalendarGaps:gridGaps}};
}
function overlap(m15,higher,width){
 const low=m15.all[0].t,high=m15.all[m15.all.length-1].t,n=width/900000;
 let matched=0,mismatched=0,partial=0,outside=0;const fields=["open","high","low","close"];
 for(const row of higher.all){
  if(row.t>high||row.t+(n-1)*900000<low){outside++;continue;}
  if(row.t<low||row.t+(n-1)*900000>high){outside++;continue;}
  const all=Array.from({length:n},(_,i)=>m15.map.get(row.t+i*900000));
  if(all.some(x=>!x)){partial++;continue;}
  const expected={open:all[0].open,high:Math.max(...all.map(x=>x.high)),
    low:Math.min(...all.map(x=>x.low)),close:all[n-1].close};
  if(fields.some(k=>Math.abs(expected[k]-row[k])>Math.max(0.00001,Math.abs(row[k])*1e-8)))mismatched++;
  else matched++;
 }
 return {completeMatches:matched,completeMismatches:mismatched,
    incompleteM15Groups:partial,outsideRetentionWindow:outside};
}
async function getJSON(url,fetchFn){
 const response=await fetchFn(url,{method:"GET",
  headers:{Accept:"application/json","User-Agent":"GoldPrecisionPro-ReadOnly-Mobile/1.0"},
  redirect:"error",credentials:"omit",cache:"no-store",signal:AbortSignal.timeout(9000)});
 if(!response||response.status!==200)throw Error("PUBLIC_HTTP_UNAVAILABLE");
 if(Number(response.headers?.get?.("content-length")||0)>MAX_BYTES)throw Error("PROVIDER_RESPONSE_TOO_LARGE");
 const raw=await response.text();
 if(raw.length>MAX_BYTES)throw Error("PROVIDER_RESPONSE_TOO_LARGE");
 const data=JSON.parse(raw);
 if(!data||Array.isArray(data)||typeof data!=="object")throw Error("PUBLIC_JSON_INVALID");
 return data;
}
async function collect(fetchFn,nowMs){
 // Read the public quote first. An explicit provider-closed state is not
 // a feed failure and must not trigger three unnecessary OHLC requests.
 const quote=await getJSON(URLS.quote,fetchFn);
 if(quote.symbol==="XAUUSD" && quote.marketState==="closed")
   throw Error("PROVIDER_REPORTED_CLOSED");
 if(quote.marketState!=="open")throw Error("MARKET_STATE_UNCONFIRMED");
 const [m15,h1,h4]=await Promise.all(FRAMES.map(tf=>getJSON(URLS[tf],fetchFn)));
 const asOf=nowMs();
 if(quote.symbol!=="XAUUSD"||!price(quote.bid)||!price(quote.ask)||quote.ask<quote.bid
    ||typeof quote.stale!=="boolean"||quote.marketState!=="open")throw Error("QUOTE_MARKET_OR_PRICE_INVALID");
 if(quote.mid!==undefined&&(!price(quote.mid)||Math.abs(quote.mid-(quote.bid+quote.ask)/2)>0.0001))throw Error("MID_NOT_PARITY");
 if(quote.spread!==undefined&&(!finite(quote.spread)||Math.abs(quote.spread-(quote.ask-quote.bid))>0.0001))throw Error("SPREAD_NOT_PARITY");
 const tick=utcMs(quote.timestamp),age=asOf-tick;
 if(age<0||age>MAX_AGE_MS||quote.stale)throw Error("QUOTE_NOT_FRESH");
 const processed={M15:frame(m15,"M15",asOf),H1:frame(h1,"H1",asOf),H4:frame(h4,"H4",asOf)};
 // A fresh BID/ASK tick is insufficient evidence when closed MID candles
 // stopped updating. While provider reports market OPEN, last completed bar
 // may lag by <= 2 full frame durations; reject any older/future dataset.
 // No weekend or broker-session calendar is inferred from this threshold.
 for(const tf of FRAMES){
   const lag=asOf-Date.parse(processed[tf].view.lastClosedUTC);
   if(!Number.isFinite(lag)||lag<0||lag>META[tf].width*2)
     throw Error("CANDLE_STALE_"+tf);
 }
 const comparisons={H1:overlap(processed.M15,processed.H1,3600000),
                    H4:overlap(processed.M15,processed.H4,14400000)};
 const all=Object.values(comparisons);
 // Only a private authenticated viewer may see these price-derived
 // levels. Use last 48 actual CLOSED bars and no cross-gap bridging.
 const privateChart=Object.fromEntries(FRAMES.map(tf=>[
    tf,processed[tf].all.slice(-48).map(row=>({
      time:new Date(row.t).toISOString(),
      open:row.open,high:row.high,low:row.low,close:row.close
    }))
  ]));
 const privateStructure=analyzeChart(privateChart,asOf);
 return {
  status:all.some(x=>x.completeMismatches>0||x.incompleteM15Groups>0)
    ?"WAIT_CROSS_FRAME_GAPS":"OBSERVED_READONLY_UNVERIFIED",
  observedUTC:new Date(asOf).toISOString(),quoteUTC:new Date(tick).toISOString(),
  quoteAgeSeconds:Math.round(age/1000*1000)/1000,
  rawPrivateQuote:{bid:quote.bid,ask:quote.ask,spread:quote.ask-quote.bid},
  // Actual, independently geometry-validated CLOSED bars, never forming bars.
  // A small in-memory snapshot for authenticated personal review display only.
  // MID OHLC may contain provider's initial BID history seed, NOT bid/ask OHLC.
  // This is never connected to the offline paper simulator or trade engine.
  rawPrivateChart:privateChart,
  rawPrivateStructure:privateStructure,
  frameSummary:Object.fromEntries(FRAMES.map(tf=>[tf,processed[tf].view])),
  crossFrameComparisons:comparisons,
  blockerCodes:["BROKER_SESSION_CALENDAR_UNVERIFIED","UPSTREAM_MT5_BROKER_RIGHTS_NOT_WARRANTED",
    "GC_DXY_US_YIELDS_ORDERFLOW_AND_NEWS_NOT_COMPLETE","HISTORICAL_BID_ASK_NOT_PROVIDED"],
  ...WAIT
 };
}
async function snapshot({fetchFn=globalThis.fetch,nowMs=Date.now,authorization="",verifyViewer}={}){
 let sample;
 try{
  // Single-flight max 4 requests; no provider creds or trading endpoints.
  const cacheNow=nowMs();
  const cachedQuoteTime=cache?Date.parse(cache.quoteUTC):NaN;
  if(cache&&cacheNow<expires&&Number.isFinite(cachedQuoteTime)&&
     cacheNow>=cachedQuoteTime&&cacheNow-cachedQuoteTime<=MAX_REUSABLE_QUOTE_AGE_MS)
    sample=cache;
  else{
   if(!pending)pending=collect(fetchFn,nowMs).then(value=>{
    cache=value;expires=nowMs()+CACHE_MS;return value;
   }).finally(()=>{pending=null;});
   sample=await pending;
  }
 }catch(error){
  // A provider-reported closure, stale history and failed HTTP are
  // different facts. Expose only fixed diagnostic reason codes, no vendor
  // error text, quote prices, broker credentials or trading permissions.
  const message=error&&error.message;
  const reason=message==="PROVIDER_REPORTED_CLOSED"?"PROVIDER_REPORTED_CLOSED"
    :typeof message==="string"&&/^CANDLE_STALE_(M15|H1|H4)$/.test(message)
      ?"CLOSED_CANDLE_STALE"
    :message==="QUOTE_NOT_FRESH"?"QUOTE_STALE_OR_UNVERIFIED"
    :message==="PUBLIC_HTTP_UNAVAILABLE"?"PUBLIC_HTTP_UNAVAILABLE"
    :"PUBLIC_FEED_INVALID_STALE_OR_UNAVAILABLE";
  return {httpStatus:503,body:{...WAIT,status:"WAIT_BIQUOTE_DATA_UNAVAILABLE",
    frameSummary:{},crossFrameComparisons:{},
    blockerCodes:[reason],rawQuoteShown:false}};
 }
 const ageAtResponse=(nowMs()-Date.parse(sample.quoteUTC))/1000;
 if(!Number.isFinite(ageAtResponse)||ageAtResponse<0||ageAtResponse>30)
  return {httpStatus:503,body:{...WAIT,status:"WAIT_BIQUOTE_DATA_STALE",
    frameSummary:{},crossFrameComparisons:{},
    blockerCodes:["LATEST_QUOTE_NO_LONGER_FRESH"],rawQuoteShown:false}};
 const {rawPrivateQuote,rawPrivateChart,rawPrivateStructure,...safe}=sample;
 safe.quoteAgeSeconds=Math.round(ageAtResponse*1000)/1000;
 let viewer=false;
 // Verify with existing private coordinator. A public visitor never gets raw BID/ASK.
 if(typeof authorization==="string"&&/^Bearer [A-Za-z0-9_-]{32,128}$/.test(authorization)&&
    typeof verifyViewer==="function"){
  try{viewer=(await verifyViewer(authorization))===true;}catch{viewer=false;}
 }
 return {httpStatus:200,body:{...safe,rawQuoteShown:viewer,
    ...(viewer?{bid:rawPrivateQuote.bid,ask:rawPrivateQuote.ask,
      spread:rawPrivateQuote.spread,privateChart:rawPrivateChart,
      privateStructure:rawPrivateStructure,
      privateChartReadOnly:true,privateChartDataBasis:"MID_WITH_POSSIBLE_BID_SEED"}:{})}};
}
function resetForTests(){cache=null;expires=0;pending=null;}
module.exports={snapshot,resetForTests,URLS};
