"""EODHD staged bid/ask -> existing XAU/USD research gate. No networking or orders.

The WebSocket bridge writes a private snapshot. This importer audits that
snapshot and will only call the existing research-only pipeline when *separate*
source-rights, independent UTC session and history evidence are supplied.
The snapshot's own status flags NEVER authorize it. Nothing auto-starts.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

from xauusd_feed_gate import SourcePolicy, parse_utc, validate_frame
from xauusd_research_pipeline import run_research_pipeline

INTERVALS = {"M15": "15min", "H1": "1h", "H4": "4h"}
FRAME_WIDTH = {"M15": 900, "H1": 3600, "H4": 14400}
MIN_WARMUP_BARS = {"M15": 50, "H1": 50, "H4": 50}
MAX_FRAME_BARS = {"M15": 2048, "H1": 512, "H4": 128}
MAX_TICK_AGE_SECONDS = 30


@dataclass(frozen=True)
class IndependentEvidence:
    """Explicitly reviewed external evidence, NEVER accepted from a vendor snapshot."""
    schedule_verified: bool = False
    schedule_reference: str = ""
    history_verified: bool = False
    history_reference: str = ""
    clock_verified: bool = False
    clock_reference: str = ""
    # Expected UTC candle opens for all three frames from a verified market calendar.
    expected_open_times: dict | None = None

    @property
    def complete(self):
        return (self.schedule_verified and self.history_verified and self.clock_verified
                and all(isinstance(v, str) and v.strip() for v in
                        (self.schedule_reference, self.history_reference, self.clock_reference))
                and isinstance(self.expected_open_times, dict)
                and set(self.expected_open_times) == set(INTERVALS))


def _blocked(reasons, counts=None, intake=None):
    return {
        "status": "WAIT_EODHD_INTAKE",
        "signal": "WAIT", "executable": False, "researchEligible": False,
        "researchCandidate": "NONE", "engineStatus": "NOT_INVOKED",
        "paperStatus": "DISABLED_PENDING_REAL_EVIDENCE",
        "sourceRequestsMade": 0, "providerConnectionStarted": False,
        "bidAskValidated": not any(x.startswith("BID_ASK_") for x in reasons),
        "blockingReasons": list(dict.fromkeys(reasons)),
        "closedBarCounts": counts or {"M15": 0, "H1": 0, "H4": 0},
        "intake": intake,
    }


def _price(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _close(a, b):
    return abs(a - b) <= max(1e-7, abs(a) * 1e-9, abs(b) * 1e-9)


def _audit_bars(snapshot):
    frames = snapshot.get("frames")
    bids = snapshot.get("bidFrames")
    asks = snapshot.get("askFrames")
    if any(not isinstance(f, dict) or set(f) != set(INTERVALS) for f in (frames, bids, asks)):
        raise ValueError("BID_ASK_FRAMES_MISSING")
    counts = {}
    for tf in INTERVALS:
        m, b, a = frames[tf], bids[tf], asks[tf]
        if any(not isinstance(rows, list) or len(rows) > MAX_FRAME_BARS[tf]
               for rows in (m, b, a)):
            raise ValueError("BID_ASK_FRAME_SIZE_OR_TYPE")
        if len(m) != len(b) or len(m) != len(a):
            raise ValueError("BID_ASK_FRAME_LENGTH_MISMATCH")
        prior = None
        width = FRAME_WIDTH[tf]
        for middle, bid, ask in zip(m, b, a):
            if any(not isinstance(row, dict) for row in (middle, bid, ask)):
                raise ValueError("BID_ASK_INVALID_BAR")
            opens = [row.get("openTime") for row in (middle, bid, ask)]
            if len(set(opens)) != 1:
                raise ValueError("BID_ASK_TIME_MISMATCH")
            try:
                start = parse_utc(opens[0])
            except (ValueError, TypeError):
                raise ValueError("BID_ASK_INVALID_UTC") from None
            stamp = int(start.timestamp())
            if stamp % width or prior is not None and stamp <= prior:
                raise ValueError("BID_ASK_UNALIGNED_OR_UNORDERED")
            prior = stamp
            if any(not all(_price(row.get(k)) for k in ("open", "high", "low", "close"))
                   for row in (middle, bid, ask)):
                raise ValueError("BID_ASK_NON_NUMERIC")
            if any(row["high"] < max(row["open"], row["close"], row["low"])
                   or row["low"] > min(row["open"], row["close"], row["high"])
                   for row in (middle, bid, ask)):
                raise ValueError("BID_ASK_INVALID_OHLC")
            if (bid["open"] > ask["open"] or bid["close"] > ask["close"]
                    or bid["low"] > ask["low"] or bid["high"] > ask["high"]):
                raise ValueError("BID_ASK_CROSSED")
            if not (_close(middle["open"], (bid["open"] + ask["open"]) / 2)
                    and _close(middle["close"], (bid["close"] + ask["close"]) / 2)):
                raise ValueError("BID_ASK_MIDQUOTE_DISAGREES")
        counts[tf] = len(b)
    return counts


def review_eodhd_snapshot(snapshot: dict, as_of: dt.datetime, *,
                          policy: SourcePolicy | None = None,
                          evidence: IndependentEvidence | None = None,
                          context: dict | None = None,
                          allow_research_evaluation: bool = False) -> dict:
    """Offline staging only. Return WAIT even if a reviewed research candidate exists.

    Never pass credentials or a live broker account. True EODHD credentials are
    not read here. The default call never invokes any analysis engine.
    """
    now = parse_utc(as_of.isoformat())
    reasons = []
    if not isinstance(snapshot, dict):
        return _blocked(["INVALID_PRIVATE_SNAPSHOT"])
    if (snapshot.get("provider") != "EODHD" or snapshot.get("instrument") != "XAU/USD"
            or snapshot.get("mode") != "REVIEW_ONLY"
            or snapshot.get("quoteType") != "INDICATIVE_MIDQUOTE_OHLC"
            or snapshot.get("signal") != "WAIT" or snapshot.get("executable") is not False
            or snapshot.get("researchEligible") is not False
            or snapshot.get("readyForTrading") is not False):
        return _blocked(["SOURCE_IDENTITY_OR_RESEARCH_CONTRACT_INVALID"])
    try:
        counts = _audit_bars(snapshot)
    except ValueError as error:
        return _blocked([str(error)])
    if not isinstance(snapshot.get("latestQuote"), dict):
        reasons.append("BID_ASK_QUOTE_MISSING")
    else:
        quote = snapshot["latestQuote"]
        if not (_price(quote.get("bid")) and _price(quote.get("ask"))
                and quote["ask"] >= quote["bid"]):
            reasons.append("BID_ASK_QUOTE_INVALID")
        try:
            quote_utc = parse_utc(quote.get("timeUTC"))
            age = (now - quote_utc).total_seconds()
            if age < -5 or age > MAX_TICK_AGE_SECONDS:
                reasons.append("QUOTE_STALE_OR_FUTURE")
        except (TypeError, ValueError):
            reasons.append("QUOTE_UTC_INVALID")
    if policy is None or not policy.authorized or policy.expected_provider != "EODHD":
        reasons.append("SOURCE_RIGHTS_OR_PROVIDER_APPROVAL_MISSING")
    if evidence is None or not evidence.complete:
        reasons.append("INDEPENDENT_SESSION_HISTORY_OR_CLOCK_EVIDENCE_MISSING")
    if any(counts[tf] < MIN_WARMUP_BARS[tf] for tf in INTERVALS):
        reasons.append("INDICATOR_HISTORY_WARMUP_INSUFFICIENT")
    if not allow_research_evaluation:
        reasons.append("RESEARCH_EVALUATION_NOT_APPROVED")
    if not isinstance(context, dict) or not isinstance(context.get("v3Feeds"), dict) or not isinstance(context.get("r2Feeds"), dict):
        reasons.append("SEPARATE_RESEARCH_CONTEXT_MISSING")
    if reasons:
        return _blocked(reasons, counts)
    # Independent schedule, not a self-declared snapshot list, is mandatory.
    # Use BID OHLC for the analytical candle convention, never midquote OHLC.
    frames = {}
    for tf, interval in INTERVALS.items():
        frames[interval] = {"candles": snapshot["bidFrames"][tf],
                            "expectedOpenTimes": evidence.expected_open_times[tf]}
        try:
            validate_frame(interval, frames[interval], now)
        except (ValueError, TypeError) as error:
            return _blocked(["INDEPENDENT_SESSION_OR_CLOSED_CANDLES_REJECTED:" + str(error)], counts)
    if "spread" not in context or "risk" not in context:
        return _blocked(["BROKER_SPREAD_OR_RISK_CONTEXT_MISSING"], counts)
    payload = {
        "provider": "EODHD", "instrument": "XAU/USD", "mode": "live",
        "receivedUTC": now.isoformat().replace("+00:00", "Z"),
        "frames": frames,
    }
    result = run_research_pipeline(payload, now, policy, context)
    if result.get("signal") != "WAIT" or result.get("executable") is not False:
        return _blocked(["RESEARCH_ENGINE_CONTRACT_VIOLATION"], counts)
    # No auto-trading, even when a research-only candidate exists.
    return {
        "status": result.get("status", "WAIT_ENGINE_UNKNOWN"),
        "signal": "WAIT", "executable": False,
        "researchEligible": bool(result.get("researchEligible", False)),
        "researchCandidate": result.get("researchCandidate", "NONE"),
        "engineStatus": result.get("engines", {}).get("v3", "UNKNOWN"),
        "paperStatus": "NOT_CONNECTED_TO_BROKER",
        "closedBarCounts": counts,
        "blockingReasons": result.get("intake", {}).get("blockingReasons", []),
        "sourceRequestsMade": 0, "providerConnectionStarted": False,
        "dataConvention": "INDICATIVE_EODHD_BID_OHLC_RESEARCH_ONLY",
        "engineReview": result,
    }
