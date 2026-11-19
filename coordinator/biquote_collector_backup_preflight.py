"""Offline read-only sealed-vault backup comparison. Never deploys or trades."""
from __future__ import annotations
import datetime as dt
import os
import pathlib
import stat
from biquote_private_forward_vault import FILE,START,FRAMES_ORDER,load_vault

END=START+dt.timedelta(days=7)
SAFE={"mode":"BIQUOTE_COLLECTOR_BACKUP_PREFLIGHT_V1","signal":"WAIT",
"executable":False,"deployApproved":False,"collectorRestartApproved":False,
"paperOrdersAllowed":False,"liveOrdersAllowed":False,
"independentOffsiteBackupVerified":False,"archiveRecoveryProven":False,
"sourceRightsVerified":False,"providerRequestsMade":0,"archiveWriteOperations":0}

def blocked(reason):
    return {**SAFE,"status":"BLOCKED","reason":reason,
            "exactSealedBytesMatch":False,"sourceClosedCounts":None}

def review(source,backup,*,now_utc,finished=False):
    """Compare existing private signed snapshots, never write/copy either."""
    if (not isinstance(now_utc,dt.datetime) or now_utc.tzinfo is None
        or now_utc.utcoffset()!=dt.timedelta(0)):
        return blocked("UTC_CLOCK_REQUIRED")
    if type(finished) is not bool:
        return blocked("CAPTURE_STATUS_INVALID")
    if not isinstance(source,(str,os.PathLike)) or not isinstance(backup,(str,os.PathLike)):
        return blocked("TWO_ARCHIVES_REQUIRED")
    a,b=pathlib.Path(source),pathlib.Path(backup)
    if not a.is_absolute() or not b.is_absolute() or a==b or ".." in a.parts+b.parts:
        return blocked("INVALID_OR_IDENTICAL_ARCHIVE_PATH")
    try:
        for folder in (a,b):
            folder_stat=folder.lstat()
            fstat=(folder/FILE).lstat()
            if (not stat.S_ISDIR(folder_stat.st_mode) or
                stat.S_ISLNK(folder_stat.st_mode) or folder_stat.st_mode&0o077 or
                not stat.S_ISREG(fstat.st_mode) or stat.S_ISLNK(fstat.st_mode) or
                fstat.st_mode&0o077 or fstat.st_uid!=os.getuid() or
                folder_stat.st_uid!=os.getuid()):
                return blocked("INSECURE_SNAPSHOT_PERMISSIONS")
        if os.path.samefile(a/FILE,b/FILE):
            return blocked("BACKUP_ALIAS_NOT_INDEPENDENT")
        original,snapshot=load_vault(a),load_vault(b)
        counts={tf:len(original["closed"][tf]) for tf in FRAMES_ORDER}
        if not original["quoteObservations"] or not any(counts.values()):
            return blocked("EMPTY_SOURCE_ARCHIVE")
        if (counts!={tf:len(snapshot["closed"][tf]) for tf in FRAMES_ORDER} or
            len(original["quoteObservations"])!=len(snapshot["quoteObservations"])):
            return blocked("BACKUP_COUNTERS_MISMATCH")
        if (a/FILE).read_bytes()!=(b/FILE).read_bytes():
            return blocked("BACKUP_SEALED_CONTENT_MISMATCH")
        same_device=(a/FILE).stat().st_dev==(b/FILE).stat().st_dev
    except (OSError,ValueError,KeyError,TypeError):
        return blocked("SNAPSHOT_UNREADABLE_OR_CORRUPTED")
    phase=("ACTIVE_CAPTURE_DO_NOT_RESTART" if now_utc<END
           else "FINAL_CAPTURE_PROOF_REQUIRED" if not finished
           else "EXTERNAL_RECOVERY_EVIDENCE_REQUIRED")
    return {**SAFE,"status":"LOCAL_MATCH_NO_DEPLOY_APPROVAL","reason":phase,
            "exactSealedBytesMatch":True,"sourceClosedCounts":counts,
            "sameDeviceDetected":same_device,"finishedOnlySelfReported":finished}
