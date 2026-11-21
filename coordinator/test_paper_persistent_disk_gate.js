"use strict";
const a=require("node:assert/strict");
const fs=require("node:fs");
const os=require("node:os");
const path=require("node:path");
const {verify,mounts}=require("./paper_persistent_disk_gate");
const root="/var/data";
const file="/var/data/paper/forward.sqlite3";
const mountInfo="21 14 0:39 / / rw,relatime - overlay overlay rw\n"+
 "22 21 8:1 / /var/data rw,relatime - ext4 /dev/sdb1 rw\n";
const fake={
 lstatSync(p){
  if(p===root)return {isDirectory:()=>true,isSymbolicLink:()=>false};
  if(p===file)return {isFile:()=>true,isSymbolicLink:()=>false,size:16384};
  throw Error("UNEXPECTED_PATH");
 },
 realpathSync(p){return p;},
 readFileSync(p){a.equal(p,"/proc/self/mountinfo");return mountInfo;}
};
const base={databasePath:file,mountRoot:root,fsAPI:fake};
a.equal(verify(base).safe,true);
a.equal(verify(base).status,"EXPLICIT_ATTACHED_LOCAL_MOUNT_CHECKED");
a.equal(mounts(mountInfo).find(m=>m.mountPoint===root)?.type,"ext4");
for(const changes of [
 {databasePath:""}, {mountRoot:""},
 {databasePath:"/opt/render/project/db.sqlite3"},
 {databasePath:"/var/data/../etc/paper.sqlite3"},
 {databasePath:"/var/dataset/paper.sqlite3"},
 {mountRoot:"/"},
 {mountRoot:"/tmp"},
 {mountRoot:"/opt/render"},
 {mountRoot:"/mnt/data"},
 {mountInfo:"21 14 0:39 / / rw - overlay overlay rw\n"},
 {mountInfo:mountInfo.replace("ext4","overlay")},
 {mountInfo:mountInfo.replace("ext4","tmpfs")},
 {mountInfo:mountInfo.replace("/var/data","/var/data-other")},
 {mountInfo:mountInfo+mountInfo.split("\n")[1]+"\n"},
 {fsAPI:{...fake,realpathSync:p=>p===file?"/tmp/linked":p}},
 {fsAPI:{...fake,lstatSync:p=>({...fake.lstatSync(p),
  isSymbolicLink:()=>p===file})}},
 {fsAPI:{...fake,lstatSync:p=>({...fake.lstatSync(p),
  isSymbolicLink:()=>p===root})}},
 {fsAPI:{...fake,lstatSync:p=>({...fake.lstatSync(p),
  size:p===file?25000001:undefined})}}
 ]){
 const report=verify({...base,...changes});
 a.equal(report.safe,false,JSON.stringify(Object.keys(changes)));
 a(report.status.startsWith("PERSISTENT_"));
}
// Do not treat a fake existing SQLite file in /tmp as durable.
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),"offline-paper-volume-"));
try{
 const p=path.join(tmp,"fake.sqlite3");fs.writeFileSync(p,"fake");
 a.equal(verify({databasePath:p,mountRoot:tmp}).safe,false);
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
console.log("PASS explicit mount contract (mock only), no tmp/overlay/root fallback; no storage created");
