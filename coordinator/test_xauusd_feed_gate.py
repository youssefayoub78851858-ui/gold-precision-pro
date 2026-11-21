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
    return {"provider": "UNIT_TEST_FIXTURE", "instrument": "XAU/USD", "mode": "synthetic",
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
    def test_validated_fixture_is_explicitly_synthetic_and_never_research_eligible(self):
        result = intake_payload(payload(), NOW, SourcePolicy())
        self.assertEqual(result["status"], "SYNTHETIC_TEST_ONLY")
        self.assertEqual(result["sourceDataMode"], "synthetic")
        self.assertIn("SYNTHETIC_DATA_NOT_REAL_MARKET_EVIDENCE", result["blockingReasons"])
        self.assertEqual(set(result["frames"]), {"15min", "1h", "4h"})
        self.assertFalse(result["researchEligible"])
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertEqual(result["sourceRequestsMade"], 0)
        self.assertFalse(result["secretPersisted"])

    def test_closed_utc_aligned_fixture_frames_are_validated_but_quarantined(self):
        approved_fixture_policy = SourcePolicy(True, True, True, True, "UNIT FIXTURE ONLY", "UNIT_TEST_FIXTURE")
        result = intake_payload(payload(), NOW, approved_fixture_policy)
        self.assertEqual(result["status"], "SYNTHETIC_TEST_ONLY", result)
        self.assertEqual(set(result["frames"]), {"15min", "1h", "4h"})
        self.assertTrue(all(row["closed"] and row["aligned"] and not row["gaps"]
                            for row in result["frames"].values()))
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertFalse(result["researchEligible"])

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
        for field, value in (("instrument", "CFI-XAUUSD"), ("provider", "OTHER"), ("mode", "unknown")):
            data = payload()
            data[field] = value
            result = intake_payload(data, NOW, policy)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["signal"], "WAIT")
        data = payload()
        data["receivedUTC"] = "2026-11-11T12:00:00+02:00"
        result = intake_payload(data, NOW, SourcePolicy())
        self.assertIn("INGEST_TIMESTAMP_INVALID", result["blockingReasons"])

    def test_future_receipt_and_fractional_candle_session_boundaries_fail_closed(self):
        # Every simulated price is a unit fixture; no external feed is called.
        # A 1 ms future receipt is not known at the research decision instant.
        for offset_ms in (1, 250, 59999):
            data = payload()
            data["receivedUTC"] = timestamp(NOW + dt.timedelta(milliseconds=offset_ms))
            with self.subTest(receipt_future_ms=offset_ms):
                result = intake_payload(data, NOW, SourcePolicy())
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn("INGEST_PACKET_STALE_OR_FUTURE", result["blockingReasons"])
                self.assertEqual(result["frames"], {})
                self.assertEqual(result["signal"], "WAIT")
                self.assertIs(result["executable"], False)

        for interval in ("15min", "1h", "4h"):
            # The old integer-epoch modulo check silently truncated 500 ms.
            data = payload()
            opened = data["frames"][interval]["candles"][0]["openTime"]
            fractional = opened.replace("Z", ".500Z")
            data["frames"][interval]["candles"][0]["openTime"] = fractional
            data["frames"][interval]["expectedOpenTimes"][0] = fractional
            with self.subTest(candle_interval=interval):
                result = intake_payload(data, NOW, SourcePolicy())
                self.assertEqual(result["status"], "BLOCKED")
                self.assertTrue(any("not UTC-aligned" in reason
                                    for reason in result["blockingReasons"]))
                self.assertEqual(result["signal"], "WAIT")
                self.assertFalse(result["researchEligible"])

            schedule_only = payload()
            schedule_only["frames"][interval]["expectedOpenTimes"][0] = fractional
            with self.subTest(schedule_interval=interval):
                result = intake_payload(schedule_only, NOW, SourcePolicy())
                self.assertEqual(result["status"], "BLOCKED")
                self.assertTrue(any("expected schedule contains unclosed or unaligned bars" in reason
                                    for reason in result["blockingReasons"]))
                self.assertEqual(result["frames"], {})

        correct = intake_payload(payload(), NOW, SourcePolicy())
        self.assertEqual(correct["status"], "SYNTHETIC_TEST_ONLY")
        self.assertFalse(correct["executable"])

    def test_recorded_source_cannot_self_certify_session_gaps(self):
        # All data below are fabricated; passing this fixture never proves a vendor feed.
        data = payload()
        data["mode"] = "recorded"
        data["priceBasis"] = "BID"
        policy = SourcePolicy(True, True, True, True, "UNIT TEST RIGHTS ONLY", "UNIT_TEST_FIXTURE")
        blocked = intake_payload(data, NOW, policy)
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertIn("INDEPENDENT_SESSION_SCHEDULE_UNVERIFIED", blocked["blockingReasons"])
        self.assertFalse(blocked["researchEligible"])

        independent = {tf: list(f["expectedOpenTimes"]) for tf, f in data["frames"].items()}
        checked = SourcePolicy(True, True, True, True, "UNIT TEST RIGHTS ONLY", "UNIT_TEST_FIXTURE",
                               "INDEPENDENT UNIT TEST CALENDAR", independent,
                               expected_price_basis="BID", price_basis_reference="UNIT QUOTE AUDIT")
        accepted = intake_payload(data, NOW, checked)
        self.assertEqual(accepted["status"], "ADMISSIBLE_FOR_RESEARCH_ONLY")
        self.assertEqual(accepted["signal"], "WAIT")
        self.assertFalse(accepted["executable"])

        mislabeled = dict(data, priceBasis="MID")
        wrong_basis = intake_payload(mislabeled, NOW, checked)
        self.assertIn("BID_QUOTE_BASIS_UNVERIFIED", wrong_basis["blockingReasons"])
        self.assertFalse(wrong_basis["researchEligible"])

        # The packet now omits a historical bar AND removes it from its own declared
        # schedule, a previously unobservable gap. The independent calendar catches it.
        independent["15min"].insert(0, timestamp(NOW.replace(minute=0) -
                                                  dt.timedelta(minutes=30)))
        mismatch = intake_payload(data, NOW, checked)
        self.assertEqual(mismatch["status"], "BLOCKED")
        self.assertIn("15MIN_INDEPENDENT_SCHEDULE_MISMATCH", mismatch["blockingReasons"])
        self.assertFalse(mismatch["researchEligible"])
        self.assertEqual(mismatch["frames"], {})

    def test_real_shape_crossframe_bid_parity_mismatch_blocks_all_intake(self):
        # Offline, fabricated 4h BID-price ladder with 16 M15 bars. No
        # external provider and no actual licensing proof in this test.
        start = NOW.replace(hour=8, minute=0)
        quarter = []
        for i in range(16):
            opened = start + dt.timedelta(minutes=15 * i)
            o = 4000 + .2 * i
            quarter.append({"openTime": timestamp(opened),
                            "open": o, "high": o + 1,
                            "low": o - 1, "close": o + .5})

        def aggregate(rows):
            return {"openTime": rows[0]["openTime"],
                    "open": rows[0]["open"],
                    "high": max(r["high"] for r in rows),
                    "low": min(r["low"] for r in rows),
                    "close": rows[-1]["close"]}

        hourly = [aggregate(quarter[i:i + 4])
                  for i in range(0, 16, 4)]
        h4 = [aggregate(quarter)]
        data = payload()
        data["mode"] = "recorded"
        data["priceBasis"] = "BID"
        data["frames"] = {
            "15min": {"candles": quarter,
                      "expectedOpenTimes": [r["openTime"] for r in quarter]},
            "1h": {"candles": hourly,
                   "expectedOpenTimes": [r["openTime"] for r in hourly]},
            "4h": {"candles": h4,
                   "expectedOpenTimes": [r["openTime"] for r in h4]}
        }
        independent = {tf: list(frame["expectedOpenTimes"])
                       for tf, frame in data["frames"].items()}
        policy = SourcePolicy(
            True, True, True, True, "OFFLINE TEST RIGHTS ONLY",
            "UNIT_TEST_FIXTURE", "OFFLINE INDEPENDENT TEST SCHEDULE",
            independent, expected_price_basis="BID",
            price_basis_reference="OFFLINE TEST BID BASIS"
        )
        good = intake_payload(data, NOW, policy)
        self.assertEqual(good["status"], "ADMISSIBLE_FOR_RESEARCH_ONLY")
        self.assertEqual(good["signal"], "WAIT")
        self.assertFalse(good["executable"])
        self.assertEqual(good["crossFrameParity"]["1h"]["matched"], 4)
        self.assertEqual(good["crossFrameParity"]["4h"]["matched"], 1)
        self.assertEqual(good["crossFrameParity"]["1h"]["uncovered"], 0)
        self.assertEqual(good["crossFrameParity"]["4h"]["uncovered"], 0)
        self.assertTrue(good["crossFrameParity"]["4h"]["allProvidedParentBarsCovered"])
        self.assertFalse(good["crossFrameParity"]["4h"]["fullMarketHistoryVerified"])
        self.assertFalse(good["crossFrameParity"]["4h"]["nativeBrokerSessionVerified"])

        for interval, target, field in (
            ("1h", 2, "high"), ("4h", 0, "close")
        ):
            tampered = json.loads(json.dumps(data))
            if field == "high":
                tampered["frames"][interval]["candles"][target][field] += 5
            else:
                tampered["frames"][interval]["candles"][target][field] -= .2
            wrong = intake_payload(tampered, NOW, policy)
            self.assertEqual(wrong["status"], "BLOCKED")
            self.assertFalse(wrong["researchEligible"])
            self.assertEqual(wrong["signal"], "WAIT")
            self.assertEqual(wrong["frames"], {})
            self.assertIsNone(wrong["crossFrameParity"])
            self.assertIn(
                f"{interval.upper()}_CLOSED_OHLC_PARITY_MISMATCH",
                wrong["blockingReasons"]
            )

        unlicensed = intake_payload(data, NOW, SourcePolicy())
        self.assertEqual(unlicensed["status"], "BLOCKED")
        self.assertIsNone(unlicensed["crossFrameParity"])
        self.assertFalse(unlicensed["researchEligible"])

    def test_partial_m15_coverage_never_claims_full_history_parity(self):
        data = payload()
        data["mode"] = "recorded"
        data["priceBasis"] = "BID"
        independent = {tf: list(f["expectedOpenTimes"])
                       for tf, f in data["frames"].items()}
        policy = SourcePolicy(True, True, True, True,
                              "OFFLINE TEST RIGHTS", "UNIT_TEST_FIXTURE",
                              "UNIT TEST SCHEDULE", independent,
                              expected_price_basis="BID",
                              price_basis_reference="UNIT TEST BID QUOTE")
        partial = intake_payload(data, NOW, policy)
        self.assertEqual(partial["signal"], "WAIT")
        self.assertEqual(partial["crossFrameParity"]["1h"]["matched"], 0)
        self.assertEqual(partial["crossFrameParity"]["4h"]["matched"], 0)
        self.assertEqual(partial["crossFrameParity"]["1h"]["uncovered"], 1)
        self.assertEqual(partial["crossFrameParity"]["4h"]["uncovered"], 1)
        self.assertFalse(partial["crossFrameParity"]["1h"]["allProvidedParentBarsCovered"])
        self.assertFalse(partial["crossFrameParity"]["4h"]["allProvidedParentBarsCovered"])

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
