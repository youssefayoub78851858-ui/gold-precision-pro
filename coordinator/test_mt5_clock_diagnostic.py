"""Synthetic fixtures test the MT5 clock diagnostic algorithm only."""
import datetime as dt
import pathlib
import tempfile
import unittest

from mt5_clock_diagnostic import diagnose, sample_from_csv

UTC = dt.timezone.utc


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def sample(phase, trusted, server_label):
    epoch = int(trusted.timestamp())
    bar_open = epoch // 900 * 900 - 900
    return {
        "phase": phase,
        "trustedUTC": stamp(trusted),
        "barEpochSeconds": bar_open,
        "tickEpochMilliseconds": epoch * 1000,
        "timeCurrentServerLabel": server_label,
        "timeGmtEpochSeconds": epoch,
    }


class MT5ClockDiagnosticTests(unittest.TestCase):
    def capture_pair(self):
        before = dt.datetime(2026, 10, 25, 0, 59, 50, tzinfo=UTC)
        after = dt.datetime(2026, 10, 25, 1, 0, 10, tzinfo=UTC)
        return [sample("before_transition", before, "2026-10-25 03:59:50"),
                sample("after_transition", after, "2026-10-25 03:00:10")]

    def test_independent_utc_and_documented_dst_shift_pass_but_never_unlock_signal(self):
        result = diagnose(self.capture_pair(), "TEST_ONLY_INDEPENDENT_UTC_FIXTURE", -3600)
        self.assertEqual(result["status"], "CLOCK_DIAGNOSTIC_PASSED_FOR_CAPTURED_DST_WINDOW")
        self.assertTrue(result["clockBasisVerified"])
        self.assertEqual(result["observedServerShiftSeconds"], -3600)
        self.assertTrue(all(row["barEpochMatchesTrustedUTC"] for row in result["samples"]))
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertFalse(result["researchEligible"])

    def test_raw_tick_one_hour_away_fails_even_if_candidate_iso_matches_epoch(self):
        samples = self.capture_pair()
        samples[1]["tickEpochMilliseconds"] += 3_600_000
        result = diagnose(samples, "TEST_ONLY_INDEPENDENT_UTC_FIXTURE", -3600)
        self.assertFalse(result["clockBasisVerified"])
        self.assertIn("AFTER_TRANSITION_TICK_EPOCH_DIFFERS_FROM_TRUSTED_UTC",
                      result["blockingReasons"])

    def test_raw_m15_epoch_one_hour_away_fails_against_trusted_closed_bar(self):
        samples = self.capture_pair()
        samples[1]["barEpochSeconds"] += 3600
        result = diagnose(samples, "TEST_ONLY_INDEPENDENT_UTC_FIXTURE", -3600)
        self.assertFalse(result["clockBasisVerified"])
        self.assertIn("AFTER_TRANSITION_M15_EPOCH_DOES_NOT_MATCH_TRUSTED_UTC_BAR",
                      result["blockingReasons"])

    def test_missing_transition_sample_or_missing_documented_shift_stays_unverified(self):
        single = diagnose(self.capture_pair()[:1], "TEST_ONLY_INDEPENDENT_UTC_FIXTURE", -3600)
        self.assertIn("BEFORE_AND_AFTER_DST_SAMPLES_REQUIRED", single["blockingReasons"])
        undocumented = diagnose(self.capture_pair(), "TEST_ONLY_INDEPENDENT_UTC_FIXTURE", 0)
        self.assertIn("BROKER_DST_SHIFT_NOT_DOCUMENTED", undocumented["blockingReasons"])
        self.assertFalse(undocumented["clockBasisVerified"])

    def test_local_csv_capture_is_read_for_diagnostic_only(self):
        from test_mt5_readonly_export import make_csv
        text, _ = make_csv(count=2, as_of=dt.datetime(2026, 11, 1, 0, 31, tzinfo=UTC))
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "synthetic-test-only.csv"
            path.write_text(text, encoding="utf-8")
            result = sample_from_csv(str(path), "before_transition", "2026-11-01T00:31:00Z")
        self.assertEqual(result["phase"], "before_transition")
        self.assertIn("barEpochSeconds", result)
        self.assertIn("tickEpochMilliseconds", result)
        self.assertEqual(result["timeCurrentServerLabel"], "2026-11-01 02:15:00")


if __name__ == "__main__":
    unittest.main()
