'use strict';
const a=require('node:assert/strict');
const {reviewFourStages,dataGeometry,ladder}=require('./ultimate_four_stage_review');
const source=structuredClone(require('./fixtures/ultimate-synthetic.json'));
for(const bars of Object.values(source.frames)){
  bars[22].high=103;
  bars[29].open=100;
  bars[29].high=105;
  bars[29].close=104;
}
const before=JSON.stringify(source);
const ready=reviewFourStages({dataOrigin:'SYNTHETIC_TEST_ONLY',snapshot:source});
a.equal(JSON.stringify(source),before);
a.equal(ready.signal,'WAIT');
a.equal(ready.executable,false);
a.equal(ready.paperOrdersAllowed,false);
a.equal(ready.liveOrdersAllowed,false);
a.equal(ready.providerRequestsMade,0);
a.equal(ready.alertsSent,0);
a.equal(ready.profitabilityProven,false);
a.equal(ready.stages.data.status,'GEOMETRY_ONLY');
a.equal(ready.stages.analysis.researchCandidate,'BUY');
a.equal(ready.stages.confirmation.status,'INDEPENDENT_CONTEXT_NOT_VERIFIED');
a.equal(ready.stages.confirmation.externalContextTiming.status,'NO_ALIGNED_CONTEXT_TIMES');
a.equal(ready.stages.confirmation.externalContextTiming.decisionClockAligned,false);
a.equal(ready.stages.confirmation.externalContextTiming.contextCanAuthorizeTrading,false);
a.equal(ready.stages.validation.status,'NEW_HOLDOUT_AND_EXECUTION_COSTS_NOT_VALIDATED');
a.equal(ready.stages.validation.independentNetExpectancy,null);
a.equal(ready.hypotheticalSyntheticPlan.direction,'BUY');
a.equal(ready.hypotheticalSyntheticPlan.tradeApproved,false);
const p=ready.hypotheticalSyntheticPlan;
a(p.stopLoss<p.entry&&p.entry<p.TP1&&p.TP1<p.TP2&&p.TP2<=p.TP3);
a(ready.shadowVetoCodes.includes('INDEPENDENT_LICENSE_AND_SOURCE_AVAILABILITY_ATTESTATION_REQUIRED'));
a.equal(ladder('SELL',{entry:100,stop:105,target:90,spread:.1}).TP3,90);
a.equal(ladder('SELL',{entry:100,stop:95,target:90,spread:.1}),null);
// Missing evidence must NEVER be converted into a signal or a fake context vote.
const noGC=structuredClone(source);delete noGC.feeds.GC;
const blocked=reviewFourStages({dataOrigin:'SYNTHETIC_TEST_ONLY',snapshot:noGC});
a.equal(blocked.hypotheticalSyntheticPlan,null);
a(blocked.stages.confirmation.blockedLayers.includes('GC'));
a(blocked.stages.analysis.reasons.includes('GC'));
// Corrupted/missing candle data and lookahead are blocked.
const future=structuredClone(source);future.frames.M15.at(-1).datetime=source.asOfUTC;
const futureOut=reviewFourStages({dataOrigin:'SYNTHETIC_TEST_ONLY',snapshot:future});
a.equal(futureOut.hypotheticalSyntheticPlan,null);
a(futureOut.stages.data.blockers.includes('M15_INVALID_OR_STALE_CLOSED_DATA'));
const gapped=structuredClone(source);gapped.frames.H1.splice(16,1);
const gap=reviewFourStages({dataOrigin:'SYNTHETIC_TEST_ONLY',snapshot:gapped});
a.equal(gap.hypotheticalSyntheticPlan,null);
a(gap.stages.data.blockers.includes('H1_SESSION_GAPS_UNVERIFIED'));
const badTime=reviewFourStages({dataOrigin:'SYNTHETIC_TEST_ONLY',snapshot:{...source,asOfUTC:'tomorrow'}});
a.equal(badTime.stages.data.status,'BLOCKED');
a.equal(badTime.signal,'WAIT');
a.equal(badTime.hypotheticalSyntheticPlan,null);
const missing=reviewFourStages({});
a.equal(missing.signal,'WAIT');
a.equal(missing.hypotheticalSyntheticPlan,null);
// Synthetic success is NEVER reusable as a real Buy/Sell candidate, even if
// a caller invents a licence flag, broker costs, or a fake paper performance.
const forged=reviewFourStages({dataOrigin:'RECORDED_UNVERIFIED',snapshot:{
 ...source,independentLicenseVerified:true,profitabilityProven:true}});
a.equal(forged.hypotheticalSyntheticPlan,null);
a.equal(forged.stages.analysis.researchCandidate,'NONE');
a.equal(forged.stages.confirmation.sourceRightsVerified,false);
a.equal(forged.stages.validation.paperFeedAdmissible,false);
const realClaim=reviewFourStages({dataOrigin:'LIVE_LICENSED',snapshot:source});
a.equal(realClaim.signal,'WAIT');
a.equal(realClaim.hypotheticalSyntheticPlan,null);
a.equal(realClaim.profitabilityProven,false);
a.equal(dataGeometry(source.frames,source.asOfUTC).state,'GEOMETRY_ONLY');
// An independent-looking chronology report from a DIFFERENT decision
// cannot be attributed to a particular frozen four-stage snapshot.
const clock="2026-11-20T06:00:00Z";
const context={
 origin:"UNATTESTED_SANITIZED_CONTEXT_TIMES_ONLY",
 decisionUTC:clock,asOfUTC:clock,
 items:{
  DXY:{kind:"INDEX_QUOTE_NOT_EXCHANGE_DXY",
   observedUTC:"2026-11-20T05:58:00Z",
   firstAvailableUTC:"2026-11-20T05:58:01Z",
   receivedUTC:"2026-11-20T05:58:02Z"},
  GC_TRADES:{kind:"COMEX_GC_EXCHANGE_TRADES_NOT_CFD",
   observedUTC:"2026-11-20T05:59:00Z",
   firstAvailableUTC:"2026-11-20T05:59:01Z",
   receivedUTC:"2026-11-20T05:59:02Z"}
 },token:"NEVER_SHARE_THIS",sourceRightsVerified:true
};
const crossedDecision=reviewFourStages({
 dataOrigin:"SYNTHETIC_TEST_ONLY",snapshot:source,
 contextTimeEvidence:context
});
a.equal(crossedDecision.stages.confirmation.externalContextTiming.status,
 'NO_ALIGNED_CONTEXT_TIMES');
a.equal(crossedDecision.stages.confirmation.externalContextTiming.decisionClockAligned,false);
const aligned=reviewFourStages({
 dataOrigin:"SYNTHETIC_TEST_ONLY",snapshot:{...source,asOfUTC:clock},
 contextTimeEvidence:context
});
const alignedContext=aligned.stages.confirmation.externalContextTiming;
a.equal(alignedContext.mode,"GOLD_EXTERNAL_CONTEXT_TIMING_PREFLIGHT_OFFLINE_V1");
a.equal(alignedContext.status,"INCOMPLETE_CONTEXT");
a.equal(alignedContext.decisionClockAligned,true);
a.equal(alignedContext.perLayer.DXY.timeSuitable,true);
a.equal(alignedContext.perLayer.GC_TRADES.timeSuitable,true);
a.equal(alignedContext.perLayer.GC_DEPTH.status,"MISSING");
a.equal(alignedContext.sourceIndependentlyAttested,false);
a.equal(alignedContext.contextCanAuthorizeTrading,false);
a.equal(aligned.stages.confirmation.sourceRightsVerified,false);
a.equal(aligned.signal,"WAIT");a.equal(aligned.executable,false);
a.equal(aligned.paperOrdersAllowed,false);
a.equal(aligned.hypotheticalSyntheticPlan,null);
a(!JSON.stringify(alignedContext).includes("NEVER_SHARE_THIS"));
a(!JSON.stringify(alignedContext).includes("sourceRightsVerified"));
const late=structuredClone(context);
late.items.GC_TRADES.receivedUTC="2026-11-20T06:00:05Z";
const contradicted=reviewFourStages({
 dataOrigin:"SYNTHETIC_TEST_ONLY",snapshot:{...source,asOfUTC:clock},
 contextTimeEvidence:late
});
a.equal(contradicted.stages.confirmation.externalContextTiming.status,
 "CONTEXT_TIMING_CONFLICTS");
a.equal(contradicted.stages.confirmation.externalContextTiming.perLayer.GC_TRADES.status,
 "INVALID_OR_LATE_RECEIPT");
a.equal(contradicted.signal,"WAIT");
console.log('PASS four-stage closed-only geometry, synthetic BUY entry/SL/TP, independent context veto, holdout/paper blockers, no lookahead or trade');
