"""Capital.com Demo synthetic-only PRIVATE page archive rehearsal.

This module has NO HTTP or broker credentials and cannot store real data.
It models durable storage for the future separately approved Demo GET collector:
owner-only pre-existing directory, bounded normalized BID/ASK closed bars,
atomic no-clobber publication, fsync, signed content, and restart checks.
Do not import this test-only writer as a live source or claim data rights.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import stat
import tempfile

from capital_demo_offline_adapter import (
    RESOLUTIONS, _normalize_row, audit_demo_get_only_request
)

MODE = "CAPITAL_DEMO_SYNTHETIC_PRIVATE_ARCHIVE_REHEARSAL_V1"
PREFIX = "capital-synthetic-page-"
MAX_BYTES = 700_000
UTC = dt.timezone.utc
WIDTHS = {x[0]: x[1] for x in RESOLUTIONS.values()}


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def _sha(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _stamp(value):
    if not isinstance(value, str) or re.fullmatch(
            r"20\d{2}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value) is None:
        raise ValueError("STRICT_UTC_RECEIPT_REQUIRED")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("STRICT_UTC_RECEIPT_REQUIRED")
    return parsed


def _directory(dirname):
    if not isinstance(dirname, (str, os.PathLike)):
        raise ValueError("OWNER_PRIVATE_DIR_REQUIRED")
    d = pathlib.Path(dirname)
    if not d.is_absolute() or ".." in d.parts or str(d) == "/" or d.resolve(strict=True) != d:
        raise ValueError("PRIVATE_DIRECTORY_CANONICAL_REQUIRED")
    st = d.lstat()
    if (not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode)
            or st.st_mode & 0o077 or st.st_uid != os.getuid()):
        raise ValueError("PRIVATE_DIRECTORY_OWNER_ONLY_REQUIRED")
    return d


def _page(chunk, page, observed_utc):
    if (not isinstance(chunk, dict) or
            set(chunk) != {"request", "firstExpectedOpenUTC", "expectedEndExclusiveUTC",
                           "expectedClosedSlots", "providerToBoundMayBeInclusive",
                           "responseWindowMustBeVerified"} or
            chunk["providerToBoundMayBeInclusive"] is not True or
            chunk["responseWindowMustBeVerified"] is not True):
        raise ValueError("INVALID_APPROVED_CHUNK_SHAPE")
    spec = chunk["request"]
    if audit_demo_get_only_request(spec)["requestShapeAcceptable"] is not True:
        raise ValueError("INERT_PRICE_GET_SPEC_REQUIRED")
    # A fictional epic is mandatory. This archive rehearses storage only.
    if spec["path"] != "/api/v1/prices/TEST.GOLD.EPIC":
        raise ValueError("REAL_BROKER_EPIC_NEVER_ALLOWED_IN_REHEARSAL")
    width = WIDTHS.get(spec["query"]["resolution"])
    if not width:
        raise ValueError("UNKNOWN_FRAME_WIDTH")
    first, end, observed = map(_stamp, (
        chunk["firstExpectedOpenUTC"], chunk["expectedEndExclusiveUTC"], observed_utc))
    n = chunk["expectedClosedSlots"]
    if (type(n) is not int or not 1 <= n <= 900 or
            (end-first).total_seconds() != n*width or end > observed or
            spec["query"]["from"] != first.strftime("%Y-%m-%dT%H:%M:%S") or
            spec["query"]["to"] != (end-dt.timedelta(seconds=width-1)).strftime("%Y-%m-%dT%H:%M:%S")):
        raise ValueError("CLOSED_WINDOW_AND_RECEIPT_MISMATCH")
    if not isinstance(page, dict) or set(page) != {"epic", "resolution", "prices"} or (
            page["epic"] != "TEST.GOLD.EPIC" or
            page["resolution"] != spec["query"]["resolution"]):
        raise ValueError("TEST_PRICE_PAGE_IDENTITY_REQUIRED")
    prices = page["prices"]
    if not isinstance(prices, list) or not 1 <= len(prices) <= n:
        raise ValueError("BOUNDED_NONEMPTY_TEST_PAGE_REQUIRED")
    rows = []
    previous = None
    for original in prices:
        # Reject unknown/untrusted fields, including accidentally embedded keys.
        if (not isinstance(original, dict) or
                set(original) != {"snapshotTimeUTC", "openPrice", "highPrice",
                                  "lowPrice", "closePrice"}):
            raise ValueError("UNEXPECTED_PRICE_OR_SECRET_FIELDS")
        opened, bid, ask = _normalize_row(original, width, observed)
        candle_open = _stamp(opened)
        if not (first <= candle_open < end) or (previous is not None and opened <= previous):
            raise ValueError("OUT_OF_WINDOW_DUPLICATE_OR_ORDERED_BARS")
        previous = opened
        rows.append({"openUTC": opened, "bid": bid, "ask": ask})
    return {
        "schema": 1, "source": "SYNTHETIC_FIXTURE_NOT_CAPITAL_BROKER_DATA",
        "epic": "TEST.GOLD.EPIC", "resolution": spec["query"]["resolution"],
        "startUTC": chunk["firstExpectedOpenUTC"],
        "endExclusiveUTC": chunk["expectedEndExclusiveUTC"],
        "firstLocalTestReceiptUTC": observed_utc, "rows": rows
    }


def _path(d, payload):
    identifying = {k: payload[k] for k in ("epic", "resolution", "startUTC", "endExclusiveUTC")}
    return d / (PREFIX + _sha(identifying) + ".json")


def _read_existing(file):
    st = file.lstat()
    if (not stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode)
            or st.st_mode & 0o077 or st.st_uid != os.getuid()
            or st.st_nlink != 1 or not 0 < st.st_size <= MAX_BYTES):
        raise ValueError("PRIVATE_ARCHIVE_FILE_UNSAFE")
    fd = os.open(file, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        with os.fdopen(fd, "rb", closefd=False) as source:
            raw = source.read(MAX_BYTES + 1)
    finally:
        os.close(fd)
    if len(raw) > MAX_BYTES:
        raise ValueError("PRIVATE_ARCHIVE_OVERSIZE")
    try:
        envelope = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError("PRIVATE_ARCHIVE_UNREADABLE") from None
    if (not isinstance(envelope, dict) or set(envelope) != {"payload", "sha256"} or
            not isinstance(envelope["sha256"], str) or
            envelope["sha256"] != _sha(envelope["payload"])):
        raise ValueError("PRIVATE_ARCHIVE_HASH_MISMATCH")
    if (not isinstance(envelope["payload"], dict) or
            envelope["payload"].get("schema") != 1 or
            envelope["payload"].get("source") != "SYNTHETIC_FIXTURE_NOT_CAPITAL_BROKER_DATA"):
        raise ValueError("PRIVATE_ARCHIVE_PROVENANCE_INVALID")
    return envelope["payload"]


def commit_fixture_page(chunk, page, dirname, observed_utc, *, explicit_synthetic_rehearsal=False):
    """Write only one synthetic page; return the EXACT sink receipt protocol.

    Default is completely disabled. This API does not attest actual data
    receipt, a provider, copyright rights, a backup, or trade eligibility.
    """
    if explicit_synthetic_rehearsal is not True:
        raise ValueError("SYNTHETIC_STORAGE_REHEARSAL_EXPLICITLY_DISABLED")
    d = _directory(dirname)
    proposed = _page(chunk, page, observed_utc)
    dest = _path(d, proposed)
    if dest.exists() or dest.is_symlink():
        old = _read_existing(dest)
        new_immutable = {k: v for k, v in proposed.items() if k != "firstLocalTestReceiptUTC"}
        old_immutable = {k: v for k, v in old.items() if k != "firstLocalTestReceiptUTC"}
        if old_immutable != new_immutable:
            raise ValueError("ARCHIVE_SLOT_CONFLICT_NEVER_OVERWRITE")
        return {"committed": True, "storedRows": len(old["rows"])}
    envelope = {"payload": proposed, "sha256": _sha(proposed)}
    raw = _canonical(envelope)
    if len(raw) > MAX_BYTES:
        raise ValueError("PRIVATE_ARCHIVE_BOUND_EXCEEDED")
    name = None
    try:
        fd, name = tempfile.mkstemp(prefix=".capital-synthetic-", suffix=".tmp", dir=d)
        os.fchmod(fd, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as output:
                output.write(raw)
                output.flush()
                os.fsync(fd)
        finally:
            os.close(fd)
        # Atomic hard-link publish: unlike os.replace, cannot overwrite an
        # existing conflicting page, including one created concurrently.
        try:
            os.link(name, dest, follow_symlinks=False)
        except FileExistsError:
            old = _read_existing(dest)
            a = {k: v for k, v in proposed.items() if k != "firstLocalTestReceiptUTC"}
            z = {k: v for k, v in old.items() if k != "firstLocalTestReceiptUTC"}
            if a != z:
                raise ValueError("ARCHIVE_SLOT_CONFLICT_NEVER_OVERWRITE")
        dirfd = os.open(d, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) |
                        getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
        _read_existing(dest)
        return {"committed": True, "storedRows": len(proposed["rows"])}
    finally:
        if name is not None:
            os.unlink(name)


def verify_fixture_page(chunk, dirname):
    """Restart audit: no raw prices, filenames, or account identifiers printed."""
    try:
        if (not isinstance(chunk, dict) or not isinstance(chunk.get("request"), dict) or
                chunk["request"].get("path") != "/api/v1/prices/TEST.GOLD.EPIC"):
            raise ValueError("NOT_A_SYNTHETIC_CHUNK")
        d = _directory(dirname)
        payload = {
            "epic": "TEST.GOLD.EPIC",
            "resolution": chunk["request"]["query"]["resolution"],
            "startUTC": chunk["firstExpectedOpenUTC"],
            "endExclusiveUTC": chunk["expectedEndExclusiveUTC"]
        }
        saved = _read_existing(_path(d, payload))
        if any(saved.get(k) != v for k, v in payload.items()):
            raise ValueError("ARCHIVED_PAGE_IDENTITY_MISMATCH")
        # Re-run full normalized-page validation on every restart, including
        # cross-side price constraints and the original first-test receipt.
        raw_rows = []
        for row in saved["rows"]:
            raw = {"snapshotTimeUTC": row["openUTC"]}
            for key, field in (("openPrice", "open"), ("highPrice", "high"),
                               ("lowPrice", "low"), ("closePrice", "close")):
                raw[key] = {side: row[side][field] for side in ("bid", "ask")}
            raw_rows.append(raw)
        reconstructed = _page(chunk, {
            "epic": "TEST.GOLD.EPIC", "resolution": saved["resolution"],
            "prices": raw_rows
        }, saved["firstLocalTestReceiptUTC"])
        if reconstructed != saved:
            raise ValueError("ARCHIVED_PAGE_SEMANTICS_INVALID")
        return {"mode": MODE, "status": "SYNTHETIC_PAGE_LOCAL_RESTORE_VERIFIED_ONLY",
                "rowsVerified": len(raw_rows), "brokerRightsVerified": False,
                "realBrokerPageVerified": False, "independentBackupVerified": False,
                "researchEligible": False, "signal": "WAIT", "executable": False,
                "paperOrdersAllowed": False, "liveOrdersAllowed": False,
                "providerRequestsMade": 0, "ordersSent": 0}
    except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError):
        return {"mode": MODE, "status": "BLOCKED_LOCAL_SYNTHETIC_ARCHIVE_NOT_VERIFIED",
                "rowsVerified": 0, "researchEligible": False, "signal": "WAIT",
                "executable": False, "paperOrdersAllowed": False, "liveOrdersAllowed": False,
                "providerRequestsMade": 0, "ordersSent": 0}
