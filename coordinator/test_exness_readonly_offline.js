'use strict';
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const {candlePath,signOfflineCandleGet,auditOfflineBundle,BLOCKERS}=require('./exness_readonly_offline');
const NOW='2026-11-13T16:00:00Z';
const W={M15:900000,H1:3600000,H4:14400000};
const start=Date.parse(NOW)-50*W.H4;
function fixture(){
 const m=[];
 for(let i=0;i<800;i++){
  const base=4000+i*.01;
  const bid={open:base,high:base+.21,low:base-.2,close:base+.01};
  const ask=Object.fromEntries(Object.entries(bid).map(([k,v])=>[k,v+.3]));
  m.push({time:new Date(start+i*W.M15).toISOString(),bid,ask,volume:4});
 }
 const aggregate=step=>Array.from({length:800/step},(_,i)=>{
  const bars=m.slice(i*step,(i+1)*step);const row={time:bars[0].time,volume:99};
  for(const side of ['bid','ask'])row[side]={
   open:bars[0][side].open,close:bars.at(-1)[side].close,
   high:Math.max(...bars.map(b=>b[side].high)),
   low:Math.min(...bars.map(b=>b[side].low))};
  return row;
 });
 return {provider:'EXNESS',instrument:'XAUUSD',priceType:'both',
  frames:{M15:{candles:m},H1:{candles:aggregate(4)},H4:{candles:aggregate(16)}},
  tick:{instrument:'XAUUSD',bid:4000,ask:4000.3,timestamp:'2026-11-13T15:59:59Z'}};
}
function check(x){
 const a=auditOfflineBundle(x,NOW);
 assert.equal(a.signal,'WAIT');assert.equal(a.executable,false);
 assert.equal(a.researchEligible,false);assert.equal(a.tradingEnabled,false);
 assert.equal(a.paperOrdersAllowed,false);assert.equal(a.engineInvoked,false);
 assert.equal(a.providerRequestsMade,0);assert.equal(a.accountAccessed,false);
 assert.equal(a.credentialsRead,false);assert.equal(a.marketDataAuthentic,false);
 assert.equal(a.rawCandlesPublished,false);assert.equal(a.rawPricesPublished,false);
 assert.equal(a.keyScopeVerified,false);assert.equal(a.licenseVerified,false);
 for(const blocker of BLOCKERS)assert(a.blockers.includes(blocker));
 const serial=JSON.stringify(a);
 assert(!serial.includes('"bid":'));assert(!serial.includes('"ask":'));
 return a;
}
let a=check(fixture());assert.equal(a.structuralAuditPassed,true,a.blockers.join(','));
assert.deepEqual(a.candleCounts,{M15:800,H1:200,H4:50});
assert.deepEqual(a.checkedOverlaps,{H1:200,H4:50});
assert.equal(a.tickStructureChecked,true);
assert.equal(check(JSON.parse(JSON.stringify(fixture()))).structuralAuditPassed,true);
function invalid(change,reason){
 const p=fixture();change(p);const result=check(p);
 assert.equal(result.structuralAuditPassed,false);
 assert(result.blockers.includes(reason),reason+':'+result.blockers.join(','));
}
invalid(p=>{p.provider='OTHER';},'EXNESS_SOURCE_IDENTITY_REQUIRED');
invalid(p=>{p.priceType='mid';},'EXNESS_SOURCE_IDENTITY_REQUIRED');
invalid(p=>{delete p.frames.H4;},'THREE_FRAMES_REQUIRED');
invalid(p=>{p.frames.M15.candles[0].time='2026-11-05T08:00:00+02:00';},'EXPLICIT_UTC_TIME_REQUIRED');
invalid(p=>{p.frames.M15.candles[1].time=p.frames.M15.candles[0].time;},'DUPLICATE_OR_UNSORTED_CANDLE');
invalid(p=>{p.frames.M15.candles[0].ask.open=1;},'INVALID_SIDE_OHLC');
invalid(p=>{for(const field of ['open','high','low','close'])p.frames.M15.candles[0].ask[field]=p.frames.M15.candles[0].bid[field]-.1;},'CROSSED_BID_ASK');
invalid(p=>{p.frames.M15.candles[0].bid.open=NaN;},'NONFINITE_OR_NONPOSITIVE_PRICE');
invalid(p=>{p.frames.M15.candles[0].bid.high=1;},'INVALID_SIDE_OHLC');
invalid(p=>{p.frames.H1.candles[0].bid.high+=.11;},'TIMEFRAME_BID_ASK_MISMATCH');
invalid(p=>{p.frames.H1.candles.splice(1,1);},'HIGHER_FRAME_CANDLE_MISSING');
invalid(p=>{p.frames.M15.candles.splice(2,1);},'PARTIAL_M15_HIGHER_BAR');
invalid(p=>{p.frames.M15.candles=p.frames.M15.candles.slice(0,60);},'STALE_LATEST_CLOSED_BAR');
invalid(p=>{p.frames.M15.candles=p.frames.M15.candles.slice(0,20);},'FRAME_HISTORY_INSUFFICIENT_OR_OVERSIZE');
invalid(p=>{p.frames.M15.candles.at(-1).time=NOW;},'UNALIGNED_OR_FORMING_CANDLE');
invalid(p=>{p.tick.ask=1;},'INVALID_TICK_BID_ASK');
invalid(p=>{p.tick.timestamp='2026-11-13T15:55:00Z';},'TICK_STALE_OR_CLOCK_SKEW');
const forged=fixture();
Object.assign(forged,{signal:'BUY',executable:true,liveDataValidated:true,
 apiKey:'forged-api-key',scope:'trading',rightsVerified:true});
const fg=check(forged);assert.equal(fg.structuralAuditPassed,true);
assert(fg.blockers.includes('EXNESS_INFO_KEY_SCOPE_AND_API_ELIGIBILITY_UNVERIFIED'));
const path=candlePath('123456','M15','2026-11-13T12:00:00Z','2026-11-13T16:00:00Z');
assert(path.startsWith('/v1/market-data/accounts/123456/candles?'));
assert(path.includes('instrument=XAUUSD'));assert(path.includes('price_type=both'));
assert(path.includes('timeframe=M15'));
assert.throws(()=>candlePath('1/orders','M15','2026-11-13T12:00:00Z',NOW),/ACCOUNT_OR_FRAME/);
assert.throws(()=>candlePath('123456','M1','2026-11-13T12:00:00Z',NOW),/ACCOUNT_OR_FRAME/);
assert.throws(()=>candlePath('123456','M15','2026-10-01T12:00:00Z',NOW),/CHUNK_SIZE/);
assert.throws(()=>candlePath('123456','M15','2026-11-13T12:01:00Z',NOW),/CHUNK_SIZE|ALIGNMENT/);
const pair=crypto.generateKeyPairSync('ed25519');
const signed=signOfflineCandleGet({accountId:'123456',tf:'M15',
 fromUTC:'2026-11-13T12:00:00Z',toUTC:NOW,apiKey:'exnsk-test-readonly',
 privateKey:pair.privateKey,timestampMs:1794571200000});
assert.equal(signed.method,'GET');assert.equal(signed.path,path);
assert.equal(signed.headers['EXN-IDEMPOTENCY-KEY'],'');
const data=Buffer.from(signed.headers['EXN-DATA'],'base64url');
const parsed=JSON.parse(data.toString('utf8'));
assert.equal(parsed.method,'GET');assert.equal(parsed.path,path);
assert.equal(parsed.body_hash,'47DEQpj8HBSa-_TImW-5JCeuQeRkm5NMpJWZG3hSuFU');
assert(crypto.verify(null,data,pair.publicKey,Buffer.from(signed.headers['EXN-SIGN'],'base64url')));
assert.equal(Object.keys(signed.headers).filter(k=>k.startsWith('EXN-')).length,6);
assert.throws(()=>signOfflineCandleGet({accountId:'1',tf:'M1',apiKey:'test-key',
 privateKey:pair.privateKey,timestampMs:10,fromUTC:NOW,toUTC:NOW}),/ACCOUNT_OR_FRAME/);
assert.equal(check(null).structuralAuditPassed,false);
console.log('PASS Exness read-only offline: 22+ BidAsk, timeframe, tick, GET signing and permission scenarios, zero requests');
