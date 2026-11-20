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
        self.assertEqual(r["selectedGoldProvider"], "CAPITAL_COM_DEMO")
        self.assertTrue(r["legacyEodhdAlternativeNotSelected"])
        primary = r["selectedCapitalDemoReadiness"]
        self.assertEqual(primary["selectedProvider"], "CAPITAL_COM_DEMO")
        self.assertEqual(primary["status"], "UNCONNECTED_RESTRICTED_STANDBY")
        self.assertEqual(primary["signal"], "WAIT")
        self.assertFalse(primary["rightsVerified"])
        self.assertFalse(primary["brokerAccountVerified"])
        self.assertFalse(primary["readOnlyApiKeyGranted"])
        self.assertFalse(primary["paperOrdersAllowed"])
        self.assertFalse(primary["researchEligible"])
        self.assertFalse(primary["liveMarketDataAvailable"])
        self.assertEqual(primary["providerRequestsMade"], 0)
        self.assertEqual(primary["offlineHistoricalBlueprint"]["plannedGETRequests"], 4)
        self.assertEqual(primary["offlineHistoricalBlueprint"]["expectedUTCGridClosedSlots"],
                         {"M15": 960, "H1": 240, "H4": 60})
        self.assertFalse(primary["offlineHistoricalBlueprint"]["actualSessionOrMarketDataProven"])
        self.assertEqual(r["eodhdFirstDayBootstrapPlan"]["signal"], "WAIT")
        self.assertEqual(r["eodhdFirstDayBootstrapPlan"]["historyMath"]["minimumClosedM15For50CompleteH4"], 800)
        self.assertFalse(r["eodhdFirstDayBootstrapPlan"]["sourceCompatibility"]["mayMergeHistoricalAndStreamBars"])
        self.assertTrue(r["eodhdFirstDayBootstrapPlan"]["sourceCompatibility"]
                        ["singleSeriesHistoryCannotInitializeBidAsk"])
        self.assertFalse(r["eodhdFirstDayBootstrapPlan"]["sourceCompatibility"]
                         ["paidMarketDataCanBeDisplayedOnPublicDemo"])
        self.assertFalse(r["eodhdFirstDayBootstrapPlan"]["subscriptionDecision"]
                         ["50CompleteH4GuaranteedOnSubscriptionDay"])
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

    def test_removed_selected_capital_guard_is_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for group in CHECKS.values():
                for relative, guards in group:
                    p = root / relative
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(" ".join(guards))
            (root / "coordinator/capital_demo_private_get_boundary.py").write_text(
                "CAPITAL_DEMO_PRIVATE_PRICE_GET_ENABLED")
            report = build_report(root)
        gold = next(s for s in report["stages"] if s["id"] == "gold_prices")
        self.assertEqual(gold["status"], "CODE_PREFLIGHT_FAILED")
        self.assertTrue(any("CAPITAL_DEMO_PRIVATE_RIGHTS_DOCUMENTED" in issue
                            for issue in gold["blockingCodeChecks"]))
        self.assertFalse(report["liveDataValidated"])

    def test_selected_source_still_requires_shared_closed_candle_guard(self):
        self.assertIn("coordinator/xauusd_feed_gate.py",
                      [path for path, _ in CHECKS["gold_prices"]])
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for group in CHECKS.values():
                for relative, guards in group:
                    p = root / relative
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(" ".join(guards))
            (root / "coordinator/xauusd_feed_gate.py").write_text(
                "SourcePolicy")
            report = build_report(root)
        gold = next(s for s in report["stages"] if s["id"] == "gold_prices")
        self.assertEqual(gold["status"], "CODE_PREFLIGHT_FAILED")
        self.assertTrue(any("expectedOpenTimes" in issue
                            for issue in gold["blockingCodeChecks"]))

    def test_unselected_eodhd_and_fxcm_files_are_not_capital_requirements(self):
        # Only the selected provider's code belongs in primary gold readiness.
        self.assertFalse(any(
            "eodhd_" in path.lower() or "fxcm_" in path.lower()
            for path, _ in CHECKS["gold_prices"]))
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for group in CHECKS.values():
                for relative, guards in group:
                    p = root / relative
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(" ".join(guards))
            # No EODHD, FXCM or Massive code at all in this fake tree.
            report = build_report(root)
        self.assertTrue(report["preSubscriptionStaticChecksPassed"])
        self.assertEqual(report["selectedGoldProvider"], "CAPITAL_COM_DEMO")
        self.assertFalse(report["liveDataValidated"])
        self.assertFalse(report["executable"])

    def test_never_contacts_network_or_exports_credentials(self):
        with patch("socket.socket", side_effect=AssertionError("no network")):
            r = build_report(ROOT)
        report = repr(r)
        for forbidden in ('"bid"', '"ask"', "Bearer ", "YOUR_API_TOKEN", "accountNumber"):
            self.assertNotIn(forbidden, report)

if __name__ == "__main__":
    unittest.main()
