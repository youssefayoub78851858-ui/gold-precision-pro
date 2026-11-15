'use strict';
const a=require('node:assert/strict');
const fs=require('node:fs');
const {snapshot}=require('./multi_source_public_readiness');
const m=JSON.parse(fs.readFileSync(__dirname+'/multi_source_layers.json','utf8'));
a.equal(m.mode,'OFFLINE_REQUIREMENTS_NOT_MARKET_DATA');
const s=snapshot(),t=snapshot();
a.deepEqual(s,t);
a.equal(s.mode,'OFFLINE_MULTISOURCE_CAPABILITY_AUDIT');
a.equal(s.signal,'WAIT');a.equal(s.executable,false);
a.equal(s.researchEligible,false);a.equal(s.paperOrdersAllowed,false);
a.equal(s.allLayersLive,false);a.equal(s.completeStackReady,false);
a.equal(s.verifiedLiveLayerCount,0);a.equal(s.requiredLayerCount,9);
for(const k of ['sourceRequestsMade','providerRequestsMade','secretReads','payments'])a.equal(s[k],0);
a.deepEqual(Object.keys(s.layers),m.layers.map(x=>x.id));
for(const x of m.layers){
 const row=s.layers[x.id];
 a.equal(row.providerCandidate,x.providerCandidate);
 a.equal(row.requiredEvidence,x.requiredEvidence);
 a.equal(row.liveReady,false);a.equal(row.researchAdmitted,false);
 a.equal(row.status,['US02Y','US10Y'].includes(x.id)?
  'FREE_DAILY_REFERENCE_CANDIDATE':'NOT_CONNECTED');
}
for(const banned of ['api_key','token','password','bid_price','ask_price','quote','buy','sell'])
 a.equal(Object.keys(s).includes(banned),false);
a.equal(s.publicLicensedDataShown,false);
console.log('PASS nine-source read-only UI contract; no live data, no provider requests');
