"""Isolated offline restoration rehearsal of one sealed owner-only vault backup.

No cloud access, no trading, no public price output, no writes to source or
backup, and no deploy approval. Rehearses a LOCAL recovery, not verified
offsite durability or a completed Render restore.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import stat
import tempfile
from biquote_private_forward_vault import FILE, FRAMES_ORDER, MAX_VAULT_BYTES, load_vault

SAFE = {
    "mode": "BIQUOTE_PRIVATE_ISOLATED_RESTORE_REHEARSAL_OFFLINE_V1",
    "signal": "WAIT", "executable": False,
    "paperOrdersAllowed": False, "liveOrdersAllowed": False,
    "providerRequestsMade": 0, "tradeOrdersSent": 0,
    "collectorArchiveWrites": 0, "backupArchiveWrites": 0,
    "deployApproved": False, "collectorRestartApproved": False,
    "sourceRightsVerified": False, "independentBackupVerified": False,
    "cloudBackupRecoverabilityVerified": False,
    "brokerCalendarVerified": False, "strategyProfitabilityProven": False,
}
def blocked(code):
    return {**SAFE, "status": "BLOCKED", "reason": code,
            "isolatedLocalRestorePassed": False,
            "closedCounts": {tf: 0 for tf in FRAMES_ORDER},
            "locallyTimestampedCounts": {tf: 0 for tf in FRAMES_ORDER},
            "legacyUnknownCounts": {tf: 0 for tf in FRAMES_ORDER}}

def rehearse_restore(backup_dir, *, now_utc):
    """Open immutable signed backup and clone to disposable 0700 directory.

    Returns COUNTS only. The clone is removed at function exit, and the
    backup file is never modified; no actual Render backup can be inferred.
    """
    if (not isinstance(now_utc, dt.datetime) or now_utc.tzinfo is None or
            now_utc.utcoffset() != dt.timedelta(0)):
        return blocked("UTC_CLOCK_REQUIRED")
    if not isinstance(backup_dir, (str, os.PathLike)):
        return blocked("PRIVATE_BACKUP_DIRECTORY_REQUIRED")
    backup = pathlib.Path(backup_dir)
    if not backup.is_absolute() or ".." in backup.parts or backup == pathlib.Path("/"):
        return blocked("INVALID_BACKUP_PATH")
    file = backup / FILE
    try:
        st_dir = backup.lstat()
        st_file = file.lstat()
        if (not stat.S_ISDIR(st_dir.st_mode) or stat.S_ISLNK(st_dir.st_mode)
                or st_dir.st_mode & 0o077 or st_dir.st_uid != os.getuid()
                or not stat.S_ISREG(st_file.st_mode) or stat.S_ISLNK(st_file.st_mode)
                or st_file.st_mode & 0o077 or st_file.st_uid != os.getuid()
                or st_file.st_size <= 0 or st_file.st_size > MAX_VAULT_BYTES):
            return blocked("BACKUP_FILE_PERMISSIONS_OR_SIZE_INVALID")
        # Loader rechecks SHA, provenance, candle timestamps, quote geometry,
        # and optional firstObservedClosedUTC (no lookahead claims).
        archive = load_vault(backup)
        counts = {tf: len(archive["closed"][tf]) for tf in FRAMES_ORDER}
        if not archive["quoteObservations"] or not any(counts.values()):
            return blocked("BACKUP_EMPTY_OR_NOT_RECOVERABLE")
        receipts = archive.get("firstObservedClosedUTC")
        timed = {tf: len(receipts[tf]) if receipts is not None else 0
                 for tf in FRAMES_ORDER}
        unknown = {tf: counts[tf] - timed[tf] for tf in FRAMES_ORDER}
        # Read through nofollow so replacing a symlink cannot trick us.
        fd = os.open(file, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            check = os.fstat(fd)
            if (not stat.S_ISREG(check.st_mode) or check.st_mode & 0o077
                    or check.st_size != st_file.st_size
                    or (check.st_dev, check.st_ino) != (st_file.st_dev, st_file.st_ino)):
                return blocked("BACKUP_FILE_CHANGED_DURING_REHEARSAL")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                original_bytes = stream.read(MAX_VAULT_BYTES + 1)
        finally:
            os.close(fd)
        if len(original_bytes) != st_file.st_size:
            return blocked("BACKUP_READ_INCOMPLETE")
        # All rehearsal writes stay in an ephemeral owner-only scratch dir;
        # nothing is ever sent to a public provider or copied to GitHub.
        with tempfile.TemporaryDirectory(prefix="gpp-isolated-restore-") as temp:
            restored = pathlib.Path(temp) / "recovered"
            restored.mkdir(mode=0o700)
            target = restored / FILE
            out = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                          getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                with os.fdopen(out, "wb", closefd=False) as stream:
                    stream.write(original_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                os.close(out)
            recovery = load_vault(restored)
            if (target.read_bytes() != original_bytes or recovery != archive):
                return blocked("RESTORED_CONTENT_DIFFERENT")
            if ({tf: len(recovery["closed"][tf]) for tf in FRAMES_ORDER} != counts
                    or len(recovery["quoteObservations"]) !=
                       len(archive["quoteObservations"])):
                return blocked("RESTORED_COUNTS_DIFFERENT")
        return {**SAFE,
                "status": "ISOLATED_LOCAL_RESTORE_PASS_NOT_DEPLOY_APPROVAL",
                "reason": "OFFSITE_BACKUP_AND_REAL_RENDER_RECOVERY_NOT_VERIFIED",
                "isolatedLocalRestorePassed": True,
                "closedCounts": counts,
                "locallyTimestampedCounts": timed,
                "legacyUnknownCounts": unknown,
                "quoteObservationCount": len(archive["quoteObservations"]),
                "recoveredCopyDestroyedAfterTest": True}
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return blocked("BACKUP_UNREADABLE_CORRUPT_OR_UNSAFE")

if __name__ == "__main__":
    raise SystemExit("OFFLINE_NO_PUBLIC_ARCHIVE_OR_PRICE_EXPORT")
