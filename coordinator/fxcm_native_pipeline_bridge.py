"""Private FXCM native -> existing XAUUSD research pipeline standby bridge.

The SDK is NOT imported or loaded. No FXCM credentials, market requests,
paper execution, live signals, Render deployment or rights decision.
"""
from __future__ import annotations
import datetime as dt
import json
import pathlib
import subprocess

from xauusd_feed_gate import SourcePolicy, parse_utc
from xauusd_research_pipeline import run_research_pipeline

ROOT = pathlib.Path(__file__).resolve().parent
JS_AUDIT = """
'use strict';
const fs=require('node:fs');
const {assess}=require('./fxcm_native_offline_boundary');
const {packet,asOfUTC}=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(assess(packet,asOfUTC)));
"""
FIXED_REASONS = [
    "FXCM_EULA_AND_PRIVATE_CLOUD_RIGHTS_UNVERIFIED",
    "FXCM_DEMO_READ_ONLY_PERMISSION_UNVERIFIED",
    "FXCM_NATIVE_LIVE_DATA_AND_UTC_CLOCK_NOT_PROVEN",
    "FXCM_SOURCE_INTAKE_REMAINS_DISABLED",
]


def review_fxcm_native_standby(candidate: object, as_of: dt.datetime) -> dict:
    """Inspect a candidate locally and prove the existing research path stays blocked.

    This function is *not* a live adapter. Caller-provided rights booleans
    are never forwarded as source policy. No price fields are returned.
    """
    reasons = list(FIXED_REASONS)
    audit = {}
    frame_counts = {"M15": 0, "H1": 0, "H4": 0}
    overlaps = {"H1": 0, "H4": 0}
    generic = {"status": "WAIT_INTAKE_BLOCKED",
               "engines": {"v3": "SKIPPED", "ultimateR2": "SKIPPED",
                           "diagnostics": "SKIPPED", "paper": "SKIPPED"}}
    try:
        now = parse_utc(as_of.isoformat())
        utc_time = now.isoformat().replace("+00:00", "Z")
        raw = json.dumps({"packet": candidate, "asOfUTC": utc_time},
                         separators=(",", ":"), allow_nan=False)
        if len(raw) > 750_000:
            raise ValueError("FXCM_PACKET_TOO_LARGE")
        checked = subprocess.run(["node", "-e", JS_AUDIT],
                                 cwd=ROOT, input=raw, text=True,
                                 capture_output=True, check=True, timeout=8)
        audit = json.loads(checked.stdout)
        if audit.get("adapter") != "NATIVE_CPP_JSON_OFFLINE_ONLY" or \
           audit.get("signal") != "WAIT" or audit.get("executable") is not False or \
           audit.get("researchEligible") is not False or \
           audit.get("sdkLoaded") is not False or \
           audit.get("sourceRequestsMade") != 0 or \
           audit.get("rawCandlesReleased") is not False:
            raise ValueError("FXCM_AUDIT_SAFETY_CONTRACT_FAILED")
        frame_counts = audit.get("frameCounts", frame_counts)
        overlaps = audit.get("verifiedGeometricOverlaps", overlaps)
        reasons.extend(audit.get("blockingReasons", []))

        # The shared pipeline requires a signed/authorized source *and* an
        # independent session calendar. Never synthesize one from broker bars.
        # Pass metadata only; no FXCM candle enters any existing engine.
        metadata = {
            "provider": "FXCM", "instrument": "XAU/USD", "mode": "recorded",
            "receivedUTC": candidate.get("receivedUTC") if isinstance(candidate, dict) else None,
            "frames": {},
        }
        generic = run_research_pipeline(
            metadata, now, SourcePolicy(expected_provider="FXCM"), {})
        if generic.get("status") != "WAIT_INTAKE_BLOCKED" or \
           any(value != "SKIPPED" for value in generic.get("engines", {}).values()) or \
           generic.get("researchEligible") is not False or \
           generic.get("executable") is not False:
            raise ValueError("SHARED_RESEARCH_PIPELINE_FAIL_CLOSED_CONTRACT_BROKEN")
    except (TypeError, ValueError, OSError, subprocess.SubprocessError,
            json.JSONDecodeError) as exc:
        reasons.append(type(exc).__name__ + "_FXCM_STANDBY_FAILED")
        audit = {}
        frame_counts = {"M15": 0, "H1": 0, "H4": 0}
        overlaps = {"H1": 0, "H4": 0}

    return {
        "status": "WAIT_FXCM_NATIVE_INTAKE_STANDBY",
        "provider": "FXCM", "signal": "WAIT", "executable": False,
        "researchEligible": False, "researchCandidate": "NONE",
        "paperOrdersAllowed": False, "paperRunning": False,
        "providerRequestsMade": 0, "credentialsRead": 0,
        "sdkLoaded": False, "tradingEnabled": False,
        "sourcePolicyAuthorized": False,
        "structuralAuditPassed": audit.get("structureValid") is True,
        "frameCounts": frame_counts,
        "checkedOverlaps": overlaps,
        "sharedResearchIntakeStatus": generic.get("status"),
        "engines": {"v3": "SKIPPED", "ultimateR2": "SKIPPED",
                    "diagnostics": "SKIPPED", "paper": "SKIPPED"},
        "rawCandlesIncluded": False, "blockingReasons": reasons,
    }
