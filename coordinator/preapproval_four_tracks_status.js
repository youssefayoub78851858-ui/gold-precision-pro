"use strict";
/**
 * Offline review of preapproval tasks. Pure static requirements only.
 * Does not claim that CI passed, that feeds are connected, or that data is
 * licensed. Never reads credentials or sends quotes/orders/network calls.
 */
const {snapshot}=require("./multi_source_public_readiness");
const BASE={mode:"GOLD_PREAPPROVAL_FOUR_TRACKS_V1",signal:"WAIT",executable:false,
 researchEligible:false,paperOrdersAllowed:false,liveOrdersAllowed:false,
 providerRequestsMade:0,brokerOrdersSent:0,sourceRightsVerified:false,
 allFourTracksTradeReady:false,verifiedLiveLayerCount:0};
function inspect(source=snapshot()){
 const fail={...BASE,status:"BLOCKED_REQUIREMENTS_UNVERIFIED",steps:null};
 const required=["XAUUSD_BBO","GC_TRADES","GC_DEPTH","DXY","US02Y","US10Y",
   "CALENDAR","HEADLINES","RISK_COSTS"];
 if(!source||source.signal!=="WAIT"||source.executable!==false||
   source.allLayersLive!==false||source.completeStackReady!==false||
   source.verifiedLiveLayerCount!==0||source.requiredLayerCount!==9||
   source.providerRequestsMade!==0||source.sourceRequestsMade!==0||
   source.payments!==0||source.secretReads!==0||
   !source.layers||Object.keys(source.layers).sort().join(",")!==required.slice().sort().join(",")||
   required.some(k=>source.layers[k]?.liveReady!==false||
                    source.layers[k]?.researchAdmitted!==false)||
   source.capitalDemoPreKyc?.connected!==false||
   source.capitalDemoPreKyc?.permissionToStoreOnPrivateRenderConfirmed!==false||
   source.capitalDemoPreKyc?.ordersSent!==0)return fail;
 return {...BASE,status:"OFFLINE_PREPARATION_ONLY",steps:{
   officialNewsCalendar:{status:"PARTIAL_US_OFFICIAL_REFERENCE_ONLY",
     liveTradeReady:false,completeWorldwideNews:false,
     actualConsensusSurpriseVerified:false},
   dxyGcOrderFlow:{status:"SYNTHETIC_VALIDATORS_NO_LIVE_FEED",
     liveTradeReady:false,dxy:"NOT_CONNECTED",gc:"NO_LICENSED_LIVE_TAPE",
     depth:"NO_LICENSED_LIVE_BOOK",deltaFootprint:"UNVERIFIED"},
   paperRisk:{status:"OFFLINE_COST_AND_HOLDOUT_TESTS_ONLY",
     liveTradeReady:false,paperOrdersActivated:false,
     actualBrokerCostVerified:false,prospectiveHoldoutVerified:false},
   capitalDemo:{status:"CLOUD_RIGHTS_WRITTEN_REPLY_PENDING",
     liveTradeReady:false,connected:false,
     kycStatus:"NOT_CHECKED_HERE",credentialsPresent:false,
     privateCloudStorageApproved:false,realHistoricalCandlesReceived:false}
 },blockers:["PRIVATE_CLOUD_AND_RETENTION_RIGHTS_PENDING",
    "DXY_GC_ORDERFLOW_NOT_LIVE_LICENSED",
    "BROKER_SPREAD_AND_FORWARD_PAPER_EVIDENCE_MISSING",
    "GOLD_EPIC_AND_BROKER_CALENDAR_UNVERIFIED"]};
}
module.exports={inspect};
