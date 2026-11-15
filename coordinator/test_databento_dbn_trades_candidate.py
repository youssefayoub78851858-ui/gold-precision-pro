"""Standalone offline tests of the quarantined Databento DBN conversion bridge."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from databento_dbn_trades_candidate import export_local_dbn, prepare_candidate


def fake_decoded(symbol="ESH1"):
    return {
        "format": "DBN", "testFixtureOnly": True, "researchEligible": False,
        "feedEmitted": False, "signal": "WAIT", "executable": False,
        "source": {"dataset": "GLBX.MDP3", "schema": "trades",
                   "priceEncoding": "FIXED_1E9", "priceScale": 1_000_000_000,
                   "sha256": "f" * 64, "symbols": [symbol],
                   "symbolMappings": {symbol: []}},
        "rowCount": 1,
        "rows": [{"ts_event": 1794493813003000000, "ts_recv": 1794493813003000123,
                  "publisher_id": 1, "instrument_id": 888, "sequence": 10,
                  "flags": 128, "rtype": 0, "action": "T", "side": "N",
                  "price": 3720250000000, "size": 2}],
    }


class DBNCandidateTests(unittest.TestCase):
    def test_exact_fixed_point_nanoseconds_and_unknown_side_preserved(self):
        output = prepare_candidate(fake_decoded())
        self.assertEqual(output["rows"][0]["price"], "3720250000000")
        self.assertEqual(output["rows"][0]["ts_recv"], "1794493813003000123")
        self.assertEqual(output["rows"][0]["side"], "N")
        self.assertFalse(output["receipt"]["datedGCNameSeen"])
        self.assertFalse(output["receipt"]["researchEligible"])
        self.assertFalse(output["receipt"]["continuityVerified"])
        self.assertEqual(output["receipt"]["signal"], "WAIT")
        self.assertFalse(output["receipt"]["executable"])
        self.assertEqual(output["receipt"]["rowsSHA256"], hashlib.sha256(
            (json.dumps(output["rows"], ensure_ascii=True, separators=(",", ":")) + "\n").encode()).hexdigest())

    def test_gc_symbol_alone_never_grants_mapping_or_rights(self):
        output = prepare_candidate(fake_decoded("GCZ6"))
        self.assertTrue(output["receipt"]["datedGCNameSeen"])
        self.assertFalse(output["receipt"]["actualGCMarketSampleVerified"])
        self.assertFalse(output["receipt"]["instrumentMappingVerified"])
        self.assertFalse(output["receipt"]["rightsVerified"])
        self.assertFalse(output["receipt"]["feedEmitted"])

    def test_invalid_schema_tampering_price_clock_action_and_flags_fail_closed(self):
        for key, bad in (("schema", "mbo"), ("priceScale", 1)):
            item = fake_decoded(); item["source"][key] = bad
            with self.assertRaises(ValueError):
                prepare_candidate(item)
        for field, bad in [("price", 4.0), ("price", -1), ("ts_recv", 1),
                           ("size", 0), ("side", "INVALID"), ("action", "A"),
                           ("flags", True), ("rtype", 160)]:
            with self.subTest(field=field, bad=bad):
                item = fake_decoded(); item["rows"][0][field] = bad
                with self.assertRaises(ValueError):
                    prepare_candidate(item)
        item = fake_decoded(); item["researchEligible"] = True
        with self.assertRaisesRegex(ValueError, "QUARANTINE"):
            prepare_candidate(item)
        item = fake_decoded(); item["rows"] = []
        with self.assertRaises(ValueError):
            prepare_candidate(item)

    def test_files_are_private_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "candidate.json"
            with patch("databento_dbn_trades_candidate.decode_dbn_file", return_value=fake_decoded()):
                result = export_local_dbn(Path(d) / "input.dbn", output)
                self.assertEqual(result["networkRequestsMade"], 0)
                self.assertEqual(result["signal"], "WAIT")
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)
                self.assertEqual((Path(d) / "candidate.receipt.json").stat().st_mode & 0o777, 0o600)
                self.assertEqual(len(json.loads(output.read_text())), 1)
                with self.assertRaises(FileExistsError):
                    export_local_dbn(Path(d) / "input.dbn", output)


if __name__ == "__main__":
    unittest.main()
