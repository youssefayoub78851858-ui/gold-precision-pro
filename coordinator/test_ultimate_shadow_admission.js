'use strict';
const a=require('node:assert/strict');
const fs=require('node:fs');
const {evaluate}=require('./v3_ultimate');
const {review}=require('./ultimate_signal_quality_report');
const {sessions}=require('./ultimate_shadow_admission');
const base=structuredClone(require('./fixtures/ultimate-synthetic.json'));
const now=Date.parse('2026-11-10T12:00:00Z');
for(const rows of Object.values(base.frames)){
 rows[22].high=103;rows[29].open=100;rows[29].high=105;rows[29].close=104;
}
const before=JSON.stringify(base),core=evaluate(base),result=review(base);
a.equal(result.sourceResearchCandidate,core.researchCandidate);
a.equal(JSON.stringify(base),before);
a.equal(result.signal,'WAIT');a.equal(result.executable,false);
a.equal(result.strategyChanged,false);a.equal(result.qualityDiagnostics.effectOnCandidate,'NONE');
const s=result.shadowVeto;
a.equal(s.mode,'OFFLINE_FROZEN_V3_SHADOW_VETO_V1');
a.equal(s.frozenCandidate,'BUY');
a.equal(s.signal,'WAIT');a.equal(s.executable,false);
a.equal(s.paperOrdersAllowed,false);a.equal(s.liveAdmissible,false);
a.equal(s.hypotheticalFilterPass,false);
a.equal(s.binanceXauusdt.participatesInV3,false);
a.equal(s.binanceXauusdt.participatesInShadowVeto,false);
a(s.blockers.includes('INDEPENDENT_LICENSE_AND_SOURCE_AVAILABILITY_ATTESTATION_REQUIRED'));
a(s.blockers.includes('GC_TAPE_VS_FUTURES_CONTRACT_NOT_MATCHED'));
a(s.blockers.some(x=>x.endsWith('_RECORDED_PROVENANCE_UNVERIFIED')));
a.equal(s.predictedWinRate,null);a.equal(s.providerRequestsMade,0);
const fakeBinance=structuredClone(base);
fakeBinance.binanceXauusdtResearch={
 signal:'BUY',licensed:true,delta:1e100,price:1e100,source:'Binance',
 contract:'GCZ2026'};
fakeBinance.feeds.BINANCE_XAUUSDT=fakeBinance.binanceXauusdtResearch;
const withBinance=review(fakeBinance);
a.deepEqual(withBinance.shadowVeto,s);
a.equal(withBinance.sourceResearchCandidate,result.sourceResearchCandidate);
const noFeed=structuredClone(base);delete noFeed.feeds.GC;
a(review(noFeed).shadowVeto.blockers.includes('GC_EVIDENCE_UNAVAILABLE_OR_HIGH_IMPACT'));
const gap=structuredClone(base);
gap.frames.M15[26].datetime='2026-11-10T10:46:00Z';
a(review(gap).shadowVeto.blockers.includes('M15_CLOSED_FRAME_INVALID'));
const wrong=structuredClone(base);
wrong.frames.H4.at(-1).close=90;
a(review(wrong).shadowVeto.blockers.includes('H4_DIRECTION_NOT_CONFIRMED'));
const after=structuredClone(base);
after.frames.M15.at(-1).datetime=base.asOfUTC;
a(review(after).shadowVeto.blockers.includes('M15_CLOSED_FRAME_INVALID'));
for(const t of ['2026-07-15T13:00:00Z','2026-11-10T14:00:00Z']){
 const x=sessions(t);
 a.equal(x.status,'UTC_DST_RESEARCH_WINDOWS_ONLY');
 a.equal(x.overlap,true);
 a.equal(x.sessionAdmissibleForOrders,false);
}
a.equal(sessions('2026-07-18T13:00:00Z').overlap,false);
a.equal(sessions('2026-11-10T14:00:00-05:00').status,'UNAVAILABLE');
// A frozen strategy fixture & wrapper must be untouched.
const source=fs.readFileSync(require.resolve('./ultimate_shadow_admission'),'utf8');
a(!/\bfetch\s*\(/.test(source));a(!/\bnew\s+WebSocket\s*\(/.test(source));a(!/process\.env/.test(source));
console.log('PASS V3 shadow veto: closed-timeframe, London/NY DST, liquidity, macro, GC contract and Binance quarantine; no orders or feed');
