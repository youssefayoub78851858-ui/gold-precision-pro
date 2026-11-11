"""Offline structural preflight for normalized GC MBO / MBP exports.

This is deliberately not a Databento DBN decoder or a live connector. It accepts
normalized JSON rows (ISO-UTC or exact UNIX-ns ``ts_event``; MBO action, side,
order_id, price and size; MBP sequence and ordered [price, size] bid/ask levels)
so local fixture tooling can be checked without contacting a provider. A
passing synthetic fixture never becomes market evidence; no strategy feed,
trade delta, continuity attestation or execution signal is emitted.
"""
from __future__ import annotations

import json
import math
import pathlib

from recorded_utils import ns


SCHEMAS = {"mbo", "mbp-1", "mbp-10"}
MBO_ACTIONS = {"ADD", "CANCEL", "MODIFY", "CLEAR", "TRADE"}
SIDES = {"B", "A", "N"}


def _number(value, *, positive=False):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and (not positive or value > 0))


def _stamp(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return ns(value, "UNIX_NS")
    if isinstance(value, str) and value.isdigit():
        return ns(value, "UNIX_NS")
    return ns(value)


def _validate_mbo(row):
    required = {"ts_event", "sequence", "action", "side", "order_id", "price", "size"}
    if not isinstance(row, dict) or not required.issubset(row):
        raise ValueError("MBO_ROW_FIELDS")
    if row["action"] not in MBO_ACTIONS or row["side"] not in SIDES:
        raise ValueError("MBO_ACTION_OR_SIDE")
    if not isinstance(row["sequence"], int) or isinstance(row["sequence"], bool) or row["sequence"] < 1:
        raise ValueError("MBO_SEQUENCE")
    if row["action"] != "CLEAR":
        order_id = row["order_id"]
        if (not isinstance(order_id, (str, int)) or isinstance(order_id, bool)
                or not str(order_id)):
            raise ValueError("MBO_ORDER_ID")
    if row["action"] == "CLEAR":
        if row["price"] is not None or row["size"] != 0:
            raise ValueError("MBO_CLEAR_SHAPE")
    elif not _number(row["price"], positive=True) or not _number(row["size"], positive=True):
        raise ValueError("MBO_PRICE_SIZE")


def _validate_mbp(row, schema):
    if not isinstance(row, dict) or not {"ts_event", "sequence", "bids", "asks"}.issubset(row):
        raise ValueError("MBP_ROW_FIELDS")
    if not isinstance(row["sequence"], int) or isinstance(row["sequence"], bool) or row["sequence"] < 1:
        raise ValueError("MBP_SEQUENCE")
    bids, asks = row["bids"], row["asks"]
    if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
        raise ValueError("MBP_EMPTY_BOOK")
    limit = 1 if schema == "mbp-1" else 10
    if len(bids) > limit or len(asks) > limit:
        raise ValueError("MBP_DEPTH_EXCEEDED")
    for side in (bids, asks):
        if any(not isinstance(level, list) or len(level) != 2 or
               not _number(level[0], positive=True) or not _number(level[1], positive=True)
               for level in side):
            raise ValueError("MBP_LEVEL")
    if any(bids[i][0] <= bids[i + 1][0] for i in range(len(bids) - 1)):
        raise ValueError("MBP_BIDS_ORDER")
    if any(asks[i][0] >= asks[i + 1][0] for i in range(len(asks) - 1)):
        raise ValueError("MBP_ASKS_ORDER")
    if bids[0][0] >= asks[0][0]:
        raise ValueError("MBP_CROSSED_BOOK")


def validate_rows(schema, rows, as_of_utc):
    """Validate normalized fixture rows; return only structural QA metadata."""
    if schema not in SCHEMAS or not isinstance(rows, list) or not rows:
        raise ValueError("SCHEMA_OR_ROWS")
    cutoff = _stamp(as_of_utc)
    previous_ts = -1
    previous_sequence = -1
    for row in rows:
        if schema == "mbo":
            _validate_mbo(row)
        else:
            _validate_mbp(row, schema)
        timestamp = _stamp(row["ts_event"])
        if timestamp <= previous_ts:
            raise ValueError("DUPLICATE_OR_REVERSED_EVENT_TIME")
        if timestamp > cutoff:
            raise ValueError("FUTURE_EVENT")
        if row["sequence"] <= previous_sequence:
            raise ValueError("DUPLICATE_OR_REVERSED_SEQUENCE")
        previous_ts, previous_sequence = timestamp, row["sequence"]
    return {
        "schema": schema,
        "rowsValidated": len(rows),
        "status": "SYNTHETIC_TEST_ONLY",
        "researchEligible": False,
        "feedEmitted": False,
        "orderFlow": "UNAVAILABLE",
        "signal": "WAIT",
        "executable": False,
        "providerRequestsMade": 0,
    }


def validate_fixture_file(path, as_of_utc):
    """Load local normalized JSON explicitly tagged as a synthetic fixture."""
    file = pathlib.Path(path)
    payload = json.loads(file.read_text())
    if not isinstance(payload, dict) or payload.get("dataOrigin") != "SYNTHETIC_TEST_ONLY":
        raise ValueError("SYNTHETIC_FIXTURE_TAG_REQUIRED")
    return validate_rows(payload.get("schema"), payload.get("rows"), as_of_utc)


if __name__ == "__main__":
    raise SystemExit("Library-only helper; use validate_fixture_file from offline tests")
