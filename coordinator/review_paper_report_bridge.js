"use strict";
/**
 * Review-only bridge from an explicitly configured existing synthetic
 * SQLite ledger to the compact Android dashboard. Fail closed when the
 * ledger is missing. No uploads, writes, provider calls or broker orders.
 * No operator file path, trade side, prices, secrets or raw fills leave here.
 */
const fs=require("node:fs");
const path=require("node:path");
const {spawnSync}=require("node:child_process");
const {verify:verifyDisk}=require("./paper_persistent_disk_gate");
const {inspect:inspectStartup}=require("./paper_startup_recovery_gate");
const MODE="GOLD_PRIVATE_OFFLINE_PAPER_REPORT_BRIDGE_V1";
const EMPTY_STATUS="NO_PERSISTENT_PAPER_JOURNAL_CONNECTED";
const int=(x,min,max)=>Number.isSafeInteger(x)&&x>=min&&x<=max;
const amount=x=>x===null||(typeof x==="number"&&Number.isFinite(x)&&Math.abs(x)<=1e7);
const fraction=x=>x===null||(typeof x==="number"&&Number.isFinite(x)&&x>=0&&x<=1);
const date=x=>typeof x==="string"&&/^20\d{2}-\d{2}-\d{2}$/.test(x)&&Number.isFinite(Date.parse(x+"T00:00:00Z"));
function empty(status=EMPTY_STATUS){
 return {mode:MODE,status,dataOrigin:"SYNTHETIC_TEST_ONLY",
  privateJournalConnected:false,provenance:"NO_PERSISTENT_RESULTS_VERIFIED",
  closedTrades:0,waitEvents:0,blockedSourceEvents:0,
  netModeledUsd:null,doubleCostStressNetUsd:null,
  winRate:null,maxClosedDrawdownUsd:null,averageNetR:null,
  latestDayUTC:null,latestWeekUTC:null,lastFiveTradeBatch:null,
  firstHundredClosedTrades:null,unverifiedNextM15ForecastAccuracy:null,
  independentHoldoutValidated:false,brokerCostsVerified:false,
  liveMarketDataConnected:false,providerRequestsMade:0,
  paperOrdersSent:0,brokerOrdersSent:0,
  signal:"WAIT",executable:false,paperOrdersAllowed:false,
  liveOrdersAllowed:false};
}
function metric(x){
 if(!x||typeof x!=="object"||Array.isArray(x)||
    !int(x.closedTrades,0,100)||!amount(x.netModeledUsd)||
    !amount(x.netDoubleCostStressUsd)||
    !amount(x.maxClosedDrawdownUsd)||!fraction(x.winRate)||
    !amount(x.averageNetR)||!amount(x.modeledCostsUsd)||
    !(x.independentlyValidated===false))return null;
 if(x.closedTrades===0&&[x.netModeledUsd,x.winRate,x.maxClosedDrawdownUsd,x.averageNetR].some(v=>v!==null))return null;
 if(x.closedTrades>0&&(x.netModeledUsd===null||x.winRate===null||
    x.maxClosedDrawdownUsd===null||x.averageNetR===null))return null;
 return {closedTrades:x.closedTrades,netModeledUsd:x.netModeledUsd,
  doubleCostStressNetUsd:x.netDoubleCostStressUsd,
  winRate:x.winRate,maxClosedDrawdownUsd:x.maxClosedDrawdownUsd,
  averageNetR:x.averageNetR};
}
function summarise(d){
 const untrusted=empty("SYNTHETIC_LOCAL_RESULTS_NOT_REAL_MARKET");
 if(!d||typeof d!=="object"||Array.isArray(d)||
    d.mode!=="GOLD_OFFLINE_SYNTHETIC_PAPER_REPORTS_V1"||
    d.status!=="OFFLINE_SYNTHETIC_DESCRIPTIVE_ONLY"||
    d.origin!=="OFFLINE_SYNTHETIC_FORWARD_PAPER_JOURNAL_V1"||
    d.signal!=="WAIT"||d.executable!==false||
    d.independentHoldoutValidated!==false||
    d.realMarketDataConnected!==false||
    d.brokerTransactionCostsVerified!==false||
    d.statisticallyValidated!==false||
    d.paperOrderExecutionEnabled!==false||
    d.liveOrderExecutionEnabled!==false||
    d.providerRequestsMade!==0||d.brokerOrdersSent!==0||
    d.paperOrdersSent!==0||d.unverifiedNextM15ForecastAccuracy!==null||
    !int(d.journalRows,0,500)||
    !Array.isArray(d.dailyUTC)||!Array.isArray(d.weeklyUTC)||
    !Array.isArray(d.completedFiveTradeBatches)||
    d.dailyUTC.length>500||d.weeklyUTC.length>100||
    d.completedFiveTradeBatches.length>20)return null;
 const sum=metric(d.cumulative);
 if(!sum||d.journalRows<sum.closedTrades||!int(d.partialFiveTradeBatchCount,0,4)||
    d.partialFiveTradeBatchCount!==sum.closedTrades%5||
    d.completedFiveTradeBatches.length!==Math.floor(sum.closedTrades/5)||
    d.dailyUTC.some(x=>!date(x.utcStart)||!metric(x))||
    d.weeklyUTC.some(x=>!date(x.utcStart)||!metric(x))||
    d.completedFiveTradeBatches.some((x,i)=>
      x.closedTradeRange?.[0]!==i*5+1||x.closedTradeRange?.[1]!==i*5+5||
      metric(x)?.closedTrades!==5)||
    d.dailyUTC.reduce((n,x)=>n+x.closedTrades,0)!==sum.closedTrades||
    d.weeklyUTC.reduce((n,x)=>n+x.closedTrades,0)!==sum.closedTrades||
    (sum.closedTrades>=100)!==Boolean(d.firstHundredClosedTradeCheckpoint)||
    (sum.closedTrades>=100&&metric(d.firstHundredClosedTradeCheckpoint)?.closedTrades!==100))
  return null;
 const pick=x=>x?{utcStart:x.utcStart, ...metric(x),
  recordedEvents:x.recordedEvents,waitEvents:x.waitEvents,
  blockedSourceEvents:x.blockedSourceEvents}:null;
 const day=d.dailyUTC.at(-1),week=d.weeklyUTC.at(-1);
 for(const x of [day,week].filter(Boolean))
  if(!int(x.recordedEvents,0,500)||!int(x.waitEvents,0,500)||
    !int(x.blockedSourceEvents,0,500))return null;
 const lastFive=d.completedFiveTradeBatches.at(-1);
 return {...untrusted,privateJournalConnected:true,
  provenance:"SANITIZED_SYNTHETIC_LOCAL_LEDGER_NOT_VERIFIED_FORWARD",
  closedTrades:sum.closedTrades,
  waitEvents:d.dailyUTC.reduce((n,x)=>n+x.waitEvents,0),
  blockedSourceEvents:d.dailyUTC.reduce((n,x)=>n+x.blockedSourceEvents,0),
  netModeledUsd:sum.netModeledUsd,
  doubleCostStressNetUsd:sum.doubleCostStressNetUsd,
  winRate:sum.winRate,maxClosedDrawdownUsd:sum.maxClosedDrawdownUsd,
  averageNetR:sum.averageNetR,
  latestDayUTC:pick(day),latestWeekUTC:pick(week),
  lastFiveTradeBatch:lastFive?{closedTradeRange:lastFive.closedTradeRange,
   ...metric(lastFive)}:null,
  firstHundredClosedTrades:d.firstHundredClosedTradeCheckpoint?
   metric(d.firstHundredClosedTradeCheckpoint):null};
}
function inspect({
 authenticated=false,
 databasePath=process.env.GOLD_SYNTHETIC_PAPER_JOURNAL||"",
 mountRoot=process.env.GOLD_SYNTHETIC_PAPER_DISK_MOUNT||"",
 checkpointPath=process.env.GOLD_SYNTHETIC_PAPER_CHECKPOINT||"",
 manifestPath=process.env.GOLD_SYNTHETIC_PAPER_CHECKPOINT_MANIFEST||"",
 startupState
}={}){
 if(!databasePath)return {statusCode:200,body:empty()};
 if(!authenticated)return {statusCode:401,body:empty("PRIVATE_VIEWER_SESSION_REQUIRED")};
 try{
  if(typeof databasePath!=="string"||!path.isAbsolute(databasePath)||
     !databasePath.endsWith(".sqlite3"))throw Error("INVALID_LOCAL_PATH");
  const st=fs.lstatSync(databasePath);
  if(!st.isFile()||st.isSymbolicLink()||st.size>25_000_000)
    throw Error("INVALID_LOCAL_FILE");
  // An existing file on Render's ephemeral root must NEVER masquerade as
  // a durable journal. Checking mountinfo is a local preflight only, not
  // evidence that backups, billing, or provider rights were approved.
  const disk=verifyDisk({databasePath,mountRoot});
  if(!disk.safe)throw Error("MOUNTED_PAPER_VOLUME_NOT_VERIFIED");
  // The process starts with a single immutable checkpoint gate. A corrupt,
  // rolled-back or absent backup never authorizes paper report viewing.
  const startup=startupState===undefined?inspectStartup({
    databasePath,mountRoot
  }):startupState;
  if(!checkpointPath||!manifestPath)throw Error("CHECKPOINT_PATHS_MISSING");
  if(!startup||startup.mode!=="GOLD_PAPER_STARTUP_RECOVERY_GATE_V1"||
     startup.status!=="STARTUP_LOCAL_CHECKPOINT_READ_ONLY_VERIFIED"||
     startup.checkpointSafe!==true||
     startup.paperResultsDisplayAllowed!==true||
     startup.backupOffsiteVerified!==false||
     startup.independentHoldoutValidated!==false||
     startup.paperOrdersAllowed!==false||
     startup.liveOrdersAllowed!==false||
     startup.signal!=="WAIT"||startup.executable!==false)
    throw Error("PAPER_STARTUP_RECOVERY_NOT_VERIFIED");
  const runner=spawnSync("python3",[
   path.join(__dirname,"offline_paper_report_readonly.py"),
   databasePath,checkpointPath,manifestPath
  ],{encoding:"utf8",timeout:15000,maxBuffer:200000,
   env:{PATH:process.env.PATH||"/usr/bin:/bin",PYTHONIOENCODING:"utf-8"}});
  if(runner.status!==0||runner.error)throw Error("OFFLINE_REPORT_FAILED");
  const parsed=JSON.parse(runner.stdout);
  const clean=summarise(parsed);
  if(!clean)throw Error("OFFLINE_REPORT_UNVERIFIED");
  return {statusCode:200,body:clean};
 }catch(_error){
  return {statusCode:503,body:empty("PRIVATE_PAPER_JOURNAL_UNVERIFIED")};
 }
}
module.exports={inspect,summarise,empty};
