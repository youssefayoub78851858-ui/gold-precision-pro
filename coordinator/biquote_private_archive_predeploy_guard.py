"""Operator-only READ-ONLY predeploy audit of an existing private BiQuote vault.

Checks exact signed archive bytes on source and separate existing backup
directories, and an isolated recoverability drill. The source file is
never copied, uploaded, renamed, or published; Render logs are NOT a
replacement for the sealed file. This code does NOT authorize a deploy,
switch market feeds, create a subscription, or prove data rights.

The current connected Render actions cannot retrieve coordinator's private
filesystem; therefore no current private archive is claimed as backed up.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib

from biquote_collector_backup_preflight import review
from biquote_collector_restore_rehearsal import rehearse_restore
from biquote_private_forward_vault import FILE

MODE = "GOLD_PRIVATE_ARCHIVE_PREDEPLOY_READ_ONLY_V1"


def _waiting(reason):
    return {
        "mode": MODE,
        "status": "BLOCKED_UNTIL_OWNER_BACKUP_EVIDENCE",
        "reason": reason,
        "originalVaultBytesVerified": False,
        "exactBackupBytesVerified": False,
        "independentStorageDeviceVerified": False,
        "isolatedRestorePassed": False,
        "reviewDeployApproved": False,
        "coordinatorRestartApproved": False,
        "rawPriceExported": False,
        "providerRequestsMade": 0,
        "brokerOrdersSent": 0,
        "independentBrokerRightsVerified": False,
        "sourceDataTradingEligible": False,
        "signal": "WAIT",
        "executable": False,
    }


def preflight(source_dir=None, backup_dir=None, *, now_utc=None):
    result = _waiting("PRIVATE_SOURCE_AND_BACKUP_NOT_ATTESTED")
    if (not isinstance(now_utc, dt.datetime) or now_utc.tzinfo is None
            or now_utc.utcoffset() != dt.timedelta(0)):
        return _waiting("UTC_CLOCK_REQUIRED")
    if (not isinstance(source_dir, (str, os.PathLike))
            or not isinstance(backup_dir, (str, os.PathLike))):
        return result
    source, backup = pathlib.Path(source_dir), pathlib.Path(backup_dir)
    if (not source.is_absolute() or not backup.is_absolute()
            or source == backup or ".." in source.parts + backup.parts):
        return _waiting("DISTINCT_PRIVATE_ABSOLUTE_PATHS_REQUIRED")
    # Reuse the existing signed-vault counter and byte-for-byte comparator.
    checked = review(source, backup, now_utc=now_utc, finished=False)
    if (checked.get("status") != "LOCAL_MATCH_NO_DEPLOY_APPROVAL"
            or checked.get("exactSealedBytesMatch") is not True
            or checked.get("sourceRightsVerified") is not False
            or checked.get("deployApproved") is not False):
        return _waiting("SEALED_SOURCE_OR_BACKUP_UNVERIFIED")
    if checked.get("sameDeviceDetected") is not False:
        # A local second file on the same ephemeral Render filesystem is
        # NOT a separately durable backup.
        return _waiting("BACKUP_SAME_DEVICE_OR_NOT_INDEPENDENT")
    restored = rehearse_restore(backup, now_utc=now_utc)
    if (restored.get("status")
            != "ISOLATED_LOCAL_RESTORE_PASS_NOT_DEPLOY_APPROVAL"
            or restored.get("isolatedLocalRestorePassed") is not True
            or restored.get("recoveredCopyDestroyedAfterTest") is not True
            or restored.get("sourceRightsVerified") is not False
            or restored.get("brokerCalendarVerified") is not False):
        return _waiting("BACKUP_ISOLATED_RECOVERY_NOT_VERIFIED")
    counts = checked.get("sourceClosedCounts")
    if (not isinstance(counts, dict)
            or not all(type(counts.get(tf)) is int and counts[tf] >= 0
                       for tf in ("M15", "H1", "H4"))
            or counts != restored.get("closedCounts")):
        return _waiting("BACKUP_RESTORED_COUNTS_CONTRADICTORY")
    # A DIFFERENT local device is NOT independently verified offsite
    # disaster recovery. Keep deploy approval false; operator must attach
    # explicit external recovery evidence and assess source permissions.
    return {
        **result,
        "status": "LOCAL_DIFFERENT_DEVICE_RESTORE_ONLY",
        "reason": "OFFSITE_RECOVERY_AND_LIVE_CLOUD_SOURCE_RIGHTS_NOT_VERIFIED",
        "originalVaultBytesVerified": True,
        "exactBackupBytesVerified": True,
        "independentStorageDeviceVerified": True,
        "isolatedRestorePassed": True,
        "sourceClosedCounts": counts,
        "quoteObservationsChecked": restored.get("quoteObservationCount", 0),
    }


if __name__ == "__main__":
    # This is library code, not a public GET or implicit filesystem export.
    raise SystemExit("PRIVATE_READ_ONLY_OPERATOR_INPUT_REQUIRED")
