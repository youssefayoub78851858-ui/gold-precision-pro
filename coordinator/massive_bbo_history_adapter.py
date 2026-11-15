"""Offline Massive C:XAUUSD historical BBO quote-to-closed-bar adapter.

Consumes ONLY a local, synthetic normalized fixture with the REST /v3/quotes
field names (bid_price, ask_price, participant_timestamp in Unix nanoseconds).
No HTTP, secrets, vendor or broker calls. This is NOT a paid quote entitlement
test and never authorizes research, simulated execution or real trading.

A historical BBO quote is not an exchange trade and has no aggressor volume.
Each closed M15 needs near-opening and near-closing quotes, and no gap over
90 seconds. Groups that fail are dropped, never filled with made-up prices.
H1 and H4 are assembled only from 4 or 16 complete, UTC-aligned M15 bars.
"""
from __future__ import annotations

import datetime as dt
import math
import re

UTC = dt.timezone.utc
SYMBOL = "C:XAUUSD"
MAX_QUOTES = 250000
M15_SECONDS = 900
MAX_SILENCE_SECONDS = 90
OPEN_END_TOLERANCE_SECONDS = 60


def _utc(value: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError("INDEPENDENT_ASOF_UTC_REQUIRED")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("INDEPENDENT_ASOF_UTC_REQUIRED") from exc
    if parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("INDEPENDENT_ASOF_UTC_REQUIRED")
    return parsed.astimezone(UTC)


def _decode_quote(row: dict, cutoff_ns: int) -> dict:
    if not isinstance(row, dict):
        raise ValueError("BBO_QUOTE_OBJECT_REQUIRED")
    stamp = row.get("participant_timestamp")
    if isinstance(stamp, bool) or not isinstance(stamp, (int, str)):
        raise ValueError("BBO_UNIX_NS_REQUIRED")
    raw = str(stamp)
    if not re.fullmatch(r"[1-9]\d{18}", raw):
        raise ValueError("BBO_UNIX_NS_REQUIRED")
    ns = int(raw)
    if ns >= cutoff_ns:
        raise ValueError("BBO_FUTURE_OR_UNCLOSED_QUOTE")
    prices = [row.get("bid_price"), row.get("ask_price")]
    if any(isinstance(x, bool) or not isinstance(x, (float, int))
           or not math.isfinite(x) or x <= 0 for x in prices):
        raise ValueError("BBO_PRICE_INVALID")
    bid, ask = map(float, prices)
    if bid > ask:
        raise ValueError("BBO_CROSSED_MARKET")
    return {"ns": ns, "second": ns // 1000000000,
            "bid": bid, "ask": ask, "mid": (bid + ask) / 2}


def _candle(start: int, quotes: list[dict], key: str) -> dict:
    values = [q[key] for q in quotes]
    return {"openTime": dt.datetime.fromtimestamp(start, tz=UTC).isoformat().replace("+00:00", "Z"),
            "open": values[0], "high": max(values),
            "low": min(values), "close": values[-1]}


def _aggregate(bars: list[dict], n: int) -> list[dict]:
    width = n * M15_SECONDS
    groups: dict[int, list[dict]] = {}
    for bar in bars:
        opened = int(dt.datetime.fromisoformat(bar["openTime"].replace("Z", "+00:00")).timestamp())
        bucket = opened // width * width
        groups.setdefault(bucket, []).append(bar)
    result = []
    for bucket, entries in sorted(groups.items()):
        opens = [int(dt.datetime.fromisoformat(x["openTime"].replace("Z", "+00:00")).timestamp()) for x in entries]
        if len(entries) != n or opens != [bucket + i * M15_SECONDS for i in range(n)]:
            continue
        result.append({"openTime": entries[0]["openTime"],
                       "open": entries[0]["open"], "high": max(x["high"] for x in entries),
                       "low": min(x["low"] for x in entries), "close": entries[-1]["close"]})
    return result


def review_synthetic_massive_bbo(payload: dict, *, as_of_utc: str) -> dict:
    """Build fully closed synthetic BID/ASK/MID M15/H1/H4; always WAIT.

    The API's timestamp alone cannot prove session closures, historical access,
    realtime parity, rights on Render or exchange execution costs.
    """
    if not isinstance(payload, dict) or set(payload) != {"ticker", "sourceDataMode", "results"}:
        raise ValueError("OFFLINE_FIXTURE_WRAPPER_REQUIRED")
    if payload["ticker"] != SYMBOL or payload["sourceDataMode"] != "SYNTHETIC_TEST_ONLY":
        raise ValueError("UNVERIFIED_PROVIDER_OR_REAL_MARKET_DATA_REJECTED")
    as_of = _utc(as_of_utc)
    rows = payload["results"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_QUOTES:
        raise ValueError("BBO_QUOTE_COUNT_INVALID")
    cutoff_ns = int(as_of.timestamp()) * 1000000000
    quotes = [_decode_quote(row, cutoff_ns) for row in rows]
    if any(quotes[i]["ns"] <= quotes[i - 1]["ns"] for i in range(1, len(quotes))):
        raise ValueError("BBO_REPLAY_DUPLICATE_OR_REVERSED")

    groups: dict[int, list[dict]] = {}
    for quote in quotes:
        slot = quote["second"] // M15_SECONDS * M15_SECONDS
        groups.setdefault(slot, []).append(quote)

    bid_bars, ask_bars, mid_bars = [], [], []
    discarded = 0
    for slot, sample in sorted(groups.items()):
        # Do not treat quote timestamps as independent proof of market hours.
        # The last quote of an interval is insufficient to close it on its own.
        if (slot + M15_SECONDS > int(as_of.timestamp())
                or sample[0]["second"] - slot > OPEN_END_TOLERANCE_SECONDS
                or slot + M15_SECONDS - sample[-1]["second"] > OPEN_END_TOLERANCE_SECONDS
                or any(sample[i]["second"] - sample[i - 1]["second"] > MAX_SILENCE_SECONDS
                       for i in range(1, len(sample)))):
            discarded += 1
            continue
        bid_bars.append(_candle(slot, sample, "bid"))
        ask_bars.append(_candle(slot, sample, "ask"))
        mid_bars.append(_candle(slot, sample, "mid"))

    def frames(base: list[dict]) -> dict:
        return {"M15": base, "H1": _aggregate(base, 4), "H4": _aggregate(base, 16)}

    bid, ask, mid = frames(bid_bars), frames(ask_bars), frames(mid_bars)
    missing_intervals = sum(
        int(dt.datetime.fromisoformat(b["openTime"].replace("Z", "+00:00")).timestamp()) -
        int(dt.datetime.fromisoformat(a["openTime"].replace("Z", "+00:00")).timestamp()) != M15_SECONDS
        for a, b in zip(mid_bars, mid_bars[1:])
    )
    return {"mode": "OFFLINE_SYNTHETIC_MASSIVE_BBO_REVIEW",
            "provider": "Massive", "ticker": SYMBOL, "priceBasis": "QUOTE_BID_ASK",
            "sourceDataMode": "SYNTHETIC_TEST_ONLY", "signal": "WAIT",
            "executable": False, "researchEligible": False,
            "liveDataValidated": False, "marketHistoryVerified": False,
            "licenseVerified": False, "independentSessionCalendarVerified": False,
            "sameFeedRealtimeParityVerified": False, "paperOrdersAllowed": False,
            "quoteActivityIsExecutedVolume": False, "gcOrderFlowAvailable": False,
            "sourceRequestsMade": 0, "secretReads": 0, "payments": 0,
            "quotesValidated": len(quotes), "incompleteM15Discarded": discarded,
            "unverifiedM15Discontinuities": missing_intervals,
            "completeClosedBarCounts": {tf: len(mid[tf]) for tf in ("M15", "H1", "H4")},
            "minimumClosed50H4MetBySyntheticGeometry": len(mid["H4"]) >= 50,
            "bidFrames": bid, "askFrames": ask, "midFrames": mid,
            "blockingReasons": [
                "SYNTHETIC_QUOTES_CANNOT_PROVE_MARKET_HISTORY",
                "HISTORICAL_BBO_ENTITLEMENT_AND_CLOUD_LICENSE_UNVERIFIED",
                "REALTIME_QUOTE_SOURCE_AND_SESSION_PARITY_UNVERIFIED",
                "GC_DXY_NEWS_AND_BROKER_COSTS_NOT_VERIFIED"]}


if __name__ == "__main__":
    raise SystemExit("Offline library only; do not run provider/network clients")
