"use strict";
const a=require("node:assert/strict");
const {summarize}=require("./biquote_pre_signal_milestones");
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
function point(h4,verified){return {
 mode:"BIQUOTE_LOCAL_POINT_IN_TIME_DATA_GATE_V1",status:"LOCAL_GEOMETRY_ONLY_NOT_TRADE_READY",
 signal:"WAIT",executable:false,tradeEligible:false,paperOrdersAllowed:false,
 brokerOrdersSent:0,sourceRightsVerified:false,independentAvailabilityVerified:false,
 asOfUTC:"2026-11-20T00:00:00Z",contiguousObservedClosed:{H4:h4},
 technicalWarmupMissing:{H4:Math.max(0,21-h4)},
 paperHistoryMissing:{H4:Math.max(0,50-h4)},
 warmupCrossFrameFullyVerified:verified,localGeometryObserved:verified,
 latestExpectedUTCGridClosedObservedAtDecision:{H4:verified},
 latestEligibleClosedObservedAtDecision:{H4:verified},
 privateQuote:"VERY_PRIVATE_QUOTE"
};}
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
const counts={mode:"BIQUOTE_H4_EVIDENCE_QUALITY_LEDGER_COUNTS_ONLY",
 signal:"WAIT",executable:false,tradeEligible:false,
 perCandleFirstSeenVerified:false,h4LatestConstituentsProven:false,
 independentHoldoutValidated:false,sourceRightsVerified:false,
 privateQuote:"VERY_PRIVATE_QUOTE"};
const countReport=summarize({pointInTime:point(11,false),countEvidence:counts});
safe(countReport);a.equal(countReport.stages[1].countOnlyLedgerRecognized,true);
a.equal(countReport.stages[1].independentPerBarParityProven,false);
const inconsistent=summarize({pointInTime:{...point(50,true),
 paperHistoryMissing:{H4:30}}});
safe(inconsistent);a.equal(inconsistent.stages[1].observedContiguousH4,null);
console.log("PASS four-stage milestone report: counted H4 receipts, no private prices, no BUY SELL or paper/live orders");
