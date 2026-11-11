'use strict';
const assert=require('node:assert/strict');
const {diagnostics,orderFlow,riskPlan,liquidityPools,monitoringAlerts}=require('./ultimate_diagnostics');

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
assert.equal(unavailable.technical.frames.M15.marketStructure.equalLevelLiquidity.method,'Equal confirmed swing levels within 0.1 ATR; diagnostic only, no signal vote');
const alertView=monitoringAlerts(unavailable.technical.frames,{layers:{DXY:{status:'UNAVAILABLE',reason:'stale'},calendar:{status:'READY',blocked:true}}},{ok:false,reason:'spread missing'});
assert.equal(alertView.delivery,'RESPONSE_ONLY_NO_PUSH_OR_EMAIL');
assert.equal(alertView.signal,'WAIT');assert.equal(alertView.executable,false);
assert.ok(alertView.items.some(x=>x.code==='TIMEFRAME_UNAVAILABLE'&&x.source==='H1'));
assert.ok(alertView.items.some(x=>x.code==='SOURCE_UNAVAILABLE'&&x.source==='DXY'));
assert.ok(alertView.items.some(x=>x.code==='EVENT_RISK_WINDOW'&&x.source==='calendar'));
assert.ok(alertView.items.some(x=>x.code==='RISK_GATE_BLOCKED'));

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

const poolBars=[
 {open:10,high:10.5,low:9.5,close:10},
 {open:10,high:10.5,low:9.5,close:10},
 {open:10,high:10.5,low:9.5,close:10},
 {open:10,high:10.5,low:9.5,close:10},
 {open:10,high:10.5,low:9.5,close:10},
 {open:10,high:10.5,low:9.5,close:10},
 {open:10,high:15.2,low:9.5,close:15.0},
 {open:10,high:10.5,low:9.5,close:10}
];
const pools=liquidityPools(poolBars,{highs:[{index:1,confirmedAt:3,price:15},{index:4,confirmedAt:6,price:15.05},{index:7,confirmedAt:9,price:18}],lows:[]},.1);
assert.equal(pools.upper.length,1);
assert.equal(pools.upper[0].touches,2);
assert.equal(pools.upper[0].status,'SWEPT_AND_RECLAIMED');
assert.equal(pools.upper[0].method,'Confirmed swing clustering; ATR-scaled heuristic');
const brokenPools=liquidityPools([...poolBars.slice(0,7),{open:15,high:16,low:14,close:15.5}],
 {highs:[{index:1,confirmedAt:3,price:15},{index:4,confirmedAt:6,price:15.05}],lows:[]},.1);
assert.equal(brokenPools.upper[0].status,'BROKEN');
assert.equal(liquidityPools(poolBars,{highs:[],lows:[]},0).tolerance,null);
console.log('Ultimate supplemental diagnostics: all offline assertions passed');
