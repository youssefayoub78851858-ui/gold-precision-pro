"""Private BiQuote forward-vault -> frozen V3 shadow analysis (offline).

No network, no broker, no orders, no market data in stdout. Actual archived
MID may be BID-seeded; only truly closed, contiguous bars are evaluated.
This is a *blocked signal research preview*, never a trade or paper admission.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import subprocess
import sys

from biquote_private_forward_vault import START, FRAMES_ORDER, inspect_metadata, load_vault, _stamp

UTC = dt.timezone.utc
MIN_CONTIGUOUS = 21
MAX_CONTIGUOUS = 48
WIDTH = {"M15": 900, "H1": 3600, "H4": 14400}
NODE = pathlib.Path(__file__).with_name("ultimate_four_stage_review.js")
NO_SOURCE_RIGHTS = [
    "UNDERLYING_BROKER_SESSION_UNVERIFIED",
    "BIQUOTE_MID_MAY_INCLUDE_BID_SEED",
    "HISTORICAL_BID_ASK_EXECUTION_COSTS_NOT_VERIFIED",
    "GC_DXY_YIELDS_CALENDAR_NEWS_AND_LICENSED_ORDERFLOW_UNVERIFIED",
    "FORWARD_PROFITABILITY_UNTESTED",
]
BASE = {
    "mode": "BIQUOTE_PRIVATE_FORWARD_V3_SHADOW_ONLY",
    "signal": "WAIT", "executable": False, "paperOrdersAllowed": False,
    "tradeEligible": False, "researchEligible": False,
    "brokerOrdersSent": 0, "sourceRequestsMade": 0,
    "historicalBidAskExecutionVerified": False,
    "independentMacroVerified": False,
    "independentBrokerRightsVerified": False,
    "brokerSessionCalendarVerified": False,
    "profitabilityProven": False, "signalReady": False,
    "brokerPricesExposed": False,
}


def tail_contiguous(rows: object, width: int) -> list[dict]:
    """Return only a strictly closed, unmodified contiguous suffix."""
    if not isinstance(rows, list):
        return []
    tail = []
    last = None
    for row in reversed(rows):
        if not isinstance(row, dict) or set(row) != {
            "openTime", "open", "high", "low", "close"
        }:
            break
        try:
            t = _stamp(row["openTime"])
        except (ValueError, TypeError):
            break
        if last is not None and (last - t).total_seconds() != width:
            break
        o, h, l, c = (row[k] for k in ("open", "high", "low", "close"))
        # The vault's hash proves local consistency, NOT market data quality.
        if any(type(v) not in (int, float) or not (0 < v < 1e8)
               for v in (o, h, l, c)) or not l <= min(o, c) <= max(o, c) <= h:
            break
        tail.append({"datetime": row["openTime"], "open": o, "high": h, "low": l, "close": c})
        last = t
        if len(tail) >= MAX_CONTIGUOUS:
            break
    return list(reversed(tail))


def shadow_review(dirname: str | pathlib.Path, *, runner=None) -> dict:
    """Read existing private vault; never write files or call an external feed.

    Only an in-process offline Node child sees OHLC. The caller receives
    counts, timestamps, blockers, and an unapproved technical *watch* state.
    """
    safe = {**BASE, "technicalWatch": "NONE", "approvedDirection": "NONE",
            "entry": None, "stopLoss": None, "takeProfit": None,
            "paperPerformance": None, "holdoutStartsUTC": "2026-11-18T00:00:00Z",
            "reasonCodes": [*NO_SOURCE_RIGHTS], "frames": {}}
    metadata = inspect_metadata(dirname)
    archive = load_vault(dirname)
    rows = archive["closed"]
    received = archive["lastImportedUTC"]
    for tf in FRAMES_ORDER:
        width = WIDTH[tf]
        continuous = tail_contiguous(rows[tf], width)
        safe["frames"][tf] = {
            "persistedClosed": metadata["counts"][tf],
            "contiguousClosed": len(continuous),
            "lastClosedUTC": metadata["forwardCoverage"][tf]["lastClosedUTC"],
            "unclassifiedGapPairs": metadata["forwardCoverage"][tf]["unclassifiedGapPairs"],
            "neededContiguous": MIN_CONTIGUOUS,
        }
    if received is None or not archive["quoteObservations"]:
        safe["reasonCodes"].append("NO_POST_HOLDOUT_CAPTURE")
        return safe
    receipt = _stamp(received)
    if receipt < START:
        safe["reasonCodes"].append("FORWARD_TIME_BOUNDARY_FAILED")
        return safe
    quote = archive["quoteObservations"][-1]
    if not isinstance(quote, dict) or quote.get("observedUTC") != received:
        safe["reasonCodes"].append("NO_CO_TIMED_BID_ASK_QUOTE")
        return safe
    tick = _stamp(quote["tickUTC"])
    if not 0 <= (receipt - tick).total_seconds() <= 30:
        safe["reasonCodes"].append("QUOTE_STALE_AT_RECORDED_DECISION")
        return safe
    if any(safe["frames"][tf]["contiguousClosed"] < MIN_CONTIGUOUS
           for tf in FRAMES_ORDER):
        safe["reasonCodes"].append("INSUFFICIENT_CONTIGUOUS_CLOSED_H4_H1_M15")
        return safe
    packet = {"dataOrigin": "BIQUOTE_ARCHIVED_UNVERIFIED_NO_PAPER",
              "snapshot": {
                  "asOfUTC": received,
                  "frames": {tf: tail_contiguous(rows[tf], WIDTH[tf])
                             for tf in FRAMES_ORDER},
                  "feeds": {},   # NEVER forge GC/DXY/yields/news/order flow.
                  "spread": quote["spread"],
                  # There is no verified broker lot/commission contract.
                  "risk": {"killSwitch": True, "activeTrades": 0},
              }}
    if runner is None:
        runner = lambda source: subprocess.run(
            ["node", str(NODE)], input=json.dumps(source, allow_nan=False),
            text=True, capture_output=True, check=True, timeout=12,
        ).stdout
    try:
        output = json.loads(runner(packet))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        safe["reasonCodes"].append("OFFLINE_FROZEN_ENGINE_UNAVAILABLE")
        return safe
    if not isinstance(output, dict) or output.get("signal") != "WAIT" or (
        output.get("executable") is not False or
        output.get("paperOrdersAllowed") is not False or
        output.get("liveOrdersAllowed") is not False or
        output.get("researchEligible") is not False or
        output.get("hypotheticalSyntheticPlan") is not None or
        output.get("dataOrigin") != "BIQUOTE_ARCHIVED_UNVERIFIED_NO_PAPER"
    ):
        safe["reasonCodes"].append("SHADOW_OUTPUT_CONTRACT_REJECTED")
        return safe
    stages = output.get("stages")
    if not isinstance(stages, dict) or stages.get("data", {}).get("status") != "GEOMETRY_ONLY":
        safe["reasonCodes"].append("FROZEN_V3_GEOMETRY_NOT_VERIFIED")
        return safe
    direction = stages.get("analysis", {}).get("technicalCandidate")
    if direction not in ("BUY", "SELL", "NONE"):
        safe["reasonCodes"].append("UNEXPECTED_TECHNICAL_CANDIDATE")
        return safe
    safe["technicalWatch"] = direction  # only a technical observation; never a trade
    safe["engineReview"] = "FROZEN_V3_COMPLETED_WITH_REAL_OBSERVED_CLOSED_BARS"
    safe["reasonCodes"].append("NO_REAL_SIGNAL_WITHOUT_INDEPENDENT_CONTEXT_AND_RISK")
    return safe


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-dir", required=True)
    args = parser.parse_args()
    # Never print raw exception text (may contain sensitive paths).
    try:
        result = shadow_review(args.vault_dir)
    except (OSError, ValueError, TypeError, KeyError):
        result = {**BASE, "technicalWatch": "NONE", "approvedDirection": "NONE",
                  "reasonCodes": ["VAULT_UNAVAILABLE_OR_TAMPERED"],
                  "entry": None, "stopLoss": None, "takeProfit": None}
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
