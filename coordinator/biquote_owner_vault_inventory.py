"""Owner-only READ-ONLY vault inventory. No copying, export, deploy or trading.

The default directory comes ONLY from the private coordinator environment.
Outputs booleans and aggregate counts, not source paths, prices or credentials.
A valid local vault and a mounted disk DO NOT attest independent offsite recovery.
"""
from __future__ import annotations

import json
import os
import pathlib
import stat

from biquote_private_forward_vault import FILE, FRAMES_ORDER, MAX_VAULT_BYTES, load_vault

MODE = "GPP_OWNER_VAULT_INVENTORY_READONLY_V1"
SAFE = {
    "mode": MODE, "status": "BLOCKED", "reason": "UNVERIFIED",
    "onDataVolumePath": False, "mountedDataVolumeObserved": False,
    "ownerOnlyVaultPresent": False, "sealedVaultValidated": False,
    "closedCounts": None, "quoteObservations": None,
    "independentOffsiteBackupVerified": False,
    "sourceRightsVerified": False, "reviewDeployApproved": False,
    "coordinatorRestartApproved": False, "rawPricesPrinted": False,
    "sourceFileWrites": 0, "providerRequestsMade": 0, "brokerOrdersSent": 0,
    "signal": "WAIT", "executable": False,
}


def _blocked(reason, **details):
    return {**SAFE, "reason": reason, **details}


def _stable(first, second):
    return (
        (first.st_dev, first.st_ino, first.st_size,
         first.st_mtime_ns, first.st_ctime_ns, first.st_nlink)
        ==
        (second.st_dev, second.st_ino, second.st_size,
         second.st_mtime_ns, second.st_ctime_ns, second.st_nlink)
    )


def inspect_private_vault(configured_dir, *, data_volume="/var/data"):
    """Read-only inventory of an already-configured vault; never create it.

    data_volume may be injected by offline unit tests, never by CLI input.
    This is not a remote or independent storage backup verification.
    """
    try:
        if not isinstance(configured_dir, (str, os.PathLike)):
            return _blocked("PRIVATE_VAULT_DIR_NOT_CONFIGURED")
        if not isinstance(data_volume, (str, os.PathLike)):
            return _blocked("INVALID_DATA_VOLUME")
        root = pathlib.Path(data_volume)
        folder = pathlib.Path(configured_dir)
        if (not root.is_absolute() or root == pathlib.Path("/")
                or ".." in root.parts or not folder.is_absolute()
                or folder == root or ".." in folder.parts
                or root not in folder.parents):
            return _blocked("PRIVATE_VAULT_NOT_WITHIN_DATA_VOLUME")
        # Resolve without creating or following a symlink as an allowed path.
        if folder.resolve(strict=True) != folder:
            return _blocked("PRIVATE_VAULT_PATH_SYMLINK")
        root_stat, dir_stat = root.lstat(), folder.lstat()
        if (not stat.S_ISDIR(root_stat.st_mode)
                or not stat.S_ISDIR(dir_stat.st_mode)
                or stat.S_ISLNK(dir_stat.st_mode)
                or dir_stat.st_uid != os.getuid()
                or dir_stat.st_mode & 0o077):
            return _blocked("PRIVATE_VAULT_DIR_INSECURE")
        on_mount = os.path.ismount(root)
        file = folder / FILE
        before = file.lstat()
        if (not stat.S_ISREG(before.st_mode)
                or stat.S_ISLNK(before.st_mode)
                or before.st_uid != os.getuid()
                or before.st_mode & 0o077 or before.st_nlink != 1
                or not 0 < before.st_size <= MAX_VAULT_BYTES):
            return _blocked("SEALED_VAULT_FILE_INSECURE",
                            onDataVolumePath=True,
                            mountedDataVolumeObserved=bool(on_mount))
        vault = load_vault(folder)
        after = file.lstat()
        if not _stable(before, after):
            return _blocked("SEALED_VAULT_CHANGED_DURING_READ",
                            onDataVolumePath=True,
                            mountedDataVolumeObserved=bool(on_mount))
        count = {tf: len(vault["closed"][tf]) for tf in FRAMES_ORDER}
        quotes = len(vault["quoteObservations"])
        if quotes == 0 or not any(count.values()):
            return _blocked("SEALED_VAULT_EMPTY",
                            onDataVolumePath=True,
                            mountedDataVolumeObserved=bool(on_mount))
        return {
            **SAFE,
            "status": "PRIVATE_SOURCE_VALIDATED_BACKUP_STILL_REQUIRED",
            "reason": "OFFSITE_COPY_AND_RESTORE_NOT_VERIFIED",
            "onDataVolumePath": True,
            "mountedDataVolumeObserved": bool(on_mount),
            "ownerOnlyVaultPresent": True,
            "sealedVaultValidated": True,
            "closedCounts": count,
            "quoteObservations": quotes,
        }
    except (OSError, ValueError, KeyError, TypeError):
        return _blocked("PRIVATE_VAULT_NOT_READABLE_OR_NOT_VALID")


if __name__ == "__main__":
    # Never echo the environment variable itself: it contains a private path.
    print(json.dumps(
        inspect_private_vault(os.environ.get("GPP_BIQUOTE_FORWARD_VAULT_DIR")),
        sort_keys=True,
    ))
