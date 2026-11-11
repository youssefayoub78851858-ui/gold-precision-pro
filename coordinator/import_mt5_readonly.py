"""Validate a local, read-only MT5 closed-bar snapshot for private research.

No network access, broker credentials, order operations, or public upload. The
terminal's broker clock offset is applied as supplied by the exporter, but its
historical/DST correctness is not authenticated. Output is always WAIT.
"""
import argparse
import csv
import datetime as dt
import io
import json
import math
import pathlib

UTC = dt.timezone.utc
BAR_SECONDS = 900
HOUR_BARS = 4
FOUR_HOUR_BARS = 16
REQUIRED = {
    "symbol", "timeframe", "bar_open_server", "server_utc_offset_minutes",
    "observed_utc", "open", "high", "low", "close", "tick_volume",
    "real_volume", "spread_points",
}


def parse_utc(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("UTC timestamp required")
    parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("explicit UTC timestamp required")
    return parsed.astimezone(UTC)


def parse_server_time(value):
    try:
        parsed = dt.datetime.strptime(value.strip(), "%Y-%m-%dT%H:%M")
    except (TypeError, ValueError) as exc:
        raise ValueError("broker server bar time must use YYYY-MM-DDTHH:MM") from exc
    return parsed.replace(tzinfo=None)


def _finite_positive(value, label):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {label}") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"invalid {label}")
    return result


def normalize_snapshot(csv_text, expected_symbol, as_of_utc, max_age_minutes=20):
    as_of = parse_utc(as_of_utc)
    if not isinstance(max_age_minutes, (int, float)) or not math.isfinite(max_age_minutes) or not 1 <= max_age_minutes <= 1440:
        raise ValueError("max_age_minutes must be between 1 and 1440")
    if not expected_symbol or len(expected_symbol) > 40:
        raise ValueError("exact broker symbol must be supplied")
    if not isinstance(csv_text, str) or len(csv_text) > 12_000_000:
        raise ValueError("CSV unavailable or exceeds 12 MB research limit")
    reader = csv.DictReader(io.StringIO(csv_text))
    columns = {str(name or "").strip().lower() for name in (reader.fieldnames or [])}
    if not REQUIRED.issubset(columns):
        raise ValueError("MT5 CSV header is incomplete")

    grouped, observations, offsets, seen = [], set(), set(), set()
    previous = None
    for line, row in enumerate(reader, start=2):
        if row.get("symbol") != expected_symbol:
            raise ValueError(f"row {line}: symbol differs from confirmed chart symbol")
        if row.get("timeframe") != "M15":
            raise ValueError(f"row {line}: only M15 input is accepted")
        try:
            observed = parse_utc(row["observed_utc"])
            offset = int(row["server_utc_offset_minutes"])
            server_open = parse_server_time(row["bar_open_server"])
            prices = [_finite_positive(row[k], k) for k in ("open", "high", "low", "close")]
            tick_volume = int(row["tick_volume"])
            real_volume = int(row["real_volume"])
            spread_points = int(row["spread_points"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"row {line}: {exc}") from exc
        if offset < -840 or offset > 840 or offset % 15:
            raise ValueError(f"row {line}: invalid server UTC offset")
        if observed > as_of or as_of - observed > dt.timedelta(minutes=5):
            raise ValueError(f"row {line}: snapshot observation time is future or stale")
        observations.add(observed)
        offsets.add(offset)
        opened = (server_open - dt.timedelta(minutes=offset)).replace(tzinfo=UTC)
        if int(opened.timestamp()) % BAR_SECONDS:
            raise ValueError(f"row {line}: M15 open is not UTC aligned after offset conversion")
        if opened + dt.timedelta(seconds=BAR_SECONDS) > observed:
            raise ValueError(f"row {line}: forming or future M15 bar is not admissible")
        if opened + dt.timedelta(seconds=BAR_SECONDS) > as_of:
            raise ValueError(f"row {line}: bar has not closed at the requested snapshot time")
        o, h, low, close = prices
        if low > min(o, close) or h < max(o, close) or low > h:
            raise ValueError(f"row {line}: invalid OHLC range")
        if min(tick_volume, real_volume, spread_points) < 0:
            raise ValueError(f"row {line}: negative volume or spread")
        if tick_volume == 0:
            raise ValueError(f"row {line}: empty tick-volume bar")
        if previous is not None and opened <= previous:
            raise ValueError(f"row {line}: duplicate or unordered bar")
        key = opened.isoformat()
        if key in seen:
            raise ValueError(f"row {line}: duplicate M15 bar")
        seen.add(key)
        previous = opened
        grouped.append({"datetime": opened.isoformat().replace("+00:00", "Z"),
                        "open": o, "high": h, "low": low, "close": close,
                        "tickVolume": tick_volume, "realVolume": real_volume,
                        "spreadPoints": spread_points})
    if not grouped:
        raise ValueError("no closed M15 bars")
    if len(observations) != 1 or len(offsets) != 1:
        raise ValueError("snapshot must have one observation time and one server offset")

    def aggregate(width):
        seconds = width * BAR_SECONDS
        bins = {}
        for bar in grouped:
            moment = parse_utc(bar["datetime"])
            start = int(moment.timestamp()) // seconds * seconds
            bins.setdefault(start, []).append((moment, bar))
        result, incomplete = [], 0
        for start, rows in sorted(bins.items()):
            rows.sort(key=lambda x: x[0])
            expected = [start + i * BAR_SECONDS for i in range(width)]
            actual = [int(moment.timestamp()) for moment, _ in rows]
            if actual != expected:
                incomplete += 1
                continue
            bars = [bar for _, bar in rows]
            result.append({"datetime": dt.datetime.fromtimestamp(start, UTC).isoformat().replace("+00:00", "Z"),
                           "open": bars[0]["open"], "high": max(x["high"] for x in bars),
                           "low": min(x["low"] for x in bars), "close": bars[-1]["close"],
                           "tickVolume": sum(x["tickVolume"] for x in bars),
                           "realVolume": sum(x["realVolume"] for x in bars),
                           "spreadPoints": max(x["spreadPoints"] for x in bars)})
        return result, incomplete

    h1, incomplete_h1 = aggregate(HOUR_BARS)
    h4, incomplete_h4 = aggregate(FOUR_HOUR_BARS)
    last_close = parse_utc(grouped[-1]["datetime"]) + dt.timedelta(seconds=BAR_SECONDS)
    age_minutes = max(0.0, (as_of - last_close).total_seconds() / 60.0)
    minimum_history = 60
    enough = len(grouped) >= minimum_history and len(h1) >= minimum_history and len(h4) >= minimum_history
    fresh = age_minutes <= max_age_minutes
    output = {
        "mode": "MT5_LOCAL_READ_ONLY_RESEARCH",
        "source": "User-local MetaTrader 5 terminal export; origin and broker entitlement not independently authenticated",
        "symbol": expected_symbol,
        "signal": "WAIT", "executable": False, "trading": "disabled",
        "liveData": False, "networkEnabled": False, "publicRedistributionEnabled": False,
        "serverUtcOffsetMinutes": next(iter(offsets)), "historicalOffsetVerified": False,
        "volumeSemantics": "MT5 tick volume is not exchange-wide GC volume; realVolume retained as supplied, not independently validated",
        "asOfUTC": as_of.isoformat().replace("+00:00", "Z"),
        "observedUTC": next(iter(observations)).isoformat().replace("+00:00", "Z"),
        "lastClosedM15UTC": grouped[-1]["datetime"], "lastBarCloseAgeMinutes": round(age_minutes, 3),
        "closedCounts": {"M15": len(grouped), "H1": len(h1), "H4": len(h4)},
        "incompleteUTCGroups": {"H1": incomplete_h1, "H4": incomplete_h4},
        "quality": {"ordered": True, "duplicates": 0, "invalidOHLC": 0, "formingBarsExcluded": 0,
                    "offsetHistoryVerified": False, "entitlementVerified": False},
        "readiness": "FRESH_LOCAL_EXPORT_RESEARCH_ONLY" if fresh and enough else "WAIT_INSUFFICIENT_OR_STALE",
        "readyForTrading": False,
        "alerts": ["BROKER_UTC_OFFSET_HISTORY_UNVERIFIED", "BROKER_DATA_RIGHTS_NOT_VERIFIED"] +
                  ([] if fresh else ["XAU_EXPORT_STALE"]) +
                  ([] if enough else ["INSUFFICIENT_M15_H1_H4_HISTORY"]) +
                  (["INCOMPLETE_H1_H4_GROUPS"] if incomplete_h1 or incomplete_h4 else []),
        "frames": {"M15": grouped, "H1": h1, "H4": h4},
        "disclaimer": "Local/private research adapter only. Broker timestamps are normalized using the exporter offset; historical DST/offset changes and license terms must be verified before research use beyond this test. No upload or trading is performed."
    }
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv")
    p.add_argument("--symbol", required=True, help="Exact chart symbol, suffix included")
    p.add_argument("--as-of-utc", required=True)
    p.add_argument("--output", required=True, help="Private local derived JSON output")
    args = p.parse_args()
    text = pathlib.Path(args.csv).read_text(encoding="utf-8-sig")
    result = normalize_snapshot(text, args.symbol, args.as_of_utc)
    pathlib.Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("mode", "symbol", "signal", "executable", "readiness", "closedCounts", "alerts")}))


if __name__ == "__main__":
    main()
