"""Normalize one local Dukascopy XAUUSD BID M15 CSV into closed M15/H1/H4.

Offline/private-research only. No network calls, credentials, orders or publishing.
Source attribution must be recorded separately; this does not authenticate origins
or confer any redistribution license. Never fill missing bars or infer volume.
"""
import argparse
import csv
import datetime as dt
import io
import json
import math
import pathlib

UTC = dt.timezone.utc
MIN15 = 900
FRAMES = {"15min": 1, "1h": 4, "4h": 16}


def to_utc(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Missing timestamp")
    raw = value.strip()
    if raw.isdigit():
        number = int(raw)
        if number < 10**12 or number > 10**14:
            raise ValueError("Expected Unix milliseconds, not ambiguous epoch seconds")
        moment = dt.datetime.fromtimestamp(number / 1000, UTC)
    else:
        moment = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if moment.tzinfo is None or moment.utcoffset() != dt.timedelta(0):
            raise ValueError("Explicit UTC timestamps are mandatory")
    return moment.astimezone(UTC)


def normalize(csv_text, as_of_utc):
    now = to_utc(as_of_utc) if isinstance(as_of_utc, str) else as_of_utc
    if not isinstance(now, dt.datetime) or now.tzinfo is None or now.utcoffset() != dt.timedelta(0):
        raise ValueError("as_of must be timezone-aware UTC")
    if not isinstance(csv_text, str) or len(csv_text) > 6_000_000:
        raise ValueError("CSV unavailable or over offline size limit")
    reader = csv.DictReader(io.StringIO(csv_text))
    names = {name.strip().lower(): name for name in (reader.fieldnames or [])}
    required = ("timestamp", "open", "high", "low", "close")
    if not all(n in names for n in required):
        raise ValueError("Dukascopy M15 CSV header is missing timestamp/open/high/low/close")
    seen = set()
    bars, rejected_in_progress = [], 0
    previous = None
    for index, row in enumerate(reader, 1):
        try:
            moment = to_utc(row[names["timestamp"]])
            values = [float(row[names[k]]) for k in ("open", "high", "low", "close")]
        except (ValueError, TypeError, KeyError, OverflowError) as err:
            raise ValueError(f"Row {index}: invalid timestamp or OHLC") from err
        o, h, l, c = values
        if moment.timestamp() % MIN15 != 0 or moment.microsecond != 0:
            raise ValueError(f"Row {index}: not a UTC-aligned 15-minute open")
        if moment in seen or previous is not None and moment <= previous:
            raise ValueError(f"Row {index}: duplicate or unordered candle")
        if not all(math.isfinite(v) and v > 0 for v in values) or l > min(o, c) or h < max(o, c):
            raise ValueError(f"Row {index}: invalid OHLC range")
        seen.add(moment)
        previous = moment
        if moment + dt.timedelta(seconds=MIN15) > now:
            rejected_in_progress += 1
            continue
        bars.append((moment, o, h, l, c))
    if not bars:
        raise ValueError("No closed valid M15 bars")
    def frame_data(count):
        if count == 1:
            return [dict(datetime=moment.isoformat().replace("+00:00", "Z"),
                         open=o, high=h, low=l, close=c) for moment, o, h, l, c in bars]
        grouped = {}
        seconds = count * MIN15
        for bar in bars:
            start = int(bar[0].timestamp()) // seconds * seconds
            grouped.setdefault(start, []).append(bar)
        output = []
        for start, group in sorted(grouped.items()):
            if len(group) != count or any(int(b[0].timestamp()) != start + i * MIN15
                                          for i, b in enumerate(group)):
                continue
            output.append(dict(datetime=dt.datetime.fromtimestamp(start, UTC).isoformat().replace("+00:00", "Z"),
                               open=group[0][1], high=max(b[2] for b in group),
                               low=min(b[3] for b in group), close=group[-1][4]))
        return output
    frames = {name: frame_data(count) for name, count in FRAMES.items()}
    counts = {name: len(rows) for name, rows in frames.items()}
    research_minimum = all(n >= 60 for n in counts.values())
    return {
        "document": {
            "source": "Local Dukascopy XAUUSD BID M15 CSV; independently authenticated: NO",
            "symbol": "XAU/USD", "frames": frames
        },
        "report": {
            "mode": "OFFLINE_DUKASCOPY_PRIVATE_RESEARCH",
            "asOfUTC": now.isoformat().replace("+00:00", "Z"),
            "sourceConvention": "BID; M15 UTC open timestamp",
            "closedCounts": counts,
            "excludedNotYetClosed": rejected_in_progress,
            "firstM15UTC": frames["15min"][0]["datetime"],
            "lastM15UTC": frames["15min"][-1]["datetime"],
            "minimumForExistingHistoricalValidator": research_minimum,
            "sourceIndependentlyAuthenticated": False,
            "rightsToRedistributeVerified": False,
            "readyForTrading": False,
            "signal": "WAIT",
            "filledMissingBars": 0,
            "requires": "Private provenance/entitlement validation and market-quality checks before research conclusions. No live service."
        }
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv")
    p.add_argument("--as-of-utc", required=True)
    p.add_argument("--report", required=True, help="Output only derived readiness metadata")
    p.add_argument("--private-json", help="Optional private local OHLC file, never commit or host publicly")
    args = p.parse_args()
    source = pathlib.Path(args.csv).read_text(encoding="utf-8-sig")
    result = normalize(source, args.as_of_utc)
    pathlib.Path(args.report).write_text(json.dumps(result["report"], indent=2) + "\n")
    if args.private_json:
        pathlib.Path(args.private_json).write_text(json.dumps(result["document"]) + "\n")
    print(json.dumps(result["report"]))


if __name__ == "__main__":
    main()
