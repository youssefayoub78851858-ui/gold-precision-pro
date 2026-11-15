'use strict';
const assert=require('node:assert/strict');
const {diagnostic,THRESHOLDS}=require('./ultimate_signal_quality');
const {evaluate}=require('./v3_ultimate');
const ASOF='2026-11-10T12:00:00Z';
const now=Date.parse(ASOF);
function frames(behavior='TREND'){
  const out={};
  for(const [name,width] of Object.entries({M15:900000,H1:3600000,H4:14400000})){
    out[name]=Array.from({length:40},(_,i)=>{
      const close=behavior==='CHOP'?100+(i%2?.3:0):100+i*.2;
      return {datetime:new Date(now-(40-i)*width).toISOString(),
        open:close,high:close+.5,low:close-.5,close};
    });
  }
  return out;
}
const tradePlan={entry:108,stop:106,target:112,spread:.4};
const risk={slippage:.1,valuePerPoint:100,commissionPerLot:7};
const layers={calendar:{status:'READY',blocked:false},headlines:{status:'READY',blocked:false}};
const source=frames();
const preserved=JSON.stringify(source);
const a=diagnostic(source,ASOF,tradePlan,risk,layers);
assert.equal(JSON.stringify(source),preserved,'quality audit is pure');
assert.equal(a.status,'RESEARCH_DIAGNOSTIC_ONLY');
assert.equal(a.regime,'DIRECTIONAL');
assert.equal(a.metrics.efficiencyRatio,1);
assert(a.metrics.netRewardRiskEstimate<THRESHOLDS.minimumNetRewardRisk);
assert(a.warnings.includes('COST_ADJUSTED_REWARD_RISK_LOW'));
assert.equal(a.signal,'WAIT');assert.equal(a.executable,false);assert.equal(a.paperOrdersAllowed,false);
assert.equal(a.providerRequestsMade,0);assert.equal(a.empiricalWinProbability,null);
assert.equal(a.qualityScore,null);assert.equal(a.effectOnCandidate,'NONE');
const costBetter=diagnostic(source,ASOF,{...tradePlan,target:116},risk,layers);
assert(costBetter.metrics.netRewardRiskEstimate>2.5);
assert(!costBetter.warnings.includes('COST_ADJUSTED_REWARD_RISK_LOW'));
assert.equal(diagnostic(frames('CHOP'),ASOF,tradePlan,risk,layers).regime,'CHOPPY');
const shock=frames();shock.M15.at(-1).high+=100;
const sh=diagnostic(shock,ASOF,tradePlan,risk,layers);
assert(sh.warnings.includes('SINGLE_CANDLE_VOLATILITY_SHOCK'));
const missing=diagnostic(source,ASOF,tradePlan,{},layers);
assert(missing.warnings.includes('BROKER_COST_OR_TRADE_GEOMETRY_NOT_VERIFIED'));
assert.equal(missing.metrics.netRewardRiskEstimate,null);
const noNews=diagnostic(source,ASOF,tradePlan,risk,{});
assert(noNews.warnings.includes('CALENDAR_COVERAGE_UNVERIFIED'));
assert(noNews.warnings.includes('NEWS_COVERAGE_UNVERIFIED'));
const event=diagnostic(source,ASOF,tradePlan,risk,{calendar:{status:'READY',blocked:true},headlines:{status:'READY',blocked:true}});
assert(event.warnings.includes('HIGH_IMPACT_EVENT_WINDOW'));
assert(event.warnings.includes('HIGH_IMPACT_NEWS_WINDOW'));
const future=frames();future.M15.push({...future.M15.at(-1),datetime:ASOF});
assert.equal(diagnostic(future,ASOF,tradePlan,risk,layers).status,'INSUFFICIENT_EVIDENCE');
assert.equal(diagnostic(source,'2026-11-10T12:00:00+00:00',tradePlan,risk,layers).status,'INSUFFICIENT_EVIDENCE');
assert.equal(diagnostic(source,'2026-11-10T20:00:00Z',tradePlan,risk,layers).status,'INSUFFICIENT_EVIDENCE');
const gap=frames();gap.H1.splice(20,1);
assert.equal(diagnostic(gap,ASOF,tradePlan,risk,layers).status,'RESEARCH_DIAGNOSTIC_ONLY');
assert(diagnostic(gap,ASOF,tradePlan,risk,layers).warnings.includes('H1_GAP_REQUIRES_BROKER_SESSION_CALENDAR'));
const existing=require('./fixtures/ultimate-synthetic.json');
const original=evaluate(existing);
assert.equal(original.signal,'WAIT');assert.equal(original.executable,false);
assert.equal(original.qualityDiagnostics?.signal,'WAIT');
assert.equal(original.qualityDiagnostics?.effectOnCandidate,'NONE');
assert.equal(original.qualityDiagnostics?.empiricalWinProbability,null);
console.log('PASS signal quality: trending/choppy, shock, net costs, news, UTC, forming/stale, pure WAIT, V3 integration');
