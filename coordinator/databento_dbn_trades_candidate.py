"""Local-only Databento DBN trades export candidate; never market authorization.

This is a narrow bridge between databento_dbn_readonly.decode_dbn_file() and
Databento's existing canonical recorded-CSV/JSON importer. It never calls an
API, authenticates, asserts continuity, or enables research/trading. A second,
independent rights/coverage manifest is mandatory before any importer use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from databento_dbn_readonly import decode_dbn_file

FIELDS = ("ts_event", "ts_recv", "publisher_id", "instrument_id", "sequence",
          "flags", "rtype", "action", "side", "price", "size")
DATED_GC = re.compile(r"^GC[FGHJKMNQUVXZ][0-9]{1,4}$")


def _integer(value, name, *, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"INVALID_{name.upper()}")
    return value


def prepare_candidate(decoded: dict) -> dict:
    """Preserve exact source fields; never transform a fixture into market proof."""
    if not isinstance(decoded, dict) or decoded.get("format") != "DBN":
        raise ValueError("OFFICIAL_DBN_DECODE_REQUIRED")
    source = decoded.get("source")
    if (not isinstance(source, dict) or source.get("dataset") != "GLBX.MDP3"
            or source.get("schema") != "trades" or source.get("priceEncoding") != "FIXED_1E9"
            or source.get("priceScale") != 1_000_000_000
            or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", "")))):
        raise ValueError("UNSUPPORTED_DBN_SOURCE")
    # The official read-only decoder deliberately labels all input quarantined.
    if (decoded.get("testFixtureOnly") is not True or decoded.get("researchEligible") is not False
            or decoded.get("feedEmitted") is not False or decoded.get("signal") != "WAIT"
            or decoded.get("executable") is not False):
        raise ValueError("QUARANTINE_CONTRACT_REQUIRED")
    rows = decoded.get("rows")
    if not isinstance(rows, list) or not rows or len(rows) != decoded.get("rowCount"):
        raise ValueError("DBN_ROWS_INVALID")
    normalized = []
    for row in rows:
        if not isinstance(row, dict) or any(key not in row for key in FIELDS):
            raise ValueError("DBN_TRADE_FIELDS_MISSING")
        for key in ("ts_event", "ts_recv", "publisher_id", "instrument_id", "sequence",
                    "flags", "rtype", "price", "size"):
            _integer(row[key], key, minimum=1 if key in ("ts_event", "ts_recv", "price", "size") else 0)
        if row["rtype"] != 0 or row["action"] != "T" or row["side"] not in ("B", "A", "N"):
            raise ValueError("DBN_NOT_CANONICAL_TRADE")
        if row["ts_recv"] < row["ts_event"]:
            raise ValueError("DBN_RECEPTION_BEFORE_EVENT")
        # Emit string nanoseconds and source fixed-point integers, not floats.
        normalized.append({key: str(row[key]) if key in ("ts_event", "ts_recv", "price")
                           else row[key] for key in FIELDS})
    symbols = source.get("symbols", [])
    if not isinstance(symbols, list) or any(not isinstance(s, str) for s in symbols):
        raise ValueError("DBN_SYMBOLS_INVALID")
    raw = (json.dumps(normalized, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
    return {
        "rows": normalized,
        "receipt": {
            "kind": "UNVERIFIED_LOCAL_DBN_TRADES_CANDIDATE",
            "dataset": source["dataset"], "schema": source["schema"],
            "sourceSHA256": source["sha256"],
            "rowsSHA256": hashlib.sha256(raw).hexdigest(),
            "rows": len(normalized), "symbols": symbols,
            "datedGCNameSeen": bool(symbols) and all(DATED_GC.fullmatch(s) for s in symbols),
            "symbolMappings": source.get("symbolMappings", {}),
            "dataOrigin": "UNVERIFIED_LOCAL_DBN",
            "rightsVerified": False, "continuityVerified": False,
            "instrumentMappingVerified": False,
            "actualGCMarketSampleVerified": False,
            "researchEligible": False, "feedEmitted": False,
            "signal": "WAIT", "executable": False,
            "nextStep": "Independently verify dated GC mapping, receipt, historical T+1 status, rights and window completeness using the existing manifest before canonical import."
        },
    }


def _exclusive_private_json(path: Path, data: object) -> None:
    # Never overwrite or expose licensed tick data via broad file permissions.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(data, output, separators=(",", ":"), ensure_ascii=True)
        output.write("\n")


def export_local_dbn(source_file: Path, output_rows: Path) -> dict:
    if output_rows.suffix != ".json":
        raise ValueError("JSON_OUTPUT_REQUIRED")
    receipt_file = output_rows.with_name(output_rows.stem + ".receipt.json")
    if output_rows.exists() or receipt_file.exists():
        raise FileExistsError("OUTPUT_ALREADY_EXISTS")
    payload = prepare_candidate(decode_dbn_file(source_file))
    _exclusive_private_json(output_rows, payload["rows"])
    try:
        _exclusive_private_json(receipt_file, payload["receipt"])
    except BaseException:
        output_rows.unlink(missing_ok=True)
        raise
    return {"status": "QUARANTINED_LOCAL_EXPORT", "rows": len(payload["rows"]),
            "receipt": str(receipt_file), "signal": "WAIT", "executable": False,
            "networkRequestsMade": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("local_dbn", type=Path)
    parser.add_argument("output_rows", type=Path)
    args = parser.parse_args()
    print(json.dumps(export_local_dbn(args.local_dbn, args.output_rows), sort_keys=True))
