"""Offline adapter joining the XAU/USD intake gate to existing research engines.

No provider transport, HTTP route, or execution function is defined here. Synthetic
inputs run only when the caller explicitly opts into an isolated test simulation;
the public result remains WAIT and is never research-eligible.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess

from xauusd_feed_gate import SourcePolicy, intake_payload, parse_utc

ROOT = pathlib.Path(__file__).resolve().parent
PIPELINE_SCRIPT = r"""
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const v3 = require('./v3_ultimate').evaluate(input.v3);
const r2 = require('./ultimate_v2').evaluate(input.r2);
const diagnostics = require('./ultimate_diagnostics').diagnostics(input.r2, r2);
process.stdout.write(JSON.stringify({v3, r2, diagnostics}));
"""


def _map_frames(accepted):
    mapping = {"15min": "M15", "1h": "H1", "4h": "H4"}
    return {
        tf: [
            {"datetime": bar["openTime"], **{key: bar[key] for key in ("open", "high", "low", "close")}}
            for bar in accepted[interval]["candles"]
        ]
        for interval, tf in mapping.items()
    }


def _blocked(status, mode, reason, intake=None):
    return {
        "status": status,
        "sourceDataMode": mode,
        "researchEligible": False,
        "signal": "WAIT",
        "executable": False,
        "researchCandidate": "NONE",
        "reason": reason,
        "intake": intake,
        "engines": {"v3": "SKIPPED", "ultimateR2": "SKIPPED", "diagnostics": "SKIPPED", "paper": "SKIPPED"},
        "providerRequestsMade": 0,
    }


def run_research_pipeline(payload: dict, as_of: dt.datetime, policy: SourcePolicy,
                          context: dict, *, allow_synthetic_simulation: bool = False) -> dict:
    """Validate closed bars, call V3/r2 and diagnostics, and expose paper input safely.

    `context` must carry separate, normalized `v3Feeds` and `r2Feeds` because the
    existing engines intentionally have different evidence contracts. Synthetic
    feed contexts must be entirely synthetic and require an explicit test opt-in.
    """
    now = parse_utc(as_of.isoformat())
    intake = intake_payload(payload, now, policy)
    mode = intake["sourceDataMode"]
    if intake["status"] == "BLOCKED":
        return _blocked("WAIT_INTAKE_BLOCKED", mode, "Candle intake failed closed", intake)

    synthetic = intake["status"] == "SYNTHETIC_TEST_ONLY"
    if synthetic and not allow_synthetic_simulation:
        return _blocked("SYNTHETIC_TEST_ONLY", mode,
                        "Synthetic candles are quarantined; opt-in is limited to isolated tests", intake)
    if synthetic and os.environ.get("GPP_SYNTHETIC_TEST_SIMULATION") != "1":
        return _blocked("SYNTHETIC_TEST_ONLY", mode,
                        "Synthetic simulation requires an explicit test-process environment flag", intake)
    if not synthetic and not intake["researchEligible"]:
        return _blocked("WAIT_SOURCE_NOT_ELIGIBLE", mode, "Source rights or entitlement are not verified", intake)
    if not isinstance(context, dict):
        return _blocked("WAIT_CONTEXT_MISSING", mode, "Engine evidence context is unavailable", intake)

    v3_feeds = context.get("v3Feeds")
    r2_feeds = context.get("r2Feeds")
    if not isinstance(v3_feeds, dict) or not isinstance(r2_feeds, dict):
        return _blocked("WAIT_CONTEXT_MISSING", mode, "Separate V3 and r2 evidence contexts are required", intake)
    if synthetic and any(not isinstance(feed, dict) or feed.get("mode") != "synthetic"
                         for feeds in (v3_feeds, r2_feeds) for feed in feeds.values()):
        return _blocked("WAIT_MIXED_SYNTHETIC_CONTEXT", mode,
                        "Synthetic tests cannot mix synthetic candles with non-synthetic evidence", intake)

    frames = _map_frames(intake["frames"])
    shared = {"asOfUTC": now.isoformat().replace("+00:00", "Z"), "frames": frames,
              "spread": context.get("spread"), "risk": context.get("risk")}
    inputs = {"v3": {**shared, "feeds": v3_feeds},
              "r2": {**shared, "feeds": r2_feeds}}
    try:
        completed = subprocess.run(
            ["node", "-e", PIPELINE_SCRIPT], cwd=ROOT,
            input=json.dumps(inputs, separators=(",", ":")), text=True,
            capture_output=True, check=True, timeout=10,
        )
        engines = json.loads(completed.stdout)
        v3, r2 = engines["v3"], engines["r2"]
        if any(result.get("signal") != "WAIT" or result.get("executable") is not False
               for result in (v3, r2)):
            raise ValueError("engine research-only contract failed")
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, json.JSONDecodeError):
        return _blocked("WAIT_ENGINE_FAILURE", mode, "Research engine or diagnostics failed", intake)

    v3_candidate = v3.get("researchCandidate", "NONE")
    r2_candidate = r2.get("researchCandidate", "NONE")
    conflict = (v3_candidate != r2_candidate and
                (v3_candidate in ("BUY", "SELL") or r2_candidate in ("BUY", "SELL")))
    agreed = v3_candidate if v3_candidate == r2_candidate and v3_candidate in ("BUY", "SELL") and not conflict else "NONE"
    eligible = not synthetic and agreed in ("BUY", "SELL")
    diagnostics = engines["diagnostics"]
    if conflict:
        alerts = diagnostics.setdefault("alerts", {"status": "BLOCKED", "delivery": "RESPONSE_ONLY_NO_PUSH_OR_EMAIL",
                                                     "signal": "WAIT", "executable": False, "items": []})
        alerts["status"] = "BLOCKED"
        alerts.setdefault("items", []).append({"severity": "BLOCKING", "code": "ENGINE_DISAGREEMENT",
                                                "source": "V3/Ultimate r2",
                                                "message": f"V3 candidate {v3_candidate} differs from Ultimate r2 candidate {r2_candidate}"})
    response = {
        "status": "SYNTHETIC_TEST_ONLY" if synthetic else "RESEARCH_REVIEWED",
        "sourceDataMode": mode,
        "researchEligible": eligible,
        "signal": "WAIT",
        "executable": False,
        "researchCandidate": agreed if eligible else "NONE",
        "engineCandidates": {"v3": v3_candidate, "ultimateR2": r2_candidate},
        "analysisConflict": conflict,
        "intake": intake,
        "v3": v3,
        "ultimateR2": r2,
        "diagnostics": diagnostics,
        "engines": {"v3": "REVIEWED", "ultimateR2": "REVIEWED", "diagnostics": "REVIEWED",
                    "paper": "ISOLATED_TEST_ONLY" if synthetic else "AVAILABLE_OFFLINE"},
        "providerRequestsMade": 0,
    }
    if synthetic:
        response["simulationOnly"] = True
        response["paperSimulationAllowed"] = True
        response["researchCandidate"] = "NONE"
        response["paperSnapshot"] = {
            **inputs["v3"],
            "frames": {tf: [{**bar, "dataOrigin": "SYNTHETIC_TEST_ONLY"} for bar in rows]
                       for tf, rows in frames.items()},
        }
    return response
