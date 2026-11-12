"""Deterministic offline readiness checks; no provider calls."""
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from pre_subscription_preflight import CHECKS, ROOT, build_report

class PreSubscriptionAudit(unittest.TestCase):
    def test_current_code_and_five_real_blockers(self):
        r = build_report(ROOT)
        self.assertTrue(r["preSubscriptionStaticChecksPassed"])
        self.assertEqual(len(r["stages"]), 5)
        self.assertEqual(r["signal"], "WAIT")
        self.assertFalse(r["executable"])
        self.assertEqual(r["payments"], 0)
        self.assertEqual(r["networkCalls"], 0)
        self.assertEqual(r["secretReads"], 0)
        self.assertTrue(all(s["status"].startswith("AWAITING") for s in r["stages"]))
        for key in ("liveDataValidated", "liveResearchReady", "paperTradingLiveReady",
                    "mt5DemoExecutionReady", "liveTradingAuthorized", "sourceLicensesVerified"):
            self.assertFalse(r[key])

    def test_missing_code_is_not_reported_as_ready(self):
        with tempfile.TemporaryDirectory() as t:
            r = build_report(pathlib.Path(t))
        self.assertFalse(r["preSubscriptionStaticChecksPassed"])
        self.assertTrue(all(s["status"] == "CODE_PREFLIGHT_FAILED" for s in r["stages"]))
        self.assertFalse(r["liveTradingAuthorized"])

    def test_removed_guard_is_blocking(self):
        with tempfile.TemporaryDirectory() as t:
            root = pathlib.Path(t)
            for group in CHECKS.values():
                for relative, guards in group:
                    p = root / relative
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(" ".join(guards))
            (root / "coordinator/eodhd_ws_bridge.js").write_text("XAUUSD")
            r = build_report(root)
        gold = next(s for s in r["stages"] if s["id"] == "gold_prices")
        self.assertEqual(gold["status"], "CODE_PREFLIGHT_FAILED")
        self.assertTrue(any("EODHD_CONNECT_APPROVED" in issue
                            for issue in gold["blockingCodeChecks"]))

    def test_never_contacts_network_or_exports_credentials(self):
        with patch("socket.socket", side_effect=AssertionError("no network")):
            r = build_report(ROOT)
        report = repr(r)
        for forbidden in ('"bid"', '"ask"', "Bearer ", "YOUR_API_TOKEN", "accountNumber"):
            self.assertNotIn(forbidden, report)

if __name__ == "__main__":
    unittest.main()
