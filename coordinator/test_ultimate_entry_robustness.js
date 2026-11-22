'use strict';
const a=require('node:assert/strict');
const {inspect,THRESHOLDS}=require('./ultimate_entry_robustness');
const AT='2026-11-19T12:00:00Z',now=Date.parse(AT);
function frames(){
 return Object.fromEntries(
  Object.entries({M15:900000,H1:3600000,H4:14400000}).map(([tf,w])=>[
   tf,Array.from({length:40},(_,i)=>{
    const p=100+i*.25;
    return {datetime:new Date(now-(40-i)*w).toISOString(),
     open:p,close:p+.16,high:p+.25,low:p-.08};
   })
  ]));
}
const snapshot={asOfUTC:AT,frames:frames()},plan={entry:110,stop:108,target:116,spread:.1};
const risk={slippage:.05,valuePerPoint:100,commissionPerLot:5};
const original=JSON.stringify(snapshot);
const good=inspect(snapshot,'BUY',plan,risk);
a.equal(JSON.stringify(snapshot),original,'no source mutation');
a.equal(good.status,'STRESS_DIAGNOSTIC_ONLY');
a.equal(good.candidateObserved,'BUY');
a.equal(good.scenarios.length,3);
a(good.scenarios[0].netRewardRisk>good.scenarios[2].netRewardRisk);
a(good.scenarios.every(x=>x.profitableAtFullTargetUnderAssumptions));
a(good.scenarios.every(x=>x.breakEvenWinRatePercent>0&&x.breakEvenWinRatePercent<100));
a.equal(good.postCostRiskQuality,'PASSED_SYNTHETIC_STRESS_ASSUMPTIONS_ONLY');
a.equal(good.exploratoryWarnings.length,0);
for(const flag of ['executable','paperOrdersAllowed','liveOrdersAllowed',
 'brokerCostsIndependentlyVerified','providerMarketDataRightsVerified',
 'brokerFillsAndStopsVerified','forwardProfitabilityEstablished',
 'tradePlanChanged'])a.equal(good[flag],false);
a.equal(good.signal,'WAIT');a.equal(good.effectOnFrozenCandidate,'NONE');
a.equal(good.empiricalWinProbability,null);a.equal(good.confidencePercent,null);
a.equal(good.providerRequestsMade,0);a.equal(good.ordersSent,0);
const thin=inspect(snapshot,'BUY',{...plan,target:110.7,spread:.3},
 {...risk,slippage:.2});
a.equal(thin.status,'STRESS_DIAGNOSTIC_ONLY');
a.equal(thin.postCostRiskQuality,'FRAGILE_UNDER_EXPLORATORY_RULES');
a(thin.exploratoryWarnings.includes('COST_STRESS_RR_BELOW_EXPLORATORY_FLOOR'));
const erased=inspect(snapshot,'BUY',{...plan,target:110.2,spread:.4},
 {...risk,slippage:.3});
a(erased.exploratoryWarnings.includes('COST_STRESS_ERASES_GROSS_REWARD'));
a.equal(erased.scenarios.at(-1).breakEvenWinRatePercent,null);
// An intrabar upper wick near the close is a descriptive rejection warning.
const wicked=structuredClone(snapshot);
wicked.frames.M15.at(-1).high+=1.5;
const wick=inspect(wicked,'BUY',plan,risk);
a(wick.exploratoryWarnings.includes('OPPOSING_M15_WICK_HIGH_FRACTION'));
const far=inspect(snapshot,'BUY',{...plan,entry:120,stop:118,target:126},risk);
a(far.exploratoryWarnings.includes('ENTRY_TOO_FAR_FROM_LAST_M15_CLOSE_VS_PRIOR_ATR'));
const wrong=inspect(snapshot,'SELL',plan,risk);
a.equal(wrong.status,'INSUFFICIENT_EVIDENCE');
a.equal(wrong.scenarios.length,0);
const sell={entry:110,stop:112,target:104,spread:.1};
const bear=structuredClone(snapshot);
for(const bar of bear.frames.M15){bar.open=bar.close;bar.close=bar.open-.05;}
const sells=inspect(bear,'SELL',sell,risk);
a.equal(sells.status,'STRESS_DIAGNOSTIC_ONLY');
a(sells.scenarios[0].netRewardRisk>sells.scenarios[2].netRewardRisk);
const unclosed=structuredClone(snapshot);
unclosed.frames.M15.push({...unclosed.frames.M15.at(-1),datetime:AT});
a.equal(inspect(unclosed,'BUY',plan,risk).status,'INSUFFICIENT_EVIDENCE');
const stale={...snapshot,asOfUTC:'2026-11-19T20:00:00Z'};
a.equal(inspect(stale,'BUY',plan,risk).status,'INSUFFICIENT_EVIDENCE');
const missingCosts=inspect(snapshot,'BUY',plan,{},);
a.equal(missingCosts.status,'INSUFFICIENT_EVIDENCE');
a.equal(missingCosts.postCostRiskQuality,'UNAVAILABLE');
const missing=inspect({},'BUY',plan,risk);
a.equal(missing.status,'INSUFFICIENT_EVIDENCE');
a.equal(inspect(snapshot,'NONE',plan,risk).candidateObserved,'NONE');
a.equal(THRESHOLDS.exploratoryMinStressRR,1.5);
const code=require('node:fs').readFileSync(require.resolve('./ultimate_entry_robustness'),'utf8');
a(!/\bfetch\s*\(/.test(code));a(!/\bWebSocket\b/.test(code));
a(!/process\.env/.test(code));
console.log('PASS: closed-only entry stress, 1x/1.5x/2x after-cost RR, wick, chasing, BUY/SELL, no lookahead or orders');
