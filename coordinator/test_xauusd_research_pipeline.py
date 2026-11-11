"""Offline end-to-end intake, V3/r2, diagnostics and paper simulation tests."""
import copy
import datetime as dt
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ultimate_paper import PaperAccount
from xauusd_feed_gate import SourcePolicy
from xauusd_research_pipeline import run_research_pipeline

ROOT = pathlib.Path(__file__).resolve().parent


def v2_fixture():
    result = subprocess.run(
        ["node", "-e", "console.log(JSON.stringify(require('./test_ultimate_v2').fixture()))"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout)


def fixture_bundle():
    v3 = json.loads((ROOT / "fixtures/ultimate-synthetic.json").read_text())
    for rows in v3["frames"].values():
        rows[22]["high"] = 103
        rows[29].update(open=100, high=105, close=104)
    r2 = v2_fixture()
    now = v3["asOfUTC"]
    payload_frames = {}
    for tf, interval in (("M15", "15min"), ("H1", "1h"), ("H4", "4h")):
        candles = []
        for row in v3["frames"][tf]:
            opened = row["datetime"].replace("+00:00", "Z")
            candles.append({"openTime": opened, **{k: row[k] for k in ("open", "high", "low", "close")}})
        payload_frames[interval] = {"candles": candles, "expectedOpenTimes": [x["openTime"] for x in candles]}
    payload = {"provider": "UNIT_TEST_FIXTURE", "instrument": "XAU/USD", "mode": "synthetic",
               "receivedUTC": now, "frames": payload_frames}
    context = {"v3Feeds": v3["feeds"], "r2Feeds": r2["feeds"],
               "spread": v3["spread"], "risk": v3["risk"]}
    return payload, context, dt.datetime.fromisoformat(now.replace("Z", "+00:00"))


def run(payload=None, context=None, now=None, **kwargs):
    original, original_context, original_now = fixture_bundle()
    return run_research_pipeline(payload or original, now or original_now, SourcePolicy(),
                                 context or original_context, **kwargs)


def simulate(payload, context, now):
    with patch.dict(os.environ, {"GPP_SYNTHETIC_TEST_SIMULATION": "1"}):
        return run_research_pipeline(payload, now, SourcePolicy(), context,
                                     allow_synthetic_simulation=True)


class XauUsdResearchPipeline(unittest.TestCase):
    def test_default_synthetic_path_is_wait_and_does_not_call_engines(self):
        payload, context, now = fixture_bundle()
        with patch("xauusd_research_pipeline.subprocess.run", side_effect=AssertionError("engine should be skipped")):
            result = run_research_pipeline(payload, now, SourcePolicy(), context)
        self.assertEqual(result["status"], "SYNTHETIC_TEST_ONLY")
        self.assertFalse(result["researchEligible"])
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertEqual(result["researchCandidate"], "NONE")
        self.assertNotIn("paperSnapshot", result)

    def test_end_to_end_v3_r2_diagnostics_and_isolated_paper_restart(self):
        payload, context, now = fixture_bundle()
        result = simulate(payload, context, now)
        self.assertEqual(result["status"], "SYNTHETIC_TEST_ONLY")
        self.assertFalse(result["researchEligible"])
        self.assertTrue(result["simulationOnly"])
        self.assertTrue(result["paperSimulationAllowed"])
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertEqual(result["researchCandidate"], "NONE")
        self.assertEqual(result["engineCandidates"], {"v3": "BUY", "ultimateR2": "BUY"})
        self.assertEqual(result["v3"]["signal"], "WAIT")
        self.assertEqual(result["ultimateR2"]["signal"], "WAIT")
        self.assertEqual(result["diagnostics"]["technical"]["status"], "INCOMPLETE")
        self.assertEqual(result["diagnostics"]["technical"]["frames"]["M15"]["status"], "PARTIAL")
        self.assertEqual(result["diagnostics"]["news"]["status"], "RESEARCH_ONLY")
        self.assertEqual(result["diagnostics"]["riskPlan"]["status"], "RESEARCH_PLAN_ONLY")
        self.assertEqual(result["providerRequestsMade"], 0)

        paper_snapshot = result["paperSnapshot"]
        decision_bar = paper_snapshot["frames"]["M15"][-1]
        with tempfile.TemporaryDirectory() as directory:
            database = pathlib.Path(directory) / "isolated-synthetic.sqlite3"
            account = PaperAccount(database)
            first = account.step(decision_bar, paper_snapshot)
            self.assertEqual(len(first["pending"]), 1)
            event_count = account.db.execute("SELECT COUNT(*) FROM events WHERE kind='DECISION'").fetchone()[0]
            self.assertEqual(event_count, 1)
            self.assertTrue(account.step(decision_bar, paper_snapshot)["duplicate"])
            account.close()

            account = PaperAccount(database)
            self.assertTrue(account.step(decision_bar, paper_snapshot)["duplicate"])
            self.assertEqual(account.db.execute("SELECT COUNT(*) FROM events WHERE kind='DECISION'").fetchone()[0], 1)
            account.step({"datetime": "2026-11-10T12:00:00Z", "open": 104, "high": 105,
                          "low": 103, "close": 104, "dataOrigin": "SYNTHETIC_TEST_ONLY"})
            position = account.summary()["position"][0]
            self.assertLessEqual(position["risk"], 50)
            account.step({"datetime": "2026-11-10T12:15:00Z", "open": 104,
                          "high": position["target"] + 1, "low": 103, "close": position["target"],
                          "dataOrigin": "SYNTHETIC_TEST_ONLY"})
            self.assertEqual(len(account.summary()["trades"]), 1)
            self.assertIn("SYNTHETIC_TEST_ONLY", account.summary()["dataOrigin"])
            self.assertEqual(account.db.execute("SELECT COUNT(*) FROM events WHERE kind='PAPER_ENTRY'").fetchone()[0], 1)
            account.close()
            account = PaperAccount(database)
            self.assertTrue(account.step({"datetime": "2026-11-10T12:15:00Z", "open": 104,
                                          "high": position["target"] + 1, "low": 103,
                                          "close": position["target"], "dataOrigin": "SYNTHETIC_TEST_ONLY"})["duplicate"])
            self.assertEqual(len(account.summary()["trades"]), 1)
            account.close()

    def test_gaps_stale_and_future_bars_fail_closed_before_any_engine(self):
        payload, context, now = fixture_bundle()
        cases = []
        gap = copy.deepcopy(payload)
        del gap["frames"]["15min"]["candles"][5]
        cases.append((gap, now, "15MIN_REJECTED"))
        stale = copy.deepcopy(payload)
        stale["receivedUTC"] = (now - dt.timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        cases.append((stale, now, "INGEST_PACKET_STALE_OR_FUTURE"))
        unclosed = copy.deepcopy(payload)
        unclosed_open = (now - dt.timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        unclosed["frames"]["15min"]["candles"][-1]["openTime"] = unclosed_open
        unclosed["frames"]["15min"]["expectedOpenTimes"][-1] = unclosed_open
        cases.append((unclosed, now, "15MIN_REJECTED"))
        future = copy.deepcopy(payload)
        future_bar = {"openTime": now.isoformat().replace("+00:00", "Z"),
                      "open": 104, "high": 110, "low": 103, "close": 109}
        future["frames"]["15min"]["candles"].append(future_bar)
        future["frames"]["15min"]["expectedOpenTimes"].append(future_bar["openTime"])
        cases.append((future, now, "15MIN_REJECTED"))
        for bad_payload, as_of, marker in cases:
            with self.subTest(marker=marker):
                result = simulate(bad_payload, context, as_of)
                self.assertEqual(result["signal"], "WAIT")
                self.assertFalse(result["executable"])
                self.assertEqual(result["researchCandidate"], "NONE")
                self.assertEqual(result["engines"]["v3"], "SKIPPED")
                self.assertTrue(any(marker in reason for reason in result["intake"]["blockingReasons"]))

    def test_engine_disagreement_missing_layer_event_and_risk_all_wait(self):
        payload, context, now = fixture_bundle()
        disagree = copy.deepcopy(context)
        disagree["v3Feeds"]["DXY"]["value"] = 101
        result = simulate(payload, disagree, now)
        self.assertTrue(result["analysisConflict"])
        self.assertEqual(result["researchCandidate"], "NONE")
        self.assertEqual(result["signal"], "WAIT")
        conflict_items = [x for x in result["diagnostics"]["alerts"]["items"] if x["code"] == "ENGINE_DISAGREEMENT"]
        self.assertEqual(len(conflict_items), 1)

        missing = copy.deepcopy(context)
        del missing["r2Feeds"]["orderFlow"]
        result = simulate(payload, missing, now)
        self.assertEqual(result["researchCandidate"], "NONE")
        self.assertEqual(result["signal"], "WAIT")
        self.assertIn("orderFlow", result["ultimateR2"]["monitoring"]["blocked"])

        event = copy.deepcopy(context)
        event["r2Feeds"]["calendar"]["events"] = [{"id": "unit-high-impact", "timeUTC": "2026-11-10T12:05:00Z",
                                                    "publishedUTC": "2026-11-10T11:30:00Z",
                                                    "availableUTC": now.isoformat().replace("+00:00", "Z"),
                                                    "impact": "high"}]
        result = simulate(payload, event, now)
        self.assertEqual(result["researchCandidate"], "NONE")
        self.assertTrue(result["ultimateR2"]["layers"]["calendar"]["blocked"])

        risk = copy.deepcopy(context)
        risk["risk"]["killSwitch"] = True
        result = simulate(payload, risk, now)
        self.assertEqual(result["researchCandidate"], "NONE")
        self.assertFalse(result["ultimateR2"]["risk"]["ok"])
        self.assertEqual(result["signal"], "WAIT")

    def test_engine_outage_returns_wait_without_paper_input(self):
        payload, context, now = fixture_bundle()
        with patch("xauusd_research_pipeline.subprocess.run", side_effect=FileNotFoundError("node unavailable")):
            with patch.dict(os.environ, {"GPP_SYNTHETIC_TEST_SIMULATION": "1"}):
                result = run_research_pipeline(payload, now, SourcePolicy(), context,
                                               allow_synthetic_simulation=True)
        self.assertEqual(result["status"], "WAIT_ENGINE_FAILURE")
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertEqual(result["researchCandidate"], "NONE")
        self.assertNotIn("paperSnapshot", result)


if __name__ == "__main__":
    unittest.main()
