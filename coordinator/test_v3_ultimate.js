'use strict';
const assert=require('node:assert/strict');
const {evaluate,evidence,riskSize}=require('./v3_ultimate');
const asOfUTC='2026-11-10T12:00:00Z',now=Date.parse(asOfUTC);
const base={mode:'synthetic',source:'offline fixture',observedUTC:asOfUTC,previous:100,value:99};
assert.equal(evidence('DXY',base,now).score,1);
assert.equal(evidence('GC',base,now).score,-1);
for(const observedUTC of ['bad','2026-11-10T12:00:01Z','2026-11-10T11:54:59Z'])assert.equal(evidence('DXY',{...base,observedUTC},now).status,'UNAVAILABLE');
assert.equal(evidence('orderFlow',{...base,volume:1000},now).status,'UNAVAILABLE');
assert.equal(evidence('orderFlow',{...base,kind:'trades',licensed:true,buyVolume:80,sellVolume:20},now).score,.6);
const calendar={...base,coverageStartUTC:'2026-11-10T11:00:00Z',coverageEndUTC:'2026-11-10T13:00:00Z',events:[{timeUTC:asOfUTC,impact:'high'}]};
assert.equal(evidence('calendar',calendar,now).blocked,true);
assert.equal(evidence('calendar',{...calendar,coverageEndUTC:asOfUTC},now).status,'UNAVAILABLE');
const risk={equity:10000,dailyLoss:0,riskFraction:.005,dailyLossFraction:.02,valuePerPoint:100,lotStep:.01,minLot:.01,maxLot:10,commissionPerLot:5,slippage:.1,killSwitch:false,activeTrades:0};
const plan={stopDistance:5,spread:.4};
const r=riskSize(plan,risk);assert.equal(r.ok,true);assert.ok(r.riskAmount<=50);
for(const patch of [{killSwitch:true},{activeTrades:1},{dailyLoss:200},{riskFraction:.1},{slippage:-1},{equity:1}])assert.equal(riskSize(plan,{...risk,...patch}).ok,false);
const frames=Object.fromEntries(Object.entries({M15:15,H1:60,H4:240}).map(([f,m])=>[f,Array.from({length:30},(_,i)=>({datetime:new Date(now-(30-i)*m*60000).toISOString(),open:100,high:101,low:99,close:100}))]));
const input={asOfUTC,frames,spread:.1,risk,feeds:{DXY:base}};
const before=JSON.stringify(input),result=evaluate(input);
assert.equal(result.signal,'WAIT');assert.equal(result.executable,false);assert.equal(result.researchCandidate,'NONE');assert.ok(result.monitoring.blocked.includes('calendar'));assert.equal(JSON.stringify(input),before);assert.deepEqual(result,evaluate(input));
assert.throws(()=>evaluate({}),/asOfUTC/);
const future=structuredClone(input);future.frames.M15.at(-1).datetime=asOfUTC;assert.match(evaluate(future).technical.reason,/unclosed/);
console.log('PASS Ultimate evidence freshness, provenance, event windows, trade-side flow, risk ceilings, determinism and no-lookahead');
// Positive path is a research candidate, never an executable recommendation.
const aligned=structuredClone(require('./fixtures/ultimate-synthetic.json'));
for(const rows of Object.values(aligned.frames)){
 rows[22].high=103;rows[29].open=100;rows[29].high=105;rows[29].close=104;
}
const positive=evaluate(aligned);
assert.equal(positive.researchCandidate,'BUY');assert.equal(positive.executable,false);
assert.equal(positive.monitoring.blocked.length,0);
const eventBlocked=structuredClone(aligned);eventBlocked.feeds.calendar.events=[{timeUTC:asOfUTC,impact:'high'}];
assert.equal(evaluate(eventBlocked).researchCandidate,'NONE');
const disagrees=structuredClone(aligned);disagrees.feeds.DXY.value=101;
assert.equal(evaluate(disagrees).researchCandidate,'NONE');
const staleFeed=structuredClone(aligned);staleFeed.feeds.GC.observedUTC='2026-11-10T11:00:00Z';
assert.equal(evaluate(staleFeed).researchCandidate,'NONE');
console.log('PASS fully aligned synthetic candidate and independent event, disagreement and stale-feed vetoes');

const archived={...base,mode:'recorded',instrument:'DXY',entitlementVerified:true,availableUTC:asOfUTC};
assert.equal(evidence('DXY',archived,now).status,'READY');
assert.equal(evidence('DXY',{...archived,availableUTC:'2026-11-10T12:01:00Z'},now).status,'UNAVAILABLE');
assert.equal(evidence('DXY',{...archived,instrument:'GC'},now).status,'UNAVAILABLE');
assert.equal(evidence('DXY',{...archived,entitlementVerified:false},now).status,'UNAVAILABLE');
assert.equal(evidence('calendar',{...calendar,mode:'recorded',instrument:'USD_EVENTS',entitlementVerified:true,availableUTC:asOfUTC},now).status,'UNAVAILABLE');
console.log('PASS direct Ultimate recorded evidence cannot bypass arrival, instrument, entitlement or news publication gates');

const genuinePastNews={...calendar,mode:'recorded',instrument:'GOLD_USD_NEWS',entitlementVerified:true,availableUTC:asOfUTC,events:[]};
assert.equal(evidence('headlines',genuinePastNews,now).status,'UNAVAILABLE');
assert.match(evidence('headlines',genuinePastNews,now).reason,/Future headline/);
console.log('PASS recorded headlines cannot assert knowledge of future unknown events');
