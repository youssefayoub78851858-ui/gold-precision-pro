"""Synthetic normalized MBO/MBP examples; no provider payload or network."""
import json
import pathlib
import tempfile
import unittest

from databento_gc_book_preflight import validate_fixture_file, validate_rows


AS_OF = "2026-11-11T12:00:03Z"


class DatabentoGCBookPreflight(unittest.TestCase):
    def setUp(self):
        self.mbo = [
            {"ts_event": "2026-11-11T12:00:01Z", "sequence": 10,
             "action": "ADD", "side": "B", "order_id": "toy-1", "price": 2000.0, "size": 2.0},
            {"ts_event": "2026-11-11T12:00:02Z", "sequence": 11,
             "action": "TRADE", "side": "A", "order_id": "toy-2", "price": 2001.0, "size": 1.0},
        ]
        self.mbp = [
            {"ts_event": "2026-11-11T12:00:01Z", "sequence": 20,
             "bids": [[2000.0, 4.0]], "asks": [[2001.0, 3.0]]},
            {"ts_event": "2026-11-11T12:00:02Z", "sequence": 21,
             "bids": [[2000.0, 5.0]], "asks": [[2001.0, 2.0]]},
        ]

    def test_mbo_structure_passes_but_never_emits_market_evidence(self):
        out = validate_rows("mbo", self.mbo, AS_OF)
        self.assertEqual(out["status"], "SYNTHETIC_TEST_ONLY")
        self.assertFalse(out["researchEligible"])
        self.assertFalse(out["feedEmitted"])
        self.assertEqual(out["orderFlow"], "UNAVAILABLE")
        self.assertEqual(out["signal"], "WAIT")
        self.assertFalse(out["executable"])
        self.assertEqual(out["providerRequestsMade"], 0)

    def test_mbp_snapshots_are_structural_only(self):
        out = validate_rows("mbp-1", self.mbp, AS_OF)
        self.assertEqual(out["rowsValidated"], 2)
        self.assertEqual(out["orderFlow"], "UNAVAILABLE")
        with self.assertRaisesRegex(ValueError, "MBP_DEPTH_EXCEEDED"):
            validate_rows("mbp-1", [{**self.mbp[0], "bids": [[2000, 2], [1999, 3]]}], AS_OF)

    def test_gaps_are_not_inferred_as_complete_sequence(self):
        gap = [{**self.mbp[0]}, {**self.mbp[1], "sequence": 23}]
        # A monotone sequence alone cannot attest capture completeness; this
        # validator deliberately makes no continuity/coverage claim.
        out = validate_rows("mbp-10", gap, AS_OF)
        self.assertFalse(out["researchEligible"])
        self.assertEqual(out["orderFlow"], "UNAVAILABLE")

    def test_equal_event_times_follow_sequence_without_duplicate_time_rejection(self):
        tied = [self.mbo[0], {**self.mbo[1], "ts_event": self.mbo[0]["ts_event"]}]
        out = validate_rows("mbo", tied, AS_OF)
        self.assertEqual(out["rowsValidated"], 2)
        self.assertEqual(out["status"], "SYNTHETIC_TEST_ONLY")
        self.assertFalse(out["feedEmitted"])

    def test_reversed_duplicate_future_and_bad_book_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_REVERSED_SEQUENCE"):
            validate_rows("mbo", [self.mbo[0], {**self.mbo[1], "sequence": 10}], AS_OF)
        with self.assertRaisesRegex(ValueError, "MBO_ORDER_ID"):
            validate_rows("mbo", [{**self.mbo[0], "order_id": True}], AS_OF)
        with self.assertRaisesRegex(ValueError, "FUTURE_EVENT"):
            validate_rows("mbo", [self.mbo[0], {**self.mbo[1], "ts_event": "2026-11-11T12:00:04Z"}], AS_OF)
        crossed = [{**self.mbp[0], "asks": [[1999.0, 3.0]]}]
        with self.assertRaisesRegex(ValueError, "MBP_CROSSED_BOOK"):
            validate_rows("mbp-1", crossed, AS_OF)

    def test_fixture_file_requires_explicit_synthetic_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "fixture.json"
            path.write_text(json.dumps({"dataOrigin": "SYNTHETIC_TEST_ONLY", "schema": "mbo", "rows": self.mbo}))
            self.assertEqual(validate_fixture_file(path, AS_OF)["status"], "SYNTHETIC_TEST_ONLY")
            path.write_text(json.dumps({"dataOrigin": "recorded", "schema": "mbo", "rows": self.mbo}))
            with self.assertRaisesRegex(ValueError, "SYNTHETIC_FIXTURE_TAG_REQUIRED"):
                validate_fixture_file(path, AS_OF)


if __name__ == "__main__":
    unittest.main()
