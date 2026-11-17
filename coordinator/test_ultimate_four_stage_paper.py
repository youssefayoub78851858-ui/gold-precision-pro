"""Offline only: synthetic four-stage signal previews MUST NOT create paper orders."""
import copy
import json
import pathlib
import subprocess
import tempfile
import unittest

from coordinator.ultimate_paper import PaperAccount

ROOT = pathlib.Path(__file__).resolve().parent


class FourStagePaperLock(unittest.TestCase):
    def get_review(self, origin="SYNTHETIC_TEST_ONLY"):
        fixture = json.loads((ROOT / "fixtures/ultimate-synthetic.json").read_text())
        for bars in fixture["frames"].values():
            bars[22]["high"] = 103
            bars[29]["open"] = 100
            bars[29]["high"] = 105
            bars[29]["close"] = 104
        packet = {"dataOrigin": origin, "snapshot": fixture}
        command = ["node", str(ROOT / "ultimate_four_stage_review.js")]
        result = subprocess.run(command, input=json.dumps(packet), text=True,
                                check=True, capture_output=True, timeout=20)
        return fixture, json.loads(result.stdout)

    def test_synthetic_plan_never_becomes_paper_position(self):
        fixture, review = self.get_review()
        self.assertEqual(review["signal"], "WAIT")
        self.assertFalse(review["executable"])
        self.assertFalse(review["paperOrdersAllowed"])
        self.assertEqual(review["hypotheticalSyntheticPlan"]["direction"], "BUY")
        self.assertNotIn("researchCandidate", review)  # no paper-admission-shaped signal
        with tempfile.TemporaryDirectory() as folder:
            db = pathlib.Path(folder) / "paper.sqlite3"
            account = PaperAccount(db)
            try:
                last = copy.deepcopy(fixture["frames"]["M15"][-1])
                as_of = fixture["asOfUTC"]
                account.step(last, {"asOfUTC": as_of}, evaluator=lambda _: review)
                later = {"datetime": as_of, "open": 104, "high": 106,
                         "low": 102, "close": 105}
                result = account.step(later)
                self.assertEqual(len(result["position"]), 0)
                self.assertEqual(len(result["pending"]), 0)
                self.assertEqual(len(result["trades"]), 0)
                self.assertEqual(result["account"]["balance"], 10000)
            finally:
                account.close()

    def test_fake_live_approval_remains_wait(self):
        _, report = self.get_review(origin="LIVE_LICENSED")
        self.assertEqual(report["signal"], "WAIT")
        self.assertFalse(report["paperOrdersAllowed"])
        self.assertIsNone(report["hypotheticalSyntheticPlan"])
        self.assertFalse(report["profitabilityProven"])


if __name__ == "__main__":
    unittest.main()
