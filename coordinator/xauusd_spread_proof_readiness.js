'use strict';
// Offline proof-readiness audit of the actual repository's historical XAU/USD
// artifacts. Do not turn a BID-only file into synthetic ASK/MID or assume an
// attestation is a license. No market feeds, secrets, executions or network.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const MAX_DATASETS=24,MAX_BYTES=4_000_000;
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
const blocked=(code)=>({status:'PROOF_BLOCKED',code,signal:'WAIT',executable:false,
 paperOrdersAllowed:false,realTradingAllowed:false});
function safeFile(file){
 const st=fs.lstatSync(file);
 if(!st.isFile()||st.isSymbolicLink()||st.size>MAX_BYTES||st.size===0)
  throw Error('UNSAFE_OR_OVERSIZE_LOCAL_FILE');
 return fs.readFileSync(file);
}
function expectedDataset(folder,item){
 if(!item||typeof item.file!=='string'||!/^\d{4}-\d\d-bid\.json$/.test(item.file)||
    typeof item.sha256!=='string'||!/^[a-f0-9]{64}$/.test(item.sha256))
  throw Error('INVALID_MANIFEST_DATASET');
 const file=path.join(folder,item.file);
 const buf=safeFile(file);
 if(sha(buf)!==item.sha256)throw Error('HISTORICAL_FILE_DIGEST_MISMATCH');
 const d=JSON.parse(buf.toString('utf8'));
 if(d?.symbol!=='XAU/USD'||item.priceConvention!=='BID'||
    !d.frames||!Array.isArray(d.frames['15min'])||
    !Array.isArray(d.frames['1h'])||!Array.isArray(d.frames['4h'])||
    typeof d.source!=='string'||!d.source.trim())
  throw Error('UNKNOWN_SOURCE_SYMBOL_OR_PRICE_CONVENTION');
 if(/synthetic|fabricated|mock/i.test(d.source))throw Error('SYNTHETIC_OR_TEST_SOURCE_CANNOT_PROVE_MARKET');
 let last=-Infinity,missingCalendarSlots=0;
 for(const row of d.frames['15min']){
  if(!row||typeof row.datetime!=='string'||! /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(row.datetime))
   throw Error('INVALID_BAR_CLOCK');
  const t=Date.parse(row.datetime);
  if(!Number.isFinite(t)||new Date(t).toISOString().slice(0,19)!==row.datetime.slice(0,19)||
     t%900000!==0||t<=last)
   throw Error('NONCHRONOLOGICAL_M15_BARS');
  if(last!==-Infinity&&t-last>900000)missingCalendarSlots+=Math.round((t-last)/900000)-1;
  last=t;
  if(['open','high','low','close'].some(k=>typeof row[k]!=='number'||!Number.isFinite(row[k])||row[k]<=0)||
     row.high<Math.max(row.open,row.close,row.low)||
     row.low>Math.min(row.open,row.close,row.high))
   throw Error('INVALID_M15_OHLC');
 }
 // These files store only "frames": single-basis price candles.
 // Unknown extra basis structures may never be implicitly admitted.
 const extraKeys=Object.keys(d).filter(k=>!['source','symbol','frames'].includes(k));
 const m15=d.frames['15min'];
 return {file:item.file,declaredConvention:item.priceConvention,
   sha256MatchesManifest:true,repositoryArtifactIntegrity:'HASH_ONLY_NOT_PROVIDER_AUTHENTICITY',
   stored15MinuteBars:m15.length,storedHourBars:d.frames['1h'].length,
   stored4HourBars:d.frames['4h'].length,missingCalendarSlots,
   firstM15UTC:m15[0]?.datetime??null,lastM15UTC:m15.at(-1)?.datetime??null,
   bid15MinuteBars:m15.length,ask15MinuteBars:0,mid15MinuteBars:0,
   extraUnregisteredPriceStructures:extraKeys,
   independentProviderAuthenticityVerified:false,
   algorithmicUsageRightsIndependentlyVerified:false,
   sourceFirstAvailabilityVerified:false};
}
function audit(root=path.resolve(__dirname,'..')){
 const folder=path.join(root,'research','recorded');
 let manifest,records;
 try{
  manifest=JSON.parse(safeFile(path.join(folder,'manifest.json')).toString('utf8'));
  if(!Array.isArray(manifest.datasets)||manifest.datasets.length<1||
     manifest.datasets.length>MAX_DATASETS||
     new Set(manifest.datasets.map(x=>x?.file)).size!==manifest.datasets.length)
   throw Error('INVALID_RECORDING_MANIFEST');
  records=manifest.datasets.map(x=>expectedDataset(folder,x));
 }catch(error){
  return {...blocked(error.message),sourceDataMode:'RECORDED_FILES_NOT_ACCEPTED',
   requiredLayers:['HISTORICAL_BID_AND_ASK_AND_MID','INDEPENDENT_SOURCE_RIGHTS',
    'BROKER_COSTS','MATCHED_FORWARD_HOLDOUT'],
   baselineResultsAvailableForSpreadFilter:false,
   afterFilterResultsAvailable:false,verifiedPerformanceImprovement:false,
   warning:'Local file integrity or schema failed. No conclusion about gold signal performance.'};
 }
 const counts=records.reduce((a,x)=>({
  bidM15:a.bidM15+x.bid15MinuteBars,askM15:a.askM15+x.ask15MinuteBars,
  midM15:a.midM15+x.mid15MinuteBars,recordedFiles:a.recordedFiles+1}),{
  bidM15:0,askM15:0,midM15:0,recordedFiles:0});
 // The recorded manifest is self-declared: neither file checksum nor a green
 // CI run independently verifies original vendor rights or historical quotes.
 return {mode:'OFFLINE_XAUUSD_SPREAD_FILTER_EVIDENCE_AUDIT',
  status:'PROOF_BLOCKED',signal:'WAIT',executable:false,
  paperOrdersAllowed:false,realTradingAllowed:false,
  dataScope:'REPOSITORY_LOCAL_RECORDINGS_ONLY',counts,records,
  bidOnlyHistory:true,
  synchronizedHistoricalBidAskMidVerified:false,
  actualHistoricalSpreadMeasured:false,
  independentProviderAuthenticityVerified:false,
  sourceLicensingVerified:false, brokerFeeScheduleVerified:false,
  filterHoldoutDataAvailable:false,baselineResultsAvailableForSpreadFilter:false,
  afterFilterResultsAvailable:false,pairedCandidateSelectionValidated:false,
  independentlyReplicatedPerformance:false,
  verifiedPerformanceImprovement:false,
  winRateBefore:null,winRateAfter:null,winRateDelta:null,
  reductionInFalseBreakouts:null,netProfitDifference:null,
  providerRequestsMade:0,paymentsMade:0,ordersSent:0,
  requiredNextEvidence:[
   'LICENSED_SYNCHRONIZED_HISTORICAL_XAUUSD_BID_ASK_AND_MID_M15',
   'PROVIDER_AUTHENTICITY_AND_CLOUD_ALGORITHMIC_USAGE_RIGHTS',
   'FIRST_AVAILABILITY_TIMESTAMPS_AND_BROKER_SESSION_CALENDAR',
   'SAME_FROZEN_BASELINE_CANDIDATES_AND_BROKER_SPREAD_SLIPPAGE_COMMISSION',
   'UNTOUCHED_CHRONOLOGICAL_FORWARD_HOLDOUT_WITH_TRADE_OUTCOMES'],
  reason:'Only historical BID candles exist in repository. Real spread widening, bid/ask breakout confirmations and paired net performance cannot be measured.',
  warning:'A passing CI test validates software behavior, not historical win rate or the legal rights to feed it live market data.'};
}
module.exports={audit,expectedDataset};
if(require.main===module){const result=audit();
 process.stdout.write(JSON.stringify(result,null,2)+'\n');
 if(result.status!=='PROOF_BLOCKED')process.exitCode=1;
}
