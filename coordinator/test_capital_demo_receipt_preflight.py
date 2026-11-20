"""Closed-frame source time tests for selected Capital.com Demo (no network)."""
import datetime as dt
import json
import socket
import unittest
from unittest.mock import patch

from capital_demo_receipt_preflight import inspect_receipts, ORIGIN

UTC = dt.timezone.utc
BASE = dt.datetime(2026, 11, 20, 8, 0, tzinfo=UTC)


def time(offset):
    return (BASE + dt.timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")


def row(open_seconds, width):
    return {"openUTC": time(open_seconds),
            "firstSeenUTC": time(open_seconds + width + 30)}


def packet():
    # Last closed H4 at 12:00 UTC, and all constituents known by 12:01.
    return {
        "dataOrigin": ORIGIN, "decisionUTC": time(4 * 3600 + 60),
        "asOfUTC": time(4 * 3600 + 60),
        "frames": {
            "M15": [row(i * 900, 900) for i in range(16)],
            "H1": [row(i * 3600, 3600) for i in range(4)],
            "H4": [row(0, 14400)]
        }
    }


class CapitalReceiptTests(unittest.TestCase):
    def safe(self, result):
        self.assertEqual(result["signal"], "WAIT")
        self.assertEqual(result["providerCandidate"],
                         "CAPITAL_COM_DEMO_SELECTED_UNCONNECTED")
        for key in ("executable", "researchEligible", "paperOrdersAllowed",
                    "liveOrdersAllowed", "connected",
                    "sourceRightsIndependentlyVerified",
                    "brokerSessionCalendarVerified",
                    "firstSeenIndependentlyAttested",
                    "realBidAskVerified", "brokerExecutionCostsVerified",
                    "independentForwardPerformanceProven"):
            self.assertIs(result[key], False, key)
        self.assertEqual(result["providerRequestsMade"], 0)
        self.assertEqual(result["brokerOrdersSent"], 0)
        raw = json.dumps(result)
        for secret in ("PRIVATE_TOKEN", "GOLD_PRICE", "apiKey", "bidPrice"):
            self.assertNotIn(secret, raw)

    def test_one_h4_has_exact_m15_h1_constituents_but_not_rights(self):
        report = inspect_receipts(packet())
        self.safe(report)
        self.assertEqual(report["status"], "UNATTESTED_GEOMETRY_ONLY_NOT_ADMITTED")
        self.assertEqual(report["receivedClosedCounts"],
                         {"M15": 16, "H1": 4, "H4": 1})
        self.assertEqual(report["h4FullyCoveredByBoth"], 1)
        self.assertTrue(report["latestH4HasBothConstituentFrames"])
        self.assertEqual(report["perFrameUnclassifiedUTCGridGaps"],
                         {"M15": 0, "H1": 0, "H4": 0})
        self.assertEqual(report["latestClosedFrameAgeSeconds"],
                         {"M15": 60, "H1": 60, "H4": 60})
        self.assertFalse(report["minimum21H4ConstituentGeometry"])
        self.assertFalse(report["minimum50H4ConstituentGeometry"])

    def test_missing_m15_constituent_never_claims_h4_parity(self):
        p = packet()
        p["frames"]["M15"].pop(6)
        out = inspect_receipts(p)
        self.safe(out)
        self.assertEqual(out["status"], "INCOMPLETE_GAPPY_OR_STALE_UNATTESTED_GEOMETRY")
        self.assertEqual(out["perFrameUnclassifiedUTCGridGaps"]["M15"], 1)
        self.assertEqual(out["h4FullyCoveredByM15"], 0)
        self.assertEqual(out["h4FullyCoveredByH1"], 1)
        self.assertEqual(out["h4FullyCoveredByBoth"], 0)

    def test_lookahead_wrong_source_spoofed_rights_and_prices_block(self):
        variants = []
        p = packet()
        p["frames"]["M15"][-1]["firstSeenUTC"] = time(4 * 3600 + 120)
        variants.append(p)
        p = packet()
        p["frames"]["H4"][0]["firstSeenUTC"] = time(14400 - 1)
        variants.append(p)
        p = packet()
        p["frames"]["H1"][0]["openUTC"] = time(60)
        variants.append(p)
        p = packet()
        p["frames"]["M15"].reverse()
        variants.append(p)
        p = packet()
        p["frames"]["M15"][1]["openUTC"] = p["frames"]["M15"][0]["openUTC"]
        variants.append(p)
        p = packet()
        p["frames"]["H4"][0]["bidPrice"] = "GOLD_PRICE"
        variants.append(p)
        variants.extend([
            {**packet(), "dataOrigin": "MASSIVE_SYNTHETIC_ALTERNATE"},
            {**packet(), "sourceRightsIndependentlyVerified": True},
            {**packet(), "privateToken": "PRIVATE_TOKEN"},
            {**packet(), "decisionUTC": "2026-11-20T12:01:00+00:00"},
            {**packet(), "asOfUTC": time(14399)},
            {**packet(), "frames": {"H4": packet()["frames"]["H4"]}},
            None,
        ])
        for bad in variants:
            with self.subTest(bad=str(bad)[:80]):
                result = inspect_receipts(bad)
                self.safe(result)
                self.assertEqual(result["status"], "BLOCKED")

    def test_old_closed_candle_never_appears_fresh(self):
        p = packet()
        p["decisionUTC"] = time(4 * 3600 + 3600)
        p["asOfUTC"] = p["decisionUTC"]
        out = inspect_receipts(p)
        self.safe(out)
        self.assertEqual(out["status"], "INCOMPLETE_GAPPY_OR_STALE_UNATTESTED_GEOMETRY")
        self.assertFalse(out["recentClosedFramesAtDecision"])

    def test_no_network_and_no_order_even_when_perfect(self):
        with patch.object(socket, "socket", side_effect=AssertionError("NO NETWORK")):
            out = inspect_receipts(packet())
        self.safe(out)


if __name__ == "__main__":
    unittest.main()
