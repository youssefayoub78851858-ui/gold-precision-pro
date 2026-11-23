"""Synthetic historical page arrival cutoff is never a live/forward signal.

Tests use the same 16 M15, 4 H1, 1 H4 fictitious BID/ASK closed bars
as the locked private restart rehearsal. No provider calls or credentials.
"""
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from capital_demo_private_page_store import commit_fixture_page
from capital_demo_synthetic_arrival_cutoff import inspect_synthetic_arrival
from test_capital_demo_synthetic_archive_mtf_replay import (
    plan, make_pages, EPIC, RESOLUTIONS, OBS, ASOF
)


class CapitalSyntheticArrivalCutoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = pathlib.Path(self.tmp.name)
        os.chmod(self.directory, 0o700)
        self.plan = plan()
        self.assertEqual(self.plan["status"], "INERT_PLAN_ONLY")

    def save(self, *, received_utc=OBS, with_gap=False):
        frames = make_pages()
        if with_gap:
            frames["M15"].pop(3)
        for tf in ("M15", "H1", "H4"):
            spec = self.plan["requests"][tf][0]
            page = {"epic": EPIC, "resolution": RESOLUTIONS[tf],
                    "prices": frames[tf]}
            result = commit_fixture_page(
                spec, page, self.directory, received_utc,
                explicit_synthetic_rehearsal=True)
            self.assertTrue(result["committed"])

    def safety(self, data):
        self.assertEqual(data["signal"], "WAIT")
        self.assertFalse(data["executable"])
        self.assertFalse(data["paperOrdersAllowed"])
        self.assertFalse(data["liveOrdersAllowed"])
        self.assertFalse(data["researchEligible"])
        self.assertFalse(data["realDataReady"])
        self.assertFalse(data["sourceRightsVerified"])
        self.assertFalse(data["genuineBrokerFeedVerified"])
        self.assertFalse(data["independentlyAttestedFirstSeen"])
        self.assertFalse(data["historicalBackfillIsProspectiveEvidence"])
        self.assertFalse(data["independentOffsiteBackupVerified"])
        self.assertFalse(data["forwardPaperResultsVerified"])
        self.assertEqual(data["providerRequestsMade"], 0)
        self.assertEqual(data["ordersSent"], 0)
        serialized = json.dumps(data)
        for secret in ("4000", EPIC, "C"*32, str(self.directory)):
            self.assertNotIn(secret, serialized)

    def test_locally_saved_closed_pages_before_decision_not_first_seen(self):
        self.save()
        result = inspect_synthetic_arrival(self.plan,self.directory,ASOF)
        self.safety(result)
        self.assertEqual(result["status"],
                         "SYNTHETIC_PAGES_WITHIN_LOCAL_DECISION_CUTOFF_ONLY")
        self.assertEqual(result["totalSealedPagesChecked"],3)
        self.assertTrue(result["historicalPagesAvailableBySyntheticCutoff"])
        self.assertTrue(result["closedBidAskMtfLocalParity"])
        self.assertFalse(result["independentlyAttestedFirstSeen"])
        self.assertEqual(result,inspect_synthetic_arrival(
            self.plan,self.directory,ASOF))

    def test_retrospectively_fetched_page_after_decision_fails(self):
        # All candles are closed, but the simulated page was saved after
        # the alleged decision, and cannot justify a past signal.
        self.save(received_utc="2026-11-20T12:13:00Z")
        result = inspect_synthetic_arrival(self.plan,self.directory,ASOF)
        self.safety(result)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["reason"],"HISTORICAL_PAGE_ARRIVED_AFTER_DECISION")

    def test_cannot_reinterpret_original_plan_as_an_earlier_decision(self):
        self.save()
        output = inspect_synthetic_arrival(
            self.plan,self.directory,"2026-11-20T12:06:00Z")
        self.safety(output)
        self.assertEqual(output["reason"],"PLAN_ASOF_DECISION_MISMATCH")
        bad=inspect_synthetic_arrival(self.plan,self.directory,
                                      "2026-11-20T12:12:00+00:00")
        self.assertEqual(bad["status"],"BLOCKED")
        self.safety(bad)

    def test_missing_m15_constituent_cannot_certify_full_quality(self):
        self.save(with_gap=True)
        result=inspect_synthetic_arrival(self.plan,self.directory,ASOF)
        self.safety(result)
        self.assertEqual(result["reason"],
                         "SEALED_MTF_REPLAY_NOT_FULLY_CONSISTENT")

    def test_missing_or_tampered_private_archive_does_not_pass(self):
        self.save()
        path=next(self.directory.glob("capital-synthetic-page-*.json"))
        original=path.read_bytes()
        path.write_bytes(original.replace(b"4000",b"4010",1))
        result=inspect_synthetic_arrival(self.plan,self.directory,ASOF)
        self.safety(result)
        self.assertEqual(result["status"],"BLOCKED")
        path.unlink()
        result=inspect_synthetic_arrival(self.plan,self.directory,ASOF)
        self.safety(result)
        self.assertEqual(result["status"],"BLOCKED")

    def test_never_approves_network_even_if_env_variables_set(self):
        self.save()
        with patch.dict(os.environ, {
            "CAPITAL_DEMO_RESEARCH_ENABLED":"TRUE",
            "CAPITAL_DEMO_RIGHTS_APPROVED":"TRUE",
            "CAPITAL_API_KEY":"DO_NOT_READ",
        }):
            result=inspect_synthetic_arrival(self.plan,self.directory,ASOF)
        self.safety(result)
        self.assertEqual(result["status"],
                         "SYNTHETIC_PAGES_WITHIN_LOCAL_DECISION_CUTOFF_ONLY")


if __name__=="__main__":
    unittest.main()
