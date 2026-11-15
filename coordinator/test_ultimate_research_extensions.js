'use strict';
const a=require('node:assert/strict');
const fs=require('node:fs');
const {regime,surprises,crossAssets,realYield,quality,inspect}=require('./ultimate_research_extensions');
const {evaluate}=require('./ultimate_v2');
const fake=structuredClone(JSON.parse(fs.readFileSync(__dirname+'/fixtures/ultimate-synthetic.json','utf8')));
const NOW='2026-11-10T12:00:00Z';
const sec=m=>m*60000;
function bars(tf,trend='UP',n=72){
 const minutes={M15:15,H1:60,H4:240}[tf];
 const now=Date.parse(NOW);
 const begin=now-n*sec(minutes);
 return Array.from({length:n},(_,i)=>{
  const val=3000+(trend==='UP'?i:trend==='DOWN'?-i:Math.sin(i)*.04);
  return {datetime:new Date(begin+i*sec(minutes)).toISOString(),open:val-.03,
   close:val,high:val+.5,low:val-.5};
 });
}
const frames={M15:bars('M15'),H1:bars('H1'),H4:bars('H4')};
const trend=regime(frames,NOW);
a.equal(trend.status,'DIAGNOSTIC_ONLY');a.equal(trend.marketRegime,'ALIGNED_TREND');
a.equal(trend.frames.M15.direction,'UP');
a.equal(trend.executable,false);a.equal(trend.confidence,'UNCALIBRATED_HEURISTIC');
const mixed={...frames,H4:bars('H4','DOWN')};
a.equal(regime(mixed,NOW).marketRegime,'MIXED_OR_TRANSITION');
const missing={...frames,H1:[]};
a.equal(regime(missing,NOW).status,'BLOCKED');
const future=structuredClone(frames);
future.M15.at(-1).datetime='2026-11-10T12:00:00Z';
a.equal(regime(future,NOW).status,'BLOCKED');
const gap=structuredClone(frames);
gap.M15.at(-3).datetime='2026-11-10T10:00:00Z';
a.equal(regime(gap,NOW).status,'BLOCKED');

const macro={sourceDataMode:'SYNTHETIC_TEST_ONLY',events:[{
 id:'test-cpi',kind:'CPI',units:'PERCENT_YOY',actual:3.2,consensus:3,previous:2.9,
 scheduledUTC:'2026-11-10T11:30:00Z',releasedUTC:'2026-11-10T11:30:01Z',
 availableUTC:'2026-11-10T11:30:02Z'}]};
const shock=surprises(macro,NOW);
a.equal(shock.events[0].surprise,0.2);
a.equal(shock.events[0].result,'ABOVE_CONSENSUS');
a.equal(shock.events[0].goldReaction,'NOT_OBSERVED');
a.equal(shock.directionalVote,false);
const late=structuredClone(macro);late.events[0].availableUTC='2026-11-10T12:00:01Z';
a.equal(surprises(late,NOW).status,'BLOCKED');
const forged={...macro,sourceDataMode:'LIVE_UNVERIFIED'};
a.equal(surprises(forged,NOW).status,'BLOCKED');
a.equal(surprises(undefined,NOW).status,'BLOCKED');
const double=structuredClone(macro);double.events.push(structuredClone(double.events[0]));
a.equal(surprises(double,NOW).status,'BLOCKED');
const prepublication=structuredClone(macro);
prepublication.events[0].releasedUTC='2026-11-10T11:29:59Z';
prepublication.events[0].availableUTC='2026-11-10T11:30:02Z';
a.equal(surprises(prepublication,NOW).status,'BLOCKED');
const zeroConsensus=structuredClone(macro);
zeroConsensus.events[0].consensus=0;
const z=surprises(zeroConsensus,NOW);
a.equal(z.events[0].surpriseRelativeToConsensus,null);
a.equal(z.directionalVote,false);a.equal(z.executable,false);
const overflow=structuredClone(macro);
overflow.events[0].actual=1e308;overflow.events[0].consensus=-1e308;
a.equal(surprises(overflow,NOW).status,'BLOCKED');

const nominal={instrument:'DGS10',value:4.25,observationDate:'2026-11-09',availableUTC:'2026-11-09T21:00:00Z'};
const tip={sourceDataMode:'SYNTHETIC_TEST_ONLY',series:'DFII10',frequency:'DAILY',
 observationDate:'2026-11-09',observedUTC:'2026-11-09T20:30:00Z',
 availableUTC:'2026-11-09T22:00:00Z',percent:1.9};
const tips=realYield(tip,nominal,{status:'READY'},NOW);
a.equal(tips.nominalMinusRealPercent,2.35);a.equal(tips.intradayEvidence,false);
a.equal(tips.directionalVote,false);
a.equal(realYield({...tip,availableUTC:'2026-11-10T12:01:00Z'},nominal,{status:'READY'},NOW).status,'BLOCKED');
a.equal(realYield(tip,{...nominal,observationDate:'2026-11-08'},{status:'READY'},NOW).status,'BLOCKED');
a.equal(realYield(tip,nominal,{status:'UNAVAILABLE'},NOW).status,'BLOCKED');

const layer=(s)=>({status:'READY',score:s,observedUTC:'2026-11-10T11:59:40Z',contract:'GCZ2026'});
const core={version:2,contractVersion:'ultimate-context-events-v2',signal:'WAIT',executable:false,networkEnabled:false,
 technical:{candidate:'BUY'},layers:{DXY:layer(1),GC:layer(1),orderFlow:layer(-1)}};
const contrast=crossAssets(core,NOW);
a.equal(contrast.status,'DIVERGENCE_DETECTED');
a.deepEqual(contrast.opposing,['orderFlow']);
a.equal(contrast.conservativeReviewCandidate,'NONE');
a.equal(contrast.executable,false);
const agrees=structuredClone(core);agrees.layers.orderFlow.score=1;
a.equal(crossAssets(agrees,NOW).status,'SYNTHETIC_ALIGNMENT_ONLY');
const different=structuredClone(core);different.layers.orderFlow.contract='GCG2027';
a.equal(crossAssets(different,NOW).status,'BLOCKED');
const delayed=structuredClone(core);delayed.layers.GC.observedUTC='2026-11-10T11:50:00Z';
a.equal(crossAssets(delayed,NOW).status,'BLOCKED');

const holdout={sourceDataMode:'SYNTHETIC_TEST_ONLY',frozenUTC:'2026-11-01T00:00:00Z',
 trades:[{id:'1',openedUTC:'2026-11-01T10:00:00Z',closedUTC:'2026-11-01T10:30:00Z',netR:2},
 {id:'2',openedUTC:'2026-11-01T11:00:00Z',closedUTC:'2026-11-01T11:30:00Z',netR:-1}]};
const perf=quality(holdout,NOW);
a.equal(perf.closedCount,2);a.equal(perf.winRatePercent,50);
a.equal(perf.netR,1);a.equal(perf.profitFactor,2);
a.equal(perf.maxDrawdownR,1);a.equal(perf.readyForStatisticalClaims,false);
a.equal(quality({...holdout,sourceDataMode:'REAL'},NOW).status,'BLOCKED');
const unseen=structuredClone(holdout);unseen.trades[1].closedUTC='2026-11-11T11:30:00Z';
a.equal(quality(unseen,NOW).status,'BLOCKED');
const duplicate=structuredClone(holdout);duplicate.trades[1].id='1';
a.equal(quality(duplicate,NOW).status,'BLOCKED');

fake.asOfUTC=NOW;
const coreReal=evaluate(fake);
const original=JSON.stringify(fake),result=inspect(fake,coreReal);
a.equal(result.mode,'OFFLINE_ULTIMATE_RESEARCH_EXTENSIONS');
a.equal(result.signal,'WAIT');a.equal(result.executable,false);
a.equal(result.predictedWinRate,null);a.equal(result.realDataSourcesActivated,0);
a.equal(result.economicSurprises.status,'BLOCKED');
a.equal(result.tips10Y.status,'BLOCKED');
a.equal(result.performance.status,'BLOCKED');
a.equal(result.spreadNoise.reasonCode,'CLOSED_BID_ASK_HISTORY_NOT_CONNECTED');
a.equal(JSON.stringify(fake),original);
a.throws(()=>inspect(fake,{...coreReal,signal:'BUY'}),/UNSAFE/);
const withSynthetic=structuredClone(fake);
withSynthetic.researchReview={releases:macro,tips10Y:tip,holdout};
const result2=inspect(withSynthetic,{...coreReal,layers:{...coreReal.layers,US10Y:{status:'READY'}}});
a.equal(result2.economicSurprises.eventCount,1);
a.equal(result2.performance.status,'SYNTHETIC_HOLDOUT_ARITHMETIC_ONLY');
a.equal(result2.signal,'WAIT');a.equal(result2.executable,false);
const moduleSource=fs.readFileSync(require.resolve('./ultimate_research_extensions'),'utf8');
a(!/new\s+WebSocket\s*\(/.test(moduleSource));
a(!/process\.env/.test(moduleSource));
a(!/\bfetch\s*\(/.test(moduleSource));
console.log('PASS research enrichment regime, surprise, cross-asset contradiction, daily TIPS, quarantined holdout; WAIT');
