"""Zero-network overlap diagnostics tests, all prices synthetic."""
import copy
import datetime as dt
import unittest
from biquote_overlap_evidence import diagnose_biquote_overlap
from test_biquote_offline_source_audit import make_samples, NOW

def examine(feeds, now=NOW):
    return diagnose_biquote_overlap(feeds, now=now)

class BiQuoteOverlapEvidenceTests(unittest.TestCase):
    def safe(self, report):
        self.assertEqual(report["status"], "UNVERIFIED_DIAGNOSTIC_ONLY")
        self.assertEqual(report["signal"], "WAIT")
        self.assertIs(report["executable"], False)
        self.assertIs(report["researchEligible"], False)
        self.assertIs(report["sessionCalendarIndependentlyVerified"], False)
        self.assertIs(report["historicalBidAskQuoteParityProven"], False)
        self.assertEqual(report["sourceRequestsMade"], 0)
        self.assertEqual(report["orderRequestsMade"], 0)

    def test_regular_synthetic_full_overlap_all_agree(self):
        _, feeds=make_samples()
        r=examine(feeds)
        self.safe(r)
        self.assertIsNone(r["error"])
        self.assertEqual(r["overlap"]["H1"]["fullyCoveredAgree"], 200)
        self.assertEqual(r["overlap"]["H4"]["fullyCoveredAgree"], 50)
        for tf in ("H1","H4"):
            self.assertEqual(r["overlap"][tf]["internalM15ConstituentGaps"], 0)
            self.assertEqual(r["overlap"][tf]["fullyCoveredOHLCDisagree"], 0)

    def test_retention_edge_not_labeled_as_internal_gap(self):
        _, feeds=make_samples()
        feeds["M15"]["bars"]=feeds["M15"]["bars"][:-2]
        r=examine(feeds)
        self.safe(r)
        self.assertEqual(r["overlap"]["H1"]["oldestOrNewestWindowEdgeIncomplete"],1)
        self.assertEqual(r["overlap"]["H4"]["oldestOrNewestWindowEdgeIncomplete"],1)
        self.assertEqual(r["overlap"]["H4"]["internalM15ConstituentGaps"],0)

    def test_interior_m15_gap_explicitly_counted_without_fabrication(self):
        _, feeds=make_samples()
        removed=feeds["M15"]["bars"].pop(150)
        r=examine(feeds)
        self.safe(r)
        self.assertEqual(r["overlap"]["H1"]["internalM15ConstituentGaps"],1)
        self.assertEqual(r["overlap"]["H4"]["internalM15ConstituentGaps"],1)
        self.assertTrue(r["overlap"]["H1"]["examplesOfInternalGapUTC"])
        self.assertEqual(r["frames"]["M15"]["missingSlotsUnclassifiedByCalendar"],1)
        self.assertIn(removed["openTime"],str(r["overlap"]["H1"]["examplesOfInternalGapUTC"]))

    def test_h4_mismatch_detected_even_when_all_m15_present(self):
        _, feeds=make_samples()
        feeds["H4"]["bars"][0]["close"] += 1
        feeds["H4"]["bars"][0]["high"] += 1
        r=examine(feeds)
        self.safe(r)
        self.assertEqual(r["overlap"]["H4"]["fullyCoveredOHLCDisagree"],1)
        self.assertEqual(r["overlap"]["H4"]["disagreedOHLCFields"]["high"],1)
        self.assertEqual(r["overlap"]["H4"]["disagreedOHLCFields"]["close"],1)

    def test_invalid_timestamp_blocks_metrics(self):
        _, feeds=make_samples()
        feeds["H4"]["bars"][0]["openTime"]="2026-11-10T12:00:00+02:00"
        r=examine(feeds)
        self.safe(r)
        self.assertEqual(r["error"],"UTC_OFFSET_REQUIRED")
        self.assertEqual(r["overlap"],{})

    def test_no_frame_and_no_utc_fail_closed(self):
        _, feeds=make_samples()
        r=examine(feeds, NOW.replace(tzinfo=None))
        self.safe(r)
        self.assertEqual(r["error"],"INDEPENDENT_UTC_REQUIRED")
        r=examine({})
        self.safe(r)
        self.assertEqual(r["error"],"THREE_FRAMES_REQUIRED")

if __name__ == "__main__":
    unittest.main()
