'use strict';
const a=require('node:assert/strict');
const fs=require('node:fs');
const {run,modeled}=require('./ultimate_entry_v2_shadow_compare');
const two=[{
 signalIndex:2,exitIndex:4,entry:100,stop:99,grossR:2
},{
 signalIndex:5,exitIndex:7,entry:101,stop:100,grossR:-1
}];
const base=modeled(two,.4,.1,.07);
a.equal(base.closedTrades,2);
a.equal(base.modeledNetR,-.14);
a.equal(base.netWinningTrades,1);
a.equal(base.modeledWinRatePercent,50);
a.equal(base.brokerFillsVerified,false);
const double=modeled(two,.8,.2,.07);
a(double.modeledNetR<base.modeledNetR);
a.throws(()=>modeled([{entry:1,stop:1,grossR:2,exitIndex:2}],.4,.1,.07),
 /V2_BID_SHADOW_REJECTED_BAD_SIMULATED_TRADE/);
// Read only the old hash-locked public BID artifacts. Synthetic tests
// cannot assert a historical improvement in profit or accuracy.
const result=run();
a.equal(result.mode,'FROZEN_V2_BID_RECORDED_ENTRY_SHADOW_COMPARISON_V1');
a.equal(result.status,'DESCRIPTIVE_NONINDEPENDENT_AFTER_COST_MODEL_ONLY');
a.equal(result.months.length,2);
a.equal(result.v3UltimateComparisonPerformed,false);
for(const field of ['realBrokerBidAskExecutionVerified',
 'historicalSessionCalendarIndependentlyVerified','independentlyLicensedData',
 'independentProspectiveHoldout','statisticalSignificanceEstablished',
 'incrementalWinRateImprovementProven','profitabilityProven',
 'eligibleForPaperTrading','executable','paperOrdersAllowed','liveOrdersAllowed'])
 a.equal(result[field],false);
a.equal(result.signal,'WAIT');
a.equal(result.providerRequestsMade,0);
a.equal(result.brokerOrdersSent,0);
a.equal(result.baselineAndShadowNotIdenticalTradePaths,true);
for(const row of result.months){
 a(['2026-09','2026-10'].includes(row.month));
 a.equal(row.frozenV2OriginalCandidatesUnchanged,true);
 a.equal(row.baselineV2ResearchCandidates,
  row.shadowRetainedCandidates+row.shadowRejectedCandidates);
 a(row.scenarios.length===2);
 a(row.sameBaselineClosedTrades>=0);
 for(const s of row.scenarios){
  a(s.baselinePath.closedTrades>=s.sameBaselineClosedTradeSubset.closedTrades);
  a(s.shadowFilterPath.closedTrades<=row.shadowRetainedCandidates);
  a.equal(s.afterFilterPathMayAdmitDifferentOverlappingTrades,true);
 }
}
const source=fs.readFileSync(require.resolve('./ultimate_entry_v2_shadow_compare'),'utf8');
a(!/\bfetch\s*\(/.test(source));
a(!/\bWebSocket\b/.test(source));
a(!/process\.env/.test(source));
console.log('PASS old BID-only frozen V2 vs independent entry-stress comparison; two cost scenarios, candidate universe retained, no real expectancy, no orders');
