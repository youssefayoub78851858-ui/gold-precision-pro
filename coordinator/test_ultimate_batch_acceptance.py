"""Offline end-to-end acceptance of all four unfinished stages in one batch."""
import datetime as dt
import json
import pathlib
import socket
import tempfile
import unittest
from unittest.mock import patch

from ultimate_batch_acceptance import review_batch
from biquote_private_forward_vault import ingest
from test_biquote_private_forward_vault import sample, iso
from test_biquote_24h_final_verdict import fixture
from test_biquote_forward_shadow_review import AFTER, EARLY

class FourStageBatchAcceptance(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix="gold-batch-offline-")
        self.folder=pathlib.Path(self.temporary.name)/"private"
    def tearDown(self):
        self.temporary.cleanup()

    def assert_blocked(self,report):
        self.assertEqual(report["mode"],"GOLD_PRECISION_FOUR_STAGE_BATCH_READONLY_V1")
        self.assertEqual(report["signal"],"WAIT")
        for flag in ("executable","paperOrdersAllowed","liveOrdersAllowed",
                     "tradeEligible","signalReady","researchEligible",
                     "brokerFeedRightsIndependentlyVerified",
                     "brokerSessionCalendarIndependentlyVerified",
                     "historicalBidAskExecutionVerified",
                     "gcOrderFlowIndependentlyVerified","macroFeedsIndependentlyVerified",
                     "outOfSampleNetExpectancyProven","rawMarketPricesExposed"):
            self.assertIs(report[flag],False,flag)
        for field in ("providerRequestsMade","brokerOrdersSent",
                      "archiveWritesMade","paperLedgerWritesMade"):
            self.assertEqual(report[field],0,field)
        self.assertEqual(report["stages"]["analysis"]["approvedDirection"],"NONE")
        for key in ("entry","stopLoss","takeProfit","winProbability"):
            self.assertIsNone(report["stages"]["analysis"][key],key)
        self.assertEqual(report["stages"]["paper"]["status"],"BLOCKED")
        self.assertFalse(report["stages"]["paper"]["paperOrdersAllowed"])
        self.assertFalse(report["stages"]["paper"]["paperLedgerOpened"])
        self.assertEqual(report["stages"]["paper"]["sampleTradesCreated"],0)
        self.assertFalse(report["stages"]["paper"]["forwardNetPerformanceEstablished"])
        self.assertEqual(report["stages"]["context"]["status"],
                         "INDEPENDENT_SOURCE_CONFIRMATIONS_REQUIRED")

    def test_empty_source_and_vault_fail_closed_no_network(self):
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            out=review_batch(self.folder)
        self.assert_blocked(out)
        self.assertEqual(out["stages"]["data"]["status"],"SOURCE_NOT_QUALIFIED")
        self.assertFalse(out["stages"]["data"]["reviewWindowCompleted"])
        self.assertEqual(out["stages"]["archive"]["status"],"NO_FORWARD_CAPTURE")
        self.assertEqual(out["stages"]["archive"]["closedCounts"]["H4"],0)
        self.assertEqual(out["stages"]["analysis"]["technicalWatch"],"NONE")
        self.assertIn("NO_POST_HOLDOUT_CAPTURE",out["reasonCodes"])
        self.assertFalse(self.folder.exists(),"Read-only must not make even an empty vault")

    def test_actual_720_slot_failure_stays_wait_and_labels_codes(self):
        report=fixture()
        for key in ("geometryFailureClasses","privateArchiveAttempts",
                    "privateArchiveSavedSnapshots","privateArchiveRejectedSnapshots",
                    "privateArchiveNewClosedBars"):
            report.pop(key)
        report.update(httpOkSamples=691,httpFailedSamples=29,
                      auditShapePassedSamples=0,marketOpenSamples=691,
                      crossFrameUnverifiedSamples=691,providerStaleSamples=0,
                      h1FullyCoveredComparedAcrossSnapshots=32643,
                      h4FullyCoveredComparedAcrossSnapshots=6646,
                      h1UnclassifiedPartialAggregatesAcrossSnapshots=0,
                      h4UnclassifiedPartialAggregatesAcrossSnapshots=2051,
                      h1DisagreementsAcrossSnapshots=0,
                      h4DisagreementsAcrossSnapshots=0,
                      maxObservedQuoteAgeSeconds=183.859)
        out=review_batch(self.folder,final_report=report)
        self.assert_blocked(out)
        quality=out["stages"]["data"]
        self.assertTrue(quality["reviewWindowCompleted"])
        self.assertEqual(quality["fullSampleCount"],720)
        self.assertEqual(quality["httpOkSamples"],691)
        self.assertEqual(quality["httpFailedSamples"],29)
        self.assertEqual(quality["fullStructuralPasses"],0)
        self.assertEqual(quality["maximumSampledQuoteAgeSeconds"],183.859)
        self.assertIn("HTTP_OR_JSON_FAILURE_SAMPLES",quality["blockers"])
        self.assertIn("ZERO_FULL_SOURCE_STRUCTURAL_CHECK_PASSES",quality["blockers"])
        self.assertFalse(quality["sourceRightsVerified"])
        self.assertFalse(quality["independentBrokerCalendarVerified"])

    def test_one_hour_private_capture_still_cannot_warm_h4(self):
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            ingest(self.folder,sample(EARLY),received_utc=iso(EARLY))
            out=review_batch(self.folder,now_utc=EARLY,shadow_runner=lambda _:
                             self.fail("Never invoke V3 with incomplete history"))
        self.assert_blocked(out)
        self.assertEqual(out["stages"]["archive"]["status"],
                         "FORWARD_CAPTURE_PRESENT_UNVERIFIED")
        self.assertLess(out["stages"]["archive"]["consecutiveClosedCounts"]["H4"],21)
        self.assertEqual(out["stages"]["analysis"]["status"],
                         "WAIT_CLOSED_DATA_OR_CONTEXT")
        self.assertIn("ONE_DAY_FORWARD_CAPTURE_CANNOT_WARM_UP_H4",
                      out["stages"]["analysis"]["blockers"])

    def test_complete_synthetic_warmup_can_only_be_technical_observation(self):
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            ingest(self.folder,sample(AFTER),received_utc=iso(AFTER))
            out=review_batch(self.folder,now_utc=AFTER)
        self.assert_blocked(out)
        self.assertEqual(out["stages"]["archive"]["status"],
                         "FORWARD_CAPTURE_PRESENT_UNVERIFIED")
        self.assertGreaterEqual(
            out["stages"]["archive"]["consecutiveClosedCounts"]["H4"],21)
        self.assertEqual(out["stages"]["analysis"]["status"],
                         "FROZEN_V3_TECHNICAL_OBSERVATION_ONLY")
        self.assertIn(out["stages"]["analysis"]["technicalWatch"],
                      ("BUY","SELL","NONE"))
        self.assertEqual(out["stages"]["paper"]["sampleTradesCreated"],0)
        self.assertFalse(any(x.suffix in (".sqlite",".sqlite3",".db")
                             for x in self.folder.parent.rglob("*")))
        encoded=json.dumps(out)
        for leak in ('"bid"','"ask"','"open"','"high"','"low"','"close"',
                     '"spread"','"quoteObservations"','"hypotheticalSyntheticPlan"'):
            self.assertNotIn(leak,encoded)
        self.assertNotIn("3900",encoded)

    def test_stale_archive_never_leaks_a_buy_or_sell(self):
        ingest(self.folder,sample(AFTER),received_utc=iso(AFTER))
        out=review_batch(self.folder,now_utc=AFTER+dt.timedelta(hours=6),
                         shadow_runner=lambda _:self.fail("Stale cannot reach V3"))
        self.assert_blocked(out)
        self.assertEqual(out["stages"]["analysis"]["technicalWatch"],"NONE")
        self.assertIn("ARCHIVED_CAPTURE_STALE_OR_FUTURE_VS_NOW",
                      out["stages"]["analysis"]["blockers"])
    def test_corrupt_archive_and_forged_source_fail_closed(self):
        ingest(self.folder,sample(AFTER),received_utc=iso(AFTER))
        target=self.folder/"biquote-forward-private-v1.json"
        payload=json.loads(target.read_text())
        payload["payload"]["closed"]["H4"][-1]["high"]+=99
        target.write_text(json.dumps(payload))
        r=review_batch(self.folder,final_report={"signal":"BUY"})
        self.assert_blocked(r)
        self.assertEqual(r["stages"]["archive"]["status"],"PRIVATE_VAULT_NOT_READABLE")
        self.assertEqual(r["stages"]["analysis"]["technicalWatch"],"NONE")
        self.assertIn("REPORT_NOT_VERIFIED",r["stages"]["data"]["blockers"])
        forged=fixture()
        forged["signal"]="BUY"
        rejected=review_batch(self.folder,final_report=forged)
        self.assert_blocked(rejected)
        self.assertIn("UNSAFE_OR_INCOMPLETE_FINAL_REPORT",
                      rejected["stages"]["data"]["blockers"])

if __name__=="__main__":
    unittest.main()
