"""Offline ONLY: single-poll forward capture, no doubled BiQuote requests."""
import copy
import datetime as dt
import json
import pathlib
import tempfile
import unittest

from biquote_public_one_shot import ENDPOINTS, one_shot_probe
from biquote_private_forward_vault import ingest, inspect_metadata, START
from biquote_24h_observer import QualityCounters
from test_biquote_private_forward_vault import sample, NOW, iso
from test_biquote_public_one_shot import FakeHTTPResponse


def simulated_poll(data):
    packets = {"quote": data["quote"], **data["frames"]}
    called = []
    endpoint_to_name = {url: name for name, url in ENDPOINTS}
    def opener(request, timeout):
        assert request.get_method() == "GET"
        assert not request.has_header("Authorization")
        called.append(request.full_url)
        return FakeHTTPResponse(packets[endpoint_to_name[request.full_url]])
    return opener, called


class ForwardCaptureSinglePoll(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gpp-biquote-integration-")
        self.path = pathlib.Path(self.temp.name) / "vault"
        self.data = sample()
    def tearDown(self):
        self.temp.cleanup()
    def sink(self, packet, received):
        return ingest(self.path, packet, received_utc=iso(received))

    def test_existing_poll_archives_from_same_four_gets_no_extra_calls(self):
        opener, calls = simulated_poll(self.data)
        report = one_shot_probe(opener, lambda: NOW,
                                private_snapshot_sink=self.sink)
        self.assertEqual(calls, [u for _, u in ENDPOINTS])
        self.assertEqual(report["requestCountAttempted"], 4)
        self.assertTrue(report["privateArchive"]["saved"])
        self.assertTrue(report["marketDataStored"])
        self.assertEqual(report["signal"], "WAIT")
        self.assertIs(report["executable"], False)
        self.assertIs(report["paperOrdersAllowed"], False)
        self.assertNotIn("frames", report)
        self.assertNotIn("quote", report)
        self.assertGreater(inspect_metadata(self.path)["counts"]["M15"], 0)
        counter = QualityCounters()
        counter.add(report)
        summary = counter.report(NOW, NOW, missed_slots=0, complete_window=False)
        self.assertTrue(summary["rawQuotesPersisted"])
        self.assertEqual(summary["privateArchiveSavedSnapshots"], 1)
        self.assertEqual(summary["privateArchiveNewClosedBars"]["M15"],
                         report["privateArchive"]["newClosedBars"]["M15"])
        self.assertEqual(summary["signal"], "WAIT")

    def test_no_private_sink_means_no_capture(self):
        opener, calls = simulated_poll(self.data)
        report = one_shot_probe(opener, lambda: NOW)
        self.assertEqual(len(calls), 4)
        self.assertFalse(report["marketDataStored"])
        self.assertNotIn("privateArchive", report)
        self.assertFalse(self.path.exists())

    def test_unverified_internal_gap_is_classified_not_falsely_parity_passed(self):
        self.data["frames"]["M15"]["bars"].pop(18)
        opener, calls = simulated_poll(self.data)
        report = one_shot_probe(opener, lambda: NOW,
                                private_snapshot_sink=self.sink)
        self.assertEqual(len(calls), 4)
        self.assertEqual(report["geometryFailureClass"],
                         "UNCLASSIFIED_M15_COVERAGE_GAP")
        self.assertFalse(report["structuralAudit"]["ohlcStructuralChecksPassed"])
        self.assertTrue(report["privateArchive"]["saved"])
        self.assertGreater(report["overlapEvidence"]["overlap"]
                           ["H4"]["internalM15ConstituentGaps"], 0)
        self.assertEqual(report["signal"], "WAIT")

    def test_reject_before_forward_holdout_and_do_not_store(self):
        opener, calls = simulated_poll(self.data)
        before = START - dt.timedelta(seconds=1)
        report = one_shot_probe(opener, lambda: before,
                                private_snapshot_sink=self.sink)
        self.assertEqual(len(calls), 4)
        self.assertFalse(report["privateArchive"]["saved"])
        self.assertEqual(report["privateArchive"]["blockedReason"],
                         "FORWARD_HOLDOUT_NOT_STARTED")
        self.assertFalse(self.path.exists())

    def test_bad_quote_rejected_without_poll_retry_or_data_leak(self):
        self.data["quote"]["stale"] = True
        opener, calls = simulated_poll(self.data)
        report = one_shot_probe(opener, lambda: NOW,
                                private_snapshot_sink=self.sink)
        self.assertEqual(len(calls), 4)
        self.assertFalse(report["privateArchive"]["saved"])
        self.assertEqual(report["privateArchive"]["blockedReason"],
                         "QUOTE_NOT_VALID_FRESH_OPEN")
        self.assertFalse(self.path.exists())
        self.assertNotIn("frames", report)

    def test_monitored_entrypoint_needs_separate_private_opt_in(self):
        entry = (pathlib.Path(__file__).resolve().parent /
                 "entrypoint.py").read_text()
        for required in (
            "forward_capture_enabled=(biquote_review_enabled",
            "os.environ.get(FORWARD_APPROVAL_ENV)==FORWARD_APPROVAL",
            "forward_vault_dir.startswith('/var/data/')",
            "if start < FORWARD_START:",
            "one_shot_probe(private_snapshot_sink=archive_received)",
            "observe_24h(start,probe=one_shared_poll)",
            "if forward_capture_enabled:",
        ):
            self.assertIn(required, entry)
        self.assertNotIn("CUTOVER_MODE=live", entry)
        self.assertNotIn("requests.post(", entry)


if __name__ == "__main__":
    unittest.main()
