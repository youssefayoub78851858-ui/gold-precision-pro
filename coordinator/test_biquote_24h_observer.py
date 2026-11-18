"""Synthetic-only quality worker tests; never contact BiQuote or Render."""
import datetime as dt
import os
import sys
import unittest
from unittest.mock import patch

from biquote_24h_observer import (
    AUTHORIZATION_ENV, AUTHORIZATION_VALUE, INTERVAL_SECONDS, MAX_PUBLIC_REQUESTS,
    MAX_SAMPLES, QualityCounters, main, observe_24h,
    PRIVATE_CAPTURE_CLASSES, classify_private_capture_failure,
)

UTC = dt.timezone.utc
START = dt.datetime(2026, 11, 16, 18, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self, current=START):
        self.current = current
        self.slept = 0

    def now(self):
        return self.current

    def sleep(self, amount):
        assert amount >= 0, amount
        self.slept += amount
        self.current += dt.timedelta(seconds=amount)


def sample():
    return {
        "allHttp200AndValidJson": True, "requestCountAttempted": 4,
        "dataGeometryConformance": "SHAPE_CHECKS_FAILED_OR_INCOMPLETE",
        "geometryFailureClass": "UNCLASSIFIED_M15_COVERAGE_GAP",
        "httpResults": [{"endpoint": "quote", "marketState": "open",
                         "providerStale": False, "bid": 3840, "ask": 3840.2}],
        "structuralAudit": {"ohlcStructuralChecksPassed": False,
                            "quoteAgeSeconds": 2.0},
        "overlapEvidence": {"overlap": {
            "H1": {"fullyCoveredCompared": 47,
                   "fullyCoveredOHLCDisagree": 0,
                   "internalM15ConstituentGaps": 0},
            "H4": {"fullyCoveredCompared": 9,
                   "fullyCoveredOHLCDisagree": 0,
                   "internalM15ConstituentGaps": 3}
        }}
    }


class BiQuote24hOfflineTests(unittest.TestCase):
    def check_safe(self, result):
        self.assertEqual(result["signal"], "WAIT")
        self.assertIs(result["executable"], False)
        self.assertIs(result["researchEligible"], False)
        self.assertIs(result["paperOrdersAllowed"], False)
        self.assertIs(result["rawQuotesPersisted"], False)
        self.assertIs(result["orderEndpointsCalled"], False)
        self.assertIs(result["profitabilityTestPerformed"], False)
        self.assertIs(result["cloudIndependentRightsProven"], False)
        self.assertIs(result["marketSessionIndependentlyVerified"], False)

    def test_exactly_24h_720_samples_and_no_more_than_2880_gets(self):
        clock = FakeClock()
        events = []
        result = observe_24h(
            START, probe=sample, utc_now=clock.now,
            sleep=clock.sleep, emit=events.append)
        self.check_safe(result)
        self.assertEqual(clock.current, START + dt.timedelta(days=1))
        self.assertEqual(result["samplesObserved"], MAX_SAMPLES)
        self.assertEqual(result["plannedSamples"], 720)
        self.assertEqual(result["requestsAttempted"], MAX_PUBLIC_REQUESTS)
        self.assertEqual(result["requestsAttempted"], 2880)
        self.assertEqual(result["missedOrSkippedSlots"], 0)
        self.assertTrue(result["completed24hWindow"])
        self.assertEqual(result["httpOkSamples"], 720)
        self.assertEqual(result["auditShapePassedSamples"], 0)
        self.assertEqual(result["crossFrameUnverifiedSamples"], 720)
        self.assertEqual(
            result["geometryFailureClasses"]["UNCLASSIFIED_M15_COVERAGE_GAP"], 720)
        self.assertEqual(
            result["geometryFailureClasses"]["OHLC_PRICE_DISAGREEMENT"], 0)
        self.assertEqual(result["h1FullyCoveredComparedAcrossSnapshots"], 47*720)
        self.assertEqual(result["h4FullyCoveredComparedAcrossSnapshots"], 9*720)
        self.assertEqual(result["h4UnclassifiedPartialAggregatesAcrossSnapshots"], 3*720)
        self.assertEqual(len(events), MAX_SAMPLES+1)
        # Logs contain no raw market BID/ASK or history contents.
        # Aggregated counts may happen to contain the digits of a fixture
        # price. Detect leaking RAW quote keys, not coincidental digits in
        # safe aggregate counters such as H1 comparison totals.
        for event in events:
            self.assertNotIn("bid", event)
            self.assertNotIn("ask", event)
            self.assertNotIn("stagedBidFrames", event)
            self.assertNotIn("stagedAskFrames", event)

    def test_private_archive_rejection_is_fixed_enum_not_provider_or_price(self):
        self.assertEqual(classify_private_capture_failure("CLOSED_CANDLE_REVISED_H1"),
                         "CLOSED_BAR_REVISION")
        self.assertEqual(classify_private_capture_failure("QUOTE_STALE_OR_FUTURE"),
                         "QUOTE_CLOCK_OR_MARKET")
        self.assertEqual(classify_private_capture_failure("LATE_OR_OUT_OF_ORDER_BACKFILL_H4"),
                         "LATE_HISTORY_BACKFILL")
        self.assertEqual(classify_private_capture_failure("PRIVATE_PASSWORD_OR_PRICE_3872"),
                         "OTHER_PRIVATE_CAPTURE_FAILURE")
        self.assertEqual(classify_private_capture_failure(None),
                         "OTHER_PRIVATE_CAPTURE_FAILURE")
        self.assertEqual(set(PRIVATE_CAPTURE_CLASSES),
                         {"NONE", "QUOTE_CLOCK_OR_MARKET", "QUOTE_PRICE_PARITY",
                          "TICK_ORDER_OR_REVISION", "CLOSED_BAR_REVISION",
                          "LATE_HISTORY_BACKFILL", "CLOSED_HISTORY_FRESHNESS",
                          "CROSS_FRAME_PRICE_CONFLICT", "FRAME_STRUCTURE",
                          "CAPACITY_LIMIT", "PRIVATE_STORAGE_SECURITY",
                          "OTHER_PRIVATE_CAPTURE_FAILURE"})
        clock=FakeClock(START+dt.timedelta(hours=23,minutes=58))
        events=[]
        fail=sample()
        fail["privateArchive"]={"attempted":True,"saved":False,
                                "blockedReason":"CLOSED_CANDLE_REVISED_H1"}
        report=observe_24h(START, probe=lambda:fail,
                           utc_now=clock.now, sleep=clock.sleep,
                           emit=events.append)
        self.assertEqual(report["signal"],"WAIT")
        self.assertEqual(report["privateArchiveRejectedSnapshots"],1)
        self.assertEqual(report["privateArchiveRejectedByClass"]["CLOSED_BAR_REVISION"],1)
        self.assertEqual(events[0]["archiveRejectionClass"],"CLOSED_BAR_REVISION")
        self.assertFalse(events[0]["executable"])
        self.assertNotIn("blockedReason",str(events))
        self.assertNotIn("privateArchive",str(events[0]))
        self.assertNotIn('"bid"',str(events))
        self.assertNotIn('"ask"',str(events))

    def test_malicious_capture_rejection_not_logged_verbatim(self):
        clock=FakeClock(START+dt.timedelta(hours=23,minutes=58))
        events=[]
        bad=sample()
        bad["privateArchive"]={"attempted":True,"saved":False,
                               "blockedReason":"SENSITIVE_VENDOR_PRIVATE_PASSWORD"}
        observe_24h(START,probe=lambda:bad,utc_now=clock.now,
                    sleep=clock.sleep,emit=events.append)
        self.assertEqual(events[0]["archiveRejectionClass"],
                         "OTHER_PRIVATE_CAPTURE_FAILURE")
        self.assertNotIn("SENSITIVE_VENDOR_PRIVATE_PASSWORD",str(events))

    def test_diagnostics_distinguish_http_faults_from_h4_internal_gap(self):
        counters=QualityCounters()
        failed={
            "allHttp200AndValidJson":False,"requestCountAttempted":4,
            "qualityDiagnostic":{
                "mode":"BIQUOTE_METADATA_FAILURE_DIAGNOSTICS_ONLY",
                "endpoint":{"quote":"OK","M15":"NO_HTTP_RESPONSE",
                            "H1":"INVALID_JSON_OR_ENVELOPE","H4":"HTTP_429"},
                "marketDataExposed":False,"sourceRequestsMade":0,
                "tradingEnabled":False},
        }
        counters.add(failed)
        okay=sample()
        okay["qualityDiagnostic"]={
            "mode":"BIQUOTE_METADATA_FAILURE_DIAGNOSTICS_ONLY",
            "endpoint":{tf:"OK" for tf in ("quote","M15","H1","H4")},
            "independentQuoteAgeOver30Seconds":True,
            "independentQuoteAgeInvalid":False,
            "h4InternalM15Gaps":3,"h4RetentionEdgesIncomplete":2,
            "h4PartialObservedPriceContradictions":1,
            "h4MissingM15VendorPauseCandidates":4,
            "h4MissingM15OutsideVendorReference":2,
            "h4MissingM15ReferenceUnknown":0,
            "marketDataExposed":False,"sourceRequestsMade":0,
            "tradingEnabled":False,
        }
        counters.add(okay)
        r=counters.report(START,START+dt.timedelta(minutes=4),
                          missed_slots=0,complete_window=False)
        self.assertEqual(r["samplesObserved"],2)
        self.assertEqual(r["diagnosticSamples"],2)
        self.assertEqual(r["httpFailedSamples"],1)
        self.assertEqual(r["httpOkSamples"],1)
        self.assertEqual(r["endpointFailureCodes"]["H4"]["HTTP_429"],1)
        self.assertEqual(r["endpointFailureCodes"]["M15"]["NO_HTTP_RESPONSE"],1)
        self.assertEqual(r["endpointFailureCodes"]["H1"]["INVALID_JSON_OR_ENVELOPE"],1)
        self.assertEqual(r["endpointFailureCodes"]["quote"]["HTTP_429"],0)
        self.assertEqual(r["independentQuoteOver30SecondsSamples"],1)
        self.assertEqual(r["h4RetentionEdgeIncompleteAcrossSnapshots"],2)
        self.assertEqual(r["h4InternalM15GapsDiagnosedAcrossSnapshots"],3)
        self.assertEqual(r["h4PartialObservedPriceConflictsAcrossSnapshots"],1)
        self.assertEqual(r["h4MissingM15VendorPauseReferenceAcrossSnapshots"],4)
        self.assertEqual(r["h4MissingM15VendorTradingReferenceAcrossSnapshots"],2)
        self.assertEqual(r["h4MissingM15ReferenceUnknownAcrossSnapshots"],0)
        self.assertEqual(r["h4UnclassifiedPartialAggregatesAcrossSnapshots"],3)
        self.check_safe(r)
        import json
        serialized=json.dumps(r)
        for phrase in ("\"bid\"","\"ask\"","\"close\"",
                       "PRIVATE_PASSWORD_DO_NOT_LOG","https://biquote.io"):
            self.assertNotIn(phrase,serialized)

    def test_malformed_diagnostic_cannot_create_dynamic_labels_or_price_dump(self):
        x=sample()
        x["qualityDiagnostic"]={
            "mode":"BIQUOTE_METADATA_FAILURE_DIAGNOSTICS_ONLY",
            "endpoint":{"quote":"OK","M15":"OK","H1":"OK",
                        "H4":"SENSITIVE_PROVIDER_SECRET"},
            "marketDataExposed":False,"sourceRequestsMade":0,
            "tradingEnabled":False,
        }
        quality=QualityCounters()
        quality.add(x)
        r=quality.report(START,START+dt.timedelta(minutes=2),
                         missed_slots=0,complete_window=False)
        self.assertEqual(r["diagnosticSamples"],0)
        self.assertEqual(r["httpOkSamples"],1)
        self.assertNotIn("SENSITIVE_PROVIDER_SECRET",str(r))

    def test_restart_keeps_absolute_end_and_never_bursts_makeup_calls(self):
        clock = FakeClock(START + dt.timedelta(hours=3))
        report = observe_24h(
            START, probe=sample, utc_now=clock.now,
            sleep=clock.sleep, emit=lambda x: None)
        self.check_safe(report)
        self.assertTrue(report["completed24hWindow"])
        self.assertEqual(report["samplesObserved"], 630)
        self.assertEqual(report["missedOrSkippedSlots"], 90)
        self.assertEqual(report["requestsAttempted"], 630*4)
        self.assertEqual(clock.current, START + dt.timedelta(days=1))

    def test_expired_start_produces_no_network_and_no_wait(self):
        called = []
        clock = FakeClock(START + dt.timedelta(days=2))
        report = observe_24h(
            START, probe=lambda: called.append("should never call"),
            utc_now=clock.now, sleep=clock.sleep,
            emit=lambda x: None)
        self.check_safe(report)
        self.assertFalse(report["completed24hWindow"])
        self.assertTrue(report["windowExpiredBeforeWorkerStart"])
        self.assertEqual(report["requestsAttempted"], 0)
        self.assertEqual(called, [])
        self.assertEqual(clock.slept, 0)

    def test_offline_or_failed_http_stays_wait_and_never_retries(self):
        clock=FakeClock()
        count=[0]
        def failed():
            count[0]+=1
            return {"allHttp200AndValidJson": False, "requestCountAttempted": 4}
        report=observe_24h(START, probe=failed, utc_now=clock.now,
                           sleep=clock.sleep, emit=lambda x: None)
        self.check_safe(report)
        self.assertEqual(count[0], MAX_SAMPLES)
        self.assertEqual(report["httpFailedSamples"], MAX_SAMPLES)
        self.assertEqual(report["auditShapePassedSamples"],0)
        self.assertEqual(report["requestsAttempted"],MAX_PUBLIC_REQUESTS)

    def test_start_in_future_and_non_utc_fail_without_provider(self):
        clock=FakeClock()
        with self.assertRaisesRegex(ValueError,"START_MORE_THAN_15_MINUTES_AHEAD"):
            observe_24h(START+dt.timedelta(hours=1), probe=sample,
                        utc_now=clock.now, sleep=clock.sleep,
                        emit=lambda x: None)
        with self.assertRaises(ValueError):
            observe_24h(START.replace(tzinfo=None), probe=sample,
                        utc_now=clock.now, sleep=clock.sleep,
                        emit=lambda x: None)

    def test_fixed_private_holdout_can_arm_early_without_early_requests(self):
        holdout=dt.datetime(2026,11,18,0,0,tzinfo=UTC)
        clock=FakeClock(holdout-dt.timedelta(hours=6))
        calls=[]
        def probe():
            calls.append(clock.now())
            return sample()
        env={"GPP_BIQUOTE_REVIEW_START_UTC":"2026-11-18T00:00:00Z",
             "GPP_BIQUOTE_PRIVATE_FORWARD_ARCHIVE":
                 "APPROVED_READONLY_PRIVATE_NO_TRADING"}
        with patch.dict(os.environ,env):
            result=observe_24h(holdout,probe=probe,utc_now=clock.now,
                               sleep=clock.sleep,emit=lambda x: None)
        self.assertEqual(len(calls),720)
        self.assertEqual(calls[0],holdout)
        self.assertEqual(clock.current,holdout+dt.timedelta(days=1))
        self.assertEqual(result["requestsAttempted"],2880)
        self.assertEqual(result["missedOrSkippedSlots"],0)
        self.assertTrue(result["completed24hWindow"])
        self.assertEqual(result["signal"],"WAIT")
        self.assertIs(result["executable"],False)

    def test_fixed_holdout_cannot_prearm_without_private_approval(self):
        holdout=dt.datetime(2026,11,18,0,0,tzinfo=UTC)
        clock=FakeClock(holdout-dt.timedelta(hours=6))
        with patch.dict(os.environ,{
                "GPP_BIQUOTE_REVIEW_START_UTC":"2026-11-18T00:00:00Z",
                "GPP_BIQUOTE_PRIVATE_FORWARD_ARCHIVE":""}):
            with self.assertRaisesRegex(ValueError,
                                        "START_MORE_THAN_15_MINUTES_AHEAD"):
                observe_24h(holdout,probe=sample,utc_now=clock.now,
                            sleep=clock.sleep,emit=lambda x: None)
        self.assertEqual(clock.slept,0)

    def test_main_requires_explicit_authorization_not_a_default_service(self):
        with patch.dict(os.environ,{AUTHORIZATION_ENV:""},clear=False):
            with patch.object(sys,"argv",["biquote_24h_observer.py",
                                         "--start-utc","2026-11-16T18:00:00Z"]):
                with self.assertRaisesRegex(SystemExit,"BLOCKED"):
                    main()
        # Adding the documented flag is an explicit staging approval step
        # separate from merely pushing code to a review branch.
        self.assertEqual(AUTHORIZATION_VALUE,"APPROVED_READONLY_NO_TRADING")

if __name__=="__main__":
    unittest.main()
