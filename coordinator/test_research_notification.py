"""Safe notification formatting tests; no sender or provider is invoked."""
import datetime as dt
import pathlib
import tempfile
import unittest

from research_notification import ResearchNotificationJournal, build_notification


class ResearchNotificationTests(unittest.TestCase):
    def test_only_verified_research_candidates_can_be_formatted_as_buy_or_sell(self):
        for candidate in ("BUY", "SELL"):
            result = build_notification({
                "status": "RESEARCH_REVIEWED", "sourceDataMode": "recorded",
                "researchEligible": True, "researchCandidate": candidate,
                "executable": False,
                "intake": {"status": "ADMISSIBLE_FOR_RESEARCH_ONLY", "researchEligible": True},
            })
            self.assertEqual(result["signal"], candidate)
            self.assertEqual(result["kind"], "RESEARCH_SIGNAL")
            self.assertFalse(result["executable"])
            self.assertEqual(result["delivery"], "DRY_RUN_LOCAL_PREVIEW_NO_EXTERNAL_SEND")

    def test_unlicensed_synthetic_stale_and_engine_failure_are_wait_alerts(self):
        cases = [
            (None, "PIPELINE_UNAVAILABLE"),
            ({"status": "WAIT_SOURCE_NOT_ELIGIBLE", "sourceDataMode": "recorded",
              "researchCandidate": "BUY", "researchEligible": False,
              "executable": False}, "WAIT_SOURCE_NOT_ELIGIBLE"),
            ({"status": "SYNTHETIC_TEST_ONLY", "sourceDataMode": "synthetic",
              "researchCandidate": "SELL", "researchEligible": False,
              "executable": False}, "SYNTHETIC_TEST_ONLY"),
            ({"status": "WAIT_ENGINE_FAILURE", "researchCandidate": "BUY",
              "researchEligible": False, "executable": False}, "WAIT_ENGINE_FAILURE"),
        ]
        for observation, code in cases:
            with self.subTest(code=code):
                result = build_notification(observation)
                self.assertEqual(result["signal"], "WAIT")
                self.assertEqual(result["code"], code)
                self.assertFalse(result["executable"])

    def test_invalid_execution_guard_never_formats_a_candidate(self):
        result = build_notification({
            "status": "RESEARCH_REVIEWED", "sourceDataMode": "recorded",
            "researchEligible": True, "researchCandidate": "BUY",
            "intake": {"researchEligible": True},
        })
        self.assertEqual(result["signal"], "WAIT")
        self.assertEqual(result["code"], "EXECUTION_GUARD_BLOCKED")
        self.assertFalse(result["executable"])

    def test_candidate_without_all_source_rights_gates_is_wait(self):
        result = build_notification({
            "status": "RESEARCH_REVIEWED", "sourceDataMode": "recorded",
            "researchEligible": True, "researchCandidate": "BUY",
            "executable": False,
            "intake": {"researchEligible": False},
        })
        self.assertEqual(result["signal"], "WAIT")
        self.assertEqual(result["code"], "SOURCE_NOT_ELIGIBLE")
        self.assertFalse(result["executable"])

    def test_local_journal_deduplicates_persists_and_records_signal_transitions(self):
        now = dt.datetime(2026, 11, 12, 12, 0, tzinfo=dt.timezone.utc)
        buy = {
            "status": "RESEARCH_REVIEWED", "sourceDataMode": "recorded",
            "researchEligible": True, "researchCandidate": "BUY", "executable": False,
            "intake": {"researchEligible": True},
        }
        sell = {**buy, "researchCandidate": "SELL"}
        with tempfile.TemporaryDirectory() as directory:
            database = pathlib.Path(directory) / "notifications.sqlite3"
            journal = ResearchNotificationJournal(database)
            first = journal.observe(buy, now)
            self.assertEqual([event["transition"] for event in first["events"]], ["RAISED"])
            self.assertEqual(first["current"]["signal"], "BUY")
            self.assertEqual(first["delivery"], "LOCAL_AUDIT_ONLY_NO_EXTERNAL_SEND")
            self.assertEqual(journal.observe(buy, now + dt.timedelta(seconds=15))["events"], [])
            journal.close()

            journal = ResearchNotificationJournal(database)
            self.assertEqual(journal.observe(buy, now + dt.timedelta(seconds=30))["events"], [])
            changed = journal.observe(sell, now + dt.timedelta(minutes=1))
            self.assertEqual([event["transition"] for event in changed["events"]],
                             ["RECOVERED", "RAISED"])
            self.assertEqual(changed["events"][-1]["signal"], "SELL")
            self.assertEqual(len(journal.history()), 3)
            self.assertTrue(all(event["executable"] is False for event in journal.history()))
            journal.close()


if __name__ == "__main__":
    unittest.main()
