"use strict";
/**
 * Review-mode startup-only, fail-closed synthetic paper ledger checkpoint gate.
 *
 * No writes, restores, provider requests, account lookup, payment or order.
 * Even successful verification proves LOCAL consistency, never offsite backup.
 * Configured paths stay on server, never in HTTP responses.
 */
const path=require("node:path");
const fs=require("node:fs");
const {spawnSync}=require("node:child_process");
const {verify:verifyDisk}=require("./paper_persistent_disk_gate");
const MODE="GOLD_PAPER_STARTUP_RECOVERY_GATE_V1";

function wait(status){
 return Object.freeze({
  mode:MODE,status,checkpointSafe:false,
  paperResultsDisplayAllowed:false,
  backupOffsiteVerified:false,
  independentHoldoutValidated:false,
  marketDataConnected:false,
  paperOrdersAllowed:false,liveOrdersAllowed:false,
  providerRequestsMade:0,brokerOrdersSent:0,
  signal:"WAIT",executable:false
 });
}
function inspect({
 databasePath=process.env.GOLD_SYNTHETIC_PAPER_JOURNAL||"",
 mountRoot=process.env.GOLD_SYNTHETIC_PAPER_DISK_MOUNT||"",
 paperDirectory=process.env.GOLD_SYNTHETIC_PAPER_PRIVATE_DIR||"",
 checkpointPath=process.env.GOLD_SYNTHETIC_PAPER_CHECKPOINT||"",
 manifestPath=process.env.GOLD_SYNTHETIC_PAPER_CHECKPOINT_MANIFEST||"",
 verifyMount=verifyDisk,
 runner=spawnSync
}={}){
 if(!databasePath&&!mountRoot&&!checkpointPath&&!manifestPath)
  return wait("NO_PERSISTENT_PAPER_JOURNAL_CONFIGURED");
 if(!databasePath||!mountRoot||!checkpointPath||!manifestPath)
  return wait("STARTUP_PAPER_CHECKPOINT_CONFIGURATION_INCOMPLETE");
 try{
  const mounts=verifyMount({databasePath,mountRoot});
  if(mounts.safe!==true)
   return wait("PERSISTENT_PAPER_DISK_NOT_ATTESTED");
  const paths=[databasePath,checkpointPath,manifestPath];
  if(!paths.every(x=>typeof x==="string"&&path.isAbsolute(x)&&
       path.normalize(x)===x)||new Set(paths).size!==3||
     !checkpointPath.endsWith(".sqlite3")||!manifestPath.endsWith(".json"))
   return wait("STARTUP_PAPER_CHECKPOINT_LOCATION_INVALID");
  const expectedPrivate=path.join(mountRoot,"synthetic-paper");
  if(typeof paperDirectory!=="string"||paperDirectory!==expectedPrivate||
     paths.some(x=>path.dirname(x)!==paperDirectory))
   return wait("STARTUP_DEDICATED_PAPER_SUBDIRECTORY_REQUIRED");
  const dir=fs.lstatSync(paperDirectory);
  const owner=typeof process.getuid==="function"?process.getuid():null;
  if(!dir.isDirectory()||dir.isSymbolicLink()||typeof dir.mode!=="number"||
     (dir.mode&0o077)!==0||owner===null||dir.uid!==owner||
     fs.realpathSync(paperDirectory)!==paperDirectory)
   return wait("STARTUP_PAPER_SUBDIRECTORY_NOT_OWNER_ONLY");
  for(const p of [checkpointPath,manifestPath]){
   const st=fs.lstatSync(p);
   if(!st.isFile()||st.isSymbolicLink()||st.size>25_000_000||
      fs.realpathSync(p)!==p)
    return wait("STARTUP_PAPER_CHECKPOINT_FILE_UNVERIFIED");
  }
  const out=runner("python3",[
    path.join(__dirname,"paper_startup_recovery_check.py"),
    databasePath,checkpointPath,manifestPath
   ],{encoding:"utf8",timeout:20000,maxBuffer:5000,
      env:{PATH:process.env.PATH||"/usr/bin:/bin",
           PYTHONIOENCODING:"utf-8"}});
  if(out.status!==0||out.error||typeof out.stdout!=="string")
   return wait("STARTUP_PAPER_CHECKPOINT_REJECTED");
  const result=JSON.parse(out.stdout);
  if(result.mode!=="GOLD_SYNTHETIC_PAPER_STARTUP_RECOVERY_GATE_V1"||
     result.status!=="LOCAL_JOURNAL_CHECKPOINT_ANCESTRY_VERIFIED"||
     result.externallyDurableOrReplicated!==false||
     result.independentHoldoutValidated!==false||
     result.realMarketDataConnected!==false||
     result.paperOrdersAllowed!==false||
     result.liveOrdersAllowed!==false||
     result.providerRequestsMade!==0||result.brokerOrdersSent!==0||
     result.signal!=="WAIT"||result.executable!==false||
     !Number.isSafeInteger(result.journalRows)||
     !Number.isSafeInteger(result.checkpointRows)||
     !Number.isSafeInteger(result.closedPaperTrades)||
     !Number.isSafeInteger(result.checkpointClosedPaperTrades)||
     result.journalRows<result.checkpointRows||
     result.closedPaperTrades<result.checkpointClosedPaperTrades||
     result.checkpointRows<0||result.closedPaperTrades<0)
   return wait("STARTUP_PAPER_CHECKPOINT_UNTRUSTED");
  return Object.freeze({
   ...wait("STARTUP_LOCAL_CHECKPOINT_READ_ONLY_VERIFIED"),
   checkpointSafe:true,paperResultsDisplayAllowed:true
  });
 }catch(_e){
  return wait("STARTUP_PAPER_CHECKPOINT_UNAVAILABLE");
 }
}
module.exports={inspect,wait};
