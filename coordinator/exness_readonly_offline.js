'use strict';
// Offline Exness Trader API GET planner + documented Bid/Ask candle validation.
// No network, account access, API key lookup, provider startup or orders.
// Reference: exness-api.com/reference/trading/get-candle-history
// and exness-api.com/authentication/request-signing (Nov 2026).
const crypto=require('node:crypto');
const WIDTH=Object.freeze({M15:900000,H1:3600000,H4:14400000});
const SIDES=Object.freeze(['bid','ask']);
const OHLC=Object.freeze(['open','high','low','close']);
const MIN_BARS=50;
const BLOCKERS=Object.freeze([
  'EXNESS_INFO_KEY_SCOPE_AND_API_ELIGIBILITY_UNVERIFIED',
  'EXNESS_KYC_AND_DEPOSIT_CONDITIONS_UNVERIFIED',
  'EXNESS_CLOUD_PERSONAL_DATA_RIGHTS_NOT_INDEPENDENTLY_VERIFIED',
  'EXNESS_AUTHENTICATED_XAUUSD_HISTORY_AND_STREAM_NOT_CONNECTED',
  'EXNESS_INDEPENDENT_SESSION_CALENDAR_AND_QUOTE_CLOCK_UNVERIFIED',
  'EXNESS_BROKER_COST_AND_PAPER_APPROVAL_MISSING'
]);
function utc(value){
 if(typeof value!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?(?:Z|\+00:00)$/.test(value))
  throw Error('EXPLICIT_UTC_TIME_REQUIRED');
 const n=Date.parse(value);
 if(!Number.isFinite(n)||new Date(n).toISOString().slice(0,19)!==value.slice(0,19))
  throw Error('INVALID_UTC_TIME');
 return n;
}
// A *plan*, not an HTTP client. Limit each historic chunk to <=1000 candles,
// and query both sides in Exness's documented response format.
function candlePath(accountId,tf,fromUTC,toUTC){
 const id=String(accountId);
 if(!/^\d{1,20}$/.test(id)||!WIDTH[tf])throw Error('ACCOUNT_OR_FRAME_INVALID');
 const start=utc(fromUTC),end=utc(toUTC),bars=(end-start)/WIDTH[tf];
 if(!(bars>0&&Number.isInteger(bars)&&bars<=1000))
  throw Error('HISTORICAL_CHUNK_SIZE_OR_ALIGNMENT_INVALID');
 if(start%WIDTH[tf]!==0||end%WIDTH[tf]!==0)throw Error('HISTORICAL_TIMEFRAME_ALIGNMENT_INVALID');
 const query=new URLSearchParams();
 query.set('instrument','XAUUSD');query.set('price_type','both');query.set('timeframe',tf);
 query.set('from',new Date(start).toISOString());query.set('to',new Date(end).toISOString());
 return '/v1/market-data/accounts/'+id+'/candles?'+query.toString();
}
// Prepare signed GET headers *offline* with an ephemeral or supplied Ed25519
// private key. No fetch or WebSocket access is implemented in this module.
function signOfflineCandleGet({accountId,tf,fromUTC,toUTC,apiKey,privateKey,timestampMs}){
 if(typeof apiKey!=='string'||!/^[-A-Za-z0-9_]{6,128}$/.test(apiKey))
  throw Error('PUBLIC_API_KEY_FORMAT_INVALID');
 if(!Number.isSafeInteger(timestampMs)||timestampMs<=0)throw Error('FRESH_TIMESTAMP_REQUIRED');
 const path=candlePath(accountId,tf,fromUTC,toUTC);
 const payload={api_key:apiKey,idempotency_key:'',timestamp:timestampMs,
  sign_version:1,method:'GET',path,body_hash:'47DEQpj8HBSa-_TImW-5JCeuQeRkm5NMpJWZG3hSuFU'};
 const data=Buffer.from(JSON.stringify(payload),'utf8');
 const key=privateKey instanceof crypto.KeyObject
  ?privateKey:crypto.createPrivateKey(privateKey);
 if(key.asymmetricKeyType!=='ed25519')throw Error('ED25519_SIGNING_KEY_REQUIRED');
 const signature=crypto.sign(null,data,key).toString('base64url');
 const headers={'EXN-API-KEY':apiKey,'EXN-IDEMPOTENCY-KEY':'',
  'EXN-TIMESTAMP':String(timestampMs),'EXN-SIGN-VERSION':'1',
  'EXN-DATA':data.toString('base64url'),'EXN-SIGN':signature,
  'Accept':'application/json'};
 return {method:'GET',path,headers};
}
function frame(input,tf,now){
 if(!input||typeof input!=='object'||Array.isArray(input)||
    !Array.isArray(input.candles)||input.candles.length<MIN_BARS||
    input.candles.length>1000)throw Error('FRAME_HISTORY_INSUFFICIENT_OR_OVERSIZE');
 const index=new Map();let last=-Infinity,gaps=0;
 for(const item of input.candles){
  const stamp=utc(item?.time);
  if(stamp%WIDTH[tf]!==0||stamp+WIDTH[tf]>now)
   throw Error('UNALIGNED_OR_FORMING_CANDLE');
  if(stamp<=last)throw Error('DUPLICATE_OR_UNSORTED_CANDLE');
  if(last>=0)gaps+=Math.max(0,(stamp-last)/WIDTH[tf]-1);
  const entry={};
  for(const side of SIDES){
   const p=item?.[side];
   if(!p||typeof p!=='object'||Array.isArray(p))throw Error('BOTH_BID_ASK_REQUIRED');
   const obj={};
   for(const field of OHLC){
    if(typeof p[field]!=='number'||!Number.isFinite(p[field])||p[field]<=0)
      throw Error('NONFINITE_OR_NONPOSITIVE_PRICE');
    obj[field]=p[field];
   }
   if(obj.high<Math.max(obj.open,obj.low,obj.close)||
      obj.low>Math.min(obj.open,obj.high,obj.close))
     throw Error('INVALID_SIDE_OHLC');
   entry[side]=obj;
  }
  for(const field of OHLC)
   if(entry.ask[field]<entry.bid[field])throw Error('CROSSED_BID_ASK');
  index.set(stamp,entry);last=stamp;
 }
 const MAX_AGE={M15:1200000,H1:4500000,H4:18000000};
 if(now-(last+WIDTH[tf])>MAX_AGE[tf])throw Error('STALE_LATEST_CLOSED_BAR');
 return {index,count:input.candles.length,gaps};
}
function compare(m15,higher,tf){
 const step=WIDTH[tf]/WIDTH.M15;let compared=0;
 for(const [stamp,p] of higher.index){
  const bars=Array.from({length:step},(_,i)=>m15.index.get(stamp+i*WIDTH.M15));
  const have=bars.filter(Boolean).length;
  if(have>0&&have<step)throw Error('PARTIAL_M15_HIGHER_BAR');
  if(!have)continue;
  for(const side of SIDES){
   const agg={open:bars[0][side].open,close:bars.at(-1)[side].close,
    high:Math.max(...bars.map(x=>x[side].high)),
    low:Math.min(...bars.map(x=>x[side].low))};
   for(const f of OHLC)
    if(Math.abs(agg[f]-p[side][f])>0.00001)throw Error('TIMEFRAME_BID_ASK_MISMATCH');
  }
  compared++;
 }
 let previous=null;
 for(const t of m15.index.keys()){
  const group=Math.floor(t/WIDTH[tf])*WIDTH[tf];
  if(group===previous)continue;
  previous=group;
  if(Array.from({length:step},(_,i)=>m15.index.has(group+i*WIDTH.M15)).every(Boolean)
     &&!higher.index.has(group))throw Error('HIGHER_FRAME_CANDLE_MISSING');
 }
 if(compared<1)throw Error('NO_COMPLETE_CROSS_FRAME_OVERLAP');
 return compared;
}
// Validate one documented tick (not a subscription). A tick can be recent
// but is never treated as a finalized candle, and no account key is read.
function tickAudit(tick,now){
 if(tick==null)return {checked:false,reason:'LIVE_TICK_NOT_CONNECTED'};
 if(tick?.instrument!=='XAUUSD')throw Error('WRONG_TICK_INSTRUMENT');
 const bid=tick.bid,ask=tick.ask,time=utc(tick.timestamp);
 if(typeof bid!=='number'||typeof ask!=='number'||!Number.isFinite(bid)||
    !Number.isFinite(ask)||bid<=0||ask<bid)throw Error('INVALID_TICK_BID_ASK');
 if(time>now+5000||now-time>60000)throw Error('TICK_STALE_OR_CLOCK_SKEW');
 return {checked:true,reason:'STRUCTURAL_TICK_ONLY_SOURCE_NOT_VERIFIED'};
}
function auditOfflineBundle(bundle,asOfUTC){
 const errors=[],counts={M15:0,H1:0,H4:0},gaps={M15:0,H1:0,H4:0};
 const overlaps={H1:0,H4:0};let tick={checked:false,reason:'LIVE_TICK_NOT_CONNECTED'};
 try{
  const now=utc(asOfUTC);
  if(!bundle||typeof bundle!=='object'||Array.isArray(bundle)||
     bundle.provider!=='EXNESS'||bundle.instrument!=='XAUUSD'||
     bundle.priceType!=='both')throw Error('EXNESS_SOURCE_IDENTITY_REQUIRED');
  if(!bundle.frames||typeof bundle.frames!=='object'||Array.isArray(bundle.frames)||
    Object.keys(bundle.frames).sort().join(',')!=='H1,H4,M15')throw Error('THREE_FRAMES_REQUIRED');
  const f={};
  for(const tf of Object.keys(WIDTH)){
   f[tf]=frame(bundle.frames[tf],tf,now);counts[tf]=f[tf].count;gaps[tf]=f[tf].gaps;
  }
  overlaps.H1=compare(f.M15,f.H1,'H1');
  overlaps.H4=compare(f.M15,f.H4,'H4');
  if(Object.values(gaps).some(n=>n>0))throw Error('SESSION_GAPS_UNVERIFIED');
  tick=tickAudit(bundle.tick??null,now);
 }catch(error){errors.push(error.message||'INVALID_EXNESS_BUNDLE');}
 return {
  mode:'EXNESS_OFFLINE_PROVIDER_SHAPE_AUDIT',
  provider:'EXNESS',status:errors.length?'BLOCKED_SHAPE_INVALID':'WAIT_UNVERIFIED_SOURCE',
  structuralAuditPassed:errors.length===0,signal:'WAIT',executable:false,
  researchEligible:false,paperOrdersAllowed:false,tradingEnabled:false,
  providerRequestsMade:0,accountAccessed:false,credentialsRead:false,
  keyScopeVerified:false,licenseVerified:false,marketDataAuthentic:false,
  rawCandlesPublished:false,rawPricesPublished:false,engineInvoked:false,
  candleCounts:counts,unverifiedGapCounts:gaps,checkedOverlaps:overlaps,
  tickStructureChecked:tick.checked,
  blockers:[...errors,...BLOCKERS]
 };
}
module.exports={candlePath,signOfflineCandleGet,auditOfflineBundle,utc,BLOCKERS};
if(require.main===module)console.log(JSON.stringify(auditOfflineBundle(null,'2026-11-14T12:00:00Z')));
