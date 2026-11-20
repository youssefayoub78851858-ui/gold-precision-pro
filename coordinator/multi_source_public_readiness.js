'use strict';
// Review-only, public, offline metadata. Zero market access, tokens, prices or
// entitlements. The registry is SHARED with Python multi_source_readiness.py.
// A candidate is never displayed as a working source.
const fs=require('node:fs');
const path=require('node:path');
const registry=JSON.parse(fs.readFileSync(path.join(__dirname,'multi_source_layers.json'),'utf8'));
const IDS=['XAUUSD_BBO','GC_TRADES','GC_DEPTH','DXY','US02Y','US10Y','CALENDAR','HEADLINES','RISK_COSTS'];
if(registry.manifestVersion!==1||
   registry.mode!=='OFFLINE_REQUIREMENTS_NOT_MARKET_DATA'||
   !Array.isArray(registry.layers)||registry.layers.length!==IDS.length||
   registry.layers.some((x,i)=>!x||x.id!==IDS[i]||
     typeof x.providerCandidate!=='string'||!x.providerCandidate||
     typeof x.requiredEvidence!=='string'||!x.requiredEvidence))
  throw Error('INVALID_OFFLINE_SOURCE_REGISTRY');
function snapshot(){
 const layers={};
 for(const item of registry.layers){
  const daily=item.id==='US02Y'||item.id==='US10Y';
  layers[item.id]={
   providerCandidate:item.providerCandidate,
   requiredEvidence:item.requiredEvidence,
   status:daily?'FREE_DAILY_REFERENCE_CANDIDATE':'NOT_CONNECTED',
   reason:daily?'DAILY_OFFICIAL_REFERENCE_NOT_INTRADAY_EVIDENCE':
                'REAL_SOURCE_ENTITLEMENT_AND_EVIDENCE_NOT_VERIFIED',
   liveReady:false,researchAdmitted:false
  };
 }
 return {
  mode:'OFFLINE_MULTISOURCE_CAPABILITY_AUDIT',source:'STATIC_REQUIREMENTS_ONLY',
  signal:'WAIT',executable:false,researchEligible:false,
  paperOrdersAllowed:false,realTradingAuthorized:false,
  subscriptionsActivated:false,allLayersLive:false,completeStackReady:false,
  verifiedLiveLayerCount:0,requiredLayerCount:IDS.length,
  sourceRequestsMade:0,providerRequestsMade:0,secretReads:0,payments:0,
  publicLicensedDataShown:false,privateAccountRead:false,
  capitalDemoPreKyc:{
   mode:'CAPITAL_DEMO_DEFER_USER_KYC_UNTIL_FINAL_CONNECTION_HANDOFF',
   selectedPrimaryCandidate:true,
   credentialRequestedNow:false,kycRequestedNow:false,
   kycRequiredBeforeRealDemoAPIUse:true,
   identityDocumentsCollected:false,tradingKeyCollected:false,
   permissionToStoreOnPrivateRenderConfirmed:false,
   brokerSessionScheduleIndependentlyVerified:false,
   actualDemoHistoryReceived:false,
   endToEndPaperHoldoutValidated:false,
   connected:false,providerRequestsMade:0,ordersSent:0,
   nextUserAction:'NONE_WHILE_OFFLINE_PREPARATION_CONTINUES',
   nextExternalDependency:'WRITTEN_PRIVATE_RENDER_DATA_RIGHTS_AND_RETENTION_REPLY',
   workPossibleWithoutKyc:[
    'OFFLINE_GET_ONLY_DEMO_ROUTE_ALLOWLIST_TESTS',
    'SYNTHETIC_BID_ASK_M15_H1_H4_AGGREGATION_TESTS',
    'OFFLINE_SPREAD_COST_AND_PAPER_AUDIT_TESTS',
    'COLLECTOR_COUNTS_ONLY_READONLY_AUDIT'
   ],
   beforeKycExternalPrerequisite:'COMPANY_PERMISSION_FOR_PRIVATE_CLOUD_DATA_STORAGE_AND_RETENTION',
   afterKycValidationRequired:[
    'INDEPENDENT_DEMO_EPIC_AND_MARKET_SESSION_VERIFICATION',
    'REAL_DEMO_HISTORY_VALIDATION_AND_FORWARD_HOLDOUT'
   ],
   signal:'WAIT',executable:false,paperOrdersAllowed:false
  },
  layers,
  warning:'This is a static coverage checklist, NOT a live health check, market data, or proof of licensing'
 };
}
module.exports={snapshot};
