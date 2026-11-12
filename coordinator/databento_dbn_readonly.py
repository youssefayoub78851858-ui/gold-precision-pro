"""Read-only conversion of local DBN files through Databento's official SDK.

This adapter deliberately emits a quarantined inspection envelope only.  It
does not certify data rights/continuity, create research feeds, or call signal
or trading engines.
"""
from __future__ import annotations

import hashlib
import warnings
from pathlib import Path


SUPPORTED_SCHEMAS = {"trades", "mbo", "mbp-10"}
PRICE_SCALE = 1_000_000_000


def _native(value):
    """Convert SDK/DataFrame scalar wrappers to plain Python values."""
    if value is None:
        return None
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except (TypeError, ValueError):
            pass
    return value


def decode_dbn_bytes(raw: bytes, *, source_name: str = "<memory>", expected_sha256: str | None = None) -> dict:
    """Decode one local DBN byte stream; malformed/incomplete streams fail closed."""
    if not isinstance(raw, bytes) or len(raw) < 8 or not raw.startswith(b"DBN"):
        raise ValueError("DBN_HEADER_INVALID")
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("DBN_SHA256_MISMATCH")

    try:
        import databento as db
        from databento.common.error import BentoWarning
    except ImportError as error:
        raise RuntimeError("Install the pinned official Databento SDK to decode DBN") from error

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            store = db.DBNStore.from_bytes(raw)
            schema = getattr(store.schema, "value", store.schema)
            schema = str(schema).lower()
            if schema not in SUPPORTED_SCHEMAS:
                raise ValueError("DBN_SCHEMA_UNSUPPORTED")
            # Fixed-point integer prices preserve the source's exact 1e-9 units.
            frame = store.to_df(price_type="fixed", pretty_ts=False, map_symbols=False)
        if any(issubclass(item.category, BentoWarning) for item in caught):
            raise ValueError("DBN_INCOMPLETE_OR_TRUNCATED")
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("DBN_DECODE_FAILED") from error

    if not len(frame):
        raise ValueError("DBN_EMPTY_RECORDS")
    rows = [
        {str(key): _native(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]
    metadata = store.metadata
    return {
        "format": "DBN",
        "source": {
            "filename": str(source_name),
            "sha256": digest,
            "byteLength": len(raw),
            "dataset": store.dataset,
            "schema": schema,
            "dbnVersion": int(metadata.version),
            "symbols": list(store.symbols or []),
            "stypeIn": str(getattr(store.stype_in, "value", store.stype_in)),
            "stypeOut": str(getattr(store.stype_out, "value", store.stype_out)),
            "startUTC": store.start.isoformat() if store.start is not None else None,
            "endUTC": store.end.isoformat() if store.end is not None else None,
            "priceEncoding": "FIXED_1E9",
        },
        "rows": rows,
        "rowCount": len(rows),
        "dataOrigin": "UPSTREAM_SOFTWARE_TEST_FIXTURE",
        "testFixtureOnly": True,
        "researchEligible": False,
        "feedEmitted": False,
        "signal": "WAIT",
        "executable": False,
    }


def decode_dbn_file(path: str | Path, *, expected_sha256: str | None = None) -> dict:
    file = Path(path)
    return decode_dbn_bytes(file.read_bytes(), source_name=file.name, expected_sha256=expected_sha256)
