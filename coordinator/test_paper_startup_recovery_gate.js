"use strict";
const a=require("node:assert/strict");
const fs=require("node:fs");
const os=require("node:os");
const path=require("node:path");
const {inspect}=require("./paper_startup_recovery_gate");
const {inspect:bridge}=require("./review_paper_report_bridge");
const empty=inspect({databasePath:"",mountRoot:"",
  checkpointPath:"",manifestPath:""});
a.equal(empty.status,"NO_PERSISTENT_PAPER_JOURNAL_CONFIGURED");
a.equal(empty.checkpointSafe,false);
a.equal(empty.paperResultsDisplayAllowed,false);
a.equal(empty.signal,"WAIT");
a.equal(empty.executable,false);
a.equal(bridge({databasePath:"",authenticated:false}).body.privateJournalConnected,false);
const missing=inspect({databasePath:"/var/data/paper/live.sqlite3",
 mountRoot:"/var/data",checkpointPath:"",manifestPath:""});
a.equal(missing.status,"STARTUP_PAPER_CHECKPOINT_CONFIGURATION_INCOMPLETE");
a.equal(missing.paperResultsDisplayAllowed,false);
const root=fs.mkdtempSync(path.join(os.tmpdir(),"startup-synthetic-"));
try{
 const file=path.join(root,"test.sqlite3");
 const backup=path.join(root,"check.sqlite3");
 const manifest=path.join(root,"check.json");
 for(const p of [file,backup,manifest])fs.writeFileSync(p,"fixture");
 const base={databasePath:file,mountRoot:root,
  checkpointPath:backup,manifestPath:manifest};
 const verified={
  mode:"GOLD_SYNTHETIC_PAPER_STARTUP_RECOVERY_GATE_V1",
  status:"LOCAL_JOURNAL_CHECKPOINT_ANCESTRY_VERIFIED",
  journalRows:2,checkpointRows:2,
  closedPaperTrades:1,checkpointClosedPaperTrades:1,
  externallyDurableOrReplicated:false,independentHoldoutValidated:false,
  realMarketDataConnected:false,paperOrdersAllowed:false,
  liveOrdersAllowed:false,providerRequestsMade:0,brokerOrdersSent:0,
  signal:"WAIT",executable:false
 };
 const mock={
  ...base,verifyMount:()=>({safe:true}),
  runner:()=>({status:0,stdout:JSON.stringify(verified)})
 };
 const accepted=inspect(mock);
 a.equal(accepted.status,"STARTUP_LOCAL_CHECKPOINT_READ_ONLY_VERIFIED");
 a.equal(accepted.checkpointSafe,true);
 a.equal(accepted.paperResultsDisplayAllowed,true);
 a.equal(accepted.backupOffsiteVerified,false);
 a.equal(accepted.brokerOrdersSent,0);
 a(!JSON.stringify(accepted).includes(root));
 for(const v of [
  {...verified,status:"FULL_READY"},
  {...verified,signal:"BUY"},
  {...verified,executable:true},
  {...verified,liveOrdersAllowed:true},
  {...verified,paperOrdersAllowed:true},
  {...verified,externallyDurableOrReplicated:true},
  {...verified,independentHoldoutValidated:true},
  {...verified,providerRequestsMade:1},
  {...verified,checkpointRows:3},
  {...verified,checkpointClosedPaperTrades:2},
  {...verified,journalRows:-1}
 ]){
  const r=inspect({...mock,runner:()=>({status:0,stdout:JSON.stringify(v)})});
  a.equal(r.checkpointSafe,false);
  a.equal(r.paperResultsDisplayAllowed,false);
  a.equal(r.signal,"WAIT");
 }
 const bad=inspect({...mock,verifyMount:()=>({safe:false})});
 a.equal(bad.status,"PERSISTENT_PAPER_DISK_NOT_ATTESTED");
 a.equal(bad.checkpointSafe,false);
 for(const p of ["/opt/render/project/check.sqlite3","/tmp/check.sqlite3","relative.sqlite3"]){
  a.equal(inspect({...mock,checkpointPath:p}).checkpointSafe,false);
 }
 const fake=path.join(root,"sym.sqlite3");
 fs.symlinkSync(backup,fake);
 a.equal(inspect({...mock,checkpointPath:fake}).checkpointSafe,false);
 const proc=inspect({...mock,runner:()=>({status:2,stdout:"",stderr:"bad"})});
 a.equal(proc.checkpointSafe,false);
}finally{fs.rmSync(root,{recursive:true,force:true});}
console.log("PASS paper boot no-config WAIT, mocked verified checkpoint safe, forged approval and bad storage fail closed");
