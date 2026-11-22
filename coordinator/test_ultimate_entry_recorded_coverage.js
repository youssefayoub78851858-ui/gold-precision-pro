'use strict';
const a=require('node:assert/strict');
const fs=require('node:fs');
const {inspect,describeDataset,runLockedRepoArchive}=
 require('./ultimate_entry_recorded_coverage');
const t=Date.parse('2026-09-01T00:00:00Z');
function make(){
 const frames={};
 for(const [tf,width,n] of [['15min',900000,40],['1h',3600000,10],['4h',14400000,3]]){
  frames[tf]=Array.from({length:n},(_,i)=>({
   datetime:new Date(t+i*width).toISOString().replace('.000Z','Z'),
   open:100,high:101,low:99,close:100.5
  }));
 }
 return {data:{symbol:'XAU/USD',frames},meta:{
  priceConvention:'BID',qualityReport:{frames:{
   '15min':{count:40},'1h':{count:10},'4h':{count:3}
  }}}};
}
const first=make(),second=make(),full=inspect([first,second]);
a.equal(full.mode,'BID_ONLY_RECORDED_ENTRY_FEATURE_COVERAGE_V1');
a.equal(full.totalM15,80);
a.equal(full.totalStrictM15PriorATRWindows,50);
a.equal(full.totalStrictM15WithNonflatLastBar,50);
a.equal(full.totalStrictM15WithRecentH1H4Timing,18);
a.equal(full.totalStrictM15WithLocallyMatchedBIDOHLC,18);
for(const field of ['brokerCostsIndependentlyVerified',
 'independentProviderRightsVerified','underlyingBrokerSessionVerified',
 'candidateUniverseAvailable','afterCostPairedComparisonPossible',
 'netPerformanceImprovementProven','executable',
 'paperOrdersAllowed','liveOrdersAllowed'])a.equal(full[field],false);
a.equal(full.signal,'WAIT');
for(const field of ['baselineNetR','filteredNetR','baselineWinRatePercent',
 'filteredWinRatePercent','confidencePercent'])a.equal(full[field],null);
a.equal(full.providerRequestsMade,0);a.equal(full.ordersSent,0);
const before=JSON.stringify(first);
inspect([first,second]);
a.equal(JSON.stringify(first),before,'pure audit must not modify data');
const gap=structuredClone(first);
for(let i=25;i<gap.data.frames['15min'].length;i++){
 const dt=new Date(Date.parse(gap.data.frames['15min'][i].datetime)+900000);
 gap.data.frames['15min'][i].datetime=dt.toISOString().replace('.000Z','Z');
}
const blockedGap=describeDataset(gap.data,gap.meta);
a(blockedGap.m15PriorATRContiguousWindows<25);
a.equal(blockedGap.chronologicalGapCounts.M15,1);
const flat=structuredClone(first);
flat.data.frames['15min'].at(-1).high=flat.data.frames['15min'].at(-1).low=100;
flat.data.frames['15min'].at(-1).close=100;
const flatOut=describeDataset(flat.data,flat.meta);
a.equal(flatOut.m15PriorATRContiguousWindows,25);
a.equal(flatOut.m15NonflatPriorATRWindows,24);
a.equal(flatOut.zeroRangeCounts.M15,1);
// Local higher-timeframe parity is evidence of internal consistency only.
const mismatch=structuredClone(first);
mismatch.data.frames['1h'][7].high=104;
const mismatched=describeDataset(mismatch.data,mismatch.meta);
a(mismatched.m15WindowsWithLocallyMatchedH1AndH4BIDOHLC<
  mismatched.m15WindowsWithRecentClosedH1AndH4Timing);
const invalid=structuredClone(first);
invalid.data.frames['15min'][4].low=105;
a.throws(()=>describeDataset(invalid.data,invalid.meta),/OHLC_GEOMETRY_INVALID/);
const duplicate=structuredClone(first);
duplicate.data.frames['15min'][1].datetime=duplicate.data.frames['15min'][0].datetime;
a.throws(()=>describeDataset(duplicate.data,duplicate.meta),/OUT_OF_ORDER_OR_DUPLICATE/);
const alteredManifest=structuredClone(first);
alteredManifest.meta.priceConvention='ASK';
a.throws(()=>describeDataset(alteredManifest.data,alteredManifest.meta),
 /BID_SOURCE_MANIFEST_REQUIRED/);
const alteredCount=structuredClone(first);
alteredCount.meta.qualityReport.frames['15min'].count=50;
a.throws(()=>describeDataset(alteredCount.data,alteredCount.meta),
 /MANIFEST_COUNT_MISMATCH/);
// The historical rows are already public repository BID data and cannot
// validate quote-side execution, a frozen candidate set or market provenance.
const archived=runLockedRepoArchive();
a.equal(archived.months.length,2);
a.equal(archived.months[0].rows.M15,2448);
a.equal(archived.months[1].rows.M15,2436);
a.equal(archived.totalM15,4884);
a(archived.totalStrictM15WithRecentH1H4Timing<=archived.totalStrictM15PriorATRWindows);
a(archived.totalStrictM15WithLocallyMatchedBIDOHLC<=archived.totalStrictM15WithRecentH1H4Timing);
a.equal(archived.afterCostPairedComparisonPossible,false);
a.equal(archived.netPerformanceImprovementProven,false);
a.equal(archived.signal,'WAIT');
const source=fs.readFileSync(require.resolve('./ultimate_entry_recorded_coverage'),'utf8');
a(!/\bfetch\s*\(/.test(source));
a(!/\bWebSocket\b/.test(source));
a(!/process\.env/.test(source));
console.log('PASS hash-locked BID-only Sep/Oct coverage, 4,884 M15, strict closed ATR windows, gap/flat/price tampering and no fabricated trading win rate');
