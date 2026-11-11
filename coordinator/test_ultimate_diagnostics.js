'use strict';
const assert=require('node:assert/strict');
const {diagnostics,orderFlow,riskPlan}=require('./ultimate_diagnostics');

const asOfUTC='2026-11-10T12:00:00Z';
function candles(minutes,count=72){
 const end=Date.parse(asOfUTC)-minutes*60000*(count-1);
 return Array.from({length:count},(_,i)=>{
  const close=2000+i*.35+Math.sin(i/2)*.15;
  return {datetime:new Date(end+i*minutes*60000).toISOString(),open:close-.08,high:close+.2,low:close-.2,close};
 });
}
const frames={M15:candles(15),H1:candles(60),H4:candles(240)};
const okLayer={status:'READY',reason:null};
const baseTape={mode:'synthetic',instrument:'GC_TRADES',contract:'GCZ6',kind:'trades',sideMethod:'EXCHANGE_AGGRESSOR',licensed:true,sequenceGapCount:0,
 windowStartUTC:'2026-11-10T11:55:00Z',windowEndUTC:'2026-11-10T12:00:00Z',observedUTC:'2026-11-10T12:00:00Z',availableUTC:asOfUTC,
 contractExpiryUTC:'2026-12-31T00:00:00Z',tickSize:.1,buyVolume:3,sellVolume:2,openPrice:2000,closePrice:2000.1,
 trades:[{timestampUTC:'2026-11-10T11:59:00Z',sequence:1,price:2000,size:3,aggressor:'BUY'},{timestampUTC:'2026-11-10T11:59:30Z',sequence:2,price:2000.1,size:2,aggressor:'SELL'}]};

const unavailable=diagnostics({asOfUTC,frames:{M15:frames.M15}}, {signal:'WAIT',executable:false});
assert.equal(unavailable.signal,'WAIT');assert.equal(unavailable.executable,false);
assert.equal(unavailable.technical.frames.M15.status,'READY');
assert.equal(unavailable.technical.frames.H1.status,'UNAVAILABLE');
assert.equal(diagnostics({asOfUTC,frames:{M15:candles(15,12)}},{signal:'WAIT'}).technical.frames.M15.status,'PARTIAL');
assert.equal(unavailable.orderFlow.status,'BLOCKED_MISSING');
assert.equal(unavailable.riskPlan.status,'WAIT_NO_MTF_CANDIDATE');
assert.equal(unavailable.technical.directionalVote,false);

const valid=diagnostics({asOfUTC,frames}, {signal:'WAIT',executable:false});
for(const tf of ['M15','H1','H4'])assert.equal(valid.technical.frames[tf].status,'READY');
assert.equal(valid.technical.frames.M15.signal,'WAIT');assert.equal(valid.technical.frames.M15.executable,false);
assert.ok(Number.isFinite(valid.technical.frames.M15.ema20));
assert.ok(Number.isFinite(valid.technical.frames.M15.ema50));
assert.ok(Number.isFinite(valid.technical.frames.M15.rsi14));
assert.ok(Number.isFinite(valid.technical.frames.M15.atr14));
assert.equal(valid.signal,'WAIT');assert.equal(valid.executable,false);

const aggregate=orderFlow({buyVolume:3,sellVolume:2},asOfUTC,okLayer);
assert.equal(aggregate.status,'AGGREGATE_ONLY');assert.equal(aggregate.features.delta,1);
assert.equal(aggregate.features.footprint,null);assert.equal(aggregate.admissionEligible,false);
const tape=orderFlow(baseTape,asOfUTC,okLayer);
assert.equal(tape.status,'SYNTHETIC_TEST_ONLY');assert.equal(tape.admissionEligible,false);
assert.equal(tape.features.delta,1);assert.equal(tape.features.poc,2000);
assert.ok(Number.isFinite(tape.features.vwap));assert.equal(tape.features.footprint.length,2);
assert.equal(orderFlow({...baseTape,sequenceGapCount:1},asOfUTC,okLayer).status,'BLOCKED_TAPE');
assert.equal(orderFlow({...baseTape,trades:baseTape.trades.map((t,i)=>({...t,sequence:i+1===2?3:t.sequence}))},asOfUTC,okLayer).status,'BLOCKED_TAPE');
assert.equal(orderFlow({...baseTape,availableUTC:'2026-11-10T12:06:00Z'},asOfUTC,okLayer).status,'BLOCKED_TAPE');
assert.equal(orderFlow(baseTape,'2026-11-10T12:10:01Z',okLayer).status,'BLOCKED_TAPE');
assert.equal(orderFlow({...baseTape,sellVolume:9},asOfUTC,okLayer).status,'BLOCKED_TAPE');
assert.equal(orderFlow({...baseTape,buyVolume:'3'},asOfUTC,okLayer).status,'BLOCKED_INVALID_AGGREGATE');

const plan=riskPlan({spread:.4,risk:{slippage:.1,commissionPerLot:2,valuePerPoint:10,equity:1000,dailyLoss:0,dailyLossFraction:.02}},
 {technical:{candidate:'BUY'},tradePlan:{entry:2000,stop:1998,stopDistance:2},risk:{ok:true,lots:.1,budget:5}});
assert.equal(plan.status,'RESEARCH_PLAN_ONLY');assert.equal(plan.signal,'WAIT');assert.equal(plan.executable,false);
assert.deepEqual([plan.tp1,plan.tp2,plan.tp3],[2002,2004,2006]);
assert.equal(plan.estimatedNetAtTargets[0].accountCurrency,1.3);
assert.equal(riskPlan({},{}).status,'WAIT_NO_MTF_CANDIDATE');
assert.equal(riskPlan({spread:.4,risk:{}},{technical:{candidate:'BUY'},tradePlan:{entry:2,stop:1,stopDistance:1},risk:{ok:true,lots:1,budget:1}}).status,'BLOCKED_RISK');

const stale={...frames,M15:frames.M15.map(x=>({...x}))};stale.M15.at(-1).datetime='2026-11-10T11:30:00Z';
assert.equal(diagnostics({asOfUTC,frames:stale},{signal:'WAIT'}).technical.frames.M15.status,'UNAVAILABLE');
console.log('Ultimate supplemental diagnostics: all offline assertions passed');
