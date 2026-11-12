"""Read real upstream DBN software-test fixtures with the official decoder."""
from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
import unittest

from databento_dbn_readonly import decode_dbn_bytes, decode_dbn_file


HERE = pathlib.Path(__file__).resolve().parent
FIXTURE_DIR = HERE / "fixtures" / "databento_dbn" / "upstream-a776930"
MANIFEST = json.loads((FIXTURE_DIR.parent / "manifest.json").read_text())


class OfficialDatabentoDBN(unittest.TestCase):
    def test_three_native_dbn_schemas_decode_and_preserve_fields(self):
        for name, expected in MANIFEST["files"].items():
            with self.subTest(file=name):
                result = decode_dbn_file(FIXTURE_DIR / name, expected_sha256=expected["sha256"])
                self.assertEqual(result["format"], "DBN")
                self.assertEqual(result["source"]["dataset"], "GLBX.MDP3")
                self.assertEqual(result["source"]["schema"], expected["schema"])
                self.assertEqual(result["source"]["dbnVersion"], 2)
                self.assertEqual(result["source"]["symbols"], ["ESH1"])
                self.assertEqual(result["source"]["symbolMappings"]["ESH1"][0]["symbol"], "5482")
                self.assertEqual(result["source"]["priceScale"], 1_000_000_000)
                self.assertEqual(result["rowCount"], expected["rows"])
                self.assertEqual(result["source"]["byteLength"], expected["bytes"])
                self.assertEqual(result["source"]["sha256"], expected["sha256"])
                self.assertTrue(result["testFixtureOnly"])
                self.assertFalse(result["researchEligible"])
                self.assertFalse(result["feedEmitted"])
                self.assertEqual(result["signal"], "WAIT")
                self.assertFalse(result["executable"])
                rows = result["rows"]
                self.assertTrue(all("ts_event" in row and "sequence" in row and "flags" in row for row in rows))
                self.assertEqual([row["ts_event"] for row in rows], sorted(row["ts_event"] for row in rows))
                self.assertEqual([row["sequence"] for row in rows], expected["sequences"])
                self.assertTrue(all(row["flags"] & 128 for row in rows))  # F_LAST

    def test_fixture_specific_schema_actions_and_fixed_point_price(self):
        trades = decode_dbn_file(FIXTURE_DIR / "test_data.trades.dbn")
        mbo = decode_dbn_file(FIXTURE_DIR / "test_data.mbo.dbn")
        mbp10 = decode_dbn_file(FIXTURE_DIR / "test_data.mbp-10.dbn")
        self.assertEqual([row["action"] for row in trades["rows"]], ["T", "T"])
        self.assertTrue(all(row["rtype"] == 0 and row["side"] == "A" for row in trades["rows"]))
        self.assertEqual(trades["rows"][0]["price"], 3_720_250_000_000)
        self.assertEqual([row["action"] for row in mbo["rows"]], ["C", "C"])
        self.assertTrue(all("order_id" in row and "channel_id" in row for row in mbo["rows"]))
        self.assertTrue(all(row["rtype"] == 160 and row["side"] == "A" for row in mbo["rows"]))
        self.assertEqual([row["action"] for row in mbp10["rows"]], ["C", "C"])
        self.assertTrue(all(row["rtype"] == 10 and row["depth"] in (1, 9) for row in mbp10["rows"]))
        self.assertTrue(all("bid_px_09" in row and "ask_ct_09" in row for row in mbp10["rows"]))
        self.assertEqual(mbo["rows"][0]["ts_event"], mbp10["rows"][0]["ts_event"])
        # The official examples identify ESH1, not GC; never reinterpret them as gold.
        self.assertNotIn("GC", mbo["source"]["symbols"])

    def test_corrupt_header_incomplete_record_and_wrong_pinned_hash_fail_closed(self):
        raw = (FIXTURE_DIR / "test_data.trades.dbn").read_bytes()
        damaged_header = b"X" + raw[1:]
        with self.assertRaisesRegex(ValueError, "DBN_HEADER_INVALID"):
            decode_dbn_bytes(damaged_header)
        with self.assertRaisesRegex(ValueError, "DBN_INCOMPLETE_OR_TRUNCATED"):
            decode_dbn_bytes(raw[:-1])
        damaged_payload = bytearray(raw)
        damaged_payload[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "DBN_SHA256_MISMATCH"):
            decode_dbn_bytes(bytes(damaged_payload), expected_sha256=MANIFEST["files"]["test_data.trades.dbn"]["sha256"])
        with self.assertRaisesRegex(ValueError, "DBN_SHA256_MISMATCH"):
            decode_dbn_bytes(raw, expected_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
