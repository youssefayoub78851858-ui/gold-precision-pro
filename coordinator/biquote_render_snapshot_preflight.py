"""Read-only evaluator of operator-provided Render disk snapshot metadata.

Render automatic snapshots are not an authenticated backup of THIS vault,
an independent offsite export, or permission to restore a live disk.
NO Render calls, no mutations, no private prices, no keys in output.
"""
from __future__ import annotations
import datetime as dt
import re

UTC=dt.timezone.utc
RETENTION=dt.timedelta(days=7)
SAFE={
 "mode":"RENDER_DISK_SNAPSHOT_EVIDENCE_ONLY_V1",
 "signal":"WAIT","executable":False,"paperOrdersAllowed":False,
 "liveOrdersAllowed":False,"restoreAllowed":False,"deployApproved":False,
 "collectorRestartApproved":False,"snapshotRestorePerformed":False,
 "rawVaultRecovered":False,"archivedCandlesVerified":False,
 "externalOffsiteBackupVerified":False,"brokerRightsVerified":False,
 "providerRequestsMade":0,"renderApiCallsMade":0,"tradingOrdersSent":0
}
def blocked(why):
    return {**SAFE,"status":"NOT_VERIFIED","reason":why,
            "reportedSnapshotsInRetention":0,"reportedRecentSnapshots":0}

def _stamp(s):
    if not isinstance(s,str) or not re.fullmatch(
        r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z",s
    ): raise ValueError("TIMESTAMP_NOT_UTC")
    return dt.datetime.fromisoformat(s.replace("Z","+00:00"))

def review_snapshot_listing(snapshot_records, *, now_utc):
    """Inspect metadata ONLY; never accept a snapshotKey as restoration approval.

    Records must come from a user-selected Render disk snapshot listing;
    their provenance is not independently authenticated by this function.
    """
    if (not isinstance(now_utc,dt.datetime) or now_utc.tzinfo is None or
        now_utc.utcoffset()!=dt.timedelta(0)):
        return blocked("UTC_CLOCK_REQUIRED")
    if not isinstance(snapshot_records,list) or len(snapshot_records)>256:
        return blocked("SNAPSHOT_LISTING_UNAVAILABLE")
    if len(snapshot_records)==0:
        return blocked("NO_LISTING_EVIDENCE_NOT_NO_BACKUP")
    ages=[]
    try:
        for record in snapshot_records:
            if (not isinstance(record,dict) or
                not isinstance(record.get("snapshotKey"),str) or
                not record["snapshotKey"] or len(record["snapshotKey"])>4096):
                raise ValueError("SNAPSHOT_RECORD_INCOMPLETE")
            created=_stamp(record.get("createdAt"))
            age=now_utc-created
            if age<dt.timedelta(0):
                raise ValueError("SNAPSHOT_IN_FUTURE")
            ages.append(age)
    except (TypeError,ValueError,OverflowError):
        return blocked("INVALID_SNAPSHOT_LISTING")
    retained=sum(age<=RETENTION for age in ages)
    recent=sum(age<=dt.timedelta(hours=48) for age in ages)
    if not retained:
        return blocked("ALL_REPORTED_SNAPSHOTS_OUTSIDE_RETENTION")
    return {**SAFE,
        "status":"PLATFORM_SNAPSHOTS_REPORTED_NOT_ARCHIVE_RECOVERY_PROOF",
        "reason":"LISTING_METADATA_ONLY_NO_VAULT_OR_OFFSITE_VERIFICATION",
        "reportedSnapshotsInRetention":retained,
        "reportedRecentSnapshots":recent,
        "fresh48hSnapshotReported":recent>0,
        "userProvidedMetadataNotIndependentlyAuthenticated":True,
        "retentionDaysDocumented":7,
        "sameProviderDisasterRecoveryOnly":True}
