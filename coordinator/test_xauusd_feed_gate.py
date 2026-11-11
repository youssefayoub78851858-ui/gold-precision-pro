"""Offline contract tests. All prices are fabricated unit fixtures, never market data."""
import datetime as dt
import hashlib
import hmac
import json
import unittest

from xauusd_feed_gate import (ReplayGuard, SourcePolicy, intake_payload,
                              retry_delay_seconds, verify_signed_body)

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 11, 12, 5, tzinfo=UTC)
SECRET = "UNIT-TEST-ONLY-never-use-as-a-real-credential-123456"


def timestamp(value):
    return value.isoformat().replace("+00:00", "Z")


def frame(opened):
    return {"candles": [{"openTime": timestamp(opened), "open": 4000,
                         "high": 4002, "low": 3998, "close": 4001}],
            "expectedOpenTimes": [timestamp(opened)]}


def payload():
    return {"provider": "UNCONFIGURED_TEST_SOURCE", "instrument": "XAU/USD", "mode": "live",
            "receivedUTC": timestamp(NOW),
            "frames": {"15min": frame(NOW.replace(minute=0) - dt.timedelta(minutes=15)),
                       "1h": frame(NOW.replace(minute=0) - dt.timedelta(hours=1)),
                       "4h": frame(NOW.replace(hour=8, minute=0))}}


def signed(data, now=NOW, nonce="test-nonce-00000001"):
    body = json.dumps(data, separators=(",", ":")).encode()
    stamp = int(now.timestamp())
    digest = hashlib.sha256(body).hexdigest()
    message = f"{stamp}\n{nonce}\n{digest}".encode()
    signature = "sha256=" + hmac.new(SECRET.encode(), message, hashlib.sha256).hexdigest()
    return body, {"X-GPP-Timestamp": str(stamp), "X-GPP-Nonce": nonce,
                  "X-GPP-Signature": signature}


class XauUsdFeedGateTests(unittest.TestCase):
    def test_validated_fixture_stays_wait_until_legal_source_is_approved(self):
        result = intake_payload(payload(), NOW, SourcePolicy())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("SOURCE_RIGHTS_OR_ENABLEMENT_NOT_VERIFIED", result["blockingReasons"])
        self.assertEqual(result["frames"], {})
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertEqual(result["sourceRequestsMade"], 0)
        self.assertFalse(result["secretPersisted"])

    def test_only_closed_utc_aligned_fresh_m15_h1_h4_are_admitted_for_research(self):
        approved_fixture_policy = SourcePolicy(True, True, True, True, "UNIT FIXTURE ONLY", "UNCONFIGURED_TEST_SOURCE")
        result = intake_payload(payload(), NOW, approved_fixture_policy)
        self.assertEqual(result["status"], "ADMISSIBLE_FOR_RESEARCH_ONLY", result)
        self.assertEqual(set(result["frames"]), {"15min", "1h", "4h"})
        self.assertTrue(all(row["closed"] and row["aligned"] and not row["gaps"]
                            for row in result["frames"].values()))
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])

    def test_missing_gap_is_rejected_and_does_not_leak_other_frames_as_complete(self):
        data = payload()
        opened = NOW.replace(minute=0) - dt.timedelta(minutes=30)
        data["frames"]["15min"]["expectedOpenTimes"].append(timestamp(opened))
        data["frames"]["15min"]["expectedOpenTimes"].sort()
        policy = SourcePolicy(True, True, True, True, "UNIT FIXTURE ONLY", "UNCONFIGURED_TEST_SOURCE")
        result = intake_payload(data, NOW, policy)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["frames"], {})
        self.assertTrue(any(reason.startswith("15MIN_REJECTED:15min candle gap")
                            for reason in result["blockingReasons"]))
        self.assertEqual(result["signal"], "WAIT")

    def test_unclosed_stale_duplicate_bad_ohlc_and_missing_schedule_fail_closed(self):
        policy = SourcePolicy(True, True, True, True, "UNIT FIXTURE ONLY", "UNCONFIGURED_TEST_SOURCE")
        cases = []
        unclosed = payload()
        unclosed["frames"]["15min"] = frame(NOW.replace(minute=15))
        cases.append((unclosed, "forming or future 15min"))
        stale = payload()
        stale["frames"]["15min"] = frame(NOW.replace(minute=15) - dt.timedelta(hours=1))
        stale["frames"]["15min"]["expectedOpenTimes"] = [timestamp(NOW.replace(minute=15) - dt.timedelta(hours=1))]
        cases.append((stale, "latest closed candle is stale"))
        duplicate = payload()
        row = dict(duplicate["frames"]["15min"]["candles"][0])
        duplicate["frames"]["15min"]["candles"].append(row)
        cases.append((duplicate, "duplicate or unordered"))
        bad = payload()
        bad["frames"]["15min"]["candles"][0]["low"] = 4002.5
        cases.append((bad, "invalid OHLC range"))
        no_schedule = payload()
        no_schedule["frames"]["4h"].pop("expectedOpenTimes")
        cases.append((no_schedule, "expected session schedule missing"))
        for data, message in cases:
            with self.subTest(message=message):
                result = intake_payload(data, NOW, policy)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["signal"], "WAIT")
                self.assertFalse(result["executable"])
                self.assertTrue(any(message in reason for reason in result["blockingReasons"]))

    def test_timestamp_provider_and_mode_mismatches_block(self):
        policy = SourcePolicy(True, True, True, True, "UNIT FIXTURE ONLY", "EXPECTED_PROVIDER")
        for field, value in (("instrument", "CFI-XAUUSD"), ("provider", "OTHER"), ("mode", "synthetic")):
            data = payload()
            data[field] = value
            result = intake_payload(data, NOW, policy)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["signal"], "WAIT")
        data = payload()
        data["receivedUTC"] = "2026-11-11T12:00:00+02:00"
        result = intake_payload(data, NOW, SourcePolicy())
        self.assertIn("INGEST_TIMESTAMP_INVALID", result["blockingReasons"])

    def test_signed_envelope_timestamp_hmac_and_nonce_replay(self):
        body, headers = signed(payload())
        guard = ReplayGuard()
        parsed = verify_signed_body(body, headers, SECRET, NOW, guard)
        self.assertEqual(parsed["instrument"], "XAU/USD")
        with self.assertRaisesRegex(ValueError, "replayed"):
            verify_signed_body(body, headers, SECRET, NOW, guard)
        tampered = body + b" "
        with self.assertRaisesRegex(ValueError, "signature invalid"):
            verify_signed_body(tampered, {**headers, "X-GPP-Nonce": "test-nonce-00000002"}, SECRET, NOW, ReplayGuard())
        with self.assertRaisesRegex(ValueError, "outside allowed skew"):
            verify_signed_body(body, headers, SECRET, NOW + dt.timedelta(minutes=2), ReplayGuard())
        with self.assertRaisesRegex(ValueError, "secret unavailable"):
            verify_signed_body(body, headers, "short", NOW, ReplayGuard())

    def test_outage_backoff_is_bounded_and_does_not_poll(self):
        self.assertEqual([retry_delay_seconds(n) for n in range(7)], [5, 10, 20, 40, 80, 160, 300])
        self.assertEqual(retry_delay_seconds(100), 300)
        for count in (-1, True, 1.2):
            with self.assertRaises(ValueError):
                retry_delay_seconds(count)


if __name__ == "__main__":
    unittest.main()
