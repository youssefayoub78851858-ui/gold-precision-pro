"""No-network tests for the private archive -> frozen V3 shadow pipeline."""
import datetime as dt
import json
import pathlib
import socket
import tempfile
import unittest
from unittest.mock import patch

from biquote_forward_shadow_review import shadow_review, tail_contiguous, overlaps_match, BASE
from biquote_private_forward_vault import ingest, load_vault
from test_biquote_private_forward_vault import sample, iso

UTC=dt.timezone.utc
AFTER=dt.datetime(2026,11,23,3,5,10,tzinfo=UTC)
EARLY=dt.datetime(2026,11,18,0,35,10,tzinfo=UTC)


class ForwardShadowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="gpp-forward-shadow-")
        self.folder=pathlib.Path(self.tmp.name)/"private-vault"
    def tearDown(self):
        self.tmp.cleanup()
    def test_empty_and_one_hour_capture_remain_wait_without_engine(self):
        def impossible(_):
            self.fail("Never invoke V3 without 21 contiguous H4 bars")
        empty=shadow_review(self.folder,runner=impossible)
        self.assertEqual(empty["technicalWatch"],"NONE")
        self.assertIn("NO_POST_HOLDOUT_CAPTURE",empty["reasonCodes"])
        self.assertEqual(empty["frames"]["H4"]["contiguousClosed"],0)
        # Test feed appears only after fixed forward start.
        with patch.object(socket,"socket",side_effect=AssertionError("NO_EXTERNAL_REQUESTS")):
            ingest(self.folder,sample(EARLY),received_utc=iso(EARLY))
            short=shadow_review(self.folder,runner=impossible,now_utc=EARLY)
        self.assertFalse(short["signalReady"])
        self.assertEqual(short["signal"],"WAIT")
        self.assertIn("INSUFFICIENT_CONTIGUOUS_CLOSED_H4_H1_M15",short["reasonCodes"])
        self.assertIn("ONE_DAY_FORWARD_CAPTURE_CANNOT_WARM_UP_H4",short["reasonCodes"])
        self.assertEqual(short["researchWarmup"]["minimumPerfectH4Hours"],84)
        self.assertFalse(short["researchWarmup"]["single24HourWindowEnoughForH4"])
        self.assertTrue(short["researchWarmup"]["additionalExplicitlyApprovedCaptureRequired"])
        self.assertFalse(short["researchWarmup"]["paperTradingAdmissible"])
        self.assertEqual(short["frames"]["H4"]["additionalContiguousNeeded"],
                         21-short["frames"]["H4"]["contiguousClosed"])
        self.assertFalse(short["paperOrdersAllowed"])
        self.assertIsNone(short["entry"])
        self.assertIsNone(short["stopLoss"])
        self.assertIsNone(short["takeProfit"])

    def test_complete_contiguous_forward_history_runs_frozen_v3_without_feeds(self):
        with patch.object(socket,"socket",side_effect=AssertionError("NO_EXTERNAL_REQUESTS")):
            saved=ingest(self.folder,sample(AFTER),received_utc=iso(AFTER))
            self.assertEqual(saved["status"],"PRIVATE_FORWARD_CAPTURE_SAVED")
            report=shadow_review(self.folder,now_utc=AFTER)
        self.assertEqual(report["signal"],"WAIT")
        self.assertFalse(report["executable"])
        self.assertFalse(report["paperOrdersAllowed"])
        self.assertFalse(report["profitabilityProven"])
        self.assertFalse(report["brokerPricesExposed"])
        self.assertEqual(report["approvedDirection"],"NONE")
        self.assertIn(report["technicalWatch"],("BUY","SELL","NONE"))
        self.assertEqual(report["engineReview"],
                         "FROZEN_V3_COMPLETED_WITH_REAL_OBSERVED_CLOSED_BARS")
        self.assertGreaterEqual(report["comparedCrossFrames"]["H4"]["fullyCoveredCompared"],1)
        self.assertEqual(report["comparedCrossFrames"]["H1"]["fullyCoveredDisagreed"],0)
        self.assertEqual(report["comparedCrossFrames"]["H4"]["fullyCoveredDisagreed"],0)
        self.assertGreaterEqual(report["frames"]["H4"]["contiguousClosed"],21)
        self.assertEqual(report["frames"]["H4"]["additionalContiguousNeeded"],0)
        self.assertIn("NO_REAL_SIGNAL_WITHOUT_INDEPENDENT_CONTEXT_AND_RISK",
                      report["reasonCodes"])
        self.assertIn("GC_DXY_YIELDS_CALENDAR_NEWS_AND_LICENSED_ORDERFLOW_UNVERIFIED",
                      report["reasonCodes"])
        # Sanitize from external / public data; even synthetic price 3900
        # must not appear in a shadow result.
        serialized=json.dumps(report)
        for key in ('"bid"','"ask"','"open"','"close"',
                    '"spread"','"privateChart"','"quoteObservations"'):
            self.assertNotIn(key,serialized)
        self.assertNotIn("3900",serialized)
        self.assertEqual(len(load_vault(self.folder)["quoteObservations"]),1)

    def test_gaps_reset_shadow_warmup_and_never_bridge_unknown_sessions(self):
        history=sample(AFTER)
        # Drop one H4 candle close to the end; do not invent session hours.
        history["frames"]["H4"]["bars"].pop(7)
        with patch.object(socket,"socket",side_effect=AssertionError("NO_EXTERNAL_REQUESTS")):
            saved=ingest(self.folder,history,received_utc=iso(AFTER))
            self.assertEqual(saved["status"],"PRIVATE_FORWARD_CAPTURE_SAVED")
            report=shadow_review(self.folder,runner=lambda _:self.fail("gap crossed"),now_utc=AFTER)
        self.assertEqual(report["signal"],"WAIT")
        self.assertEqual(report["technicalWatch"],"NONE")
        self.assertIn("INSUFFICIENT_CONTIGUOUS_CLOSED_H4_H1_M15",report["reasonCodes"])
        self.assertGreater(report["frames"]["H4"]["unclassifiedGapPairs"],0)
        self.assertLess(report["frames"]["H4"]["contiguousClosed"],21)

    def test_forged_engine_buy_or_synthetic_plan_never_promotes_trade(self):
        ingest(self.folder,sample(AFTER),received_utc=iso(AFTER))
        standard={"signal":"WAIT","executable":False,"paperOrdersAllowed":False,
                  "liveOrdersAllowed":False,"researchEligible":False,
                  "hypotheticalSyntheticPlan":None,
                  "dataOrigin":"BIQUOTE_ARCHIVED_UNVERIFIED_NO_PAPER",
                  "stages":{"data":{"status":"GEOMETRY_ONLY"},
                            "analysis":{"status":"FROZEN_ENGINE_EVALUATED",
                                        "technicalCandidate":"SELL"}}}
        received=[]
        def fake(packet):
            received.append(packet)
            return json.dumps(standard)
        out=shadow_review(self.folder,runner=fake,now_utc=AFTER)
        self.assertEqual(out["technicalWatch"],"SELL")
        self.assertEqual(out["approvedDirection"],"NONE")
        self.assertIsNone(out["entry"])
        self.assertEqual(received[0]["snapshot"]["feeds"],{})
        self.assertTrue(received[0]["snapshot"]["risk"]["killSwitch"])
        self.assertEqual(received[0]["dataOrigin"],"BIQUOTE_ARCHIVED_UNVERIFIED_NO_PAPER")
        for change in ({"signal":"SELL"}, {"executable":True},
                       {"paperOrdersAllowed":True},
                       {"hypotheticalSyntheticPlan":{"direction":"SELL"}},
                       {"dataOrigin":"SYNTHETIC_TEST_ONLY"}):
            bad={**standard,**change}
            result=shadow_review(self.folder,runner=lambda _:json.dumps(bad),now_utc=AFTER)
            self.assertEqual(result["signal"],"WAIT")
            self.assertEqual(result["technicalWatch"],"NONE")
            self.assertIn("SHADOW_OUTPUT_CONTRACT_REJECTED",result["reasonCodes"])

    def test_full_overlap_catches_intraday_price_disagreement(self):
        ingest(self.folder,sample(AFTER),received_utc=iso(AFTER))
        archive=load_vault(self.folder)
        from biquote_forward_shadow_review import WIDTH
        frames={tf:tail_contiguous(archive["closed"][tf],WIDTH[tf])
                for tf in ("M15","H1","H4")}
        healthy=overlaps_match(frames)
        self.assertGreater(healthy["H4"]["fullyCoveredCompared"],0)
        self.assertEqual(healthy["H4"]["fullyCoveredDisagreed"],0)
        changed=frames["H4"][-2]
        changed["high"]+=8
        faulty=overlaps_match(frames)
        self.assertGreater(faulty["H4"]["fullyCoveredDisagreed"],0)
        self.assertEqual(faulty["H1"]["fullyCoveredDisagreed"],0)

    def test_tampered_vault_fails_and_no_secret_or_prices_printed(self):
        ingest(self.folder,sample(AFTER),received_utc=iso(AFTER))
        file=self.folder/"biquote-forward-private-v1.json"
        payload=json.loads(file.read_text())
        payload["payload"]["closed"]["H4"][-1]["high"]+=12
        file.write_text(json.dumps(payload))
        from biquote_forward_shadow_review import main
        # Direct load must fail. The CLI catches errors without disclosing paths.
        with self.assertRaisesRegex(ValueError,"VAULT_TAMPER"):
            shadow_review(self.folder)
        self.assertEqual(BASE["signal"],"WAIT")

    def test_no_stale_or_future_archive_is_presented_as_current_signal(self):
        ingest(self.folder,sample(AFTER),received_utc=iso(AFTER))
        def cannot(_):
            self.fail("Stale or future archive must never be evaluated")
        for clock in (AFTER-dt.timedelta(seconds=1),
                      AFTER+dt.timedelta(minutes=5,seconds=1)):
            report=shadow_review(self.folder,runner=cannot,now_utc=clock)
            self.assertEqual(report["signal"],"WAIT")
            self.assertEqual(report["technicalWatch"],"NONE")
            self.assertIn("ARCHIVED_CAPTURE_STALE_OR_FUTURE_VS_NOW",
                          report["reasonCodes"])
            self.assertFalse(report["paperOrdersAllowed"])
        live=shadow_review(self.folder,now_utc=AFTER+dt.timedelta(minutes=4))
        self.assertIn(live["technicalWatch"],("BUY","SELL","NONE"))
        self.assertEqual(live["approvedDirection"],"NONE")

    def test_tail_contiguous_uses_real_post_gap_only(self):
        rows=[{"openTime":f"2026-11-18T{h:02d}:00:00Z",
               "open":100,"high":101,"low":99,"close":100}
              for h in (0,1,2,6,7,8)]
        tail=tail_contiguous(rows,3600)
        self.assertEqual(len(tail),3)
        self.assertEqual(tail[0]["datetime"],"2026-11-18T06:00:00Z")


if __name__=="__main__":
    unittest.main()
