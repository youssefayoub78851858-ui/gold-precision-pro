"""Synthetic-only acceptance tests for the local MT5 CSV adapter."""
import csv
import datetime as dt
import io
import pathlib
import unittest

from import_mt5_readonly import normalize_snapshot

UTC = dt.timezone.utc
BASE = dt.datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
WIDTH = 1600


def make_csv(count=WIDTH, omit=(), as_of=None, offset=120, symbol="XAUUSD.a", reverse=False,
             bad_ohlc_at=None, offsets=None):
    final_close = BASE + dt.timedelta(minutes=15 * count)
    observed = as_of or final_close + dt.timedelta(minutes=1)
    if isinstance(observed, str):
        observed = dt.datetime.fromisoformat(observed.replace("Z", "+00:00"))
    rows = []
    for i in range(count):
        if i in omit:
            continue
        opened = BASE + dt.timedelta(minutes=15 * i)
        server_time = opened + dt.timedelta(minutes=offset)
        value = 4000.0 + i / 100
        high, low = value + 1, value - 1
        if i == bad_ohlc_at:
            low = value + 2
        rows.append([symbol, "M15", server_time.strftime("%Y-%m-%dT%H:%M"),
                     offsets[i] if offsets and i in offsets else offset,
                     observed.isoformat().replace("+00:00", "Z"), value, high, low, value + .2, 100, 0, 4])
    if reverse:
        rows.reverse()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["symbol", "timeframe", "bar_open_server", "server_utc_offset_minutes",
                     "observed_utc", "open", "high", "low", "close", "tick_volume",
                     "real_volume", "spread_points"])
    writer.writerows(rows)
    writer.writerow(["#SNAPSHOT_END", observed.isoformat().replace("+00:00", "Z"), len(rows)])
    return out.getvalue(), final_close


class MT5ReadOnlyExport(unittest.TestCase):
    def test_closed_m15_and_complete_utc_h1_h4_are_derived(self):
        text, close = make_csv()
        as_of = close + dt.timedelta(minutes=1)
        result = normalize_snapshot(text, "XAUUSD.a", as_of.isoformat().replace("+00:00", "Z"))
        self.assertEqual(result["closedCounts"], {"M15": 1600, "H1": 400, "H4": 100})
        self.assertEqual(result["frames"]["H4"][0]["open"], 4000.0)
        self.assertEqual(result["frames"]["H4"][0]["close"], 4000 + 15 / 100 + .2)
        self.assertEqual(result["serverUtcOffsetMinutes"], 120)
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertFalse(result["readyForTrading"])
        self.assertFalse(result["historicalOffsetVerified"])
        self.assertTrue(result["quality"]["snapshotComplete"])
        self.assertIn("BROKER_DATA_RIGHTS_NOT_VERIFIED", result["alerts"])

    def test_unclosed_bar_and_stale_export_are_rejected_or_alerted(self):
        now = BASE + dt.timedelta(minutes=14)
        text, _ = make_csv(count=1, as_of=now)
        with self.assertRaisesRegex(ValueError, "forming or future M15"):
            normalize_snapshot(text, "XAUUSD.a", now.isoformat().replace("+00:00", "Z"))
        old_close = BASE + dt.timedelta(minutes=15 * 100)
        later = old_close + dt.timedelta(hours=2)
        stale_csv, _ = make_csv(count=100, as_of=later)
        result = normalize_snapshot(stale_csv, "XAUUSD.a", later.isoformat().replace("+00:00", "Z"))
        self.assertIn("XAU_EXPORT_STALE", result["alerts"])
        self.assertFalse(result["readyForTrading"])

    def test_incomplete_groups_are_omitted_without_filling(self):
        text, close = make_csv(count=WIDTH, omit={10})
        result = normalize_snapshot(text, "XAUUSD.a", (close + dt.timedelta(minutes=1)).isoformat().replace("+00:00", "Z"))
        self.assertEqual(len(result["frames"]["M15"]), WIDTH - 1)
        self.assertEqual(len(result["frames"]["H1"]), 399)
        self.assertEqual(len(result["frames"]["H4"]), 99)
        self.assertGreater(result["incompleteUTCGroups"]["H1"], 0)
        self.assertGreater(result["incompleteUTCGroups"]["H4"], 0)
        self.assertIn("INCOMPLETE_H1_H4_GROUPS", result["alerts"])

    def test_wrong_symbol_duplicate_order_and_invalid_ohlc_fail_closed(self):
        text, close = make_csv()
        as_of = (close + dt.timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        with self.assertRaisesRegex(ValueError, "symbol differs"):
            normalize_snapshot(text, "XAUUSD", as_of)
        lines = text.splitlines()
        duplicate = "\n".join(lines[:-1] + [lines[-2], lines[-1]]) + "\n"
        with self.assertRaisesRegex(ValueError, "duplicate or unordered"):
            normalize_snapshot(duplicate, "XAUUSD.a", as_of)
        with self.assertRaisesRegex(ValueError, "footer missing"):
            normalize_snapshot("\n".join(lines[:-1]) + "\n", "XAUUSD.a", as_of)
        reversed_csv, _ = make_csv(reverse=True)
        with self.assertRaisesRegex(ValueError, "duplicate or unordered"):
            normalize_snapshot(reversed_csv, "XAUUSD.a", as_of)
        bad, _ = make_csv(count=1, as_of=dt.datetime(2026, 11, 1, 0, 16, tzinfo=UTC), bad_ohlc_at=0)
        with self.assertRaisesRegex(ValueError, "invalid OHLC"):
            normalize_snapshot(bad, "XAUUSD.a", "2026-11-01T00:16:00Z")

    def test_offset_changes_inside_snapshot_are_not_guessed(self):
        offsets = {0: 120, 1: 105}
        text, close = make_csv(count=2, offsets=offsets,
                               as_of=BASE + dt.timedelta(minutes=46))
        as_of = (close + dt.timedelta(minutes=16)).isoformat().replace("+00:00", "Z")
        with self.assertRaisesRegex(ValueError, "one observation time and one server offset"):
            normalize_snapshot(text, "XAUUSD.a", as_of)

    def test_ea_is_local_read_only_and_has_no_network_or_trade_calls(self):
        root = pathlib.Path(__file__).parents[1]
        source = (root / "mt5" / "Experts" /
                  "GoldPrecisionReadOnlyExport.mq5").resolve().read_text()
        for banned in ("OrderSend", "CTrade", "WebRequest", "WebSocket", "https://"):
            self.assertNotIn(banned, source)
        for required in ("CopyRates", "PERIOD_M15, 1", "FILE_COMMON", "EventSetTimer",
                         "tick_volume", "real_volume", "#SNAPSHOT_END"):
            self.assertIn(required, source)
        import json
        inventory = json.loads((root / "research/results/connector-readiness.json").read_text())
        readiness = inventory["XAUUSD_MT5_LOCAL_EXPORT"]
        self.assertFalse(readiness["enabled"])
        self.assertFalse(readiness["networkImplemented"])
        self.assertFalse(readiness["entitlementVerified"])
        self.assertFalse(readiness["terminalRunVerified"])


if __name__ == "__main__":
    unittest.main()
