'use strict';
const assert=require('node:assert/strict');
const {MARKET_STREAM,referenceHoursEstimate,newState,intake,status}=require('./binance_xauusdt_research');
const time=s=>Date.parse(s);
const make=(a,T='2026-11-16T12:00:00Z',opts={})=>({e:'aggTrade',s:'XAUUSDT',a,p:'4000.50',q:'2.5',T:time(T),m:false,...opts});
const at='2026-11-16T12:00:05Z';
assert(MARKET_STREAM.includes('/market/ws/'));
assert.equal(referenceHoursEstimate(time('2026-11-15T21:59:00Z')),false); // Sun 16:59 NY EST
assert.equal(referenceHoursEstimate(time('2026-11-15T23:00:00Z')),true);  // Sun 18:00 NY EST
assert.equal(referenceHoursEstimate(time('2026-07-05T21:59:00Z')),false); // Sun 17:59 NY EDT
assert.equal(referenceHoursEstimate(time('2026-07-05T22:00:00Z')),true);  // Sun 18:00 NY EDT
assert.equal(referenceHoursEstimate(time('2026-11-13T22:00:00Z')),false); // Fri 17 NY
assert.equal(referenceHoursEstimate(time('2026-11-16T22:00:00Z')),false); // Mon 17 NY daily break
assert.equal(referenceHoursEstimate(time('2026-11-16T23:00:00Z')),true); // Mon 18 NY
const s=newState();
assert.deepEqual({signal:s.signal,executable:s.executable,canTrade:s.canTrade},{signal:'WAIT',executable:false,canTrade:false});
assert.equal(intake(s,JSON.stringify({stream:'xauusdt@aggTrade',data:make(100)}),time(at)).accepted,true);
assert.equal(intake(s,make(100),time(at)).reason,'DUPLICATE_AGGREGATE');
assert.equal(s.seen,1);
assert.equal(intake(s,make(101,'2026-11-16T12:00:01Z',{m:true,q:'1.0'}),time(at)).accepted,true);
assert.equal(s.minute.delta,1.5);
assert.equal(intake(s,make(104,'2026-11-16T12:01:01Z'),time('2026-11-16T12:01:05Z')).accepted,true);
assert.equal(s.suspectMissingAggregates,2);
assert.equal(s.minuteSummaries.length,1);
assert.equal(s.minuteSummaries[0].count,2);
assert.equal(intake(s,make(103,'2026-11-16T12:01:02Z'),time('2026-11-16T12:01:05Z')).reason,'OUT_OF_ORDER_AGGREGATE');
assert.equal(intake(s,make(105,'2026-11-16T12:01:02Z',{s:'BTCUSDT'}),time('2026-11-16T12:01:05Z')).reason,'WRONG_EVENT_OR_SYMBOL');
assert.equal(intake(s,make(105,'2026-11-16T12:01:02Z',{q:'NaN'}),time('2026-11-16T12:01:05Z')).reason,'INVALID_PRICE_QUANTITY_OR_SIDE');
assert.equal(intake(s,make(105,'2026-11-16T12:02:02Z'),time('2026-11-16T12:01:05Z')).reason,'INVALID_EVENT_ID_OR_TIMESTAMP');
const off=newState();assert.equal(intake(off,make(1,'2026-11-15T15:00:00Z'),time('2026-11-15T15:00:01Z')).referenceHours,false);
assert.equal(off.onHoursVolumeBuy,0);
for(const v of [s,off]){
 const z=status(v,time('2026-11-16T12:01:05Z'));
 assert.equal(z.signal,'WAIT');assert.equal(z.executable,false);assert.equal(z.reliable,false);
 assert.equal(z.researchEligible,false);assert.equal(z.paperOrdersAllowed,false);assert.equal(z.providerRequestsMade,0);
}
assert.equal(intake(newState(),'{bad-json',time(at)).reason,'INVALID_JSON');
console.log('PASS Binance XAUUSDT offline research: DST, session break, wrong symbol, duplicate, gap, time, fail-closed WAIT. Zero provider calls or orders.');
