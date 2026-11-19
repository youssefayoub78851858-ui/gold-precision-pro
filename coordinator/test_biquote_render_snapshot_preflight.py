"""Synthetic Render snapshot metadata, never calling Render or trading."""
import datetime as dt
import json
import socket
import unittest
from unittest.mock import patch
from biquote_render_snapshot_preflight import review_snapshot_listing as review

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,19,12,tzinfo=UTC)
SECRET="SENSITIVE_SNAPSHOT_KEY_993884"
def entry(hours=24):
    return {"createdAt":(NOW-dt.timedelta(hours=hours)).isoformat(
        timespec="milliseconds").replace("+00:00","Z"),
        "snapshotKey":SECRET,"instanceId":"i-secret-should-not-leak"}

class SnapshotEvidence(unittest.TestCase):
    def test_reported_snapshot_is_never_restoration_authority(self):
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            out=review([entry(3),entry(26),entry(180)],now_utc=NOW)
        self.assertEqual(out["reportedSnapshotsInRetention"],2)
        self.assertEqual(out["reportedRecentSnapshots"],2)
        self.assertTrue(out["fresh48hSnapshotReported"])
        self.assertEqual(out["signal"],"WAIT")
        self.assertFalse(out["restoreAllowed"])
        self.assertFalse(out["deployApproved"])
        self.assertFalse(out["collectorRestartApproved"])
        self.assertFalse(out["rawVaultRecovered"])
        self.assertFalse(out["archivedCandlesVerified"])
        self.assertFalse(out["externalOffsiteBackupVerified"])
        self.assertEqual(out["renderApiCallsMade"],0)
        self.assertNotIn(SECRET,json.dumps(out))
        self.assertNotIn("i-secret",json.dumps(out))
        self.assertNotIn("2026-11-19T",json.dumps(out))
    def test_missing_stale_forged_or_future_metadata_fails_closed(self):
        for listing in (None,[],[entry(190)],[entry(-1)],
                        [{"createdAt":"tomorrow","snapshotKey":SECRET}],
                        [{"createdAt":entry()["createdAt"],"snapshotKey":""}],
                        [entry(1),{"createdAt":"broken","snapshotKey":SECRET}]):
            out=review(listing,now_utc=NOW)
            self.assertEqual(out["status"],"NOT_VERIFIED")
            self.assertEqual(out["signal"],"WAIT")
            self.assertFalse(out["restoreAllowed"])
            self.assertFalse(out["deployApproved"])
            self.assertNotIn(SECRET,json.dumps(out))
        self.assertEqual(review([entry()],now_utc=dt.datetime(2026,11,19))
                         ["status"],"NOT_VERIFIED")

if __name__=="__main__":unittest.main()
