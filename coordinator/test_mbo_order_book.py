"""Clearly synthetic order-life-cycle tests for the isolated MBO reducer."""
from __future__ import annotations

import pathlib
import unittest

from databento_dbn_readonly import decode_dbn_file
from mbo_order_book import F_BAD_TS_RECV, F_LAST, F_MAYBE_BAD_BOOK, F_SNAPSHOT, UNDEF_PRICE, replay_mbo


HERE = pathlib.Path(__file__).resolve().parent
DBN_FIXTURES = HERE / "fixtures" / "databento_dbn" / "upstream-a776930"
SYNTHETIC_COVERAGE = {
    "status": "VERIFIED_COMPLETE",
    "scope": "CHANNEL",
    "gapCount": 0,
    "evidenceReference": "test-only:closed-fixture-sequence",
}


def event(ts, seq, action, side="N", order_id=0, price=UNDEF_PRICE, size=0, flags=F_LAST,
          publisher=1, instrument=999, channel=7, symbol="TEST-ONLY"):
    return {"ts_event": ts, "sequence": seq, "action": action, "side": side,
            "order_id": order_id, "price": price, "size": size, "flags": flags,
            "publisher_id": publisher, "instrument_id": instrument,
            "channel_id": channel, "symbol": symbol}


def snapshot(ts=1, seq=0, instrument=999, channel=7):
    return [
        event(ts, seq, "R", flags=F_SNAPSHOT | F_BAD_TS_RECV, instrument=instrument, channel=channel),
        event(ts, seq + 1, "A", "B", 11, 100 * 1_000_000_000, 5, F_SNAPSHOT, instrument=instrument, channel=channel),
        event(ts, seq + 2, "A", "B", 12, 100 * 1_000_000_000, 3, F_SNAPSHOT, instrument=instrument, channel=channel),
        event(ts, seq + 3, "A", "A", 21, 101 * 1_000_000_000, 4, F_SNAPSHOT | F_LAST, instrument=instrument, channel=channel),
    ]


def rebuild(rows, cutoff=100, coverage=SYNTHETIC_COVERAGE):
    return replay_mbo(rows, as_of_event_ns=cutoff, coverage=coverage, data_origin="SYNTHETIC_TEST_ONLY")


class MBOOrderBookTests(unittest.TestCase):
    def test_snapshot_add_modify_partial_full_cancel_trade_fill_and_tied_time(self):
        rows = snapshot()
        # Equal timestamps and source sequence are intentionally preserved.
        rows += [
            event(2, 4, "M", "B", 12, 100_500_000_000, 2, 0),
            event(2, 5, "T", "A", 0, 101_000_000_000, 1, 0),
            event(2, 5, "F", "B", 12, 100_500_000_000, 1, F_LAST),
            event(3, 6, "C", "B", 11, 100_000_000_000, 2, F_LAST),
            event(4, 7, "C", "B", 11, 100_000_000_000, 3, F_LAST),
        ]
        result = rebuild(rows, cutoff=4)
        book = result["books"][0]
        self.assertTrue(book["bookReady"], book["blockers"])
        self.assertEqual(book["bestBid"], {"price": 100_500_000_000, "size": 2, "orderCount": 1})
        self.assertEqual(book["bestAsk"], {"price": 101_000_000_000, "size": 4, "orderCount": 1})
        self.assertEqual(book["orderCount"], 2)
        self.assertEqual([order["order_id"] for order in book["orders"]], [21, 12])
        self.assertEqual(book["orders"][-1]["prioritySourceIndex"], 4)
        self.assertEqual([x["action"] for x in result["eventTrace"]], [x["action"] for x in rows])
        self.assertEqual([x["sequence"] for x in result["eventTrace"]], [x["sequence"] for x in rows])
        self.assertEqual(result["status"], "SYNTHETIC_TEST_ONLY")
        self.assertFalse(result["researchEligible"])
        self.assertFalse(result["feedEmitted"])
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])

    def test_depth_aggregation_and_tool_channel_scope_are_separate(self):
        rows = snapshot() + [
            event(2, 4, "A", "B", 31, 99_000_000_000, 7, F_LAST),
            event(2, 5, "A", "A", 41, 102_000_000_000, 6, F_LAST, instrument=1000, channel=8),
        ]
        result = rebuild(rows, cutoff=2)
        by_instrument = {b["instrument_id"]: b for b in result["books"]}
        self.assertEqual(len(by_instrument), 2)
        self.assertEqual(by_instrument[999]["bids"][0]["size"], 8)
        self.assertEqual(by_instrument[999]["bids"][1]["price"], 99_000_000_000)
        self.assertEqual(by_instrument[1000]["blockers"], ["MBO_SNAPSHOT_REQUIRED"])

    def test_no_snapshot_unknown_order_or_unverified_coverage_never_ready(self):
        no_snapshot = [event(1, 1, "C", "B", 999, 100_000_000_000, 1)]
        result = rebuild(no_snapshot)
        self.assertFalse(result["books"][0]["bookReady"])
        self.assertIn("MBO_SNAPSHOT_REQUIRED", result["books"][0]["blockers"])
        with self.assertRaisesRegex(ValueError, "MBO_CANCEL_UNKNOWN_ORDER"):
            rebuild(snapshot() + [event(2, 4, "C", "B", 404, 100_000_000_000, 1)], cutoff=2)
        unverified = rebuild(snapshot(), cutoff=1, coverage=None)
        self.assertFalse(unverified["books"][0]["bookReady"])
        self.assertIn("CHANNEL_CONTINUITY_UNVERIFIED", unverified["books"][0]["blockers"])
        boolean_gap = rebuild(snapshot(), cutoff=1, coverage={**SYNTHETIC_COVERAGE, "gapCount": False})
        self.assertFalse(boolean_gap["books"][0]["bookReady"])

    def test_gap_and_clear_invalidate_until_a_new_snapshot_recovers(self):
        broken = snapshot() + [event(2, 4, "N", flags=F_MAYBE_BAD_BOOK | F_LAST)]
        result = rebuild(broken, cutoff=2)
        self.assertFalse(result["books"][0]["bookReady"])
        self.assertIn("F_MAYBE_BAD_BOOK", result["books"][0]["blockers"])
        self.assertFalse(result["books"][0]["orderCount"])
        # Recovery is a new complete replay segment rooted in a fresh snapshot.
        recovered = rebuild(snapshot(ts=3, seq=0), cutoff=3)
        self.assertTrue(recovered["books"][0]["bookReady"])
        recovered_same_stream = rebuild(broken + snapshot(ts=3, seq=0), cutoff=3)
        self.assertTrue(recovered_same_stream["books"][0]["bookReady"])
        cleared = rebuild(snapshot() + [event(2, 4, "R")], cutoff=2)
        self.assertFalse(cleared["books"][0]["bookReady"])
        self.assertIn("CLEAR_REQUIRES_FRESH_SNAPSHOT", cleared["books"][0]["blockers"])

    def test_reported_sequence_gaps_and_missing_final_event_boundary_block(self):
        gap_coverage = {**SYNTHETIC_COVERAGE, "gapCount": 1}
        gap = rebuild(snapshot(), cutoff=1, coverage=gap_coverage)
        self.assertFalse(gap["books"][0]["bookReady"])
        incomplete = snapshot() + [event(2, 4, "A", "B", 13, 99_000_000_000, 1, 0)]
        result = rebuild(incomplete, cutoff=2)
        self.assertFalse(result["books"][0]["bookReady"])
        self.assertIn("MBO_EVENT_INCOMPLETE", result["books"][0]["blockers"])

    def test_future_reversed_and_equal_timestamp_source_order(self):
        future = snapshot() + [event(101, 4, "N")]
        with self.assertRaisesRegex(ValueError, "MBO_FUTURE_EVENT"):
            rebuild(future, cutoff=100)
        reversed_time = snapshot() + [event(2, 4, "N"), event(1, 5, "N")]
        with self.assertRaisesRegex(ValueError, "MBO_REVERSED_EVENT_TIME"):
            rebuild(reversed_time, cutoff=2)
        reversed_sequence = snapshot() + [event(2, 4, "N"), event(2, 3, "N")]
        with self.assertRaisesRegex(ValueError, "MBO_REVERSED_CHANNEL_SEQUENCE"):
            rebuild(reversed_sequence, cutoff=2)
        tied = snapshot() + [event(2, 4, "T", "A", price=101_000_000_000, size=1, flags=0),
                             event(2, 4, "F", "B", 12, 100_000_000_000, 1, F_LAST)]
        tied_result = rebuild(tied, cutoff=2)
        self.assertEqual([e["sourceIndex"] for e in tied_result["eventTrace"]], list(range(len(tied))))
        self.assertEqual(tied_result["eventTrace"][-2]["sequence"], tied_result["eventTrace"][-1]["sequence"])

    def test_invalid_orders_prices_sides_and_depth_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "MBO_ADD_ORDER_ID_OR_SIDE"):
            rebuild(snapshot() + [event(2, 4, "A", "B", 11, 99_000_000_000, 1)], cutoff=2)
        with self.assertRaisesRegex(ValueError, "MBO_PRICE_SIZE"):
            rebuild(snapshot() + [event(2, 4, "A", "B", 33, UNDEF_PRICE, 1)], cutoff=2)
        with self.assertRaisesRegex(ValueError, "MBO_MODIFY_UNKNOWN_ORDER"):
            rebuild(snapshot() + [event(2, 4, "M", "B", 404, 100_000_000_000, 2)], cutoff=2)
        with self.assertRaisesRegex(ValueError, "MBO_CANCEL_EXCEEDS_ORDER"):
            rebuild(snapshot() + [event(2, 4, "C", "B", 11, 100_000_000_000, 99)], cutoff=2)
        with self.assertRaisesRegex(ValueError, "MBO_DEPTH_RANGE"):
            replay_mbo(snapshot(), as_of_event_ns=1, coverage=SYNTHETIC_COVERAGE, depth=11)
        crossed = snapshot() + [event(2, 4, "A", "B", 99, 102_000_000_000, 1)]
        crossed[-1]["price"] = 102_000_000_000
        crossed[-1]["flags"] = F_LAST
        result = rebuild(crossed, cutoff=2)
        self.assertFalse(result["books"][0]["bookReady"])
        self.assertIn("CROSSED_BOOK", result["books"][0]["blockers"])

    def test_official_mbo_fixture_is_compatible_but_not_a_complete_book(self):
        decoded = decode_dbn_file(DBN_FIXTURES / "test_data.mbo.dbn")
        result = replay_mbo(decoded["rows"], as_of_event_ns=max(r["ts_event"] for r in decoded["rows"]),
                            coverage=None, data_origin="UPSTREAM_SOFTWARE_TEST_FIXTURE")
        self.assertEqual(result["eventsProcessed"], 2)
        self.assertEqual([x["action"] for x in result["eventTrace"]], ["C", "C"])
        self.assertFalse(result["books"][0]["bookReady"])
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])


if __name__ == "__main__":
    unittest.main()
