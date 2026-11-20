"use strict";
const a=require("node:assert/strict");
const {summarize}=require("./biquote_pre_signal_milestones");
const START=Date.parse("2026-11-18T00:00:00Z");
const WIDTH={M15:900000,H1:3600000,H4:14400000};
const FRAMES=Object.keys(WIDTH);
const iso=t=>new Date(t).toISOString().replace(".000Z","Z");
function safe(x){
 a.equal(x.mode,"GOLD_PRECISION_PRE_SIGNAL_MILESTONES_V1");
 a.equal(x.signal,"WAIT");
 for(const k of ["executable","recommendationAllowed","tradeEligible",
  "paperOrdersAllowed","liveOrdersAllowed","sourceRightsVerified",
  "upstreamBrokerScheduleVerified","independentHoldoutValidated"])
  a.equal(x[k],false,k);
 a.equal(x.brokerOrdersSent,0);a.equal(x.providerRequestsMade,0);
 a.equal(x.completedStages,0);a.equal(x.requiredStages,4);
 a.equal(x.stages.length,4);
 a(x.stages.every(s=>s.complete===false));
 a(!JSON.stringify(x).includes("VERY_PRIVATE_QUOTE"));
}
const noData=summarize();safe(noData);
a.equal(noData.stages[1].remainingToTechnicalH4,null);
a.equal(noData.stages[1].state,"NO_VALID_POINT_IN_TIME_REPORT");
function point(h4,verified){
 // Plausible counter geometry only. Synthetic test metadata is never
 // actual market, broker-session, or receipt/profitability proof.
 const counts={M15:h4*16,H1:h4*4,H4:h4};
 const missing=Object.fromEntries(FRAMES.map(tf=>
  [tf,Math.max(0,21-counts[tf])]));
 const paper=Object.fromEntries(FRAMES.map(tf=>
  [tf,Math.max(0,50-counts[tf])]));
 const zero=Object.fromEntries(FRAMES.map(tf=>[tf,0]));
 const flags=Object.fromEntries(FRAMES.map(tf=>[tf,verified]));
 return {
  mode:"BIQUOTE_LOCAL_POINT_IN_TIME_DATA_GATE_V1",
  status:verified?"LOCAL_GEOMETRY_ONLY_NOT_TRADE_READY":"INSUFFICIENT_EVIDENCE",
  signal:"WAIT",executable:false,tradeEligible:false,paperOrdersAllowed:false,
  brokerOrdersSent:0,sourceRightsVerified:false,independentAvailabilityVerified:false,
  asOfUTC:iso(START+h4*WIDTH.H4+60000),
  storedClosedCounts:counts,observedAtDecision:counts,
  legacyWithoutFirstSeen:zero,firstSeenAfterDecision:zero,
  contiguousObservedClosed:counts,technicalWarmupMissing:missing,
  paperHistoryMissing:paper,
  warmupCrossFrameMatchedH4:verified?21:0,
  warmupCrossFrameFullyVerified:verified,
  localTimingAndParityCheck:verified?"LOCAL_ONLY_NOT_INDEPENDENT":"NOT_PROVEN",
  localGeometryObserved:verified,
  latestExpectedUTCGridClosedObservedAtDecision:flags,
  latestEligibleClosedObservedAtDecision:flags,
  privateQuote:"VERY_PRIVATE_QUOTE"
 };
}
const initial=summarize({pointInTime:point(11,false)});safe(initial);
a.equal(initial.stages[1].remainingToTechnicalH4,10);
a.equal(initial.stages[1].remainingToPaperH4,39);
a.equal(initial.local21H4Observed,false);
const warmup=summarize({pointInTime:point(21,true)});safe(warmup);
a.equal(warmup.local21H4Observed,true);
a.equal(warmup.local50H4Observed,false);
a.equal(warmup.stages[1].state,"LOCAL_21_H4_ONLY_PAPER_HISTORY_PENDING");
const fifty=summarize({pointInTime:point(50,true)});safe(fifty);
a.equal(fifty.local50H4Observed,true);
a.equal(fifty.stages[1].state,"LOCAL_50_H4_ONLY_NOT_MARKET_PROOF");
const forged=summarize({pointInTime:{...point(50,true),signal:"BUY",
 executable:true,sourceRightsVerified:true},countEvidence:{
 mode:"BIQUOTE_H4_EVIDENCE_QUALITY_LEDGER_COUNTS_ONLY",signal:"BUY",
 executable:true,tradeEligible:true},paperNetProfitable:true,allowTrade:true});
safe(forged);a.equal(forged.local50H4Observed,false);
// A single H4 count is insufficient evidence unless M15/H1 receipts,
// latest closed bars, point-in-time counters AND warmup parity agree.
function rejectPoint(p){
 const r=summarize({pointInTime:p});safe(r);
 a.equal(r.local21H4Observed,false);
 a.equal(r.local50H4Observed,false);
 return r;
}
rejectPoint({...point(50,true),asOfUTC:"2026-11-20T00:00:00Z"});
rejectPoint({...point(50,true),storedClosedCounts:{M15:799,H1:200,H4:50}});
rejectPoint({...point(50,true),observedAtDecision:{M15:799,H1:200,H4:50}});
rejectPoint({...point(50,true),legacyWithoutFirstSeen:{M15:1,H1:0,H4:0}});
rejectPoint({...point(50,true),firstSeenAfterDecision:{M15:1,H1:0,H4:0}});
rejectPoint({...point(50,true),contiguousObservedClosed:{M15:800,H1:19,H4:50}});
rejectPoint({...point(50,true),latestEligibleClosedObservedAtDecision:
 {M15:false,H1:true,H4:true}});
rejectPoint({...point(50,true),latestExpectedUTCGridClosedObservedAtDecision:
 {M15:true,H1:false,H4:true}});
rejectPoint({...point(50,true),warmupCrossFrameMatchedH4:20});
rejectPoint({...point(50,true),localTimingAndParityCheck:"NOT_PROVEN"});
rejectPoint({...point(50,true),status:"INSUFFICIENT_EVIDENCE"});
const pt=point(11,false);
const counts={mode:"BIQUOTE_H4_EVIDENCE_QUALITY_LEDGER_COUNTS_ONLY",
 status:"NOT_READY_COUNT_ONLY",signal:"WAIT",executable:false,
 tradeEligible:false,paperOrdersAllowed:false,
 perCandleFirstSeenVerified:false,h4LatestConstituentsProven:false,
 independentHoldoutValidated:false,sourceRightsVerified:false,
 stage3ReportAtUTC:pt.asOfUTC,
 storedClosed:pt.storedClosedCounts,contiguousClosed:pt.contiguousObservedClosed,
 h4WarmupDeficit:10,h4PaperHistoryDeficit:39,
 privateQuote:"VERY_PRIVATE_QUOTE"};
const countReport=summarize({pointInTime:pt,countEvidence:counts});
safe(countReport);a.equal(countReport.stages[1].countOnlyLedgerRecognized,true);
a.equal(countReport.stages[1].countLedgerSameDecisionCycle,true);
a.equal(countReport.stages[1].countLedgerProvided,true);
a.equal(countReport.stages[1].countLedgerConflictsWithPointInTime,false);
a.equal(countReport.stages[1].countLedgerCanAuthorizeTrades,false);
a.equal(countReport.stages[1].independentPerBarParityProven,false);
const mismatchedCount=summarize({pointInTime:pt,countEvidence:
 {...counts,stage3ReportAtUTC:iso(Date.parse(pt.asOfUTC)+1000)}});
safe(mismatchedCount);
a.equal(mismatchedCount.stages[1].countOnlyLedgerRecognized,true);
a.equal(mismatchedCount.stages[1].countLedgerSameDecisionCycle,false);
a.equal(mismatchedCount.stages[1].countLedgerConflictsWithPointInTime,true);
a.equal(mismatchedCount.stages[1].state,"CONFLICTING_OR_INVALID_CROSS_REPORTS");
const fakeCount=summarize({pointInTime:pt,countEvidence:
 {...counts,storedClosed:{...counts.storedClosed,H4:1000}}});
safe(fakeCount);
a.equal(fakeCount.stages[1].countLedgerSameDecisionCycle,false);
a.equal(fakeCount.stages[1].countLedgerConflictsWithPointInTime,true);
// Conflicting or invalid second ledger cannot inflate the headline to 21/50.
const pt21=point(21,true),pt50=point(50,true);
const ledgerFor=p=>({
 ...counts,stage3ReportAtUTC:p.asOfUTC,
 storedClosed:p.storedClosedCounts,
 contiguousClosed:p.contiguousObservedClosed,
 h4WarmupDeficit:Math.max(0,21-p.contiguousObservedClosed.H4),
 h4PaperHistoryDeficit:Math.max(0,50-p.contiguousObservedClosed.H4)
});
const cross21=summarize({pointInTime:pt21,
 countEvidence:{...ledgerFor(pt21),stage3ReportAtUTC:
   iso(Date.parse(pt21.asOfUTC)+1000)}});
safe(cross21);a.equal(cross21.local21H4Observed,false);
a.equal(cross21.stages[1].state,"CONFLICTING_OR_INVALID_CROSS_REPORTS");
a.equal(cross21.stages[1].countLedgerConflictsWithPointInTime,true);
const cross50=summarize({pointInTime:pt50,
 countEvidence:{...ledgerFor(pt50),
   storedClosed:{...pt50.storedClosedCounts,H4:51}}});
safe(cross50);a.equal(cross50.local50H4Observed,false);
a.equal(cross50.stages[1].state,"CONFLICTING_OR_INVALID_CROSS_REPORTS");
const malformed=summarize({pointInTime:pt50,
 countEvidence:{...ledgerFor(pt50),tradeEligible:true}});
safe(malformed);a.equal(malformed.local50H4Observed,false);
a.equal(malformed.stages[1].countLedgerConflictsWithPointInTime,true);
const goodPair=summarize({pointInTime:pt50,countEvidence:ledgerFor(pt50)});
safe(goodPair);
a.equal(goodPair.local50H4Observed,true);
a.equal(goodPair.stages[1].countLedgerSameDecisionCycle,true);
// A forged H4-ready point summary with M15/H1 too short cannot claim
// multiframe EMA warmup or 50-H4 paper history.
const shortM15=point(50,true);
shortM15.storedClosedCounts.M15=10;
shortM15.observedAtDecision.M15=10;
shortM15.contiguousObservedClosed.M15=10;
shortM15.technicalWarmupMissing.M15=11;
shortM15.paperHistoryMissing.M15=40;
const overclaim=summarize({pointInTime:shortM15});
safe(overclaim);a.equal(overclaim.local21H4Observed,false);
a.equal(overclaim.local50H4Observed,false);
const shortPaper=point(50,true);
shortPaper.storedClosedCounts.H1=30;
shortPaper.observedAtDecision.H1=30;
shortPaper.contiguousObservedClosed.H1=30;
shortPaper.technicalWarmupMissing.H1=0;
shortPaper.paperHistoryMissing.H1=20;
const noPaper=summarize({pointInTime:shortPaper});
safe(noPaper);a.equal(noPaper.local21H4Observed,true);
a.equal(noPaper.local50H4Observed,false);
const inconsistent=summarize({pointInTime:{...point(50,true),
 paperHistoryMissing:{...point(50,true).paperHistoryMissing,H4:30}}});
safe(inconsistent);a.equal(inconsistent.stages[1].observedContiguousH4,null);
const injected=summarize({pointInTime:{...point(21,true),asOfUTC:"VERY_PRIVATE_QUOTE"}});
safe(injected);a.equal(injected.asOfUTC,null);
console.log("PASS fail-closed four-stage milestone: all timeframes, receipt sums, impossible as-of, latest slots, no private data or trades");
