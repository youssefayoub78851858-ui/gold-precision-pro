"""Offline synthetic Capital page/receipt synchronization. No live feed."""
import copy
import json
import socket
import unittest
from unittest.mock import patch

from test_capital_demo_offline_batch_audit import sample
from capital_demo_historical_receipt_link import inspect_link
from capital_demo_receipt_preflight import ORIGIN

START = "2026-11-16T08:00:00Z"
DECISION = "2026-11-16T12:01:00Z"


def packet():
    plan, pages = sample(start=START, end="2026-11-16T12:00:00Z",
                         asof=DECISION)
    opens = {
        frame: [
            raw["snapshotTimeUTC"] + "Z"
            for block in pages[frame]
            for raw in block["response"]["prices"]
        ]
        for frame in pages
    }
    seconds = {"M15": 900, "H1": 3600, "H4": 14400}
    import datetime as dt
    rows = {}
    for frame, stamps in opens.items():
        rows[frame] = []
        for stamp in stamps:
            first = (dt.datetime.fromisoformat(stamp.replace("Z","+00:00"))
                     + dt.timedelta(seconds=seconds[frame]+30)
                     ).isoformat().replace("+00:00", "Z")
            rows[frame].append({"openUTC": stamp, "firstSeenUTC": first})
    return {"dataOrigin": "SYNTHETIC_TEST_ONLY", "plan": plan,
            "pages": pages, "receipts": {
                "dataOrigin": ORIGIN, "decisionUTC": DECISION,
                "asOfUTC": DECISION, "frames": rows
            }}


class LinkTests(unittest.TestCase):
    def safe(self, out):
        self.assertEqual(out["signal"], "WAIT")
        for key in ("executable", "researchEligible", "paperOrdersAllowed",
                    "liveOrdersAllowed", "sourceRightsIndependentlyVerified",
                    "historicalPagesIndependentlyAuthenticated",
                    "firstSeenIndependentlyAttested",
                    "brokerSessionCalendarVerified",
                    "historicalBidAskExecutionVerified",
                    "independentHoldoutValidated"):
            self.assertIs(out[key], False)
        self.assertEqual(out["providerRequestsMade"], 0)
        self.assertEqual(out["brokerOrdersSent"], 0)
        raw = json.dumps(out)
        for secret in ("4000", "TEST.GOLD.EPIC", "privateToken", "SECRET_PRICE"):
            self.assertNotIn(secret, raw)

    def test_same_synthetic_historical_pages_and_receipts_only(self):
        out = inspect_link(packet())
        self.safe(out)
        self.assertEqual(out["status"], "OFFLINE_SYNTHETIC_BARS_TIMESTAMPS_MATCH_ONLY")
        self.assertTrue(out["allFrameTimestampsMatched"])
        self.assertEqual(out["matchingBarCounts"], {"M15": 16, "H1": 4, "H4": 1})
        self.assertEqual(out["h4FullyCoveredByBoth"], 1)

    def test_mismatched_even_with_same_counts_is_rejected(self):
        p = packet()
        p["receipts"]["frames"]["M15"][0]["openUTC"] = "2026-11-16T07:45:00Z"
        p["receipts"]["frames"]["M15"][0]["firstSeenUTC"] = "2026-11-16T08:00:30Z"
        result = inspect_link(p)
        self.safe(result)
        self.assertEqual(result["reason"],
                         "RECEIPT_BARS_DIFFER_FROM_HISTORICAL_BARS")

    def test_post_decision_plan_lookahead_and_missing_source(self):
        p = packet()
        p["plan"]["asOfUTC"] = "2026-11-20T12:00:00Z"
        self.safe(inspect_link(p))
        self.assertEqual(inspect_link(p)["status"], "BLOCKED")
        p = packet()
        p["pages"]["H4"][0]["response"]["epic"] = "NOT.GOLD"
        result = inspect_link(p)
        self.safe(result)
        self.assertEqual(result["reason"], "HISTORICAL_OHLC_AUDIT_BLOCKED")

    def test_spoofed_rights_prices_and_unauthorized_origin_fail(self):
        for mutate in (
            lambda p: p.update(sourceRightsIndependentlyVerified=True),
            lambda p: p["receipts"]["frames"]["M15"][0].update(price="SECRET_PRICE"),
            lambda p: p.update(dataOrigin="CAPITAL_DEMO_LIVE"),
            lambda p: p["receipts"]["frames"]["H1"][0].update(
                firstSeenUTC="2026-11-16T08:59:59Z"),
        ):
            p = packet()
            mutate(p)
            out = inspect_link(p)
            self.safe(out)
            self.assertEqual(out["status"], "BLOCKED")

    def test_no_network_broker_or_automatic_paper_order(self):
        with patch.object(socket, "socket", side_effect=AssertionError("NO NETWORK")):
            out = inspect_link(packet())
        self.safe(out)


if __name__ == "__main__":
    unittest.main()
