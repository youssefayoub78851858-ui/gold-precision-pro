'use strict';
/*
 * A public/review-only, no-credential quarantine AROUND the FROZEN Ultimate
 * v2 engine. Never alter the historical strategy, its frozen hash, or replay
 * outcomes to make new safety checks pass. A caller-controlled "recorded",
 * "rights verified", or synthetic fixture flag is NOT independent evidence.
 *
 * This adapter returns NO prices, market direction, entry, SL, TP, forecasts,
 * signatures or source credentials, and never sends paper/live orders.
 */
const {evaluate}=require('./ultimate_v2');
const LAYERS=['US02Y','US10Y','DXY','GC','orderFlow','calendar','headlines'];
function blocked(code){
 return {
  mode:'ULTIMATE_V2_UNATTESTED_PUBLIC_SHADOW',
  status:'WAIT_UNATTESTED_CONTEXT',reason:code,
  engineVersion:2,signal:'WAIT',researchCandidate:'NONE',
  executable:false,paperOrdersAllowed:false,liveOrdersAllowed:false,
  sourceRightsIndependentlyVerified:false,
  brokerCostsIndependentlyVerified:false,
  prospectiveHoldoutIndependentlyVerified:false,
  credentialsUsed:false,providerRequestsMade:0,brokerOrdersSent:0,
  technicalPatternPresent:false,contextFramesStructurallyReady:0,
  syntheticFeedsPresent:false,allSevenRecordedMode:false,
  originalFrozenEngineUnchanged:true
 };
}
function assessPublicShadow(input){
 if(!input||typeof input!=='object'||Array.isArray(input)||
    !input.feeds||typeof input.feeds!=='object'||Array.isArray(input.feeds))
  return blocked('OFFLINE_INPUT_REQUIRED');
 try {
  const out=evaluate(input); // the original frozen, non-networked v2
  const modes=LAYERS.map(name=>input.feeds[name]?.mode);
  const synthetic=modes.includes('synthetic');
  const completeRecorded=modes.every(mode=>mode==='recorded');
  return {
   ...blocked('NO_INDEPENDENT_VETTED_MARKET_FEED_RIGHTS_OR_FORWARD_HOLDOUT'),
   status:synthetic?'WAIT_SYNTHETIC_SCENARIO_NOT_TRADING_EVIDENCE':'WAIT_UNATTESTED_CONTEXT',
   technicalPatternPresent:['BUY','SELL'].includes(out.technical?.candidate),
   contextFramesStructurallyReady:out.monitoring?.readyFeeds||0,
   syntheticFeedsPresent:synthetic,
   allSevenRecordedMode:completeRecorded,
   // An in-memory payload may claim "recorded"/"licensed" and yield a
   // researchCandidate in the frozen engine. Do NOT echo that candidate.
   frozenEngineCandidateWithheld:out.researchCandidate!=='NONE'
  };
 } catch (_error) {
  // Avoid returning input or exception text, which might contain private
  // prices, account identifiers, market symbols or tokens.
  return blocked('INVALID_OFFLINE_EVIDENCE');
 }
}
module.exports={assessPublicShadow};
