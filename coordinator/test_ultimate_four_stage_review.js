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
a(ready.stages.analysis.entryRobustness,'frozen V3 review has independent stress report');
a.equal(ready.stages.analysis.entryRobustness.executable,false);
a.equal(ready.stages.analysis.entryRobustness.paperOrdersAllowed,false);
a.equal(ready.stages.analysis.entryRobustness.strategyChanged,false);
a.equal(ready.stages.analysis.entryRobustness.empiricalWinProbability,null);
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
   contract:"GCZ2026",
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
a.equal(alignedContext.gcTradeDepthCrossCheck.status,
 "GC_PAIR_UNAVAILABLE_OR_NOT_TIME_SUITABLE");
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
// Even paired GC-looking packets cannot confirm exchange activity when
// their futures contract labels disagree. They are offline metadata only.
const crossContract=structuredClone(context);
crossContract.items.GC_DEPTH={
 kind:"COMEX_GC_MBP_OR_MBO_NOT_CFD",
 contract:"GCG2027",
 observedUTC:"2026-11-20T05:59:10Z",
 firstAvailableUTC:"2026-11-20T05:59:11Z",
 receivedUTC:"2026-11-20T05:59:12Z"
};
const mismatch=reviewFourStages({
 dataOrigin:"SYNTHETIC_TEST_ONLY",snapshot:{...source,asOfUTC:clock},
 contextTimeEvidence:crossContract
});
const status=mismatch.stages.confirmation.externalContextTiming;
a.equal(status.status,"CONTEXT_TIMING_CONFLICTS");
a.equal(status.gcTradeDepthCrossCheck.status,"GC_CONTRACT_MISMATCH");
a.equal(status.contextCanAuthorizeTrading,false);
a.equal(status.sourceIndependentlyAttested,false);
a.equal(status.perLayer.GC_DEPTH.sourceQualified,false);
a.equal(mismatch.signal,"WAIT");
a.equal(mismatch.executable,false);
a.equal(mismatch.hypotheticalSyntheticPlan,null);
// A vendor-declared weekend research sequence may span missing CLOSED
// market slots, but must NEVER displace the strict UTC-grid data gate,
// attest an original broker, leak raw receipts or authorize trades.
const vendorAsOf="2026-11-23T09:00:00Z";
const vendorH4={
 origin:"UNATTESTED_VENDOR_NOV2026_H4_OPEN_AND_RECEIPT_TIMES_ONLY",
 asOfUTC:vendorAsOf,
 bars:[
  {openUTC:"2026-11-20T16:00:00Z",firstSeenClosedUTC:"2026-11-20T20:00:30Z"},
  {openUTC:"2026-11-20T20:00:00Z",firstSeenClosedUTC:"2026-11-22T23:01:00Z"},
  {openUTC:"2026-11-22T20:00:00Z",firstSeenClosedUTC:"2026-11-23T00:00:30Z"}
 ],
 brokerPermissionVerified:true,originalBrokerCalendarVerified:true,
 rawBid:98765.43,privateToken:"H4_SECRET_DO_NOT_EXPOSE"
};
const vendorView=reviewFourStages({
 dataOrigin:"RECORDED_UNVERIFIED",
 snapshot:{...source,asOfUTC:vendorAsOf},
 h4SessionTimeEvidence:vendorH4
});
const vendorResult=vendorView.stages.data.vendorConditionalH4Timing;
a.equal(vendorResult.mode,"BIQUOTE_VENDOR_SESSION_H4_OFFLINE_DIAGNOSTIC_V1");
a.equal(vendorResult.status,"VENDOR_CONDITIONAL_COUNTS_ONLY_NOT_TRADE_READY");
a.equal(vendorResult.decisionClockAligned,true);
a.equal(vendorResult.rawUtcGridTail,1);
a.equal(vendorResult.vendorConditionalSessionTail,3);
a.equal(vendorResult.providerDeclaredFullyClosedH4SlotsBridged,11);
a.equal(vendorResult.originalBrokerSessionCalendarVerified,false);
a.equal(vendorResult.sourceRightsVerified,false);
a.equal(vendorResult.canReplaceStrictDataGate,false);
a.equal(vendorResult.sessionTimesCanAuthorizeTrades,false);
a.equal(vendorView.stages.data.status,"BLOCKED");
a.equal(vendorView.signal,"WAIT");
a.equal(vendorView.executable,false);
a.equal(vendorView.paperOrdersAllowed,false);
a.equal(vendorView.hypotheticalSyntheticPlan,null);
a(!JSON.stringify(vendorResult).includes("H4_SECRET_DO_NOT_EXPOSE"));
a(!JSON.stringify(vendorResult).includes("98765.43"));
a(!JSON.stringify(vendorResult).includes("openUTC"));
a(!JSON.stringify(vendorResult).includes("firstSeenClosedUTC"));
const stalePacket=reviewFourStages({
 dataOrigin:"RECORDED_UNVERIFIED",snapshot:{...source,asOfUTC:clock},
 h4SessionTimeEvidence:vendorH4
});
a.equal(stalePacket.stages.data.vendorConditionalH4Timing.status,
 "NO_ALIGNED_H4_SESSION_TIMES");
a.equal(stalePacket.stages.data.vendorConditionalH4Timing.decisionClockAligned,false);
a.equal(stalePacket.signal,"WAIT");
const contaminated=structuredClone(vendorH4);
contaminated.bars[0].openPrice=12345678;
const contaminatedView=reviewFourStages({
 dataOrigin:"RECORDED_UNVERIFIED",snapshot:{...source,asOfUTC:vendorAsOf},
 h4SessionTimeEvidence:contaminated
});
a.equal(contaminatedView.stages.data.vendorConditionalH4Timing.status,"BLOCKED");
a(!JSON.stringify(contaminatedView).includes("12345678"));
a.equal(contaminatedView.signal,"WAIT");
console.log('PASS four-stage closed-only geometry, synthetic BUY entry/SL/TP, independent context veto, holdout/paper blockers, no lookahead or trade');
