"""Offline private feed status: no EODHD credentials or calls."""
import datetime as dt
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from eodhd_private_readiness import read_private_status

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 12, 17, 0, 0, tzinfo=UTC)


class PrivateReadiness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name) / "eodhd-private-review.json"

    def check(self):
        result = read_private_status(self.temp.name, now=NOW)
        self.assertEqual(result["signal"], "WAIT")
        self.assertIs(result["executable"], False)
        self.assertIs(result["researchEligible"], False)
        self.assertIs(result["providerAccess"], False)
        self.assertIs(result["paperRunning"], False)
        self.assertFalse(result["priceVisible"])
        self.assertEqual(result["sourceRequestsOnThisCall"], 0)
        self.assertNotIn("latestQuote", result)
        self.assertNotIn("bid", result)
        self.assertNotIn("ask", result)
        return result

    def write(self, *, age=3, file_age=2, override=None):
        value = {"provider": "EODHD", "instrument": "XAU/USD",
                 "mode": "REVIEW_ONLY", "signal": "WAIT", "executable": False,
                 "researchEligible": False, "readyForTrading": False,
                 "latestQuote": {"bid": 4001.2, "ask": 4001.5,
                                 "timeUTC": (NOW - dt.timedelta(seconds=age)).isoformat()},
                 "frames": {"M15": [{}], "H1": [], "H4": []}}
        if override:
            value.update(override)
        self.path.write_text(json.dumps(value))
        self.path.chmod(0o600)
        st = NOW.timestamp() - file_age
        os.utime(self.path, (st, st))

    def test_missing_is_wait_and_no_network(self):
        self.assertEqual(self.check()["status"], "NOT_CONNECTED")

    def test_fresh_snapshot_shows_counts_but_never_prices_or_eligibility(self):
        self.write()
        r = self.check()
        self.assertEqual(r["status"], "WAIT_REVIEW_OBSERVATION_ONLY")
        self.assertEqual(r["closedBarCounts"], {"M15": 1, "H1": 0, "H4": 0})
        self.assertEqual(r["lastQuoteAgeSeconds"], 3)

    def test_stale_quote_or_file_is_blocked(self):
        self.write(age=100)
        self.assertEqual(self.check()["status"], "WAIT_STALE")
        self.write(age=1, file_age=100)
        self.assertEqual(self.check()["status"], "WAIT_STALE")

    def test_future_timestamp_cannot_gain_readiness(self):
        self.write(age=-100)
        self.assertEqual(self.check()["status"], "BLOCKED")

    def test_hijacked_signal_is_rejected(self):
        self.write(override={"signal": "BUY", "executable": True})
        self.assertEqual(self.check()["status"], "BLOCKED")

    def test_wrong_vendor_is_rejected(self):
        self.write(override={"provider": "UNVERIFIED"})
        self.assertEqual(self.check()["status"], "BLOCKED")

    def test_world_readable_or_symlink_is_rejected(self):
        self.write()
        self.path.chmod(0o644)
        self.assertEqual(self.check()["status"], "BLOCKED")
        self.path.unlink()
        self.path.symlink_to(pathlib.Path(self.temp.name) / "target.json")
        self.assertEqual(self.check()["status"], "BLOCKED")

    def test_corrupted_snapshot_cannot_fail_open(self):
        self.path.write_text("{not-json")
        self.path.chmod(0o600)
        self.assertEqual(self.check()["status"], "BLOCKED")

    def test_missing_quote_is_no_evidence(self):
        self.write(override={"latestQuote": None})
        self.assertEqual(self.check()["status"], "WAIT_NO_VERIFIED_QUOTE")

    def test_never_accesses_network(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.assertEqual(self.check()["status"], "NOT_CONNECTED")


if __name__ == "__main__":
    unittest.main()
