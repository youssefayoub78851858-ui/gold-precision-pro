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
// Capital Demo is the explicitly selected XAUUSD candidate only, never
// a connected/approved feed or order-capable integration.
a.match(s.layers.XAUUSD_BBO.providerCandidate,/Capital\.com Demo/);
a.match(s.layers.XAUUSD_BBO.requiredEvidence,/CLOUD_STORAGE_RIGHTS/);
a.equal(s.layers.XAUUSD_BBO.liveReady,false);
a.equal(s.layers.XAUUSD_BBO.researchAdmitted,false);
const handoff=s.capitalDemoPreKyc;
a.equal(handoff.mode,'CAPITAL_DEMO_PRIVATE_CLOUD_RIGHTS_PENDING_PRECONNECTION_HANDOFF');
a.equal(handoff.accountVerificationStatusAttestedByThisPublicModule,false);
a.equal(handoff.selectedPrimaryCandidate,true);
a.equal(handoff.kycRequestedNow,false);
a.equal(handoff.credentialRequestedNow,false);
a.equal(handoff.kycRequiredBeforeRealDemoAPIUse,true);
a.equal(handoff.identityDocumentsCollected,false);
a.equal(handoff.tradingKeyCollected,false);
a.equal(handoff.permissionToStoreOnPrivateRenderConfirmed,false);
a.equal(handoff.actualDemoHistoryReceived,false);
a.equal(handoff.connected,false);
a.equal(handoff.providerRequestsMade,0);
a.equal(handoff.ordersSent,0);
a.equal(handoff.signal,'WAIT');
a.equal(handoff.executable,false);
a.equal(handoff.paperOrdersAllowed,false);
a.equal(handoff.nextUserAction,'NO_API_KEY_UNTIL_WRITTEN_RIGHTS_AND_EGRESS_ISOLATION');
a.equal(handoff.beforeConnectionExternalPrerequisite,'COMPANY_PERMISSION_FOR_PRIVATE_CLOUD_DATA_STORAGE_AND_RETENTION');
a.equal(handoff.workPossibleWithoutAccountAccess.length,4);
a.equal(handoff.afterPermissionValidationRequired.length,2);
for(const unsafe of ['apiKey','identityDocument','apiSecret','liveUrl','token'])
 a.equal(Object.prototype.hasOwnProperty.call(handoff,unsafe),false);
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
