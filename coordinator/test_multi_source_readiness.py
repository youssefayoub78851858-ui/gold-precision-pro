"""Multi-vendor readiness uses only isolated synthetic quotes and GC fixtures."""
import datetime as dt
import unittest
from unittest.mock import patch

from multi_source_readiness import assess_offline_stack

UTC = dt.timezone.utc
BASE = int(dt.datetime(2026, 11, 10, 8, 0, tzinfo=UTC).timestamp())
AS_OF = "2026-11-10T12:00:03Z"


def xau(count=16):
    rows = []
    for i in range(count):
        for j in range(15):
            at = BASE + 900 * i + 30 + j * 60
            bid = 3900 + i / 100 + j / 1000
            rows.append({"participant_timestamp": str(at * 10**9),
                         "bid_price": bid, "ask_price": bid + .4})
    return {"ticker": "C:XAUUSD", "sourceDataMode": "SYNTHETIC_TEST_ONLY",
            "results": rows}


def gc(schema="mbo", contract="GCZ2026"):
    if schema == "mbo":
        rows = [{"ts_event": "2026-11-10T12:00:01Z", "sequence": 100,
                 "action": "TRADE", "side": "A", "order_id": "synthetic",
                 "price": 3901., "size": 1.}]
    else:
        rows = [{"ts_event": "2026-11-10T12:00:02Z", "sequence": 200,
                 "bids": [[3900., 5.]], "asks": [[3901., 3.]]}]
    return {"dataOrigin": "SYNTHETIC_TEST_ONLY", "schema": schema,
            "contract": contract, "rows": rows}


class MultiSourceOfflineTests(unittest.TestCase):
    def assert_wait(self, output):
        self.assertEqual(output["signal"], "WAIT")
        for flag in ("executable", "researchEligible", "paperOrdersAllowed",
                     "realTradingAuthorized", "subscriptionsActivated",
                     "allLayersLive", "completeStackReady"):
            self.assertFalse(output[flag], flag)
        self.assertEqual(output["verifiedLiveLayerCount"], 0)
        self.assertEqual(output["requiredLayerCount"], 9)
        self.assertEqual(output["sourceRequestsMade"], 0)
        self.assertEqual(output["payments"], 0)
        self.assertEqual(output["secretReads"], 0)
        self.assertTrue(all(not layer["liveReady"] and not layer["researchAdmitted"]
                            for layer in output["layers"].values()))

    def test_empty_review_has_all_nine_categories_without_false_free_intraday(self):
        result = assess_offline_stack(as_of_utc=AS_OF)
        self.assert_wait(result)
        self.assertEqual(len(result["layers"]), 9)
        self.assertEqual(result["layers"]["DXY"]["status"], "NOT_CONNECTED")
        self.assertEqual(result["layers"]["US02Y"]["status"], "FREE_DAILY_REFERENCE_CANDIDATE")
        self.assertEqual(result["layers"]["US10Y"]["status"], "FREE_DAILY_REFERENCE_CANDIDATE")
        self.assertEqual(result["layers"]["GC_DEPTH"]["status"], "NOT_CONNECTED")

    def test_cross_source_synthetic_geometry_and_sync_never_promotes_market(self):
        result = assess_offline_stack(
            as_of_utc=AS_OF, xau_fixture=xau(),
            gc_mbo_fixture=gc(), gc_mbp10_fixture=gc("mbp-10"))
        self.assert_wait(result)
        self.assertEqual(result["layers"]["XAUUSD_BBO"]["syntheticClosedBars"],
                         {"M15": 16, "H1": 4, "H4": 1})
        self.assertEqual(result["layers"]["GC_TRADES"]["status"], "SYNTHETIC_SCHEMA_ONLY")
        self.assertEqual(result["layers"]["GC_DEPTH"]["status"], "SYNTHETIC_SCHEMA_ONLY")
        self.assertEqual(result["diagnosticOnlySyntheticTemporalComparison"]["status"],
                         "SYNTHETIC_CLOCK_ALIGNMENT_ONLY")
        self.assertEqual(result["rejectedFixtures"], [])
        self.assertNotIn("bid_price", str(result))
        self.assertNotIn("ask_price", str(result))

    def test_foreign_contract_and_unauthorized_live_flag_are_rejected(self):
        # A valid synthetic XAU fixture allows us to detect the mismatch
        # rather than merely rely on the mandatory WAIT default.
        mismatch = assess_offline_stack(
            as_of_utc=AS_OF, xau_fixture=xau(),
            gc_mbo_fixture=gc(), gc_mbp10_fixture=gc("mbp-10", contract="GCG2027"))
        self.assert_wait(mismatch)
        self.assertIn("GC_CONTRACT_MISMATCH", mismatch["rejectedFixtures"])
        self.assertEqual(mismatch["diagnosticOnlySyntheticTemporalComparison"]["status"],
                         "BLOCKED_SYNTHETIC_SKEW_OR_CONTRACT")

        raw = xau()
        raw["sourceDataMode"] = "live"
        result = assess_offline_stack(
            as_of_utc=AS_OF, xau_fixture=raw,
            gc_mbo_fixture=gc(), gc_mbp10_fixture=gc("mbp-10"))
        self.assert_wait(result)
        self.assertEqual(result["layers"]["XAUUSD_BBO"]["status"], "REJECTED_FIXTURE")
        self.assertIn("XAUUSD_BBO", result["rejectedFixtures"])

    def test_future_stale_or_bad_depth_fails_closed(self):
        bogus = gc("mbp-10")
        bogus["rows"][0]["asks"] = [[3899., 1.]]
        result = assess_offline_stack(as_of_utc=AS_OF, xau_fixture=xau(),
                                      gc_mbo_fixture=gc(), gc_mbp10_fixture=bogus)
        self.assert_wait(result)
        self.assertEqual(result["layers"]["GC_DEPTH"]["status"], "REJECTED_FIXTURE")
        stale = assess_offline_stack(as_of_utc="2026-11-10T12:30:00Z",
                                     xau_fixture=xau(), gc_mbo_fixture=gc(),
                                     gc_mbp10_fixture=gc("mbp-10"))
        self.assert_wait(stale)
        self.assertEqual(stale["diagnosticOnlySyntheticTemporalComparison"]["status"],
                         "BLOCKED_SYNTHETIC_SKEW_OR_CONTRACT")

    def test_spoofed_rights_missing_schema_and_public_page_cannot_override_wait(self):
        raw = xau()
        raw["licenseVerified"] = True
        trade = gc()
        trade["dataOrigin"] = "live"
        result = assess_offline_stack(as_of_utc=AS_OF, xau_fixture=raw,
                                      gc_mbo_fixture=trade)
        self.assert_wait(result)
        self.assertEqual(result["layers"]["XAUUSD_BBO"]["status"], "REJECTED_FIXTURE")
        self.assertEqual(result["layers"]["GC_TRADES"]["status"], "REJECTED_FIXTURE")
        self.assertIn("PRIVATE_AUTHENTICATED_SINGLE_USER_RENDER_DEPLOYMENT_AND_USER_APPROVAL",
                      result["remainingExternalRequirements"])

    def test_no_network_even_with_all_synthetic_layers(self):
        with patch("socket.socket", side_effect=AssertionError("NO NETWORK")):
            result = assess_offline_stack(
                as_of_utc=AS_OF, xau_fixture=xau(), gc_mbo_fixture=gc(),
                gc_mbp10_fixture=gc("mbp-10"))
        self.assert_wait(result)

    def test_naive_clock_rejected(self):
        with self.assertRaisesRegex(ValueError, "EXPLICIT_ASOF_UTC_REQUIRED"):
            assess_offline_stack(as_of_utc="2026-11-10T12:00:03")
        

if __name__ == "__main__":
    unittest.main()
