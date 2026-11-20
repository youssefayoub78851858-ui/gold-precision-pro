'use strict';
const assert=require('node:assert/strict');
const {fixture}=require('./test_ultimate_v2');
const {evaluate}=require('./ultimate_v2'); // frozen v2 must remain as-is
const {assessPublicShadow}=require('./ultimate_v2_public_shadow');

function wait(report){
 assert.equal(report.mode,'ULTIMATE_V2_UNATTESTED_PUBLIC_SHADOW');
 assert.equal(report.signal,'WAIT');
 assert.equal(report.researchCandidate,'NONE');
 for(const flag of ['executable','paperOrdersAllowed','liveOrdersAllowed',
  'sourceRightsIndependentlyVerified','brokerCostsIndependentlyVerified',
  'prospectiveHoldoutIndependentlyVerified','credentialsUsed'])
  assert.equal(report[flag],false,flag);
 assert.equal(report.providerRequestsMade,0);
 assert.equal(report.brokerOrdersSent,0);
 assert.equal(report.engineVersion,2);
 assert.equal(report.originalFrozenEngineUnchanged,true);
 for(const secret of ['apiKey','password','bidPrice','askPrice','tradePlan',
  'entry','stopLoss','takeProfit','researchCandidateBUY','accountId'])
  assert.equal(Object.hasOwn(report,secret),false);
}
const unit=fixture('synthetic'),before=JSON.stringify(unit);
assert.equal(evaluate(unit).researchCandidate,'BUY'); // preserved frozen calculation
const shadow=assessPublicShadow(unit);wait(shadow);
assert.equal(shadow.syntheticFeedsPresent,true);
assert.equal(shadow.allSevenRecordedMode,false);
assert.equal(shadow.status,'WAIT_SYNTHETIC_SCENARIO_NOT_TRADING_EVIDENCE');
assert.equal(shadow.technicalPatternPresent,true);
assert.equal(shadow.frozenEngineCandidateWithheld,true);
assert.equal(shadow.contextFramesStructurallyReady,7);
assert.equal(JSON.stringify(unit),before);
assert.ok(!JSON.stringify(shadow).includes('BUY'));

const pretendReal=fixture('recorded');
const recorded=assessPublicShadow(pretendReal);wait(recorded);
assert.equal(recorded.allSevenRecordedMode,true);
assert.equal(recorded.syntheticFeedsPresent,false);
assert.equal(recorded.frozenEngineCandidateWithheld,true);
assert.equal(recorded.status,'WAIT_UNATTESTED_CONTEXT');
assert.ok(!JSON.stringify(recorded).includes('BUY'));

const mixed=fixture('recorded');mixed.feeds.GC.mode='synthetic';
const mixedResult=assessPublicShadow(mixed);wait(mixedResult);
assert.equal(mixedResult.syntheticFeedsPresent,true);
assert.equal(mixedResult.researchCandidate,'NONE');
const missing=fixture('recorded');delete missing.feeds.DXY;
const missingResult=assessPublicShadow(missing);wait(missingResult);
assert.equal(missingResult.allSevenRecordedMode,false);
assert.equal(missingResult.contextFramesStructurallyReady,6);

for(const payload of [null,undefined,3,'RAW_KEY',[],{}, {feeds:[]},
 {feeds:{US02Y:{apiKey:'SECRET'}},asOfUTC:'2026-11-10T12:00:00Z'}]){
 const report=assessPublicShadow(payload);wait(report);
 assert.ok(!JSON.stringify(report).includes('SECRET'));
 assert.equal(report.technicalPatternPresent,false);
}
// Every macro/news/order-flow layer is independently mandatory. Even a
// forged "recorded" mode, rights flag or valid-looking timestamp is never
// independent proof that a public BUY/SELL may be exposed.
for (const layer of ['US02Y','US10Y','DXY','GC','orderFlow','calendar','headlines']) {
 const missingLayer=fixture('recorded');
 delete missingLayer.feeds[layer];
 const missingReport=assessPublicShadow(missingLayer);wait(missingReport);
 assert.equal(missingReport.allSevenRecordedMode,false,layer);
 assert.equal(missingReport.contextFramesStructurallyReady,6,layer);
 const forged=fixture('recorded');
 forged.feeds[layer].rights={status:'VERIFIED_INTERNAL_RESEARCH',algorithmicResearchAuthorized:true};
 forged.feeds[layer].entitlementVerified=true;
 const forgedReport=assessPublicShadow(forged);wait(forgedReport);
 assert.equal(forgedReport.allSevenRecordedMode,true,layer);
 assert.ok(!JSON.stringify(forgedReport).includes('BUY'),layer);
}
const newsRisk=fixture('recorded');
newsRisk.feeds.calendar.events=[{id:'future-high-impact',timeUTC:'2026-11-10T12:15:00Z',publishedUTC:'2026-11-10T11:00:00Z',availableUTC:'2026-11-10T11:00:01Z',impact:'high'}];
assert.equal(evaluate(newsRisk).researchCandidate,'NONE');
assert.equal(evaluate(newsRisk).layers.calendar.blocked,true);
const newsRiskReport=assessPublicShadow(newsRisk);wait(newsRiskReport);
assert.equal(newsRiskReport.contextFramesStructurallyReady,7);
assert.ok(!JSON.stringify(newsRiskReport).includes('BUY'));

// Regression matrix: stale macro, mismatched GC contract, missing order-flow
// provenance, incomplete news coverage and emergency risk stop must all stay
// quarantined. These are offline fixtures, never market evidence.
const blockedScenarios={
 staleDXY:x=>{x.feeds.DXY.observedUTC='2026-11-10T11:50:00Z';},
 mismatchedGC:x=>{x.feeds.orderFlow.contract='GCG2027';},
 unlicensedOrderFlow:x=>{x.feeds.orderFlow.licensed=false;},
 newsContinuityLost:x=>{x.feeds.headlines.continuityVerified=false;},
 emergencyKillSwitch:x=>{x.risk.killSwitch=true;}
};
for(const [scenario,mutate] of Object.entries(blockedScenarios)){
 const x=fixture('recorded');mutate(x);
 assert.equal(evaluate(x).researchCandidate,'NONE',scenario);
 const result=assessPublicShadow(x);wait(result);
 assert.equal(result.researchCandidate,'NONE',scenario);
 assert.equal(result.brokerOrdersSent,0,scenario);
 assert.ok(!JSON.stringify(result).includes('BUY'),scenario);
 assert.ok(!JSON.stringify(result).includes('SELL'),scenario);
}

console.log('PASS frozen Ultimate v2 unchanged; public adapter suppresses all synthetic/spoofed recorded candidates and orders');
