"""Synthetic-only tests: no vendor data, secrets, external calls or trading."""
import csv
import datetime as dt
import io
import unittest
from import_dukascopy_single_m15 import normalize
from validate_history import validate

UTC = dt.timezone.utc
START = dt.datetime(2026, 11, 2, 0, 0, tzinfo=UTC)


def synthetic_csv(count=96, omit=(), append_in_progress=False):
    f = io.StringIO()
    w = csv.writer(f)
    w.writerow(("timestamp", "open", "high", "low", "close", "volume"))
    for i in range(count + int(append_in_progress)):
        if i in omit:
            continue
        ts = START + dt.timedelta(minutes=15*i)
        value = 4000 + i/100
        w.writerow((int(ts.timestamp()*1000), value, value+2, value-2, value+1, 12))
    return f.getvalue()


class SingleM15(unittest.TestCase):
    def test_full_day_m15_h1_h4(self):
        report = normalize(synthetic_csv(), "2026-11-03T00:00:00Z")
        self.assertEqual(report["report"]["closedCounts"], {"15min": 96, "1h": 24, "4h": 6})
        self.assertFalse(report["report"]["readyForTrading"])
        self.assertEqual(report["report"]["signal"], "WAIT")
        self.assertFalse(report["report"]["rightsToRedistributeVerified"])
        self.assertFalse(report["report"]["sourceIndependentlyAuthenticated"])
        self.assertFalse(report["report"]["minimumForExistingHistoricalValidator"])
        self.assertEqual(report["document"]["frames"]["4h"][0]["open"], 4000)
        self.assertEqual(report["document"]["frames"]["4h"][0]["close"], 4000+15/100+1)

    def test_partial_current_candle_excluded(self):
        x = normalize(synthetic_csv(96, append_in_progress=True), "2026-11-03T00:00:00Z")
        self.assertEqual(x["report"]["closedCounts"]["15min"], 96)
        self.assertEqual(x["report"]["excludedNotYetClosed"], 1)

    def test_missing_bar_disqualifies_whole_hour_and_four_hour(self):
        x = normalize(synthetic_csv(96, omit={2}), "2026-11-03T00:00:00Z")
        self.assertEqual(x["report"]["closedCounts"], {"15min": 95, "1h": 23, "4h": 5})
        self.assertEqual(x["report"]["signal"], "WAIT")

    def test_existing_validator_compatible_when_history_is_sufficient(self):
        x = normalize(synthetic_csv(1024), "2026-11-13T00:00:00Z")
        self.assertTrue(x["report"]["minimumForExistingHistoricalValidator"])
        self.assertEqual(validate(x["document"])["status"], "VALID")
        self.assertFalse(x["report"]["readyForTrading"])

    def test_duplicate_rejected(self):
        sample = synthetic_csv(2).splitlines()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            normalize("\n".join(sample + [sample[-1]])+"\n", "2026-11-03T00:00:00Z")

    def test_wrong_symbol_header_and_invalid_ohlc(self):
        with self.assertRaisesRegex(ValueError, "header"):
            normalize("time,open,high,low,close\n", "2026-11-03T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "invalid OHLC"):
            normalize("timestamp,open,high,low,close\n1793577600000,4000,3990,3995,4001\n",
                      "2026-11-03T00:00:00Z")

    def test_non_utc_time_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid timestamp"):
            normalize("timestamp,open,high,low,close\n2026-11-02T12:00:00+02:00,4000,4001,3999,4000\n",
                      "2026-11-03T00:00:00Z")

    def test_unclosed_no_valid_bar(self):
        with self.assertRaisesRegex(ValueError, "No closed"):
            normalize(synthetic_csv(1), "2026-11-02T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
