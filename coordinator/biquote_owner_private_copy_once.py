"""One-shot operator-authorized PRIVATE copy of the existing sealed BiQuote vault.

No network, Render API, GitHub upload, encryption, automatic scheduling,
broker feed, subscription, real/paper orders, or deploy. Data licensing for
cross-device/offsite copies must be separately confirmed by the owner.
This module cannot prove independent persistence or cloud recoverability.

Both directories must already exist and be owner-only (0700). The source
remains read-only. Destination archive must not exist, including a symlink.
Copy is written to a private 0600 temp file and published via a hard-link
no-clobber operation, then checked byte-for-byte and restored in a throwaway
directory. Even a passing result NEVER approves a Render redeploy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import stat
import sys
import tempfile

from biquote_private_forward_vault import (
    FILE, FRAMES_ORDER, MAX_VAULT_BYTES, load_vault
)
from biquote_collector_restore_rehearsal import rehearse_restore

MODE = "BIQUOTE_OWNER_PRIVATE_COPY_ONCE_NO_DEPLOY_V1"


def _wait(reason):
    return {
        "mode": MODE, "status": "BLOCKED", "reason": reason,
        "privateCopyVerified": False,
        "isolatedRestorePassed": False,
        "sameDeviceDetected": None,
        "externallyDurableBackupVerified": False,
        "sourceRightsVerified": False,
        "reviewDeployApproved": False,
        "coordinatorRestartApproved": False,
        "rawPricesPrinted": False,
        "providerRequestsMade": 0, "brokerOrdersSent": 0,
        "signal": "WAIT", "executable": False,
    }


def _directory(value):
    if not isinstance(value, (str, os.PathLike)):
        raise ValueError("OWNER_PRIVATE_ABSOLUTE_DIRECTORY_REQUIRED")
    p = pathlib.Path(value)
    if not p.is_absolute() or p == pathlib.Path("/") or ".." in p.parts:
        raise ValueError("OWNER_PRIVATE_ABSOLUTE_DIRECTORY_REQUIRED")
    s = p.lstat()
    if (not stat.S_ISDIR(s.st_mode) or stat.S_ISLNK(s.st_mode)
            or s.st_mode & 0o077 or s.st_uid != os.getuid()
            or p.resolve(strict=True) != p):
        raise ValueError("OWNER_ONLY_DIRECTORY_REQUIRED")
    return p


def _source_file(directory):
    p = directory / FILE
    s = p.lstat()
    if (not stat.S_ISREG(s.st_mode) or stat.S_ISLNK(s.st_mode)
            or s.st_mode & 0o077 or s.st_uid != os.getuid()
            or s.st_size <= 0 or s.st_size > MAX_VAULT_BYTES
            or s.st_nlink != 1):
        raise ValueError("UNSAFE_PRIVATE_SOURCE_FILE")
    return p, s


def _file_unchanged(first, second):
    return (
        first.st_dev == second.st_dev and first.st_ino == second.st_ino
        and first.st_size == second.st_size
        and first.st_mtime_ns == second.st_mtime_ns
        and first.st_ctime_ns == second.st_ctime_ns
    )


def _checked_paths(source_dir, destination_dir):
    src = _directory(source_dir)
    dst = _directory(destination_dir)
    if src == dst or src.resolve() == dst.resolve():
        raise ValueError("DISTINCT_PRIVATE_DIRECTORIES_REQUIRED")
    origin, state = _source_file(src)
    target = dst / FILE
    if target.exists() or target.is_symlink():
        raise ValueError("NO_OVERWRITE_OF_EXISTING_PRIVATE_ARCHIVE")
    # A source vault must contain actual recorded samples. Never back up
    # an empty placeholder and describe it as preserving captured prices.
    current = load_vault(src)
    counts = {tf: len(current["closed"][tf]) for tf in FRAMES_ORDER}
    samples = len(current["quoteObservations"])
    if samples == 0 or not any(counts.values()):
        raise ValueError("EMPTY_PRIVATE_SOURCE_NOT_BACKUP_EVIDENCE")
    return src, dst, origin, target, state, current, counts, samples


def check(source_dir, destination_dir):
    try:
        src, dst, origin, target, before, _vault, counts, samples = (
            _checked_paths(source_dir, destination_dir))
        return {
            **_wait("EXPLICIT_OPERATOR_COPY_NOT_PERFORMED"),
            "status": "PRIVATE_SOURCE_PRECHECK_ONLY_NO_BACKUP",
            "sourceClosedCounts": counts,
            "quoteObservationsSeen": samples,
            "sameDeviceDetected": before.st_dev == dst.stat().st_dev,
        }
    except (OSError, ValueError, KeyError, TypeError):
        return _wait("OWNER_ARCHIVE_OR_DESTINATION_UNVERIFIED")


def copy_once(source_dir, destination_dir, *, operator_approved=False,
              now_utc=None):
    if operator_approved is not True:
        return _wait("EXPLICIT_OPERATOR_COPY_APPROVAL_REQUIRED")
    if (not isinstance(now_utc, dt.datetime) or now_utc.tzinfo is None
            or now_utc.utcoffset() != dt.timedelta(0)):
        return _wait("UTC_CLOCK_REQUIRED")
    published = False
    inode = None
    temp_path = None
    target = None
    try:
        src, dst, origin, target, source_stat, source_vault, counts, samples = (
            _checked_paths(source_dir, destination_dir))
        fd, name = tempfile.mkstemp(prefix=".sealed-private-copy-",
                                   suffix=".tmp", dir=dst)
        temp_path = pathlib.Path(name)
        os.fchmod(fd, 0o600)
        digest = hashlib.sha256()
        bytes_seen = 0
        try:
            input_fd = os.open(origin, os.O_RDONLY |
                               getattr(os, "O_NOFOLLOW", 0))
            try:
                opened = os.fstat(input_fd)
                if not _file_unchanged(source_stat, opened):
                    raise ValueError("SOURCE_CHANGED_BEFORE_COPY")
                while True:
                    block = os.read(input_fd, 65536)
                    if not block:
                        break
                    bytes_seen += len(block)
                    if bytes_seen > MAX_VAULT_BYTES:
                        raise ValueError("SOURCE_SIZE_LIMIT")
                    digest.update(block)
                    remaining = block
                    while remaining:
                        written = os.write(fd, remaining)
                        if written <= 0:
                            raise OSError("PRIVATE_COPY_WRITE_FAILED")
                        remaining = remaining[written:]
            finally:
                os.close(input_fd)
            os.fsync(fd)
        finally:
            os.close(fd)
        if bytes_seen != source_stat.st_size:
            raise ValueError("SOURCE_SIZE_CHANGED")
        if not _file_unchanged(source_stat, origin.lstat()):
            raise ValueError("SOURCE_CHANGED_DURING_COPY")
        # The hard link publishes atomically and MUST fail on any existing
        # file/symlink. After verification, all temporary names are removed.
        os.link(temp_path, target, follow_symlinks=False)
        published = True
        inode = target.lstat().st_ino
        restored_vault = load_vault(dst)
        if (restored_vault != source_vault
                or not _file_unchanged(source_stat, origin.lstat())):
            raise ValueError("PRIVATE_ARCHIVE_CHANGED_OR_MISMATCHED")
        recovery = rehearse_restore(dst, now_utc=now_utc)
        if (recovery.get("status") !=
                "ISOLATED_LOCAL_RESTORE_PASS_NOT_DEPLOY_APPROVAL"
                or recovery.get("isolatedLocalRestorePassed") is not True
                or recovery.get("recoveredCopyDestroyedAfterTest") is not True
                or recovery.get("closedCounts") != counts):
            raise ValueError("ISOLATED_RESTORE_NOT_VERIFIED")
        # The matched SHA is deliberately NOT displayed: private source
        # contents, API keys, directory paths and prices never leave CLI.
        final = target.lstat()
        if (final.st_ino != inode or not stat.S_ISREG(final.st_mode)
                or final.st_mode & 0o077 or final.st_size != bytes_seen):
            raise ValueError("PUBLISHED_COPY_REPLACED")
        with open(target, "rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if actual != digest.hexdigest():
            raise ValueError("PRIVATE_COPY_CHECKSUM_MISMATCH")
        return {
            **_wait("PRIVATE_LOCAL_COPY_NOT_OFFSITE_ATTESTED"),
            "status": "LOCAL_OWNER_ONLY_SEALED_COPY_VERIFIED",
            "privateCopyVerified": True,
            "isolatedRestorePassed": True,
            "sameDeviceDetected": source_stat.st_dev == final.st_dev,
            "sourceClosedCounts": counts,
            "quoteObservationsCopied": samples,
        }
    except (OSError, ValueError, KeyError, TypeError):
        # Never delete a preexisting destination. Only remove a copy
        # created by THIS attempt and still matching our inode.
        if published and target is not None:
            try:
                if target.lstat().st_ino == inode:
                    target.unlink()
            except OSError:
                pass
        return _wait("PRIVATE_COPY_OR_RECOVERY_VERIFICATION_FAILED")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Owner-only, no-network private BiQuote vault copy; never approves Render deploy")
    parser.add_argument("source_directory")
    parser.add_argument("existing_private_backup_directory")
    parser.add_argument("--copy", action="store_true",
                        help="explicit one-time private copy (disabled by default)")
    parser.add_argument("--operator-approved-private-copy", action="store_true",
                        help="operator confirms storage and source copying rights")
    options = parser.parse_args()
    if options.copy:
        outcome = copy_once(
            options.source_directory, options.existing_private_backup_directory,
            operator_approved=options.operator_approved_private_copy,
            now_utc=dt.datetime.now(dt.timezone.utc))
    else:
        outcome = check(
            options.source_directory, options.existing_private_backup_directory)
    sys.stdout.write(json.dumps(outcome, sort_keys=True) + "\n")
    if outcome["status"] == "BLOCKED":
        sys.exit(2)
