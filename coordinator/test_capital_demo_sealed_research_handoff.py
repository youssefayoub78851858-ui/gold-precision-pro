"""Synthetic sealed Capital BID/ASK -> existing source gate integration test.

A successful test demonstrates compatibility and quarantine, NOT a source
license, verified real prices, data entitlement or trade profitability.
"""
import copy
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from capital_demo_historical_batch_plan import plan_demo_closed_history
from capital_demo_private_page_store import commit_fixture_page
from capital_demo_sealed_research_handoff import inspect_sealed_to_research_gate
from test_capital_demo_synthetic_archive_mtf_replay import (
    make_pages, RESOLUTIONS, EPIC, START, END, ASOF,
)

class SealedResearchHandoffTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=pathlib.Path(temp.name)
        os.chmod(self.root, 0o700)
        self.plan=plan_demo_closed_history(EPIC, START, END, ASOF)
        self.assertEqual(self.plan["status"],"INERT_PLAN_ONLY")

    def save(self, pages=None, receipt="2026-11-20T12:11:00Z"):
        frames=make_pages() if pages is None else pages
        for frame in ("M15","H1","H4"):
            chunk=self.plan["requests"][frame][0]
            result=commit_fixture_page(
                chunk,
                {"epic":EPIC,"resolution":RESOLUTIONS[frame],
                 "prices":frames[frame]},
                self.root,receipt,explicit_synthetic_rehearsal=True
            )
            self.assertTrue(result["committed"])

    def check_wait(self,report):
        self.assertEqual(report["signal"],"WAIT")
        self.assertFalse(report["executable"])
        self.assertFalse(report["paperOrdersAllowed"])
        self.assertFalse(report["liveOrdersAllowed"])
        self.assertFalse(report["resultEligibleForResearch"])
        self.assertFalse(report["readyForPaperSignals"])
        self.assertFalse(report["enginesInvoked"])
        self.assertFalse(report["paperRecorderInvoked"])
        self.assertFalse(report["sourceRightsIndependentlyVerified"])
        self.assertFalse(report["independentBrokerSessionVerified"])
        self.assertFalse(report["genuineProviderQuotes"])
        self.assertFalse(report["actualNetworkEgressEnforced"])
        self.assertFalse(report["independentOffsiteBackupVerified"])
        self.assertTrue(report["realSourceIntakeBlocked"])
        self.assertEqual(report["providerRequestsMade"],0)
        self.assertEqual(report["brokerOrdersSent"],0)
        output=json.dumps(report)
        for secret in ("4000", EPIC, "C"*32, "S"*32,
                       str(self.root), "bid", "ask"):
            self.assertNotIn(secret,output)

    def test_real_pipeline_entrypoint_exercises_quarantine_and_no_engines(self):
        self.save()
        with patch("xauusd_research_pipeline.subprocess.run",
                   side_effect=AssertionError("NO_ENGINE_SPAWN")):
            result=inspect_sealed_to_research_gate(self.plan,self.root,ASOF)
        self.check_wait(result)
        self.assertEqual(result["status"],"SEALED_SYNTHETIC_HANDOFF_QUARANTINED_ONLY")
        self.assertTrue(result["sealedPagesValidated"])
        self.assertTrue(result["arrivalCutoffChecked"])
        self.assertTrue(result["bidAskParityLocallyMatched"])
        self.assertTrue(result["syntheticIntakeShapeChecked"])
        self.assertTrue(result["syntheticPacketHadFullClosedFrameGeometry"])
        self.assertEqual(result["syntheticClosedCounts"],
                         {"M15":16,"H1":4,"H4":1})
        self.assertEqual(result,inspect_sealed_to_research_gate(
            self.plan,self.root,ASOF))

    def test_stale_original_receipt_is_never_reset_to_decision(self):
        self.save(receipt="2026-11-20T12:05:00Z")
        report=inspect_sealed_to_research_gate(self.plan,self.root,ASOF)
        self.check_wait(report)
        self.assertEqual(report["status"],"SEALED_SYNTHETIC_HANDOFF_QUARANTINED_ONLY")
        self.assertFalse(report["syntheticPacketHadFullClosedFrameGeometry"])

    def test_missing_constituent_rejects_before_engine(self):
        data=make_pages()
        data["M15"].pop(7)
        self.save(pages=data)
        with patch("xauusd_research_pipeline.subprocess.run",
                   side_effect=AssertionError("NO_ENGINE_SPAWN")):
            result=inspect_sealed_to_research_gate(self.plan,self.root,ASOF)
        self.check_wait(result)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["reason"],"SEALED_BID_ASK_MTF_REPLAY_NOT_VERIFIED")

    def test_local_h1_parity_mismatch_blocks(self):
        data=make_pages()
        data["H1"][2]["highPrice"]["bid"]+=4
        data["H1"][2]["highPrice"]["ask"]+=4
        self.save(pages=data)
        report=inspect_sealed_to_research_gate(self.plan,self.root,ASOF)
        self.check_wait(report)
        self.assertEqual(report["status"],"BLOCKED")

    def test_late_local_receipt_cannot_represent_prior_decision(self):
        self.save(receipt="2026-11-20T12:13:00Z")
        report=inspect_sealed_to_research_gate(self.plan,self.root,ASOF)
        self.check_wait(report)
        self.assertEqual(report["reason"],
                         "SYNTHETIC_PAGE_ARRIVAL_CUTOFF_NOT_VERIFIED")

    def test_missing_or_modified_sealed_private_file_blocks(self):
        self.save()
        file=next(self.root.glob("capital-synthetic-page-*.json"))
        original=file.read_bytes()
        file.write_bytes(original.replace(b"4000",b"3000",1))
        damaged=inspect_sealed_to_research_gate(self.plan,self.root,ASOF)
        self.check_wait(damaged)
        self.assertEqual(damaged["status"],"BLOCKED")
        file.unlink()
        absent=inspect_sealed_to_research_gate(self.plan,self.root,ASOF)
        self.check_wait(absent)
        self.assertEqual(absent["status"],"BLOCKED")

    def test_tampered_plan_and_fake_rights_flags_never_admitted(self):
        self.save()
        plan=copy.deepcopy(self.plan)
        plan["expectedClosedBarCounts"]["M15"]+=1
        self.check_wait(inspect_sealed_to_research_gate(plan,self.root,ASOF))
        with patch.dict(os.environ,{
            "CAPITAL_DEMO_PRIVATE_RIGHTS_DOCUMENTED":"APPROVED_PRIVATE_REVIEW_ONLY",
            "CAPITAL_DEMO_PRIVATE_PRICE_GET_ENABLED":"APPROVED_PRIVATE_REVIEW_ONLY",
            "CAPITAL_API_KEY":"DO_NOT_READ",
            "GPP_SYNTHETIC_TEST_SIMULATION":"1",
        }):
            with patch("xauusd_research_pipeline.subprocess.run",
                       side_effect=AssertionError("NO_ENGINE_SPAWN")):
                result=inspect_sealed_to_research_gate(self.plan,self.root,ASOF)
        self.check_wait(result)
        self.assertTrue(result["syntheticIntakeShapeChecked"])


if __name__=="__main__":
    unittest.main()
