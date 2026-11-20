'use strict';
// Fabricated unit evidence only; never archived market performance.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {ROLES,INSTRUMENTS,issues,assessLayer,selectKnown}=require('./ultimate_v2_contracts');
const {evaluate}=require('./ultimate_v2');
const now='2026-11-10T12:00:00Z';
function fixture(mode='synthetic'){
 const base=structuredClone(require('./fixtures/ultimate-synthetic.json'));
 for(const rows of Object.values(base.frames)){rows[22].high=103;rows[29].high=105;rows[29].close=104;}
 const feeds={};
 for(const name of Object.keys(ROLES)){
  feeds[name]={schemaVersion:2,role:ROLES[name],instrument:INSTRUMENTS[name],mode,source:'FABRICATED UNIT EVIDENCE ONLY',availabilityEvidence:'UNIT RECEIPT',observedUTC:now,availableUTC:now,rights:{status:'VERIFIED_INTERNAL_RESEARCH',evidenceReference:'UNIT ATTESTATION',algorithmicResearchAuthorized:true},entitlementVerified:true};
 }
 for(const name of ['DXY','GC'])Object.assign(feeds[name],{previous:100,value:name==='DXY'?99:101,previousObservedUTC:'2026-11-10T11:57:00Z',previousAvailableUTC:'2026-11-10T11:57:01Z'});
 for(const name of ['US02Y','US10Y'])Object.assign(feeds[name],{frequency:'DAILY',units:'PERCENT_PER_ANNUM',value:4.2,previous:4.1,observationDate:'2026-11-09',observedUTC:'2026-11-09T20:30:00Z',availableUTC:'2026-11-09T21:15:00Z',previousObservationDate:'2026-11-06',previousObservedUTC:'2026-11-06T20:30:00Z',previousAvailableUTC:'2026-11-06T21:15:00Z',nextExpectedReleaseUTC:'2026-11-10T21:15:00Z',releaseScheduleAvailableUTC:'2026-11-01T00:00:00Z',releaseScheduleReference:'UNIT RELEASE CALENDAR'});
 Object.assign(feeds.GC,{contract:'GCZ2026',referenceContract:'GCZ2026',priceConvention:'TRADE',contractExpiryUTC:'2026-12-20T00:00:00Z'});
 Object.assign(feeds.orderFlow,{kind:'trades',sideMethod:'EXCHANGE_AGGRESSOR',licensed:true,sequenceGapCount:0,buyVolume:80,sellVolume:20,contract:'GCZ2026',contractExpiryUTC:'2026-12-20T00:00:00Z',windowStartUTC:'2026-11-10T11:59:00Z',windowEndUTC:now});
 Object.assign(feeds.calendar,{scope:'USD_MATERIAL_SCHEDULED',coverageEvidenceReference:'UNIT SCHEDULE',coverageStartUTC:'2026-11-10T11:00:00Z',coverageEndUTC:'2026-11-10T14:00:00Z',nextReviewUTC:'2026-11-10T13:00:00Z',events:[]});
 Object.assign(feeds.headlines,{scope:'USD_GOLD_MATERIAL_NEWS',coverageEvidenceReference:'UNIT MONITOR RECEIPT',continuityVerified:true,coverageStartUTC:'2026-11-10T11:30:00Z',coverageEndUTC:now,events:[]});
 return {...base,asOfUTC:now,feeds};
}
function run(){
 const input=fixture(),before=JSON.stringify(input),p=evaluate(input);
 assert.equal(p.version,2);assert.equal(p.researchCandidate,'BUY');assert.equal(p.signal,'WAIT');assert.equal(p.executable,false);
 assert.equal(p.layers.US02Y.directionalVote,false);assert.ok(p.layers.US02Y.ageSeconds>300);
 assert.equal(p.layers.US02Y.observedUTC,'2026-11-09T20:30:00Z');assert.equal(JSON.stringify(input),before);
 assert.equal(p.legacyComparison.version,1);assert.ok(p.legacyComparison.blockers.includes('US02Y'));
 assert.deepEqual(p,evaluate(input));
 for(const name of Object.keys(ROLES)){const missing=fixture();delete missing.feeds[name];assert.equal(evaluate(missing).researchCandidate,'NONE');}
 const daily=input.feeds.US02Y;
 assert.equal(assessLayer('US02Y',daily,'2026-11-10T21:14:59Z').status,'READY');
 assert.equal(assessLayer('US02Y',daily,'2026-11-10T21:15:00Z').reason,'DAILY_CONTEXT_EXPIRED');
 assert.equal(assessLayer('US02Y',daily,'2026-11-09T21:14:59Z').reason,'NOT_AVAILABLE_AT_DECISION');
 assert.ok(issues('US02Y',{...daily,observedUTC:now,availableUTC:now}).includes('DAILY_IDENTITY'));
 assert.ok(issues('US02Y',{...daily,previousAvailableUTC:'2026-11-11T00:00:00Z'}).includes('REFERENCE_VINTAGE_UNAVAILABLE'));
 assert.ok(issues('US02Y',{...daily,nextExpectedReleaseUTC:'2027-01-01T00:00:00Z'}).includes('RELEASE_SCHEDULE_UNVERIFIED'));
 const revised={...daily,availableUTC:'2026-11-10T13:00:00Z',value:4.3};
 assert.equal(selectKnown({US02Y:[daily,revised]},now).US02Y.value,4.2);
 assert.equal(selectKnown({US02Y:[daily,revised]},'2026-11-10T13:00:00Z').US02Y.value,4.3);
 const older={...daily,observationDate:'2026-11-08',observedUTC:'2026-11-08T20:30:00Z',availableUTC:'2026-11-10T13:00:00Z',value:4.9};
 assert.equal(selectKnown({US02Y:[daily,older]},'2026-11-10T13:00:00Z').US02Y.value,4.2);
 assert.throws(()=>selectKnown({US02Y:[daily,daily]},now),/DUPLICATE/);
 assert.equal(selectKnown({US02Y:[older,revised]},'2026-11-10T13:00:00Z').US02Y.value,4.3);
 const calendarUpdate={...daily,releaseScheduleAvailableUTC:'2026-11-10T13:00:00Z',nextExpectedReleaseUTC:'2026-11-11T21:15:00Z'};
 assert.equal(selectKnown({US02Y:[daily,calendarUpdate]},now).US02Y.nextExpectedReleaseUTC,daily.nextExpectedReleaseUTC);
 const knownUpdate=selectKnown({US02Y:[daily,calendarUpdate]},'2026-11-10T14:00:00Z').US02Y;
 assert.equal(knownUpdate.availableUTC,daily.availableUTC);
 assert.equal(assessLayer('US02Y',knownUpdate,'2026-11-10T22:00:00Z').status,'READY');
 assert.equal(assessLayer('US02Y',calendarUpdate,now).reason,'RELEASE_SCHEDULE_NOT_AVAILABLE');
 assert.throws(()=>selectKnown({US02Y:[daily,{...calendarUpdate,value:8}]},'2026-11-10T14:00:00Z'),/CONFLICTING_DAILY/);
 const future=fixture();future.feeds.calendar.events=[{id:'unit-event',timeUTC:'2026-11-10T12:15:00Z',publishedUTC:'2026-11-10T11:00:00Z',availableUTC:'2026-11-10T11:00:01Z',impact:'high'}];
 assert.equal(evaluate(future).researchCandidate,'NONE');assert.equal(evaluate(future).layers.calendar.blocked,true);
 future.feeds.calendar.events[0].availableUTC='2026-11-10T12:01:00Z';assert.equal(evaluate(future).layers.calendar.status,'UNAVAILABLE');
 const late=fixture();late.feeds.headlines.events=[{id:'late-arrival',publishedUTC:'2026-11-10T11:00:00Z',availableUTC:'2026-11-10T11:50:00Z',impact:'high'}];
 assert.equal(evaluate(late).layers.headlines.blocked,true);assert.equal(evaluate(late).researchCandidate,'NONE');
 const unknown=fixture();unknown.feeds.headlines.events=[{id:'future',publishedUTC:'2026-11-10T12:01:00Z',availableUTC:'2026-11-10T12:01:00Z',impact:'high'}];
 assert.equal(evaluate(unknown).layers.headlines.status,'UNAVAILABLE');
 const gap=fixture();gap.feeds.headlines.coverageEndUTC='2026-11-10T11:58:59Z';assert.equal(evaluate(gap).researchCandidate,'NONE');
 const restampedNews=fixture();restampedNews.feeds.headlines.observedUTC='2026-11-10T11:00:00Z';assert.equal(evaluate(restampedNews).researchCandidate,'NONE');
 const badUTC=fixture();badUTC.feeds.DXY.observedUTC='2026-02-30T12:00:00Z';assert.ok(issues('DXY',badUTC.feeds.DXY).length);
 const noContinuity=fixture();noContinuity.feeds.headlines.continuityVerified=false;assert.equal(evaluate(noContinuity).layers.headlines.status,'UNAVAILABLE');
 const mismatch=fixture();mismatch.feeds.US10Y={...older,availableUTC:daily.availableUTC,role:'DAILY_CONTEXT',instrument:'DGS10'};assert.ok(evaluate(mismatch).monitoring.blocked.includes('dailyContext: different observation dates'));
 const skew=fixture();skew.feeds.GC.observedUTC='2026-11-10T11:58:59Z';assert.ok(evaluate(skew).monitoring.blocked.includes('intraday: observation skew'));
 const contract=fixture();contract.feeds.orderFlow.contract='GCG2027';assert.ok(evaluate(contract).monitoring.blocked.includes('intraday: GC contract mismatch'));
 const staleReference=fixture();staleReference.feeds.DXY.previousObservedUTC='2026-11-09T11:00:00Z';assert.equal(evaluate(staleReference).researchCandidate,'NONE');
 const oldWindow=fixture();oldWindow.feeds.orderFlow.windowEndUTC='2026-11-09T12:00:00Z';assert.equal(evaluate(oldWindow).researchCandidate,'NONE');
 const inferred=fixture();inferred.feeds.orderFlow.sideMethod='INTRABAR_PRICE_DIRECTION';assert.equal(evaluate(inferred).researchCandidate,'NONE');
 const noRights=fixture('recorded');noRights.feeds.GC.rights.algorithmicResearchAuthorized=false;assert.equal(evaluate(noRights).researchCandidate,'NONE');
 const kill=fixture();kill.risk.killSwitch=true;assert.equal(evaluate(kill).researchCandidate,'NONE');
 console.log('PASS Ultimate v2: daily vintages/expiry, past-only news, known future schedule, rights, real trade-side flow, missing gates, skew, risk and non-execution');
}
if(require.main===module)run();
module.exports={fixture};
