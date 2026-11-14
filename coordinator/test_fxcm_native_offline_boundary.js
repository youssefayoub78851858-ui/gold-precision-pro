'use strict';
const assert=require('node:assert/strict');
const {assess}=require('./fxcm_native_offline_boundary');
const T0=Date.parse('2026-11-13T12:00:00Z'),ASOF='2026-11-13T16:00:00Z';
const W={M15:900000,H1:3600000,H4:14400000};
function make(){
 const m=Array.from({length:16},(_,i)=>{
  const p={open:4000+i*.01,high:4000+(i+1)*.01+.2,low:3999+i*.01,close:4000+(i+1)*.01};
  const q=Object.fromEntries(Object.entries(p).map(([k,v])=>[k,v+.3]));
  return {openTime:new Date(T0+i*W.M15).toISOString(),bid:p,ask:q};
 });
 const aggregate=(size)=>Array.from({length:16/size},(_,i)=>{
  const b=m.slice(i*size,(i+1)*size), out={openTime:b[0].openTime};
  for(const s of ['bid','ask'])out[s]={open:b[0][s].open,high:Math.max(...b.map(x=>x[s].high)),
   low:Math.min(...b.map(x=>x[s].low)),close:b.at(-1)[s].close};
  return out;
 });
 return {provider:'FXCM',source:'FOREXCONNECT_NATIVE_CPP',instrument:'XAU/USD',
  receivedUTC:'2026-11-13T15:59:55Z',frames:{M15:m,H1:aggregate(4),H4:aggregate(16)}};
}
function check(p,reason){
 const r=assess(p,ASOF);
 assert.equal(r.signal,'WAIT');assert.equal(r.executable,false);
 assert.equal(r.paperOrdersAllowed,false);assert.equal(r.researchEligible,false);
 assert.equal(r.sdkLoaded,false);assert.equal(r.credentialReads,0);
 assert.equal(r.engineCalled,false);assert.equal(r.rawCandlesReleased,false);
 assert.equal(r.sourceRightsVerified,false);assert.equal(r.sourceRequestsMade,0);
 if(reason){assert.equal(r.structureValid,false);assert(r.blockingReasons.includes(reason),r.blockingReasons.join(','));}
 return r;
}
let ok=check(make());assert.equal(ok.structureValid,true);
assert.deepEqual(ok.verifiedGeometricOverlaps,{H1:4,H4:1});
assert.deepEqual(ok.frameCounts,{M15:16,H1:4,H4:1});
const cases=[
 ['WRONG_PROVIDER_SOURCE_OR_INSTRUMENT',p=>{p.provider='CFI';}],
 ['SEPARATE_BID_ASK_REQUIRED',p=>{delete p.frames.M15[0].ask;}],
 ['CROSSED_BID_ASK',p=>{p.frames.M15[0].ask.open=1;}],
 ['INVALID_PRICE',p=>{p.frames.M15[0].bid.high=NaN;}],
 ['INVALID_OHLC',p=>{p.frames.M15[0].bid.high=1;}],
 ['UTC_Z_REQUIRED',p=>{p.frames.M15[0].openTime='2026-11-13T12:00:00+00:00';}],
 ['UNALIGNED_OR_UNCLOSED_CANDLE',p=>{p.frames.M15[0].openTime='2026-11-13T16:00:00Z';}],
 ['DUPLICATE_OR_UNSORTED_TIME',p=>{p.frames.M15[1].openTime=p.frames.M15[0].openTime;}],
 ['BID_ASK_TIMEFRAME_MISMATCH',p=>{p.frames.H1[0].ask.high+=.7;}],
 ['PARTIAL_M15_COVERAGE',p=>{p.frames.M15.splice(2,1);}],
 ['ALL_THREE_FRAMES_REQUIRED',p=>{delete p.frames.H4;}],
 ['STALE_PACKET',p=>{p.receivedUTC='2026-11-13T10:00:00Z';}],
];
for(const [reason,mutate] of cases){let p=make();mutate(p);check(p,reason);}
let forged=make();forged.eulaSigned=true;forged.sourceApproved=true;forged.signal='BUY';
ok=check(forged);assert(ok.structureValid);assert(ok.blockingReasons.includes('FXCM_CLOUD_EULA_UNVERIFIED'));
check(null,'INVALID_PACKET');
assert(check(JSON.parse(JSON.stringify(make()))).structureValid);
console.log('PASS: 16 offline FXCM candidate scenarios; ALWAYS WAIT; zero FXCM data/trading calls');
