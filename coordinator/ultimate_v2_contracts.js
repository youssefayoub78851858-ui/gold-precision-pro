'use strict';
// New contract only. No clocks, HTTP clients, credential loading or timestamp rewriting.
const ROLES={US02Y:'DAILY_CONTEXT',US10Y:'DAILY_CONTEXT',DXY:'INTRADAY_CONFIRMATION',GC:'INTRADAY_CONFIRMATION',orderFlow:'INTRADAY_CONFIRMATION',calendar:'KNOWN_SCHEDULE',headlines:'OBSERVED_NEWS'};
const INSTRUMENTS={US02Y:'DGS2',US10Y:'DGS10',DXY:'DXY',GC:'GC',orderFlow:'GC_TRADES',calendar:'USD_EVENTS',headlines:'GOLD_USD_NEWS'};
function time(value){
 if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|\+00:00)$/.test(value))return NaN;
 const t=Date.parse(value);
 return Number.isFinite(t)&&new Date(t).toISOString().slice(0,19)===value.slice(0,19)?t:NaN;
}
const finite=Number.isFinite;
const text=x=>typeof x==='string'&&Boolean(x.trim());
function issues(name,f){
 const bad=reason=>[reason];
 if(!ROLES[name]||!f||typeof f!=='object'||f.schemaVersion!==2||f.role!==ROLES[name])return bad('SCHEMA_OR_ROLE');
 if(!['recorded','synthetic'].includes(f.mode)||!text(f.source)||!text(f.availabilityEvidence)||f.instrument!==INSTRUMENTS[name])return bad('PROVENANCE_OR_INSTRUMENT');
 const o=time(f.observedUTC),a=time(f.availableUTC);
 if(!finite(o)||!finite(a)||o>a)return bad('OBSERVATION_AVAILABILITY_ORDER');
 if(f.mode==='recorded'&&(!f.rights||f.rights.status!=='VERIFIED_INTERNAL_RESEARCH'||!text(f.rights.evidenceReference)||f.rights.algorithmicResearchAuthorized!==true))return bad('USAGE_RIGHTS_UNVERIFIED');
 if(['US02Y','US10Y','DXY','GC'].includes(name)){
  if(![f.value,f.previous].every(v=>finite(v)&&v>0))return bad('INVALID_VALUES');
  const po=time(f.previousObservedUTC),pa=time(f.previousAvailableUTC);
  if(!finite(po)||!finite(pa)||po>=o||po>pa||pa>a)return bad('REFERENCE_VINTAGE_UNAVAILABLE');
  if(['DXY','GC'].includes(name)&&o-po>300000)return bad('INTRADAY_REFERENCE_STALE');
 }
 if(ROLES[name]==='DAILY_CONTEXT'){
  const next=time(f.nextExpectedReleaseUTC),known=time(f.releaseScheduleAvailableUTC);
  if(f.frequency!=='DAILY'||f.units!=='PERCENT_PER_ANNUM'||f.observationDate!==f.observedUTC.slice(0,10)||f.previousObservationDate!==f.previousObservedUTC.slice(0,10)||f.previousObservationDate>=f.observationDate)return bad('DAILY_IDENTITY');
  if(!finite(next)||next<=a||next-a>7*86400000||!finite(known)||known>=next||!text(f.releaseScheduleReference))return bad('RELEASE_SCHEDULE_UNVERIFIED');
 }
 if(['GC','orderFlow'].includes(name)){
  if(!/^GC[FGHJKMNQUVXZ]\d{1,4}$/.test(f.contract||'')||!finite(time(f.contractExpiryUTC)))return bad('ACTUAL_GC_CONTRACT_REQUIRED');
 }
 if(name==='GC'&&(f.referenceContract!==f.contract||f.priceConvention!=='TRADE'))return bad('GC_REFERENCE_CONVENTION');
 if(name==='orderFlow'){
  if(f.kind!=='trades'||f.sideMethod!=='EXCHANGE_AGGRESSOR'||f.licensed!==true||f.sequenceGapCount!==0)return bad('TRUE_TRADE_SIDE_AND_CONTINUITY_REQUIRED');
  if(![f.buyVolume,f.sellVolume].every(v=>finite(v)&&v>=0)||f.buyVolume+f.sellVolume<=0)return bad('INVALID_TRADE_VOLUME');
  const start=time(f.windowStartUTC),end=time(f.windowEndUTC);
  if(!finite(start)||!finite(end)||start>=end||end!==o||end-start>300000)return bad('TRADE_WINDOW_ORDER');
 }
 if(['calendar','headlines'].includes(name)){
  if(!Array.isArray(f.events)||f.events.some(e=>!e||!text(e.id)||!['low','medium','high'].includes(e.impact)||!finite(time(e.publishedUTC))||!finite(time(e.availableUTC))||time(e.publishedUTC)>time(e.availableUTC)||time(e.availableUTC)>a))return bad('EVENT_NOT_KNOWN_AT_SNAPSHOT');
  if(new Set(f.events.map(e=>e.id)).size!==f.events.length)return bad('DUPLICATE_EVENT');
  const start=time(f.coverageStartUTC),end=time(f.coverageEndUTC);
  if(!finite(start)||!finite(end)||start>end||!text(f.coverageEvidenceReference))return bad('COVERAGE_UNVERIFIED');
  if(name==='calendar'){
   const review=time(f.nextReviewUTC);
   if(f.scope!=='USD_MATERIAL_SCHEDULED'||!finite(review)||review<=a||review-a>86400000||f.events.some(e=>!finite(time(e.timeUTC))))return bad('SCHEDULE_SCOPE_OR_REVIEW');
  }else{
   if(f.scope!=='USD_GOLD_MATERIAL_NEWS'||f.continuityVerified!==true||end>o||end>a||f.events.some(e=>Math.max(time(e.publishedUTC),time(e.availableUTC))<start||Math.max(time(e.publishedUTC),time(e.availableUTC))>end))return bad('PAST_NEWS_COVERAGE_OR_SCOPE');
  }
 }
 return [];
}
function assessLayer(name,f,asOfUTC){
 const errors=issues(name,f),now=time(asOfUTC);
 const fail=reason=>({status:'UNAVAILABLE',role:ROLES[name],reason});
 if(!finite(now))return fail('INVALID_ASOF');
 if(!f)return fail('MISSING_LAYER');
 if(errors.length)return fail(errors[0]);
 const observed=time(f.observedUTC),available=time(f.availableUTC);
 if(available>now||observed>now)return fail('NOT_AVAILABLE_AT_DECISION');
 const base={status:'READY',role:ROLES[name],mode:f.mode,source:f.source,observedUTC:f.observedUTC,availableUTC:f.availableUTC,ageSeconds:(now-observed)/1000};
 if(ROLES[name]==='DAILY_CONTEXT'){
  if(time(f.releaseScheduleAvailableUTC)>now)return fail('RELEASE_SCHEDULE_NOT_AVAILABLE');
  if(now>=time(f.nextExpectedReleaseUTC)||now-observed>7*86400000)return fail('DAILY_CONTEXT_EXPIRED');
  return {...base,observationDate:f.observationDate,releaseScheduleAvailableUTC:f.releaseScheduleAvailableUTC,validUntilUTC:f.nextExpectedReleaseUTC,dailyChange:f.value-f.previous,directionalVote:false};
 }
 if(ROLES[name]==='INTRADAY_CONFIRMATION'){
  if(now-observed>300000)return fail('INTRADAY_STALE');
  if(['GC','orderFlow'].includes(name)&&now>=time(f.contractExpiryUTC))return fail('GC_CONTRACT_EXPIRED');
  if(name==='orderFlow')return {...base,contract:f.contract,score:(f.buyVolume-f.sellVolume)/(f.buyVolume+f.sellVolume)};
  return {...base,...(name==='GC'?{contract:f.contract}:{}),score:Math.sign(f.value-f.previous)*(name==='DXY'?-1:1)};
 }
 if(name==='calendar'){
  if(now>=time(f.nextReviewUTC))return fail('SCHEDULE_REVIEW_EXPIRED');
  if(time(f.coverageStartUTC)>now-1800000||time(f.coverageEndUTC)<now+1800000)return fail('SCHEDULE_WINDOW_MISSING');
  return {...base,blocked:f.events.some(e=>e.impact==='high'&&Math.abs(time(e.timeUTC)-now)<=1800000),window:'KNOWN_SCHEDULE_MINUS_PLUS_30_MINUTES'};
 }
 if(time(f.coverageStartUTC)>now-1800000||time(f.coverageEndUTC)>now||now-time(f.coverageEndUTC)>60000)return fail('PAST_NEWS_WINDOW_OR_WATERMARK_GAP');
 return {...base,blocked:f.events.some(e=>e.impact==='high'&&now-Math.max(time(e.publishedUTC),time(e.availableUTC))<=1800000),watermarkUTC:f.coverageEndUTC,window:'OBSERVED_PAST_30_MINUTES_ONLY'};
}
function selectKnown(records,asOfUTC){
 const now=time(asOfUTC),selected={};
 if(!finite(now))throw Error('Invalid UTC asOf');
 for(const [name,rows] of Object.entries(records)){
  if(!ROLES[name]||!Array.isArray(rows))throw Error('Unknown layer or invalid records');
  const seen=new Set(),vintages=new Map();let prior=-Infinity;
  for(const row of rows){
   const invalid=issues(name,row);if(invalid.length)throw Error(name+': '+invalid[0]);
   const a=time(row.availableUTC),schedule=ROLES[name]==='DAILY_CONTEXT'?time(row.releaseScheduleAvailableUTC):a;
   const arrival=Math.max(a,schedule),vintage=row.observedUTC+'|'+row.availableUTC;
   const key=vintage+(ROLES[name]==='DAILY_CONTEXT'?'|'+row.releaseScheduleAvailableUTC:'');
   if(ROLES[name]==='DAILY_CONTEXT'){
    const values=JSON.stringify([row.value,row.previous,row.previousObservedUTC,row.previousAvailableUTC]);
    if(vintages.has(vintage)&&vintages.get(vintage)!==values)throw Error(name+': CONFLICTING_DAILY_VINTAGE');
    vintages.set(vintage,values);
   }
   if(seen.has(key)||arrival<prior)throw Error(name+': DUPLICATE_OR_REVERSED_ARRIVAL');
   seen.add(key);prior=arrival;
   if(arrival>now)continue;
   const old=selected[name];
   if(!old||ROLES[name]!=='DAILY_CONTEXT'||time(row.observedUTC)>time(old.observedUTC)||(row.observedUTC===old.observedUTC&&(a>time(old.availableUTC)||(a===time(old.availableUTC)&&schedule>time(old.releaseScheduleAvailableUTC)))))selected[name]=row;
  }
 }
 return selected;
}
module.exports={ROLES,INSTRUMENTS,time,issues,assessLayer,selectKnown};
if(require.main===module){
 const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
 const errors=[];
 for(const [name,rows] of Object.entries(input)){
  if(!Array.isArray(rows)){errors.push(name+': ROWS_REQUIRED');continue;}
  rows.forEach((row,i)=>issues(name,row).forEach(e=>errors.push(name+'['+i+']: '+e)));
 }
 try{selectKnown(input,'1970-01-01T00:00:00Z');}catch(e){errors.push(e.message);}
 process.stdout.write(JSON.stringify({valid:errors.length===0,errors}));if(errors.length)process.exitCode=1;
}
