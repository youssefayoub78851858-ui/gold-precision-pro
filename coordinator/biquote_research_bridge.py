"""Offline BiQuote -> existing XAUUSD intake and paper gate; never activates either."""
from __future__ import annotations
import datetime as dt
from biquote_offline_source_audit import audit_biquote_sample
from paper_admission_gate import assess_biquote_paper_gate
from xauusd_feed_gate import SourcePolicy, intake_payload, parse_utc

FRAMES = {"M15": "15min", "H1": "1h", "H4": "4h"}
FIELDS = ("openTime", "open", "high", "low", "close")

def review_biquote_standby(quote: object, feeds: object, *, as_of: dt.datetime) -> dict:
    """Quarantine externally supplied quotes and candles without transport.

    No rights are inherited from vendor metadata, no independently established
    session calendar exists, and historical OHLC cannot be assumed BID simply
    because BiQuote provides a separate live BID/ASK quote.
    """
    now = parse_utc(as_of.isoformat())
    audit = audit_biquote_sample(quote, feeds, now=now)
    frames = {}
    if audit["ohlcStructuralChecksPassed"]:
        for tf, interval in FRAMES.items():
            closed = [bar for bar in feeds[tf]["bars"] if bar["isOpen"] is False]
            frames[interval] = {
                "candles": [{key: bar[key] for key in FIELDS}
                            for bar in reversed(closed)],
                "expectedOpenTimes": [],  # MUST come from an independently verified calendar.
            }
    packet = {
        "provider": "BiQuote", "instrument": "XAU/USD", "mode": "recorded",
        "receivedUTC": now.isoformat().replace("+00:00", "Z"),
        "frames": frames,
    }
    intake = intake_payload(packet, now, SourcePolicy(expected_provider="BiQuote"))
    paper = assess_biquote_paper_gate(audit, intake)
    return {
        "status": "WAIT_BIQUOTE_STANDBY",
        "signal": "WAIT", "executable": False, "researchEligible": False,
        "researchCandidate": "NONE", "providerConnected": False,
        "sourceRequestsMade": 0, "orderRequestsMade": 0,
        "engineStatus": "NOT_INVOKED_SOURCE_GATE_CLOSED",
        "researchIntakeStatus": intake["status"],
        "researchIntakeReasons": intake["blockingReasons"],
        "dataOrigin": "BIQUOTE_UNVERIFIED_HISTORICAL_OHLC_BASIS",
        "sourceAudit": audit, "paperAdmission": paper,
        "blockingReasons": list(dict.fromkeys(
            audit["blockingReasons"] + intake["blockingReasons"]
            + paper["reasonCodes"])),
    }
