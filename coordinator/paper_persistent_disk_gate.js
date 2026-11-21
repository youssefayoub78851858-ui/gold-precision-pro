"use strict";
/**
 * STRICTLY READ-ONLY preflight for a future attached persistent volume.
 * Never creates, mounts, prices, upgrades or writes storage. A configured
 * path or a SQLite file on Render's ephemeral root is NOT durable storage.
 * A passing local mount check is not proof of backups or plan entitlement.
 */
const fs=require("node:fs");
const path=require("node:path");
const MOUNT_TYPES=new Set(["ext4","xfs","btrfs","zfs"]);
const BAD_ROOTS=["/tmp","/var/tmp","/opt/render","/mnt/data","/dev/shm","/run","/proc","/sys"];
function decodeMount(s){
 return s.replace(/\\(040|011|012|134)/g,(_m,o)=>({
  "040":" ","011":"\t","012":"\n","134":"\\"
 })[o]);
}
function mounts(text){
 if(typeof text!=="string")return [];
 return text.split("\n").map(line=>{
  const [left,right]=line.split(" - ");
  if(!left||!right)return null;
  const a=left.split(" "),b=right.split(" ");
  if(a.length<5||b.length<2)return null;
  return {mountPoint:decodeMount(a[4]),type:b[0],source:b[1]};
 }).filter(Boolean);
}
function verify({databasePath="",mountRoot="",mountInfo,fsAPI=fs}={}){
 const fail=code=>({safe:false,status:code});
 if(!databasePath||!mountRoot)return fail("PERSISTENT_DISK_NOT_CONFIGURED");
 if(typeof databasePath!=="string"||typeof mountRoot!=="string"||
    !path.isAbsolute(databasePath)||!path.isAbsolute(mountRoot)||
    path.normalize(databasePath)!==databasePath||
    path.normalize(mountRoot)!==mountRoot||
    databasePath.includes("\0")||mountRoot.includes("\0")||
    !databasePath.endsWith(".sqlite3")||
    mountRoot==="/"||BAD_ROOTS.some(x=>mountRoot===x||mountRoot.startsWith(x+"/"))||
    !databasePath.startsWith(mountRoot+"/"))
    return fail("PERSISTENT_DISK_LOCATION_INVALID");
 try{
  const root=fsAPI.lstatSync(mountRoot);
  if(!root.isDirectory()||root.isSymbolicLink()||
     fsAPI.realpathSync(mountRoot)!==mountRoot)
    return fail("PERSISTENT_MOUNT_ROOT_UNVERIFIED");
  const file=fsAPI.lstatSync(databasePath);
  if(!file.isFile()||file.isSymbolicLink()||file.size>25_000_000||
     fsAPI.realpathSync(databasePath)!==databasePath)
    return fail("PERSISTENT_JOURNAL_FILE_UNVERIFIED");
  const raw=mountInfo??fsAPI.readFileSync("/proc/self/mountinfo","utf8");
  const found=mounts(raw).filter(x=>x.mountPoint===mountRoot);
  if(found.length!==1||!MOUNT_TYPES.has(found[0].type)||
     found[0].source==="overlay"||found[0].source==="tmpfs")
    return fail("PERSISTENT_VOLUME_MOUNT_NOT_VERIFIED");
  return {safe:true,status:"EXPLICIT_ATTACHED_LOCAL_MOUNT_CHECKED"};
 }catch(_e){
  return fail("PERSISTENT_VOLUME_OR_JOURNAL_UNAVAILABLE");
 }
}
module.exports={verify,mounts};
