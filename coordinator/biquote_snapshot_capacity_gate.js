"use strict";
/**
 * Conservative count-only upper bounds for the EXISTING BiQuote snapshot.
 * A 21-H4 complete M15/H1 parity audit requires 21*16 distinct M15
 * constituents, and 21*4 H1 constituents, even before weekends or gaps.
 * Do not imply that merely raising an API limit would prove first-seen,
 * broker schedule, OHLC parity, data rights or execution costs.
 */
const NEED_H4=21,M15_PER_H4=16,H1_PER_H4=4;
const LIMITS=Object.freeze({M15:200,H1:180,H4:180});
const PRIVATE_DISPLAY_LIMIT=48;
const BASE=Object.freeze({
 mode:"BIQUOTE_SINGLE_SNAPSHOT_21_H4_PARITY_CAPACITY_ONLY",
 signal:"WAIT",executable:false,tradeEligible:false,
 paperOrdersAllowed:false,liveOrdersAllowed:false,
 brokerOrdersSent:0,providerRequestsMade:0,
 firstSeenVerified:false,brokerScheduleVerified:false,
 brokerRightsVerified:false,priceParityVerified:false,
 sufficientForTradeRecommendations:false
});
function assess(){
 const requiredM15=NEED_H4*M15_PER_H4;
 const requiredH1=NEED_H4*H1_PER_H4;
 const upperBoundH4ByM15=Math.floor(LIMITS.M15/M15_PER_H4);
 const upperBoundH4ByPrivateChart=Math.floor(PRIVATE_DISPLAY_LIMIT/M15_PER_H4);
 return {...BASE,status:"SINGLE_SNAPSHOT_CAPACITY_INSUFFICIENT",
  requiredContiguousH4:NEED_H4,
  requiredM15Constituents:requiredM15,
  requiredH1Constituents:requiredH1,
  configuredProviderMaxM15Bars:LIMITS.M15,
  configuredProviderMaxH1Bars:LIMITS.H1,
  configuredProviderMaxH4Bars:LIMITS.H4,
  privateChartMaxM15Bars:PRIVATE_DISPLAY_LIMIT,
  maxCompleteH4GroupsFromProviderM15:upperBoundH4ByM15,
  maxCompleteH4GroupsFromPrivateM15:upperBoundH4ByPrivateChart,
  providerM15CapacityShortfall:Math.max(0,requiredM15-LIMITS.M15),
  singleSnapshotCanProve21H4M15Parity:LIMITS.M15>=requiredM15&&
    LIMITS.H1>=requiredH1,
  archiveRequiredForFullWindow:true,
  archiveCurrentlyVerified:false,
  collectorChanged:false,providerLimitChanged:false,
  blockers:["M15_SINGLE_SNAPSHOT_WINDOW_TOO_SHORT_FOR_21_H4",
   "ARCHIVE_POINT_IN_TIME_RECEIPTS_NOT_PROVEN",
   "BROKER_SCHEDULE_AND_RIGHTS_UNVERIFIED"]
 };
}
module.exports={assess};
