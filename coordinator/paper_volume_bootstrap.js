"use strict";
/**
 * Explicit, opt-in ONE-TIME preparation of an EMPTY synthetic paper ledger.
 *
 * This never creates a Render disk, upgrades a plan, calls a provider,
 * schedules a background recorder, or places paper/real trades. On the
 * current Free Render host (no persistent disk), it returns WAIT with no
 * writes. Only a previously attached verified volume can be prepared.
 *
 * Usage (by an approved operator AFTER provisioning separately):
 *   node coordinator/paper_volume_bootstrap.js --check
 *   node coordinator/paper_volume_bootstrap.js --initialize
 *
 * The paths are operator-only env vars, never browser-supplied or logged.
 */
const fs=require("node:fs");
const path=require("node:path");
const {spawnSync}=require("node:child_process");
const {verifyMountRoot}=require("./paper_persistent_disk_gate");
const MODE="GOLD_OFFLINE_PAPER_VOLUME_BOOTSTRAP_V1";
const DEFAULT_FILES=[
 "synthetic-paper.sqlite3","synthetic-checkpoint.sqlite3","synthetic-checkpoint.json"
];
function blocked(status){
 return {mode:MODE,status,storagePrepared:false,autoRecordingEnabled:false,
  marketDataConnected:false,providerApprovalVerified:false,
  paperOrdersAllowed:false,liveOrdersAllowed:false,providerRequestsMade:0,
  brokerOrdersSent:0,signal:"WAIT",executable:false};
}
function prepare({
 mountRoot=process.env.GOLD_SYNTHETIC_PAPER_DISK_MOUNT||"",
 fileNames=DEFAULT_FILES,
 initialize=false,rootGate=verifyMountRoot,fsAPI=fs,runner=spawnSync
}={}){
 if(!mountRoot)return blocked("EXTERNAL_PERSISTENT_VOLUME_REQUIRED");
 if(typeof mountRoot!=="string"||!path.isAbsolute(mountRoot)||
    path.normalize(mountRoot)!==mountRoot||
    !Array.isArray(fileNames)||fileNames.length!==3||
    new Set(fileNames).size!==3||
    fileNames.some((x,i)=>typeof x!=="string"||!x||
     !/^[a-zA-Z0-9_-]{1,50}\.(sqlite3|json)$/.test(x)||
     (i<2?!x.endsWith(".sqlite3"):!x.endsWith(".json"))))
   return blocked("BOOTSTRAP_PATHS_INVALID");
 try{
  const m=rootGate({mountRoot});
  if(!m||m.safe!==true||
     m.status!=="EXPLICIT_ATTACHED_MOUNT_ROOT_CHECKED")
    return blocked("ATTACHED_PERSISTENT_VOLUME_NOT_VERIFIED");
  const names=fileNames.map(x=>path.join(mountRoot,x));
  for(const filepath of names){
   try{
    fsAPI.lstatSync(filepath);
    return blocked("EXISTING_OR_PARTIAL_JOURNAL_NEEDS_MANUAL_REVIEW");
   }catch(e){
    if(e?.code!=="ENOENT")
      return blocked("DESTINATION_STATE_NOT_VERIFIED");
   }
  }
  if(!initialize)return blocked("EXTERNAL_VOLUME_VERIFIED_INITIALIZATION_DISABLED");
  const out=runner("python3",[
   path.join(__dirname,"paper_fresh_volume_init.py"),mountRoot,...fileNames
  ],{encoding:"utf8",timeout:20000,maxBuffer:4000,
     env:{PATH:process.env.PATH||"/usr/bin:/bin",PYTHONIOENCODING:"utf-8"}});
  if(out?.status!==0||out.error||typeof out.stdout!=="string")
    return blocked("EMPTY_LOCAL_JOURNAL_INIT_REJECTED");
  const result=JSON.parse(out.stdout);
  if(result.status!=="EMPTY_SYNTHETIC_LEDGER_CHECKPOINT_PREPARED"||
     result.journalRows!==0||result.checkpointRows!==0||
     result.paperResultsDisplayAllowed!==false||
     result.paperAutoRecordingEnabled!==false||
     result.externalStorageAndBackupServiceProvisioned!==false||
     result.dataSourceLicensed!==false||
     result.liveMarketDataConnected!==false||
     result.independentHoldoutValidated!==false||
     result.brokerOrdersSent!==0||result.providerRequestsMade!==0||
     result.signal!=="WAIT"||result.executable!==false)
    return blocked("BOOTSTRAP_RESULT_UNTRUSTED");
  return {...blocked("EMPTY_SYNTHETIC_STORAGE_PREPARED_NOT_RECORDING"),
    storagePrepared:true};
 }catch(_error){
  return blocked("BOOTSTRAP_VOLUME_OR_JOURNAL_UNAVAILABLE");
 }
}
if(require.main===module){
 if(!["--check","--initialize"].includes(process.argv[2])||
    process.argv.length!==3){
  process.stderr.write("Use only --check or --initialize; storage is not provisioned automatically.\n");
  process.exitCode=2;
 }else{
  const report=prepare({initialize:process.argv[2]==="--initialize"});
  process.stdout.write(JSON.stringify(report)+"\n");
  if(!report.storagePrepared&&process.argv[2]==="--initialize")
   process.exitCode=2;
 }
}
module.exports={prepare,blocked};
