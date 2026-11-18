"""BiQuote upstream session-reference evidence never promotes paper orders."""
import datetime as dt
import json
import socket
import unittest
from unittest.mock import patch

from biquote_declared_pause_forensics import classify_pause_failures
from test_biquote_24h_final_verdict import fixture

UTC=dt.timezone.utc
FIRST_FAILURE=dt.datetime(2026,11,16,22,3,2,tzinfo=UTC)

def observed():
    return [(FIRST_FAILURE+dt.timedelta(minutes=i*2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ") for i in range(29)]

def actual_report():
    r=fixture()
    for key in ("geometryFailureClasses","privateArchiveAttempts",
                "privateArchiveSavedSnapshots","privateArchiveRejectedSnapshots",
                "privateArchiveNewClosedBars"):
        r.pop(key)
    r.update(samplesObserved=720,missedOrSkippedSlots=0,
        requestsAttempted=2880,httpOkSamples=691,httpFailedSamples=29,
        auditShapePassedSamples=0,marketOpenSamples=691,
        providerStaleSamples=0,crossFrameUnverifiedSamples=691,
        h1FullyCoveredComparedAcrossSnapshots=32643,
        h4FullyCoveredComparedAcrossSnapshots=6646,
        h1DisagreementsAcrossSnapshots=0,
        h4DisagreementsAcrossSnapshots=0,
        h1UnclassifiedPartialAggregatesAcrossSnapshots=0,
        h4UnclassifiedPartialAggregatesAcrossSnapshots=2051,
        maxObservedQuoteAgeSeconds=183.859)
    return r

class BiQuoteDeclaredPauseForensics(unittest.TestCase):
    def safe(self,x):
        self.assertEqual(x["signal"],"WAIT")
        for k in ("executable","paperOrdersAllowed","liveOrdersAllowed",
                  "researchEligible","brokerSessionCalendarIndependentlyVerified",
                  "brokerSourceRightsIndependentlyVerified",
                  "independentQuoteFreshnessFullyProven",
                  "sourceAdmittedToResearchOrTrades",
                  "marketDataExposed","allOpenMarketQuotesFresh",
                  "allCrossFrameCandlesComplete"):
            self.assertIs(x[k],False,k)
        for k in ("providerRequestsMade","archiveWritesMade","brokerOrdersSent"):
            self.assertEqual(x[k],0)
        encoded=json.dumps(x,sort_keys=True)
        for key in ('"bid"','"ask"','"open"','"close"','"price"','"token"',
                    '"apiKey"','"quoteObservations"','"rawCandles"'):
            self.assertNotIn(key,encoded)
        self.assertNotIn("3900",encoded)

    def test_actual_29_failures_are_vendor_pause_candidates_not_source_certification(self):
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            out=classify_pause_failures(actual_report(),observed())
        self.safe(out)
        self.assertEqual(out["status"],"VENDOR_PAUSE_ONLY_CANDIDATE")
        self.assertEqual(out["reviewSamples"],720)
        self.assertEqual(out["httpFailedSamples"],29)
        self.assertEqual(out["observedFailureTimesCount"],29)
        self.assertEqual(out["vendorReferencePauseFailures"],29)
        self.assertEqual(out["vendorReferenceTradingTimeFailures"],0)
        self.assertEqual(out["outsideReferenceDateRangeFailures"],0)
        self.assertTrue(out["allObservedFailuresInsideVendorReferencePause"])
        self.assertIn("UPSTREAM_BROKER_CALENDAR_UNVERIFIED",out["reasonCodes"])
        self.assertIn("SOURCE_GEOMETRY_STILL_UNQUALIFIED",out["reasonCodes"])

    def test_one_unexpected_trading_hour_failure_overrules_vendor_pause_class(self):
        timestamps=observed()
        timestamps[-1]="2026-11-16T23:01:02Z"
        x=classify_pause_failures(actual_report(),timestamps)
        self.safe(x)
        self.assertEqual(x["status"],"OTHER_OR_UNEXPLAINED_FAILURES")
        self.assertEqual(x["vendorReferencePauseFailures"],28)
        self.assertEqual(x["vendorReferenceTradingTimeFailures"],1)
        self.assertFalse(x["allObservedFailuresInsideVendorReferencePause"])

    def test_missing_extra_duplicate_or_invalid_timestamps_never_certify(self):
        r=actual_report()
        for times in (observed()[:-1], observed()+["2026-11-16T23:01:02Z"],
                      sorted(observed()[:-1]+[observed()[0]]),
                      observed()[:-1]+["2026-11-16T22:59:02+00:00"],
                      observed()[:-1]+["2026-11-16T22:58:02Z"],
                      observed()[:-1]+["2026-11-18T22:59:02Z"],
                      list(reversed(observed()))):
            with self.subTest(times=times[-1]):
                x=classify_pause_failures(r,times)
                self.safe(x)
                self.assertNotEqual(x["status"],"VENDOR_PAUSE_ONLY_CANDIDATE")
                self.assertFalse(x["allObservedFailuresInsideVendorReferencePause"])

    def test_forged_final_report_never_promotes_quality(self):
        r=actual_report()
        for change in (
            {"signal":"BUY"},
            {"marketSessionIndependentlyVerified":True},
            {"cloudIndependentRightsProven":True},
            {"httpOkSamples":690},
            {"httpFailedSamples":30},
            {"startedUTC":"2026-11-18T19:45:00Z"},
            {"requestsAttempted":2881},
        ):
            out=classify_pause_failures({**r,**change},observed())
            self.safe(out)
            self.assertEqual(out["status"],"UNVERIFIED")
            self.assertIn("FINISHED_REPORT_NOT_VERIFIED",out["reasonCodes"])
        x=classify_pause_failures({"signal":"WAIT"},observed())
        self.safe(x)
        self.assertFalse(x["allObservedFailuresInsideVendorReferencePause"])

if __name__=="__main__":
    unittest.main()
