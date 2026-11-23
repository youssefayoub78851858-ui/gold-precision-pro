"use strict";
const a=require("node:assert/strict");
const fs=require("node:fs");
const os=require("node:os");
const path=require("node:path");
const {prepare}=require("./paper_volume_bootstrap");
const {verifyMountRoot}=require("./paper_persistent_disk_gate");
const defaults={
 status:"EMPTY_SYNTHETIC_LEDGER_CHECKPOINT_PREPARED",
 journalRows:0,checkpointRows:0,paperResultsDisplayAllowed:false,
 paperAutoRecordingEnabled:false,externalStorageAndBackupServiceProvisioned:false,
 dataSourceLicensed:false,liveMarketDataConnected:false,
 independentHoldoutValidated:false,brokerOrdersSent:0,providerRequestsMade:0,
 signal:"WAIT",executable:false
};
function wait(p){
 a.equal(p.signal,"WAIT");
 a.equal(p.executable,false);
 a.equal(p.paperOrdersAllowed,false);
 a.equal(p.liveOrdersAllowed,false);
 a.equal(p.providerRequestsMade,0);
 a.equal(p.brokerOrdersSent,0);
 a.equal(p.autoRecordingEnabled,false);
 a.equal(p.marketDataConnected,false);
 a(!JSON.stringify(p).includes("apiKey"));
 a(!JSON.stringify(p).includes("fake-secret"));
}
wait(prepare({mountRoot:""}));
a.equal(prepare({mountRoot:""}).status,"EXTERNAL_PERSISTENT_VOLUME_REQUIRED");
for(const p of ["/","/tmp","/mnt/data","/opt/render/project","relative","/var/data/.."]){
 const result=verifyMountRoot({mountRoot:p});
 a.equal(result.safe,false,p);
}
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),"paper-free-dry-run-"));
try {
 const result=prepare({mountRoot:tmp,initialize:true});
 wait(result);a.equal(result.storagePrepared,false);
 a.equal(fs.readdirSync(tmp).length,0);
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
let runs=0,checks=0;
const paperDirectory="/var/data/synthetic-paper";
const ownerId=typeof process.getuid==="function"?process.getuid():0;
const privateStat={isDirectory:()=>true,isSymbolicLink:()=>false,mode:0o40700,uid:ownerId};
const files={
 lstatSync(p){
  if(p===paperDirectory)return privateStat;
  const e=new Error("not found");
  e.code="ENOENT";
  throw e;
 },
 realpathSync(p){return p;}
};
const root="/var/data";
const rootGate=({mountRoot})=>{
 a.equal(mountRoot,root);
 checks++;
 return {safe:true,status:"EXPLICIT_ATTACHED_MOUNT_ROOT_CHECKED"};
};
const runner=(_program,args,options)=>{
 runs++;
 a.equal(_program,"python3");
 a.equal(args[1],paperDirectory);
 a.deepEqual(args.slice(2),[
  "synthetic-paper.sqlite3","synthetic-checkpoint.sqlite3",
  "synthetic-checkpoint.json"]);
 a.equal(options.timeout,20000);
 return {status:0,stdout:JSON.stringify(defaults)};
};
const test={mountRoot:root,paperDirectory,rootGate,fsAPI:files,runner};
const dry=prepare(test);wait(dry);
a.equal(dry.status,"EXTERNAL_VOLUME_VERIFIED_INITIALIZATION_DISABLED");
a.equal(runs,0);
const good=prepare({...test,initialize:true});wait(good);
a.equal(good.status,"EMPTY_SYNTHETIC_STORAGE_PREPARED_NOT_RECORDING");
a.equal(good.storagePrepared,true);
a.equal(runs,1);
a.equal(checks,2);
for(const forged of [
 {...defaults,signal:"BUY"},
 {...defaults,executable:true},
 {...defaults,paperAutoRecordingEnabled:true},
 {...defaults,externalStorageAndBackupServiceProvisioned:true},
 {...defaults,providerRequestsMade:1},
 {...defaults,marketDataOrTradingEnabled:true,journalRows:1},
 {...defaults,independentHoldoutValidated:true},
]){
 const outcome=prepare({...test,initialize:true,
  runner:()=>({status:0,stdout:JSON.stringify(forged)})});
 wait(outcome);a.equal(outcome.storagePrepared,false);
}
const exists={...files,lstatSync:p=>p===paperDirectory?privateStat:{isFile:()=>true}};
const stop=prepare({...test,fsAPI:exists,initialize:true});
wait(stop);a.equal(stop.status,"EXISTING_OR_PARTIAL_JOURNAL_NEEDS_MANUAL_REVIEW");
for(const malformed of [
 "",
 root,
 "/var/data/gold-live",
 "/var/data/synthetic-paper/..",
 "/tmp/synthetic-paper",
 "/var/data/synthetic-paper/extra"
]){
 const state=prepare({...test,paperDirectory:malformed,initialize:true});
 wait(state);
 a.equal(state.storagePrepared,false);
 a.equal(state.status,"DEDICATED_PAPER_SUBDIRECTORY_REQUIRED");
}
for(const unsafe of [
 {...privateStat,mode:0o40755},
 {...privateStat,uid:ownerId+1},
 {...privateStat,isSymbolicLink:()=>true},
]){
 const state=prepare({...test,initialize:true,fsAPI:{
  ...files,lstatSync:p=>p===paperDirectory?unsafe:files.lstatSync(p)
 }});
 wait(state);a.equal(state.status,"PAPER_SUBDIRECTORY_NOT_OWNER_ONLY");
}
const linked=prepare({...test,initialize:true,fsAPI:{
 ...files,realpathSync:p=>p===paperDirectory?"/var/data/gold-live":p
}});
wait(linked);a.equal(linked.status,"PAPER_SUBDIRECTORY_NOT_OWNER_ONLY");
a.equal(runs,1,"unsafe attempts never initialize journal");
const down=prepare({...test,rootGate:()=>({safe:false,status:"NO_VOLUME"}),initialize:true});
wait(down);a.equal(down.storagePrepared,false);
for(const names of [
 ["a.sqlite3","a.sqlite3","c.json"],
 ["../a.sqlite3","b.sqlite3","c.json"],
 ["a.json","b.sqlite3","c.json"]
]){
 const state=prepare({...test,fileNames:names,initialize:true});
 wait(state);a.equal(state.status,"BOOTSTRAP_PATHS_INVALID");
}
console.log("PASS no-disk/no-payment default WAIT, mocked pre-existing volume dry run and exact opt-in init, forged/untrusted result veto");
