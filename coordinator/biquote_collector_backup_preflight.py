"""Offline read-only sealed-vault backup comparison. Never deploys or trades."""
from __future__ import annotations
import datetime as dt
import os
import pathlib
import stat
from biquote_private_forward_vault import FILE,START,FRAMES_ORDER,MAX_VAULT_BYTES,load_vault

END=START+dt.timedelta(days=7)
SAFE={"mode":"BIQUOTE_COLLECTOR_BACKUP_PREFLIGHT_V1","signal":"WAIT",
"executable":False,"deployApproved":False,"collectorRestartApproved":False,
"paperOrdersAllowed":False,"liveOrdersAllowed":False,
"independentOffsiteBackupVerified":False,"archiveRecoveryProven":False,
"sourceRightsVerified":False,"providerRequestsMade":0,"archiveWriteOperations":0}

def blocked(reason):
    return {**SAFE,"status":"BLOCKED","reason":reason,
            "exactSealedBytesMatch":False,"sourceClosedCounts":None}

def _secure_existing_archive_bytes(folder):
    """Read one sealed private file without following symlinks or accepting
    multiple hard links, then reject any inode/metadata change while read.

    A passing comparison is only a *point-in-time local check*, not an
    offsite backup or exclusive lock on a running source collector.
    """
    if folder.resolve(strict=True) != folder:
        raise ValueError("NON_CANONICAL_ARCHIVE_DIRECTORY")
    file = folder / FILE
    directory = folder.lstat()
    before = file.lstat()
    if (not stat.S_ISDIR(directory.st_mode) or
        stat.S_ISLNK(directory.st_mode) or
        (directory.st_mode & 0o077) != 0 or
        directory.st_uid != os.getuid() or
        not stat.S_ISREG(before.st_mode) or
        stat.S_ISLNK(before.st_mode) or
        (before.st_mode & 0o077) != 0 or
        before.st_uid != os.getuid() or
        before.st_nlink != 1 or
        not 0 < before.st_size <= MAX_VAULT_BYTES):
        raise ValueError("INSECURE_OR_ALIASED_PRIVATE_ARCHIVE")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(file, flags)
    try:
        opened = os.fstat(fd)
        if (not stat.S_ISREG(opened.st_mode) or
            (opened.st_dev, opened.st_ino) !=
            (before.st_dev, before.st_ino) or
            opened.st_nlink != 1 or opened.st_uid != os.getuid() or
            (opened.st_mode & 0o077) != 0):
            raise ValueError("ARCHIVE_REPLACED_DURING_OPEN")
        with os.fdopen(fd, "rb", closefd=False) as source:
            contents = source.read(MAX_VAULT_BYTES + 1)
        after = os.fstat(fd)
        latest = file.lstat()
        identity = lambda st: (
            st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns,
            st.st_ctime_ns, st.st_nlink, st.st_mode, st.st_uid
        )
        if (len(contents) != before.st_size or
            identity(before) != identity(opened) or
            identity(opened) != identity(after) or
            identity(after) != identity(latest) or
            len(contents) > MAX_VAULT_BYTES):
            raise ValueError("ARCHIVE_CHANGED_WHILE_CHECKING")
        return contents, after.st_dev
    finally:
        os.close(fd)


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
        # Reuse only the files whose exact owner-only bytes were checked.
        # Reading those bytes again after load_vault makes concurrent source
        # collection activity a conservative failed check, not a green copy.
        src_before, src_device=_secure_existing_archive_bytes(a)
        dst_before, dst_device=_secure_existing_archive_bytes(b)
        if os.path.samefile(a/FILE,b/FILE):
            return blocked("BACKUP_ALIAS_NOT_INDEPENDENT")
        original,snapshot=load_vault(a),load_vault(b)
        if (src_before,src_device)!=_secure_existing_archive_bytes(a) or (
            dst_before,dst_device)!=_secure_existing_archive_bytes(b):
            return blocked("ARCHIVE_CHANGED_WHILE_CHECKING")
        counts={tf:len(original["closed"][tf]) for tf in FRAMES_ORDER}
        if not original["quoteObservations"] or not any(counts.values()):
            return blocked("EMPTY_SOURCE_ARCHIVE")
        if (counts!={tf:len(snapshot["closed"][tf]) for tf in FRAMES_ORDER} or
            len(original["quoteObservations"])!=len(snapshot["quoteObservations"])):
            return blocked("BACKUP_COUNTERS_MISMATCH")
        if src_before!=dst_before:
            return blocked("BACKUP_SEALED_CONTENT_MISMATCH")
        same_device=src_device==dst_device
    except (OSError,ValueError,KeyError,TypeError):
        return blocked("SNAPSHOT_UNREADABLE_OR_CORRUPTED")
    phase=("ACTIVE_CAPTURE_DO_NOT_RESTART" if now_utc<END
           else "FINAL_CAPTURE_PROOF_REQUIRED" if not finished
           else "EXTERNAL_RECOVERY_EVIDENCE_REQUIRED")
    return {**SAFE,"status":"LOCAL_MATCH_NO_DEPLOY_APPROVAL","reason":phase,
            "exactSealedBytesMatch":True,"sourceClosedCounts":counts,
            "sameDeviceDetected":same_device,"finishedOnlySelfReported":finished}
