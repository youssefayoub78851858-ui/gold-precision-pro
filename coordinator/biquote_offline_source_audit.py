"""Offline BiQuote XAUUSD bid/ask and multi-timeframe OHLC intake audit.

Accepts externally supplied JSON envelopes only. No HTTP, WebSocket, credentials,
trading, paper order creation or changes to production services.
BiQuote describes MT5/Yahoo/tick-derived OHLC, but does not state a guaranteed
bid/ask candle basis or grant underlying-feed cloud-algorithm rights here.
Passing structural checks is NOT market-data, licence or profitability proof.
"""
from __future__ import annotations

import datetime as dt
import math

UTC = dt.timezone.utc
FRAMES = {"M15": ("15m", 900), "H1": ("1h", 3600), "H4": ("4h", 14400)}
MIN_CLOSED = {"M15": 50, "H1": 50, "H4": 50}
LIMIT = 1000
MAX_QUOTE_AGE_SECONDS = 30
STATIC_BLOCKERS = (
    "BIQUOTE_UPSTREAM_MT5_DATA_RIGHTS_FOR_PRIVATE_RENDER_NOT_CONFIRMED",
    "BIQUOTE_HISTORICAL_OHLC_PRICE_BASIS_VS_LIVE_BID_ASK_UNCONFIRMED",
    "BIQUOTE_INDEPENDENT_SESSION_AND_DATA_PROVENANCE_NOT_VERIFIED",
    "BIQUOTE_ONGOING_AVAILABILITY_AND_REAL_PRICE_PARITY_NOT_VERIFIED",
)


def _utc(value):
    if not isinstance(value, str) or not value:
        raise ValueError("UTC_ISO_TIMESTAMP_REQUIRED")
    try:
        parsed = dt.datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
    except ValueError:
        raise ValueError("INVALID_UTC_TIMESTAMP") from None
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta():
        raise ValueError("UTC_OFFSET_REQUIRED")
    return parsed.astimezone(UTC)


def _price(value):
    return (type(value) in (float, int) and math.isfinite(value)
            and value > 0)


def _bar(row, width, now):
    if not isinstance(row, dict) or type(row.get("isOpen")) is not bool:
        raise ValueError("MALFORMED_BAR_OR_MISSING_OPEN_FLAG")
    start = _utc(row.get("openTime"))
    stamp = start.timestamp()
    if start.microsecond or stamp % width:
        raise ValueError("UNALIGNED_OR_SUBSECOND_CANDLE_OPEN")
    if start > now:
        raise ValueError("FUTURE_CANDLE_OPEN")
    if not row["isOpen"] and start + dt.timedelta(seconds=width) > now:
        raise ValueError("CLOSED_BAR_IN_FUTURE")
    keys = ("open", "high", "low", "close")
    if not all(_price(row.get(k)) for k in keys):
        raise ValueError("INVALID_OHLC_PRICE")
    if (row["high"] < max(row["open"], row["close"], row["low"])
            or row["low"] > min(row["open"], row["close"], row["high"])):
        raise ValueError("INVALID_OHLC_EXTREMA")
    if (type(row.get("tickVolume")) is not int
            or row["tickVolume"] < 0):
        raise ValueError("INVALID_TICK_VOLUME")
    # Tick volume is NOT COMEX traded contracts. Real volume may be zero.
    if (type(row.get("volume")) not in (int, float)
            or not math.isfinite(row["volume"]) or row["volume"] < 0):
        raise ValueError("INVALID_REPORTED_VOLUME")
    return start


def _frame(envelope, interval, width, now):
    if not isinstance(envelope, dict):
        raise ValueError("MISSING_OHLC_ENVELOPE")
    if envelope.get("symbol") != "XAUUSD" or envelope.get("interval") != interval:
        raise ValueError("SYMBOL_OR_INTERVAL_MISMATCH")
    bars = envelope.get("bars")
    if not isinstance(bars, list) or not 0 < len(bars) <= LIMIT:
        raise ValueError("OHLC_ARRAY_MISSING_OR_TOO_LARGE")
    closed = {}
    previous = None
    for index, row in enumerate(bars):
        stamp = _bar(row, width, now)
        if previous is not None and stamp >= previous:
            raise ValueError("CANDLES_NOT_NEWEST_FIRST_OR_DUPLICATED")
        previous = stamp
        if row["isOpen"]:
            if index != 0:
                raise ValueError("OPEN_CANDLE_NOT_FIRST")
            continue
        closed[int(stamp.timestamp())] = row
    return closed


def _close(a, b):
    return math.isclose(a, b, rel_tol=1e-8, abs_tol=1e-5)


def _compare_aggregates(m15, higher, width):
    if not m15 or not higher:
        return
    count = width // 900
    for start, actual in higher.items():
        members = [m15.get(start + k * 900) for k in range(count)]
        if any(member is None for member in members):
            continue  # Missing inputs are not fabricated or counted as parity.
        expected = {
            "open": members[0]["open"],
            "high": max(m["high"] for m in members),
            "low": min(m["low"] for m in members),
            "close": members[-1]["close"],
        }
        if any(not _close(actual[k], expected[k]) for k in expected):
            raise ValueError("CROSS_TIMEFRAME_OHLC_MISMATCH")


def audit_biquote_sample(quote, frame_envelopes, *, now):
    """Deterministic mock/raw snapshot inspection; always WAIT and no execution.

    Independent source authorization must be assessed outside this envelope.
    A provider response must NEVER authorize its own licence.
    """
    if not isinstance(now, dt.datetime) or now.tzinfo is None or now.utcoffset() != dt.timedelta():
        raise ValueError("Independent UTC observation clock required")
    now = now.astimezone(UTC)
    problems = []
    counts = {name: 0 for name in FRAMES}
    quality = False
    quote_age = None
    if not isinstance(quote, dict) or quote.get("symbol") != "XAUUSD":
        problems.append("INVALID_XAUUSD_QUOTE")
    else:
        try:
            bid, ask = quote.get("bid"), quote.get("ask")
            if not _price(bid) or not _price(ask) or ask < bid:
                raise ValueError("INVALID_OR_CROSSED_BID_ASK")
            if quote.get("stale") is True:
                raise ValueError("PROVIDER_REPORTS_STALE_QUOTE")
            tick_time = _utc(quote.get("timestamp"))
            quote_age = round((now - tick_time).total_seconds(), 3)
            if quote_age < -5 or quote_age > MAX_QUOTE_AGE_SECONDS:
                raise ValueError("INDEPENDENT_QUOTE_CLOCK_FRESHNESS_FAILED")
        except (ValueError, TypeError, OverflowError) as error:
            problems.append(str(error))
    if not isinstance(frame_envelopes, dict) or set(frame_envelopes) != set(FRAMES):
        problems.append("THREE_FRAMES_REQUIRED")
    else:
        try:
            verified = {}
            for name, (interval, width) in FRAMES.items():
                verified[name] = _frame(frame_envelopes[name], interval, width, now)
                counts[name] = len(verified[name])
            _compare_aggregates(verified["M15"], verified["H1"], 3600)
            _compare_aggregates(verified["M15"], verified["H4"], 14400)
            quality = True
            for name in MIN_CLOSED:
                if counts[name] < MIN_CLOSED[name]:
                    problems.append(name + "_INSUFFICIENT_CLOSED_HISTORY")
        except (ValueError, TypeError, OverflowError) as error:
            problems.append(str(error))
    return {
        "status": "WAIT_BIQUOTE_SOURCE_REVIEW",
        "signal": "WAIT",
        "executable": False,
        "researchEligible": False,
        "paperOrdersAllowed": False,
        "sourceRequestsMade": 0,
        "paymentsMade": 0,
        "independentSourceLicenceVerified": False,
        "sameFeedBidAskCandleBasisVerified": False,
        "priceParityAgainstBrokerVerified": False,
        "minimumClosedBars": dict(MIN_CLOSED),
        "closedBarCounts": counts,
        "quoteAgeSeconds": quote_age,
        "ohlcStructuralChecksPassed": quality,
        "blockingReasons": list(dict.fromkeys([*problems, *STATIC_BLOCKERS])),
        "tickVolumeIsExchangeTradedVolume": False,
        "mayMergeWithBrokerBidAskOrComexOrderFlow": False,
    }
