"use strict";
/**
 * Offline, privacy-safe four-stage readiness milestones.
 * A diagnostic summary, never a recommendation or order admission engine.
 * Inputs are existing point-in-time and count-only evidence reports.
 */
const MODE="GOLD_PRECISION_PRE_SIGNAL_MILESTONES_V1";
const START=Date.parse("2026-11-18T00:00:00Z");
const WIDTH=Object.freeze({M15:900000,H1:3600000,H4:14400000});
const FRAMES=Object.keys(WIDTH);
// A fully CLOSED H4 period spans 16 M15 and four H1 constituents.
// A claimed 21/50-H4 multi-frame milestone cannot rely on merely
// 21/50 M15 and H1 candle counts. This is a NECESSARY upper-bound
// check, not independent provenance or per-bar timestamp proof.
const H4_CONSTITUENTS=Object.freeze({M15:16,H1:4,H4:1});
const MIN_21=Object.freeze({M15:336,H1:84,H4:21});
const MIN_50=Object.freeze({M15:800,H1:200,H4:50});
const NUM=x=>Number.isSafeInteger(x)&&x>=0&&x<=20000000;
const ISO=/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/;
const utc=x=>typeof x==="string"&&ISO.test(x)&&Number.isFinite(Date.parse(x))&&
 new Date(x).toISOString().slice(0,19)===x.slice(0,19);
const hardWait=()=>({mode:MODE,signal:"WAIT",executable:false,
 recommendationAllowed:false,tradeEligible:false,paperOrdersAllowed:false,
 liveOrdersAllowed:false,brokerOrdersSent:0,providerRequestsMade:0,
 sourceRightsVerified:false,upstreamBrokerScheduleVerified:false,
 independentHoldoutValidated:false});
// Check the COMPLETE receipt counter contract, not just the H4 headline.
// A forged "50 H4" cannot pass when other frames or receipts are missing.
function validPointFrames(p){
 const asOf=Date.parse(p.asOfUTC);
 if(!Number.isFinite(asOf)||asOf<START)return false;
 return FRAMES.every(tf=>{
  const stored=p.storedClosedCounts?.[tf],
   observed=p.observedAtDecision?.[tf],
   legacy=p.legacyWithoutFirstSeen?.[tf],
   future=p.firstSeenAfterDecision?.[tf],
   tail=p.contiguousObservedClosed?.[tf],
   warm=p.technicalWarmupMissing?.[tf],
   paper=p.paperHistoryMissing?.[tf],
   maximum=Math.floor((asOf-START)/WIDTH[tf]);
  return [stored,observed,legacy,future,tail,warm,paper].every(NUM)&&
   stored<=maximum&&observed+legacy+future===stored&&tail<=observed&&
   warm===Math.max(0,21-tail)&&paper===Math.max(0,50-tail);
 });
}
function validCountLedger(q){
 if(q?.mode!=="BIQUOTE_H4_EVIDENCE_QUALITY_LEDGER_COUNTS_ONLY"||
    q?.status!=="NOT_READY_COUNT_ONLY"||
    q?.signal!=="WAIT"||q?.executable!==false||
    q?.tradeEligible!==false||q?.paperOrdersAllowed!==false||
    q?.perCandleFirstSeenVerified!==false||
    q?.h4LatestConstituentsProven!==false||
    q?.independentHoldoutValidated!==false||
    q?.sourceRightsVerified!==false||!utc(q?.stage3ReportAtUTC))
  return false;
 return FRAMES.every(tf=>NUM(q.storedClosed?.[tf])&&
   NUM(q.contiguousClosed?.[tf])&&
   q.contiguousClosed[tf]<=q.storedClosed[tf])&&
   [q.h4FullyCoveredCompared,q.h4NotFullyCovered,
    q.h4FullyCoveredDisagreed,q.h4UnverifiedOrNotCompared].every(NUM)&&
   q.h4FullyCoveredCompared+q.h4UnverifiedOrNotCompared===q.storedClosed.H4&&
   q.h4NotFullyCovered<=q.h4UnverifiedOrNotCompared&&
   q.h4FullyCoveredDisagreed<=q.h4FullyCoveredCompared&&
   q.h4WarmupDeficit===Math.max(0,21-q.contiguousClosed.H4)&&
   q.h4PaperHistoryDeficit===Math.max(0,50-q.contiguousClosed.H4);
}
function summarize(input){
 const p=input?.pointInTime,q=input?.countEvidence;
 const validPoint=p?.mode==="BIQUOTE_LOCAL_POINT_IN_TIME_DATA_GATE_V1"&&
  p?.signal==="WAIT"&&p?.executable===false&&p?.tradeEligible===false&&
  p?.paperOrdersAllowed===false&&p?.brokerOrdersSent===0&&
  p?.sourceRightsVerified===false&&p?.independentAvailabilityVerified===false&&
  ["LOCAL_GEOMETRY_ONLY_NOT_TRADE_READY","INSUFFICIENT_EVIDENCE"].includes(p?.status)&&
  utc(p?.asOfUTC)&&
  NUM(p?.contiguousObservedClosed?.H4)&&
  NUM(p?.technicalWarmupMissing?.H4)&&
  NUM(p?.paperHistoryMissing?.H4)&&
  p.technicalWarmupMissing.H4===Math.max(0,21-p.contiguousObservedClosed.H4)&&
  p.paperHistoryMissing.H4===Math.max(0,50-p.contiguousObservedClosed.H4)&&
  validPointFrames(p)&&NUM(p.warmupCrossFrameMatchedH4)&&
  p.warmupCrossFrameMatchedH4<=21;
 const validCounts=validCountLedger(q);
 const sameCycle=!!(validCounts&&validPoint&&q.stage3ReportAtUTC===p.asOfUTC&&
  FRAMES.every(tf=>q.storedClosed[tf]===p.storedClosedCounts[tf]&&
   q.contiguousClosed[tf]===p.contiguousObservedClosed[tf]));
 // When a separate count-only ledger IS supplied, it cannot disagree
 // with point-in-time receipts and still leave a positive "locally ready"
 // headline. Missing ledger is permissible only as an explicitly weaker
 // point-in-time-only diagnostic, never approval for trade execution.
 const ledgerProvided=q!==undefined;
 // A ledger with fewer than 21 M15-covered H4 comparisons cannot
 // corroborate a point report claiming 21 fully parity-matched H4 bars.
 // Aggregate overlap counts are UNORDERED: passing is necessary, not
 // sufficient to prove the latest 21 H4 or any vendor entitlement.
 const parityCountContradiction=!!(sameCycle&&
  p.warmupCrossFrameFullyVerified===true&&
  p.warmupCrossFrameMatchedH4===21&&q.h4FullyCoveredCompared<21);
 const ledgerConflict=ledgerProvided&&(!sameCycle||parityCountContradiction);
 const h4=validPoint?p.contiguousObservedClosed.H4:null;
 const enough21=!!(validPoint&&FRAMES.every(tf=>
   p.contiguousObservedClosed?.[tf]>=MIN_21[tf]));
 const enough50=!!(validPoint&&FRAMES.every(tf=>
   p.contiguousObservedClosed?.[tf]>=MIN_50[tf]));
 const local21=validPoint&&enough21&&!ledgerConflict&&
  FRAMES.every(tf=>p.technicalWarmupMissing?.[tf]===0)&&
  p.status==="LOCAL_GEOMETRY_ONLY_NOT_TRADE_READY"&&
  p.technicalWarmupMissing.H4===0&&p.warmupCrossFrameMatchedH4===21&&
  p.warmupCrossFrameFullyVerified===true&&
  p.localTimingAndParityCheck==="LOCAL_ONLY_NOT_INDEPENDENT"&&
  FRAMES.every(tf=>p.latestExpectedUTCGridClosedObservedAtDecision?.[tf]===true&&
   p.latestEligibleClosedObservedAtDecision?.[tf]===true)&&
  p.localGeometryObserved===true;
 const local50=local21&&enough50&&
  FRAMES.every(tf=>p.paperHistoryMissing?.[tf]===0);
 const stages=[
  {id:"SOURCE_RIGHTS_AND_SESSION",state:"EXTERNAL_EVIDENCE_REQUIRED",complete:false,
   reason:"BIQUOTE_PRIVATE_USE_PERMISSION_IS_NOT_UPSTREAM_BROKER_ATTESTATION"},
  {id:"CLOSED_HISTORY_AND_PARITY",state:ledgerConflict?
   "CONFLICTING_OR_INVALID_CROSS_REPORTS":
   local50?"LOCAL_50_H4_ONLY_NOT_MARKET_PROOF":
   local21?"LOCAL_21_H4_ONLY_PAPER_HISTORY_PENDING":
   validPoint?"LOCAL_H4_HISTORY_INCOMPLETE_OR_UNVERIFIED":"NO_VALID_POINT_IN_TIME_REPORT",
   complete:false,requiredTechnicalH4:21,requiredPaperH4:50,
   required21H4Constituents:{...MIN_21},
   required50H4Constituents:{...MIN_50},
   local21H4ConstituentCountsSufficient:enough21,
   local50H4ConstituentCountsSufficient:enough50,
   perBarConstituentIdentityNotAuthenticated:true,
   observedContiguousH4:h4,remainingToTechnicalH4:h4===null?null:Math.max(0,21-h4),
   remainingToPaperH4:h4===null?null:Math.max(0,50-h4),
   localWarmupCrossFrameVerified:local21,
   independentPerBarParityProven:false,countOnlyLedgerRecognized:validCounts,
   countLedgerProvided:ledgerProvided,countLedgerConflictsWithPointInTime:ledgerConflict,
   countLedgerParityShortfall:parityCountContradiction,
   h4ArchiveM15OverlapComparedCountOnly:sameCycle?q.h4FullyCoveredCompared:null,
   h4ArchiveM15ParityUnverifiedCountOnly:sameCycle?q.h4UnverifiedOrNotCompared:null,
   countLedgerSameDecisionCycle:sameCycle,countLedgerCanAuthorizeTrades:false},
  {id:"MACRO_GC_ORDER_FLOW",state:"REALTIME_PROVENANCE_AND_SYNC_UNVERIFIED",complete:false,
   reason:"NO_LICENSED_SYNCHRONIZED_DXY_YIELDS_GC_AND_NEWS_EVIDENCE"},
  {id:"PROSPECTIVE_PAPER_HOLDOUT",state:"UNTOUCHED_AFTER_COST_RESULTS_REQUIRED",complete:false,
   reason:"NO_INDEPENDENT_NET_OF_SPREAD_BROKER_COST_VALIDATION"}
 ];
 return {...hardWait(),asOfUTC:validPoint?
  p.asOfUTC:null,stages,completedStages:0,requiredStages:4,
  local21H4Observed:local21,local50H4Observed:local50,
  blockers:stages.map(x=>x.id)};
}
module.exports={summarize};
