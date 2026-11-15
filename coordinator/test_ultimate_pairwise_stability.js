'use strict';
const a=require('node:assert/strict');
const crypto=require('node:crypto');
const {RULES}=require('./ultimate_filter_pairwise_audit');
const {inspect}=require('./ultimate_pairwise_stability');
const sha=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
const rows=[];
for(let i=0;i<4;i++){
 const h=String(i+1).padStart(2,'0');
 const at='2026-12-01T'+h+':00:00Z';
 rows.push({id:'candidate-'+i,signalUTC:at,
  entryUTC:'2026-12-01T'+h+':15:00Z',
  exitUTC:'2026-12-01T'+h+':45:00Z',
  side:'BUY',grossR:i%2? -1:2,
  costs:{spreadR:.1,slippageR:.1,commissionR:.1},
  atSignal:{regime:i%2?'CHOPPY':'DIRECTIONAL',
   directionConfirmedM15H1H4:true,liquidityConfirmedBeforeSignal:true,
   volatilityShock:false,highImpactEventWindow:false,dxyConsistent:true,
   gcConsistent:true,orderFlowConsistent:true,gcContractMatched:true,
   referenceSession:'LONDON',verifiedSessionCalendar:true,netRewardRiskAtSignal:2,
   featuresAvailableUTC:at,
   sourceEvidenceAvailableUTC:Object.fromEntries(
    ['DXY','GC','US02Y','US10Y','orderFlow','calendar','headlines'].map(k=>[k,at]))}});
}
const d={dataOrigin:'SYNTHETIC_TEST_ONLY',
 manifest:{rules:RULES,frozenEngine:'V3 Ultimate',
  filterFrozenUTC:'2026-11-15T00:00:00Z',
  holdoutStartUTC:'2026-12-01T00:00:00Z',
  holdoutEndUTC:'2026-12-01T06:00:00Z',
  asOfUTC:'2026-12-02T00:00:00Z',
  expectedCandidateCount:rows.length,
  sourceDescription:'SYNTHETIC ONLY NO LIVE PERFORMANCE',
  candidatesSHA256:sha(rows)},candidates:rows};
const before=JSON.stringify(d),x=inspect(d);
a.equal(JSON.stringify(d),before);
a.equal(x.originalCandidateCount,4);
a.equal(x.panels.length,2);
a.equal(x.panels[0].retained,1);
a.equal(x.panels[1].retained,1);
a.equal(x.panels[0].baselineNetR,.4);
a.equal(x.panels[0].shadowNetR,1.7);
a.equal(x.panels[1].baselineNetR,.4);
a.equal(x.panels[1].shadowNetR,1.7);
a.equal(x.descriptiveSameDirectionOfDelta,true);
a.equal(x.netPerformanceImprovementProven,false);
a.equal(x.smallSampleOrSelectionWarning,true);
a.equal(x.empiricalWinProbability,null);
a.equal(x.signal,'WAIT');a.equal(x.executable,false);
a.equal(x.providerRequestsMade,0);
const altered=structuredClone(d);altered.candidates[0].grossR=99;
a.throws(()=>inspect(altered),/BASELINE_CANDIDATE_SET_CHANGED/);
console.log('PASS fixed paired holdout chronological stability partitions, costs, integrity, no trading claims');
