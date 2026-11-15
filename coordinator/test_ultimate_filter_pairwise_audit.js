'use strict';
const a=require('node:assert/strict');
const crypto=require('node:crypto'),fs=require('node:fs');
const {RULES,DECISION_CODES,audit}=require('./ultimate_filter_pairwise_audit');
const sha=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
const holdout='2026-12-01T00:00:00Z',freeze='2026-11-15T00:00:00Z';
function stamp(hour){return '2026-12-01T'+String(hour).padStart(2,'0')+':00:00Z';}
function candidate(i,gross,spread,failKey){
 const f={
  regime:'DIRECTIONAL',directionConfirmedM15H1H4:true,
  liquidityConfirmedBeforeSignal:true,volatilityShock:false,
  highImpactEventWindow:false,dxyConsistent:true,gcConsistent:true,
  orderFlowConsistent:true,gcContractMatched:true,referenceSession:'LONDON',
  verifiedSessionCalendar:true,netRewardRiskAtSignal:2,
  featuresAvailableUTC:stamp(i),sourceEvidenceAvailableUTC:Object.fromEntries(['DXY','GC','US02Y','US10Y','orderFlow','calendar','headlines'].map(k=>[k,stamp(i)]))
 };
 if(failKey==='regime')f.regime='CHOPPY';
 if(failKey==='news')f.highImpactEventWindow=true;
 const row={id:'candidate-'+i,signalUTC:stamp(i),entryUTC:'2026-12-01T'+String(i).padStart(2,'0')+':15:00Z',
  exitUTC:'2026-12-01T'+String(i).padStart(2,'0')+':45:00Z',side:i%2?'BUY':'SELL',
  grossR:gross,costs:{spreadR:spread,slippageR:.05,commissionR:.05},atSignal:f};
 return row;
}
const rows=[candidate(1,2.1,.1),candidate(2,-.9,.1,'regime'),
 candidate(3,3.1,.1),candidate(4,-1.9,.1,'news')];
function doc(origin='SYNTHETIC_TEST_ONLY'){
 return {dataOrigin:origin,manifest:{rules:RULES,frozenEngine:'V3 Ultimate',
  filterFrozenUTC:freeze,holdoutStartUTC:holdout,holdoutEndUTC:stamp(5),
  asOfUTC:'2026-12-02T00:00:00Z',expectedCandidateCount:rows.length,
  sourceDescription:'SYNTHETIC MATH TEST, NOT A MARKET BACKTEST',
  candidatesSHA256:sha(rows)},candidates:structuredClone(rows)};
}
const d=doc(),snapshot=JSON.stringify(d),r=audit(d);
a.equal(r.mode,'OFFLINE_PAIRED_QUALITY_FILTER_AUDIT');
a.equal(r.baseline.candidates,4);a.equal(r.shadowFiltered.candidates,2);
a.equal(r.suppressedCandidates,2);
a.equal(r.blockingCodeCounts.NOT_DIRECTIONAL,1);
a.equal(r.blockingCodeCounts.HIGH_IMPACT_NEWS,1);
a.equal(r.baseline.netR,1.6);
a.equal(r.shadowFiltered.netR,4.8);
a.equal(r.deltaNetR,3.2);
a.equal(r.baseline.roundTripCostR,.8);
a.equal(r.shadowFiltered.roundTripCostR,.4);
a.equal(r.baseline.winRatePercent,50);
a.equal(r.baseline.maxDrawdownR,2.1);
a.equal(r.statisticalSignificanceEstablished,false);
a.equal(r.netPerformanceImprovementProven,false);
a.equal(r.signal,'WAIT');a.equal(r.executable,false);a.equal(r.paperOrdersAllowed,false);
a.equal(r.dataLicensingIndependentlyVerified,false);
a.equal(r.identicalFrozenCandidateSetIndependentlyRegenerated,false);
a.equal(r.decisionTimeFeaturesIndependentlyAttested,false);
a.equal(r.providerRequestsMade,0);a.equal(r.ordersSent,0);
a.equal(JSON.stringify(d),snapshot);
const local=audit(doc('LOCAL_RECORDED_RESEARCH_UNVERIFIED'));
a.equal(local.netPerformanceImprovementProven,false);
a.equal(local.dataLicensingIndependentlyVerified,false);
a.equal(local.signal,'WAIT');
const bad=(patch,regex)=>{const copy=doc();patch(copy);if(!regex)copy.manifest.candidatesSHA256=sha(copy.candidates);
 a.throws(()=>audit(copy),regex||/PAIRED_AUDIT_REJECTED_/);};
bad(x=>{x.candidates[0].atSignal.regime='CHOPPY';},/BASELINE_CANDIDATE_SET_CHANGED/);
bad(x=>{x.candidates[0].atSignal.featuresAvailableUTC='2026-12-01T01:00:01Z';},null);
bad(x=>{x.candidates[0].atSignal.sourceEvidenceAvailableUTC.GC='2026-12-01T01:15:00Z';},null);
bad(x=>{x.candidates[0].atSignal.sourceEvidenceAvailableUTC.GC='2026-12-01T00:54:59Z';},/INTRADAY_CROSS_MARKET_EVIDENCE_STALE/);
bad(x=>{x.candidates[0].atSignal.sourceEvidenceAvailableUTC.GC='2026-12-01T00:59:00Z';},null);
bad(x=>{x.candidates[0].atSignal.sourceEvidenceAvailableUTC.GC='2026-12-01T00:58:59Z';},/INTRADAY_CROSS_MARKET_EVIDENCE_SKEW/);
bad(x=>{x.candidates[0].atSignal.sourceEvidenceAvailableUTC.US10Y='2026-11-30T21:00:00Z';},null);
bad(x=>{delete x.candidates[0].atSignal.sourceEvidenceAvailableUTC.headlines;},null);
bad(x=>{x.candidates[0].atSignal.highImpactEventWindow='not certain';},null);
bad(x=>{x.candidates[0].signalUTC='2026-12-01T01:10:00Z';},null);
bad(x=>{x.candidates[0].exitUTC='2026-12-01T01:10:00Z';},null);
bad(x=>{x.candidates[0].costs.spreadR=-1;},null);
bad(x=>{x.candidates[1].id=x.candidates[0].id;},null);
bad(x=>{x.candidates.splice(1,1);},/BASELINE_CANDIDATE_UNIVERSE_COUNT_MISMATCH/);
bad(x=>{x.manifest.filterFrozenUTC='2026-12-02T00:00:00Z';},/FROZEN_HOLDOUT_WINDOW_INVALID/);
bad(x=>{x.manifest.rules='POSTHOC_OPTIMIZED';},/FROZEN_PLAN_AND_HASH_MANIFEST_MISSING/);
a(DECISION_CODES.includes('COST_ADJUSTED_RR_LOW'));
const source=fs.readFileSync(require.resolve('./ultimate_filter_pairwise_audit'),'utf8');
a(!/\bfetch\s*\(/.test(source));a(!/\bnew\s+WebSocket\s*\(/.test(source));a(!/process\.env/.test(source));
console.log('PASS paired baseline vs fixed filter math, costs, complete candidate set hash, as-of availability, freeze, no-lookahead and safety flags');
