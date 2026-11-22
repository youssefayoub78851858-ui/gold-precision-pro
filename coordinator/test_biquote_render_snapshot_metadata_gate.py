"""Offline synthetic-only tests; never fetch or restore Render snapshots."""
import datetime as dt
import json
import socket
import unittest
from unittest.mock import patch

from biquote_render_snapshot_metadata_gate import assess

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 22, 20, 0, tzinfo=UTC)


class SnapshotMetadataOnlyGate(unittest.TestCase):
    def safe(self, value):
        self.assertEqual(value["signal"], "WAIT")
        self.assertFalse(value["executable"])
        for field in ("reviewDeployApproved", "coordinatorRestartApproved",
                      "vaultIncludedInSnapshotVerified",
                      "independentOffsiteBackupVerified", "isolatedRestorePassed",
                      "snapshotRestored", "snapshotKeyPrinted", "rawPricesPrinted",
                      "marketDataRightsVerified"):
            self.assertIs(value[field], False)
        self.assertEqual(value["providerRequestsMade"], 0)
        self.assertEqual(value["brokerOrdersSent"], 0)
        payload = json.dumps(value)
        for leak in ("12345-secret-short-lived-key", "api_key", "bid",
                     "ask", "snapshotKey", "2999."):
            self.assertNotIn(leak, payload)

    def test_recent_snapshot_is_never_vault_evidence(self):
        metadata = [{
            "createdAt": "2026-11-22T08:00:00.000Z",
            "snapshotKey": "12345-secret-short-lived-key",
            "instanceId": "instance-private",
        }, {"createdAt": "2026-11-21T08:00:00Z"}]
        with patch.object(socket, "socket",
                          side_effect=AssertionError("NO_NETWORK")):
            got = assess(metadata, now_utc=NOW)
        self.safe(got)
        self.assertEqual(got["status"], "RECENT_SNAPSHOT_LISTED_NOT_ARCHIVE_PROOF")
        self.assertEqual(got["listedWithinSevenDays"], 2)
        self.assertEqual(got["latestSnapshotAgeHours"], 12.0)
        self.assertTrue(got["snapshotMetadataRecentOnly"])
        self.assertIsNone(got["snapshotMayContainVault"])

    def test_stale_and_expired_snapshots_are_not_evidence(self):
        got = assess([{"createdAt": "2026-11-19T20:00:00+00:00"},
                      {"createdAt": "2026-11-10T20:00:00Z"}], now_utc=NOW)
        self.safe(got)
        self.assertEqual(got["status"], "STALE_SNAPSHOT_METADATA_ONLY")
        self.assertEqual(got["listedWithinSevenDays"], 1)
        self.assertFalse(got["snapshotMetadataRecentOnly"])

    def test_invalid_snapshot_list_is_fail_closed(self):
        inputs = [None, [], "snapshot", {}, [False],
                  [{"createdAt": "2026-11-23T00:00:00Z"}],
                  [{"createdAt": "2026-11-22T08:00:00+02:00"}],
                  [{"createdAt": "2026-11-22T08:00:00Z"},
                   {"createdAt": "2026-11-XXT08:00:00Z"}],
                  [{"createdAt": "2026-11-22T08:00:00Z"}] * 101]
        for input_value in inputs:
            got = assess(input_value, now_utc=NOW)
            self.safe(got)
            self.assertEqual(got["status"], "BLOCKED")

    def test_utc_clock_required(self):
        items = [{"createdAt": "2026-11-22T08:00:00Z"}]
        for now in (None, "not a clock", NOW.replace(tzinfo=None),
                    NOW.astimezone(dt.timezone(dt.timedelta(hours=2)))):
            got = assess(items, now_utc=now)
            self.safe(got)
            self.assertEqual(got["reason"], "UTC_CLOCK_REQUIRED")


if __name__ == "__main__":
    unittest.main()
