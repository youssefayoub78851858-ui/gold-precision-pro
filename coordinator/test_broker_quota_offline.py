"""Offline-only shared broker tests. The injected provider is local and never uses Twelve Data."""
import datetime
import pathlib
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from broker import Blocked, Broker

NOW = 1794301205000  # 2026-11-10 09:00:05 UTC, during the FX market week
FRAMES = {"15min": 900000, "1h": 3600000, "4h": 14400000}


def candles(frame, now=NOW):
    interval = FRAMES[frame]
    newest = now // interval * interval - interval
    result = []
    for offset in range(3):
        start = newest - offset * interval
        price = 4100 + offset
        result.append({
            "datetime": datetime.datetime.fromtimestamp(start / 1000, datetime.timezone.utc)
                .isoformat().replace("+00:00", "Z"),
            "open": price,
            "high": price + 2,
            "low": price - 2,
            "close": price + 1,
        })
    return {"symbol": "XAU/USD", "meta": {"interval": frame}, "values": result}


class BrokerQuotaOfflineTests(unittest.TestCase):
    def make_broker(self, path, calls, initial_daily_usage=0):
        def provider(frame, size, end):
            calls.append((frame, size, end))
            return candles(frame)
        return Broker(path, provider, clock=lambda: NOW, initial_daily_usage=initial_daily_usage)

    def test_cache_deduplicates_same_request_and_separates_native_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            broker = self.make_broker(pathlib.Path(directory) / "quota.sqlite3", calls)
            first = broker.get("15min")
            repeat = broker.get("15min")
            hourly = broker.get("1h")
            four_hour = broker.get("4h")
            self.assertEqual(len(calls), 3)
            self.assertFalse(first["broker"]["cacheHit"])
            self.assertTrue(repeat["broker"]["cacheHit"])
            self.assertEqual(hourly["meta"]["interval"], "1h")
            self.assertEqual(four_hour["meta"]["interval"], "4h")

    def test_cache_and_quota_ledger_survive_broker_recreation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "quota.sqlite3"
            calls = []
            first = self.make_broker(path, calls)
            first.get("15min")
            restarted = self.make_broker(path, calls)
            cached = restarted.get("15min")
            with restarted.db() as db:
                reserved = db.execute("SELECT COUNT(*) FROM calls WHERE kind='live'").fetchone()[0]
            self.assertTrue(cached["broker"]["cacheHit"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(reserved, 1)

    def test_shared_sqlite_lease_blocks_duplicate_across_broker_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "quota.sqlite3"
            calls = []
            entered_provider = threading.Event()
            release_provider = threading.Event()
            def slow_provider(frame, size, end):
                calls.append((frame, size, end))
                entered_provider.set()
                if not release_provider.wait(2):
                    raise TimeoutError("mock provider wait expired")
                return candles(frame)
            first = Broker(path, slow_provider, clock=lambda: NOW)
            second = Broker(path, slow_provider, clock=lambda: NOW)
            result = []
            worker = threading.Thread(target=lambda: result.append(first.get("15min")))
            worker.start()
            self.assertTrue(entered_provider.wait(1))
            try:
                with self.assertRaises(Blocked) as blocked:
                    second.get("15min")
                self.assertEqual(blocked.exception.reason, "FETCH_IN_FLIGHT")
            finally:
                release_provider.set()
                worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(len(result), 1)
            self.assertEqual(len(calls), 1)

    def test_rolling_minute_safety_limit_blocks_eighth_provider_request(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            broker = self.make_broker(pathlib.Path(directory) / "quota.sqlite3", calls)
            requests = [(frame, end) for frame in FRAMES for end in (None, "2026-08-31", "2026-09-30")]
            for frame, end in requests[:7]:
                broker.get(frame, end=end, kind="history" if end else "live")
            with self.assertRaises(Blocked) as blocked:
                frame, end = requests[7]
                broker.get(frame, end=end, kind="history" if end else "live")
            self.assertEqual(blocked.exception.reason, "MINUTE_SAFETY_LIMIT")
            self.assertEqual(len(calls), 7)

    def test_daily_safety_limit_reserves_last_allowed_credit_then_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            clock = [NOW]
            def provider(frame, size, end):
                calls.append((frame, size, end))
                return candles(frame, clock[0])
            broker = Broker(pathlib.Path(directory) / "quota.sqlite3", provider,
                            clock=lambda: clock[0], initial_daily_usage=719)
            broker.get("15min")
            clock[0] += 61000  # keep the second request outside the rolling-minute window
            with self.assertRaises(Blocked) as blocked:
                broker.get("1h")
            self.assertEqual(blocked.exception.reason, "DAILY_SAFETY_LIMIT")
            self.assertEqual(len(calls), 1)

    def test_provider_429_cooldown_blocks_other_frames_globally(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def rate_limited_provider(frame, size, end):
                calls.append((frame, size, end))
                raise Blocked("PROVIDER_429", NOW + 60000)
            broker = Broker(pathlib.Path(directory) / "quota.sqlite3", rate_limited_provider, clock=lambda: NOW)
            with self.assertRaises(Blocked) as first:
                broker.get("15min")
            with self.assertRaises(Blocked) as second:
                broker.get("1h")
            self.assertEqual(first.exception.reason, "PROVIDER_429")
            self.assertEqual(second.exception.reason, "UPSTREAM_COOLDOWN")
            self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
