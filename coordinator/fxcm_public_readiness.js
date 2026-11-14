"use strict";
// Public REVIEW-DEMO only: immutable pre-license status. Not a market feed.
const reasons=Object.freeze([
  "FXCM_EULA_AND_CLOUD_RIGHTS_UNVERIFIED",
  "FXCM_DEMO_READ_ONLY_ENTITLEMENT_UNVERIFIED",
  "FXCM_REAL_XAUUSD_BID_ASK_NOT_CONNECTED",
  "FXCM_UTC_SESSION_AND_HISTORY_PARITY_UNVERIFIED"
]);
function readOnlyStatus(){
 return {
  provider:"FXCM", mode:"OFFLINE_PREPARATION_ONLY",
  status:"WAIT_FXCM_NOT_CONNECTED",signal:"WAIT",executable:false,
  researchEligible:false,paperOrdersAllowed:false,tradingEnabled:false,
  providerAccessStarted:false,sdkLoaded:false,sourceRequestsMade:0,
  credentialsRead:0,livePricesAvailable:false,licenseVerified:false,
  accountPermissionsVerified:false,validatedClosedBarCounts:{M15:0,H1:0,H4:0},
  blockingReasons:[...reasons]
 };
}
module.exports={readOnlyStatus,reasons};
