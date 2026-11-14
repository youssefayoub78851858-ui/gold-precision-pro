'use strict';
const assert=require('node:assert/strict');
const core=require('../paper-terminal-core');
const {inspect}=require('./paper-terminal-inspect');
let sample=core.sample();
const source=JSON.stringify(sample);
const r=inspect(sample);
assert.equal(r.mode,'OFFLINE_SYNTHETIC_REPLAY');
assert.equal(r.signal,'WAIT');assert.equal(r.executable,false);
assert.equal(r.researchEligible,false);
assert.equal(r.brokerExecution,false);
assert.equal(r.paperExecutionOnServer,false);
assert.equal(r.connectedRealMarketData,false);
assert.equal(r.tradePlanExecutable,false);
assert.equal(r.entry,null);assert.equal(r.stop,null);
assert.equal(r.tp1,null);assert.equal(r.tp2,null);assert.equal(r.tp3,null);
assert.equal(r.providerRequests,0);assert.equal(r.ordersSent,0);
assert.equal(r.credentialsRead,0);
assert.equal(r.frameCounts.M15,512);assert.equal(r.frameCounts.H4,32);
assert.equal(r.structure.H4.bars,32);
assert.equal(r.sourceStatus.GC,'UNAVAILABLE');
assert.equal(r.sourceStatus.orderFlow,'UNAVAILABLE');
assert.equal(r.indicators.vwap,null);
assert.equal(r.indicators.vwapStatus,'NO_VERIFIED_TRADES_OR_VOLUME');
assert(r.blocked.includes('DXY')&&r.blocked.includes('GC')&&r.blocked.includes('orderFlow'));
assert.equal(source,JSON.stringify(sample),'research may not mutate candle data');
assert.deepEqual(r,inspect(sample));
for(const p of [
 {...sample,dataOrigin:'RECORDED_UNVERIFIED'},
 {...sample,source:'LIVE'},
 {...sample,researchApproved:true},
 {...sample,symbol:'EURUSD'},
 ])assert.throws(()=>inspect(p),/ONLY_SYNTHETIC|EXPLICIT/);
const invalid=structuredClone(sample);invalid.bars.at(-1).bid.open=-1;
assert.throws(()=>inspect(invalid),/NONFINITE_OR_INVALID_PRICE/);
console.log('PASS paper-terminal existing V3 Ultimate integration: 512 synthetic bars, MTF, WAIT, no real providers');
