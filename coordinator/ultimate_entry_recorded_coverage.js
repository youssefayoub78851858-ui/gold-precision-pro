'use strict';
/**
 * Offline historical BID-only entry-feature COVERAGE (never a backtest).
 * The two repo recordings are old, previously researched, BID-only and
 * cannot validate actual spread/slippage or incremental win rate.
 * Neither this inspector nor its CLI generates BUY/SELL candidates.
 */
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const FRAMES=Object.freeze({'15min':900000,'1h':3600000,'4h':14400000});
const MAX_BYTES=1_000_000;
const RESEARCH_DIR=path.resolve(__dirname,'../research/recorded');
const DT=/^20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const finite=x=>typeof x==='number'&&Number.isFinite(x);
function bad(code){throw Error('BID_RECORDED_COVERAGE_REJECTED_'+code);}
function millis(s,width){
 if(typeof s!=='string'||!DT.test(s))bad('UTC_TIMESTAMP');
 const t=Date.parse(s);
 if(!finite(t)||new Date(t).toISOString().slice(0,19)!==s.slice(0,19)||t%width!==0)bad('UTC_ALIGNMENT');
 return t;
}
function parseFrame(rows,width){
 if(!Array.isArray(rows)||rows.length>10000)bad('FRAME_UNAVAILABLE_OR_UNBOUNDED');
 let last=-Infinity, gaps=0, flats=0;
 const times=[];
 for(const bar of rows){
  if(!bar||typeof bar!=='object')bad('ROW_INVALID');
  const t=millis(bar.datetime,width);
  if(t<=last)bad('OUT_OF_ORDER_OR_DUPLICATE');
  if(last!==-Infinity&&t-last>width)gaps++;
  const prices=['open','high','low','close'].map(k=>bar[k]);
  if(prices.some(x=>!finite(x)||x<=0)||bar.low>Math.min(bar.open,bar.close)||
     bar.high<Math.max(bar.open,bar.close))bad('OHLC_GEOMETRY_INVALID');
  if(bar.high===bar.low)flats++;
  times.push(t);last=t;
 }
 return {times,rows,gaps,flats};
}
function latestValid(rows,times,index,decision,width){
 if(index<1)return false;
 return times[index]+width<=decision&&decision-(times[index]+width)<=width&&
  times[index]-times[index-1]===width;
}
function describeDataset(data,meta){
 if(!data||data.symbol!=='XAU/USD'||!data.frames||!meta?.qualityReport?.frames||
    meta.priceConvention!=='BID')bad('BID_SOURCE_MANIFEST_REQUIRED');
 const parsed={};
 for(const [name,width] of Object.entries(FRAMES)){
  const frame=parseFrame(data.frames[name],width);
  if(frame.rows.length!==meta.qualityReport.frames[name]?.count)bad('MANIFEST_COUNT_MISMATCH');
  parsed[name]=frame;
 }
 const m=parsed['15min'],h1=parsed['1h'],h4=parsed['4h'];
 let contiguousM15=0,nonflatM15=0,contextCovered=0,unknownContext=0;
 let one=-1,four=-1;
 for(let i=0;i<m.rows.length;i++){
  const decision=m.times[i]+FRAMES['15min'];
  while(one+1<h1.times.length&&h1.times[one+1]+FRAMES['1h']<=decision)one++;
  while(four+1<h4.times.length&&h4.times[four+1]+FRAMES['4h']<=decision)four++;
  if(i<15)continue;
  const recent=m.times.slice(i-15,i+1);
  if(recent.some((t,j)=>j>0&&t-recent[j-1]!==FRAMES['15min']))continue;
  const tr=m.rows.slice(i-14,i).map((bar,j)=>{
   const prev=m.rows[i-15+j].close;
   return Math.max(bar.high-bar.low,Math.abs(bar.high-prev),Math.abs(bar.low-prev));
  });
  const atr=tr.reduce((a,x)=>a+x,0)/tr.length;
  if(!finite(atr)||atr<=0)continue;
  contiguousM15++;
  if(m.rows[i].high===m.rows[i].low)continue;
  nonflatM15++;
  const ready1=latestValid(h1.rows,h1.times,one,decision,FRAMES['1h']);
  const ready4=latestValid(h4.rows,h4.times,four,decision,FRAMES['4h']);
  if(ready1&&ready4)contextCovered++;
  else unknownContext++;
 }
 return {
  rows:{M15:m.rows.length,H1:h1.rows.length,H4:h4.rows.length},
  chronologicalGapCounts:{M15:m.gaps,H1:h1.gaps,H4:h4.gaps},
  zeroRangeCounts:{M15:m.flats,H1:h1.flats,H4:h4.flats},
  m15PriorATRContiguousWindows:contiguousM15,
  m15NonflatPriorATRWindows:nonflatM15,
  m15WindowsWithRecentClosedH1AndH4Geometry:contextCovered,
  m15WindowsMissingRecentH1OrH4:unknownContext,
  hasBrokerSessionCalendar:false,
  hasCompleteAskSide:false,
  hasBrokerExecutionCosts:false,
  hasFrozenV3CandidateAndFillOutcomes:false
 };
}
function inspect(records){
 if(!Array.isArray(records)||records.length!==2)bad('TWO_LOCKED_RECORDED_MONTHS_REQUIRED');
 const months=records.map(x=>describeDataset(x.data,x.meta));
 const add=(f)=>months.reduce((a,x)=>a+f(x),0);
 return {
  mode:'BID_ONLY_RECORDED_ENTRY_FEATURE_COVERAGE_V1',
  status:'DESCRIPTIVE_FEATURE_COVERAGE_ONLY_NOT_PAIRED_PERFORMANCE',
  historicalDataConvention:'BID_ONLY_DUKASCOPY_DERIVED_NOT_ATTESTED',
  months:months.map((x,i)=>({month:i===0?'2026-09':'2026-10',...x})),
  totalM15:add(x=>x.rows.M15),
  totalStrictM15PriorATRWindows:add(x=>x.m15PriorATRContiguousWindows),
  totalStrictM15WithNonflatLastBar:add(x=>x.m15NonflatPriorATRWindows),
  totalStrictM15WithRecentH1H4:add(x=>x.m15WindowsWithRecentClosedH1AndH4Geometry),
  brokerCostsIndependentlyVerified:false,
  independentProviderRightsVerified:false,
  underlyingBrokerSessionVerified:false,
  candidateUniverseAvailable:false,
  afterCostPairedComparisonPossible:false,
  baselineNetR:null,filteredNetR:null,
  baselineWinRatePercent:null,filteredWinRatePercent:null,
  netPerformanceImprovementProven:false,
  confidencePercent:null,
  signal:'WAIT',executable:false,paperOrdersAllowed:false,liveOrdersAllowed:false,
  providerRequestsMade:0,ordersSent:0
 };
}
function readStrict(file){
 const stats=fs.lstatSync(file);
 if(!stats.isFile()||stats.isSymbolicLink()||stats.size<=0||stats.size>MAX_BYTES)
  bad('UNSAFE_OR_OVERSIZE_RECORDED_FILE');
 return fs.readFileSync(file);
}
function runLockedRepoArchive(){
 const manifest=JSON.parse(readStrict(path.join(RESEARCH_DIR,'manifest.json')));
 if(!Array.isArray(manifest.datasets)||manifest.datasets.length!==2)
  bad('MANIFEST_DATASETS_UNEXPECTED');
 const names=['2026-09-bid.json','2026-10-bid.json'];
 const records=names.map((name,i)=>{
  const meta=manifest.datasets[i];
  if(meta?.file!==name||! /^[a-f0-9]{64}$/.test(meta.sha256||''))
   bad('MONTH_OR_SHA_MANIFEST_MISMATCH');
  const buffer=readStrict(path.join(RESEARCH_DIR,name));
  const checksum=crypto.createHash('sha256').update(buffer).digest('hex');
  if(checksum!==meta.sha256)bad('RECORDED_DIGEST_MISMATCH');
  return {data:JSON.parse(buffer.toString('utf8')),meta};
 });
 return inspect(records);
}
module.exports={inspect,describeDataset,runLockedRepoArchive};
if(require.main===module){
 try{process.stdout.write(JSON.stringify(runLockedRepoArchive())+'\n');}
 catch(e){console.error(typeof e.message==='string'&&e.message.startsWith('BID_RECORDED_COVERAGE_REJECTED_')?e.message:'BID_RECORDED_COVERAGE_INVALID');process.exitCode=1;}
}
