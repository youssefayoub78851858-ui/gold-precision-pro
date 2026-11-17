"""Offline regressions: classify completed BiQuote review correctly."""
from __future__ import annotations
import datetime as dt
import json
import unittest
from biquote_24h_observer import QualityCounters
from test_biquote_24h_observer import sample
from biquote_24h_final_verdict import verdict

UTC=dt.timezone.utc
START=dt.datetime(2026,11,16,19,45,tzinfo=UTC)
END=START+dt.timedelta(days=1)

def fixture(samples=720,missed=0):
    counter=QualityCounters()
    for _ in range(samples):
        counter.add(sample())  # existing synthetic partial-gap case
    output=counter.report(START,END,missed_slots=missed,complete_window=True)
    return {"event":"BIQUOTE_REVIEW24H_REPORT",**output}

class FinalVerdictTests(unittest.TestCase):
    def test_closed_24h_with_synthetic_partial_h4_is_not_fake_price_mismatch(self):
        report=fixture()
        self.assertEqual(report["httpOkSamples"],720)
        self.assertEqual(report["h4DisagreementsAcrossSnapshots"],0)
        self.assertEqual(report["geometryFailureClasses"]["UNCLASSIFIED_M15_COVERAGE_GAP"],720)
        result=verdict(json.loads(json.dumps(report)))
        self.assertEqual(result["status"],"REVIEW_FINISHED_READONLY_NOT_TRADE_ADMISSIBLE")
        self.assertIn("UNCLASSIFIED_M15_H1_H4_COVERAGE_GAPS",result["reasonCodes"])
        self.assertNotIn("SOURCE_OHLC_PRICE_DISAGREEMENT",result["reasonCodes"])
        self.assertEqual(result["h4OHLCDisagreements"],0)
        self.assertEqual(result["unclassifiedCoverageSamples"],720)
        for k in ("executable","paperOrdersAllowed","tradeEligible","researchEligible",
                  "archiveEnabled","archiveActivationAllowed",
                  "crossFramePriceParityProven","profitabilityProven"):
            self.assertIs(result[k],False,k)
        self.assertFalse(any(k in result for k in (
            "minObservedSpreadPrice","maxObservedSpreadPrice",
            "bid","ask","open","high","low","close")))

    def test_actual_deployed_989699cd_legacy_report_schema(self):
        r=fixture()
        # Deployed Coordinator's previous 24h observer reports no typed
        # geometryFailureClasses or privateArchive* counters.
        for k in ("geometryFailureClasses","privateArchiveAttempts",
                  "privateArchiveSavedSnapshots","privateArchiveRejectedSnapshots",
                  "privateArchiveNewClosedBars"):
            r.pop(k)
        out=verdict(r)
        self.assertEqual(out["status"],"REVIEW_FINISHED_READONLY_NOT_TRADE_ADMISSIBLE")
        self.assertEqual(out["reportSchema"],"LEGACY_989699CD_NO_FAILURE_CLASS")
        self.assertEqual(out["h1OHLCDisagreements"],0)
        self.assertEqual(out["h4OHLCDisagreements"],0)
        self.assertIn("LEGACY_FAILED_GEOMETRY_CLASS_NOT_AVAILABLE",out["reasonCodes"])
        self.assertIn("UNCLASSIFIED_M15_H1_H4_COVERAGE_GAPS",out["reasonCodes"])
        self.assertNotIn("SOURCE_OHLC_PRICE_DISAGREEMENT",out["reasonCodes"])
        self.assertFalse(out["archiveActivationAllowed"])
        r["h4DisagreementsAcrossSnapshots"]=1
        out=verdict(r)
        self.assertIn("SOURCE_OHLC_PRICE_DISAGREEMENT",out["reasonCodes"])
        r.pop("h4DisagreementsAcrossSnapshots")
        self.assertEqual(verdict(r)["status"],"BLOCKED")
        r=fixture()
        r.pop("geometryFailureClasses")
        self.assertIn("MIXED_OR_UNKNOWN_REPORT_SCHEMA",verdict(r)["reasonCodes"])
        r=fixture()
        r["startedUTC"]="2026-11-15T19:45:00Z"
        self.assertIn("REVIEW_RUN_START_UNEXPECTED",verdict(r)["reasonCodes"])

    def test_real_finished_2026_nov17_metadata_only_no_quote_prices(self):
        # Exact counters from the finished deployed 989699cd observation;
        # not invented synthetic "live trades" or a broker entitlement.
        r=fixture()
        for k in ("geometryFailureClasses","privateArchiveAttempts",
                  "privateArchiveSavedSnapshots","privateArchiveRejectedSnapshots",
                  "privateArchiveNewClosedBars"):
            r.pop(k)
        r.update(
            samplesObserved=720,missedOrSkippedSlots=0,
            requestsAttempted=2880,httpOkSamples=691,httpFailedSamples=29,
            auditShapePassedSamples=0,marketOpenSamples=691,
            providerStaleSamples=0,crossFrameUnverifiedSamples=691,
            h1FullyCoveredComparedAcrossSnapshots=32643,
            h4FullyCoveredComparedAcrossSnapshots=6646,
            h1DisagreementsAcrossSnapshots=0,
            h4DisagreementsAcrossSnapshots=0,
            h1UnclassifiedPartialAggregatesAcrossSnapshots=0,
            h4UnclassifiedPartialAggregatesAcrossSnapshots=2051,
            maxObservedQuoteAgeSeconds=183.859,
        )
        result=verdict(r)
        self.assertEqual(result["status"],"REVIEW_FINISHED_READONLY_NOT_TRADE_ADMISSIBLE")
        self.assertEqual(result["reportSchema"],"LEGACY_989699CD_NO_FAILURE_CLASS")
        self.assertEqual(result["samplesObserved"],720)
        self.assertEqual(result["httpOkSamples"],691)
        self.assertEqual(result["httpFailedSamples"],29)
        self.assertEqual(result["totalStructuralAuditPassed"],0)
        self.assertEqual(result["h4PartialAggregatesAcrossSnapshots"],2051)
        self.assertEqual(result["totalFullyCoveredH1Compared"],32643)
        self.assertEqual(result["totalFullyCoveredH4Compared"],6646)
        self.assertEqual(result["independentQuoteAgeMaximumSeconds"],183.859)
        self.assertEqual(result["h4OHLCDisagreements"],0)
        self.assertEqual(result["h1OHLCDisagreements"],0)
        for reason in ("HTTP_OR_JSON_FAILURE_SAMPLES",
                       "INDEPENDENT_QUOTE_AGE_EXCEEDED_30_SECONDS",
                       "ZERO_FULL_SOURCE_STRUCTURAL_CHECK_PASSES",
                       "UNCLASSIFIED_M15_H1_H4_COVERAGE_GAPS",
                       "LEGACY_FAILED_GEOMETRY_CLASS_NOT_AVAILABLE"):
            self.assertIn(reason,result["reasonCodes"])
        for perm in ("archiveEnabled","archiveActivationAllowed",
                     "paperOrdersAllowed","executable","tradeEligible",
                     "researchEligible","profitabilityProven"):
            self.assertIs(result[perm],False)

    def test_actual_price_disagreement_class_is_a_separate_hard_veto(self):
        report=fixture()
        report["h4DisagreementsAcrossSnapshots"]=1
        report["geometryFailureClasses"]["UNCLASSIFIED_M15_COVERAGE_GAP"]-=1
        report["geometryFailureClasses"]["OHLC_PRICE_DISAGREEMENT"]+=1
        output=verdict(report)
        self.assertEqual(output["status"],"REVIEW_FINISHED_READONLY_NOT_TRADE_ADMISSIBLE")
        self.assertIn("SOURCE_OHLC_PRICE_DISAGREEMENT",output["reasonCodes"])
        self.assertIn("UNCLASSIFIED_M15_H1_H4_COVERAGE_GAPS",output["reasonCodes"])
        self.assertIs(output["archiveActivationAllowed"],False)

    def test_completed_window_missing_slots_not_falsely_full_coverage(self):
        report=fixture(711,9)
        result=verdict(report)
        self.assertEqual(result["samplesObserved"],711)
        self.assertEqual(result["missedSlots"],9)
        self.assertIn("MISSING_OBSERVATION_SLOTS",result["reasonCodes"])
        self.assertFalse(result["archiveActivationAllowed"])

    def test_no_final_report_or_unsafe_claim_is_blocked(self):
        for invalid in ({},
                        {"event":"BIQUOTE_REVIEW24H_SAMPLE"},
                        {**fixture(), "signal":"BUY"},
                        {**fixture(), "executable":True},
                        {**fixture(), "paperOrdersAllowed":0},
                        {**fixture(), "marketSessionIndependentlyVerified":True},
                        {**fixture(), "rawQuotesPersisted":True},
                        {**fixture(), "completed24hWindow":False},
                        {**fixture(), "observedAsOfUTC":START.isoformat().replace("+00:00","Z")},
                        {**fixture(), "requestsAttempted":2881},
                        {**fixture(), "samplesObserved":719},
                        {**fixture(), "privateArchiveSavedSnapshots":1}):
            out=verdict(invalid)
            self.assertEqual(out["status"],"BLOCKED")
            self.assertEqual(out["signal"],"WAIT")
            self.assertFalse(out["archiveActivationAllowed"])

    def test_aggregate_totals_must_be_self_consistent(self):
        r=fixture()
        for field,bad in (
            ("geometryFailureClasses",{"OHLC_PRICE_DISAGREEMENT":1}),
            ("httpFailedSamples",20),
            ("h1DisagreementsAcrossSnapshots",2000000),
            ("privateArchiveAttempts",True),
            ("providerStaleSamples",721),
            ("startedUTC","2026-11-16T19:45:00+01:00"),
            ("marketOpenSamples",721)
        ):
            trial={**r,field:bad}
            self.assertEqual(verdict(trial)["status"],"BLOCKED",field)

if __name__=="__main__":
    unittest.main()
