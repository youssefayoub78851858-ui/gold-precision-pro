"""Offline end-to-end acceptance of all four unfinished stages in one batch."""
import datetime as dt
import json
import pathlib
import socket
import tempfile
import unittest
from unittest.mock import patch

from ultimate_batch_acceptance import review_batch
from biquote_private_forward_vault import ingest, inspect_metadata, load_vault
from biquote_forward_shadow_review import shadow_review
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
        checklist=report["completionAudit"]
        self.assertEqual(checklist["mode"],
                         "GOLD_PRECISION_ONE_BATCH_COMPLETION_GATE_V1")
        self.assertEqual(checklist["status"],
                         "WAIT_EXTERNAL_EVIDENCE_AND_FORWARD_DATA")
        self.assertEqual(checklist["signal"],"WAIT")
        for field in ("executable","paperOrdersAllowed","liveOrdersAllowed",
                      "independentMarketRightsVerified","brokerSessionDSTVerified",
                      "GCOrderFlowLicensed","independentMacroFeedsVerified",
                      "executionCostsVerified","outOfSampleNetExpectancyVerified"):
            self.assertIs(checklist[field],False,field)
        self.assertEqual(checklist["providerRequestsMade"],0)
        self.assertEqual(checklist["brokerOrdersSent"],0)
        self.assertEqual(
            checklist["archiveIntegrityObserved"],
            report["stages"]["archive"]["status"]==
            "FORWARD_CAPTURE_PRESENT_UNVERIFIED")
        self.assertEqual(
            checklist["missingStrictClosedBarsUntil21"],
            {tf:max(0,21-report["stages"]["archive"]["consecutiveClosedCounts"][tf])
             for tf in ("M15","H1","H4")})
        self.assertIn("UNDERLYING_BROKER_MARKET_DATA_RIGHTS_UNCONFIRMED",
                      checklist["remainingBlockerCodes"])
        self.assertIn("BROKER_XAUUSD_SESSION_DST_UNCONFIRMED",
                      checklist["remainingBlockerCodes"])
        self.assertIn("GC_TRADES_MBO_MBP10_LICENSING_NOT_ESTABLISHED",
                      checklist["remainingBlockerCodes"])
        self.assertIn("EXECUTION_BID_ASK_SPREAD_SLIPPAGE_FEES_UNVERIFIED",
                      checklist["remainingBlockerCodes"])
        self.assertIn("OUT_OF_SAMPLE_NET_EXPECTANCY_NOT_PROVEN",
                      checklist["remainingBlockerCodes"])
        self.assertFalse(report["stages"]["archive"]["automaticQuoteDeletionAllowed"])
        archive=report["stages"]["archive"]
        self.assertFalse(archive["stage2SourceVerified"])
        self.assertFalse(archive["stage2SessionCalendarVerified"])
        self.assertFalse(archive["stage2EligibleForPaper"])
        analysis=report["stages"]["analysis"]
        stage3=analysis["stage3"]
        self.assertEqual(stage3["signal"],"WAIT")
        self.assertFalse(stage3["brokerRightsVerified"])
        self.assertFalse(stage3["brokerSessionCalendarVerified"])
        self.assertFalse(stage3["independentMacroOrderFlowVerified"])
        self.assertFalse(stage3["paperOrdersAllowed"])
        self.assertFalse(stage3["liveOrdersAllowed"])
        self.assertEqual(stage3["minimumContiguousClosedEachFrame"],21)
        self.assertEqual(stage3["framesWithWarmup"],
                         sum(archive["consecutiveClosedCounts"][tf]>=21
                             for tf in ("M15","H1","H4")))
        self.assertEqual(stage3["h4ContiguousClosed"],archive["consecutiveClosedCounts"]["H4"])
        self.assertEqual(stage3["h4RemainingUntil21"],
                         max(0,21-stage3["h4ContiguousClosed"]))
        self.assertEqual(stage3["frozenV3Observed"],
                         analysis["status"]=="FROZEN_V3_TECHNICAL_OBSERVATION_ONLY")
        self.assertEqual(stage3["crossFrameParityObserved"],stage3["frozenV3Observed"])
        self.assertEqual(set(archive["stage2Frames"]),{"M15","H1","H4"})
        for tf in ("M15","H1","H4"):
            frame=archive["stage2Frames"][tf]
            self.assertEqual(frame["persistedClosed"],archive["closedCounts"][tf])
            self.assertEqual(frame["contiguousClosed"],archive["consecutiveClosedCounts"][tf])
            self.assertEqual(frame["remainingUntil21"],max(0,21-frame["contiguousClosed"]))
            self.assertGreaterEqual(frame["unclassifiedGapPairs"],0)
            self.assertGreaterEqual(frame["unclassifiedMissingSlots"],0)
        self.assertIn(report["stages"]["archive"]["capacityStatus"],
                      ("CAPACITY_HEADROOM","CAPACITY_WARNING","CAPACITY_LIMIT_REACHED",
                       "CAPACITY_METADATA_UNAVAILABLE"))

    def test_empty_source_and_vault_fail_closed_no_network(self):
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            out=review_batch(self.folder)
        self.assert_blocked(out)
        self.assertEqual(out["stages"]["data"]["status"],"SOURCE_NOT_QUALIFIED")
        self.assertFalse(out["stages"]["data"]["reviewWindowCompleted"])
        self.assertEqual(out["stages"]["archive"]["status"],"NO_FORWARD_CAPTURE")
        self.assertEqual(out["stages"]["archive"]["stage2Status"],"WAIT_NO_FORWARD_CLOSED_BARS")
        self.assertEqual(out["stages"]["archive"]["stage2Frames"]["H4"]["remainingUntil21"],21)
        self.assertEqual(out["stages"]["archive"]["closedCounts"]["H4"],0)
        self.assertEqual(out["stages"]["analysis"]["stage3"]["status"],
                         "WAIT_CLOSED_BAR_WARMUP")
        self.assertEqual(out["stages"]["archive"]["capacityStatus"],"CAPACITY_HEADROOM")
        self.assertEqual(out["stages"]["archive"]["quoteSamplesRemaining"],10000)
        self.assertFalse(out["stages"]["archive"]["archiveCapacityExhausted"])
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
        self.assertEqual(out["stages"]["archive"]["stage2Status"],
                         "WAIT_CONTIGUOUS_CLOSED_BAR_WARMUP")
        self.assertGreater(out["stages"]["archive"]["stage2Frames"]["H4"]["remainingUntil21"],0)
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
        self.assertEqual(out["stages"]["archive"]["stage2Status"],
                         "WAIT_INDEPENDENT_SOURCE_RIGHTS_AND_CALENDAR")
        self.assertEqual(out["stages"]["archive"]["stage2Frames"]["H4"]["remainingUntil21"],0)
        self.assertEqual(out["stages"]["archive"]["capacityStatus"],"CAPACITY_HEADROOM")
        self.assertEqual(out["stages"]["archive"]["quoteSamplesRemaining"],9999)
        self.assertEqual(out["stages"]["analysis"]["status"],
                         "FROZEN_V3_TECHNICAL_OBSERVATION_ONLY")
        self.assertEqual(out["stages"]["analysis"]["stage3"]["status"],
                         "WAIT_INDEPENDENT_FEEDS_AND_RIGHTS")
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

    def test_protected_monitor_reuses_once_computed_status_safely(self):
        ingest(self.folder,sample(AFTER),received_utc=iso(AFTER))
        meta=inspect_metadata(self.folder)
        shadow=shadow_review(self.folder,now_utc=AFTER)
        with patch("ultimate_batch_acceptance.load_vault",
                   side_effect=AssertionError("NO_EXTRA_VAULT_READ")),patch(
             "ultimate_batch_acceptance.shadow_review",
                   side_effect=AssertionError("NO_DUPLICATE_V3_RUN")):
            out=review_batch(self.folder,now_utc=AFTER,
                             vault_metadata=meta,shadow_status=shadow)
        self.assert_blocked(out)
        self.assertEqual(out["stages"]["analysis"]["status"],
                         "FROZEN_V3_TECHNICAL_OBSERVATION_ONLY")
        forged={**meta,"tradeSignalReady":True}
        rejected=review_batch(self.folder,now_utc=AFTER,
                              vault_metadata=forged,shadow_status=shadow)
        self.assert_blocked(rejected)
        self.assertEqual(rejected["stages"]["archive"]["status"],
                         "PRIVATE_VAULT_NOT_READABLE")
        self.assertEqual(rejected["stages"]["analysis"]["technicalWatch"],"NONE")
        missing=review_batch(self.folder,now_utc=AFTER,
                             vault_metadata=meta)
        self.assert_blocked(missing)
        self.assertEqual(missing["stages"]["analysis"]["technicalWatch"],"NONE")

    def test_forged_precomputed_v3_parity_never_evaluates(self):
        ingest(self.folder,sample(AFTER),received_utc=iso(AFTER))
        m=inspect_metadata(self.folder)
        shadow=shadow_review(self.folder,now_utc=AFTER)
        for fake in (
            {**shadow,"comparedCrossFrames":{"H1":{"fullyCoveredCompared":0,
                "fullyCoveredDisagreed":0},"H4":{"fullyCoveredCompared":1,
                "fullyCoveredDisagreed":0}}},
            {**shadow,"comparedCrossFrames":{"H1":{"fullyCoveredCompared":1,
                "fullyCoveredDisagreed":1},"H4":{"fullyCoveredCompared":1,
                "fullyCoveredDisagreed":0}}},
        ):
            r=review_batch(self.folder,vault_metadata=m,shadow_status=fake,now_utc=AFTER)
            self.assert_blocked(r)
            self.assertEqual(r["stages"]["archive"]["status"],"PRIVATE_VAULT_NOT_READABLE")
            self.assertEqual(r["stages"]["analysis"]["technicalWatch"],"NONE")
        self.assertFalse(self.folder.joinpath("fake-approval").exists())

    def test_checklist_distinguishes_empty_warmup_and_broker_blockers(self):
        no_data=review_batch(self.folder)
        self.assert_blocked(no_data)
        codes=no_data["completionAudit"]["remainingBlockerCodes"]
        self.assertIn("NO_POST_HOLDOUT_CLOSED_CANDLES",codes)
        self.assertIn("STRICT_H4_CLOSED_WARMUP_INCOMPLETE",codes)
        ingest(self.folder,sample(AFTER),received_utc=iso(AFTER))
        full=review_batch(self.folder,now_utc=AFTER)
        self.assert_blocked(full)
        codes=full["completionAudit"]["remainingBlockerCodes"]
        self.assertNotIn("NO_POST_HOLDOUT_CLOSED_CANDLES",codes)
        self.assertNotIn("STRICT_H4_CLOSED_WARMUP_INCOMPLETE",codes)
        self.assertEqual(full["completionAudit"]["missingStrictClosedBarsUntil21"]["H4"],0)
        self.assertIn("BROKER_XAUUSD_SESSION_DST_UNCONFIRMED",codes)
        self.assertIn("OUT_OF_SAMPLE_NET_EXPECTANCY_NOT_PROVEN",codes)
        self.assertEqual(full["stages"]["paper"]["sampleTradesCreated"],0)

    def test_standalone_four_stages_read_only_one_verified_vault(self):
        ingest(self.folder,sample(AFTER),received_utc=iso(AFTER))
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            with patch("ultimate_batch_acceptance.load_vault",
                       wraps=load_vault) as one_read:
                report=review_batch(self.folder,now_utc=AFTER)
        self.assertEqual(one_read.call_count,1)
        self.assert_blocked(report)
        self.assertEqual(report["stages"]["analysis"]["status"],
                         "FROZEN_V3_TECHNICAL_OBSERVATION_ONLY")
        self.assertEqual(report["stages"]["archive"]["closedCounts"]["H4"],
                         len(load_vault(self.folder)["closed"]["H4"]))
        self.assertFalse(report["stages"]["paper"]["paperOrdersAllowed"])

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
        self.assertEqual(r["stages"]["analysis"]["stage3"]["status"],
                         "WAIT_ARCHIVE_UNAVAILABLE")
        self.assertEqual(r["stages"]["archive"]["stage2Status"],"WAIT_PRIVATE_ARCHIVE_UNAVAILABLE")
        self.assertEqual(r["stages"]["archive"]["capacityStatus"],"CAPACITY_METADATA_UNAVAILABLE")
        self.assertTrue(r["stages"]["archive"]["archiveCapacityExhausted"])
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
