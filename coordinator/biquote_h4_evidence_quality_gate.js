"use strict";
/**
 * Offline, sanitized XAUUSD H4 EVIDENCE ledger for a private 7-day collector.
 * It consumes only validated count reports; it cannot inspect candles,
 * prove individual last-H4 M15 coverage, authorize a data license, or trade.
 * "Fully covered" counts are UNORDERED. No inference of the latest H4's
 * coverage, individual first seen, broker costs or profitability is allowed.
 */
const WARMUP=21,PAPER=50,FRAMES=["M15","H1","H4"];
const int=x=>Number.isSafeInteger(x)&&x>=0&&x<=20000000;
const unknown=()=>({M15:null,H1:null,H4:null});
function blocked(reason){
 return {
  mode:"BIQUOTE_H4_EVIDENCE_QUALITY_LEDGER_COUNTS_ONLY",
  status:"BLOCKED",signal:"WAIT",executable:false,tradeEligible:false,
  paperOrdersAllowed:false,liveOrdersAllowed:false,brokerOrdersSent:0,
  providerRequestsMade:0,collectorRestarted:false,deployTriggered:false,
  sourceRightsVerified:false,independentBrokerSessionVerified:false,
  perCandleFirstSeenVerified:false,h4LatestConstituentsProven:false,
  brokerBidAskExecutionVerified:false,independentHoldoutValidated:false,
  storedClosed:unknown(),contiguousClosed:unknown(),h4FullyCoveredCompared:null,
  h4NotFullyCovered:null,h4FullyCoveredDisagreed:null,
  h4UnverifiedOrNotCompared:null,h4ContiguousVsCoveredNotJoinable:true,
  h4WarmupDeficit:null,h4PaperHistoryDeficit:null,
  maxPossibleContiguousH4ByCaptureEnd:null,
  blockers:["LEGACY_PER_BAR_FIRST_SEEN_UNAVAILABLE",
            "UPSTREAM_RIGHTS_AND_BROKER_SESSION_UNVERIFIED",
            "BID_ASK_FILL_COSTS_NOT_VERIFIED",
            "INDEPENDENT_OUT_OF_SAMPLE_PERFORMANCE_UNVERIFIED",reason]
 };
}
function assessEvidence(input){
 if(input?.origin!=="SANITIZED_STAGE3_AND_CAPTURE_HORIZON_UNATTESTED")
  return blocked("INVALID_AUDIT_ORIGIN");
 const s=input.stage3Consistency,h=input.h4CaptureHorizon;
 if(!s||s.status!=="CONSISTENT_COUNTS_ONLY_NOT_MARKET_PROOF"||
    s.signal!=="WAIT"||s.executable!==false||s.brokerOrdersSent!==0)
  return blocked("STAGE3_EVIDENCE_INCOMPLETE_OR_INVALID");
 if(!h||h.status!=="THEORETICAL_COUNT_CEILING_NOT_READINESS"||
    h.signal!=="WAIT"||h.executable!==false||h.brokerOrdersSent!==0||
    h.tradeEligible!==false||h.paperOrdersAllowed!==false||
    h.liveOrdersAllowed!==false||h.firstSeenVerified!==false||
    h.brokerRightsVerified!==false||h.brokerSessionCalendarVerified!==false||
    h.asOfUTC!==s.latestProgressAtUTC)
  return blocked("H4_CAPTURE_HORIZON_NOT_PROVEN_FROM_SAME_CYCLE");
 const stored=s.persistedClosed,tail=s.contiguousClosed,gaps=s.unclassifiedMissingSlots,
       compared=s.comparedClosed,notCovered=s.notFullyCoveredClosed,
       disagree=s.fullyCoveredDisagreements,
       ceiling=h.maximumPossibleContiguousClosed;
 if(!stored||!tail||!gaps||!compared||!notCovered||!disagree||!ceiling||
    FRAMES.some(tf=>!int(stored[tf])||!int(tail[tf])||
       tail[tf]>stored[tf]||!int(gaps[tf])||!int(ceiling[tf])||
       ceiling[tf]<tail[tf]||
       stored[tf]!==h.persistedClosedCounts?.[tf]||
       tail[tf]!==h.contiguousClosedCounts?.[tf])||
    !int(compared.H4)||!int(notCovered.H4)||!int(disagree.H4)||
    !int(compared.H1)||!int(notCovered.H1)||!int(disagree.H1)||
    compared.H4+notCovered.H4>stored.H4||
    compared.H1+notCovered.H1>stored.H1||
    disagree.H4>compared.H4||disagree.H1>compared.H1||
    ceiling.H4!==h.maxPossibleContiguousH4||
    h.paperH4HistoryReachableByWindowEnd!==(ceiling.H4>=PAPER)||
    h.theoreticalWarmupH4ReachableByWindowEnd!==(ceiling.H4>=WARMUP))
  return blocked("STAGE3_AND_CAPTURE_COUNTERS_CONTRADICT");
 const h4Unknown=stored.H4-compared.H4;
 const reasons=[];
 if(tail.H4<WARMUP)reasons.push("H4_CONTIGUOUS_TECHNICAL_WARMUP_SHORT");
 if(tail.H4<PAPER)reasons.push("H4_CONTIGUOUS_PAPER_HISTORY_SHORT");
 if(h4Unknown>0)reasons.push("H4_M15_OVERLAP_NOT_FULLY_VERIFIED");
 if(notCovered.H4>0)reasons.push("H4_EXAMINED_BARS_WITH_MISSING_M15_CONSTITUENTS");
 if(disagree.H4>0)reasons.push("H4_OHLC_M15_DISAGREEMENTS_REPORTED");
 if(gaps.M15>0||gaps.H1>0||gaps.H4>0)
  reasons.push("UNCLASSIFIED_CLOSED_FRAME_GAPS");
 if(ceiling.H4<PAPER)reasons.push("H4_50_BAR_HISTORY_UNREACHABLE_BY_CAPTURE_END");
 // This cannot establish the newest CLOSED H4 coverage, even if ALL
 // archived H4 bars are counted as fully covered by an untrusted log.
 reasons.push("LATEST_H4_M15_BAR_IDENTITY_NOT_PRESENT_IN_COUNT_LOGS");
 return {
  ...blocked("COUNT_LOGS_ARE_NOT_TRADE_EVIDENCE"),
  status:"NOT_READY_COUNT_ONLY",
  storedClosed:Object.fromEntries(FRAMES.map(tf=>[tf,stored[tf]])),
  contiguousClosed:Object.fromEntries(FRAMES.map(tf=>[tf,tail[tf]])),
  h4FullyCoveredCompared:compared.H4,
  h4NotFullyCovered:notCovered.H4,
  h4FullyCoveredDisagreed:disagree.H4,
  h4UnverifiedOrNotCompared:h4Unknown,
  h4WarmupDeficit:Math.max(0,WARMUP-tail.H4),
  h4PaperHistoryDeficit:Math.max(0,PAPER-tail.H4),
  maxPossibleContiguousH4ByCaptureEnd:ceiling.H4,
  stage3ReportAtUTC:s.latestProgressAtUTC,
  captureEndUTC:h.captureEndUTC,
  blockers:[...blocked("COUNT_LOGS_ARE_NOT_TRADE_EVIDENCE").blockers,...reasons]
 };
}
module.exports={assessEvidence};
if(require.main===module){
 let raw="";
 process.stdin.setEncoding("utf8");
 process.stdin.on("data",c=>{
  raw+=c;if(raw.length>65536){process.stderr.write("AUDIT_TOO_LARGE\n");process.exit(2);}
 });
 process.stdin.on("end",()=>{
  try{process.stdout.write(JSON.stringify(assessEvidence(JSON.parse(raw)))+"\n");}
  catch(_){process.stdout.write(JSON.stringify(blocked("INVALID_AUDIT_PAYLOAD"))+"\n");}
 });
}
