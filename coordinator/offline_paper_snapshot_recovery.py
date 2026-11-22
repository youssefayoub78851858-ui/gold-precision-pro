"""OFFLINE synthetic paper journal backup and explicit restart recovery.

Never opens providers, schedules a worker, activates trading, pays for a
volume or creates a Render database. SQLite's online backup API snapshots an
existing WAL-mode journal consistently. Both backup and restore are manual
operator actions with explicit absolute local paths. A local SHA256 manifest
detects accidental file corruption, NOT malicious replacement of both files.

To survive host deletion this backup MUST be copied to separately persistent
storage by an approved operator; the Render free root cannot provide that.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import sqlite3
import sys
import tempfile
from urllib.parse import quote

from offline_paper_outcome_journal import OfflineJournal, MODE as JOURNAL_MODE, utc

FORMAT = "SYNTHETIC_PAPER_SQLITE_SNAPSHOT_V1"
MAX_DB_SIZE = 25_000_000
MAX_ROWS = 500
TRIGGERS = {"no_journal_update", "no_journal_delete",
            "no_settings_update", "no_settings_delete"}


def _existing(filename, suffix):
    if not isinstance(filename, (str, pathlib.Path)):
        raise ValueError("Explicit file path required")
    p = pathlib.Path(filename)
    if not p.is_absolute() or p.suffix != suffix or p.is_symlink() or (
            not p.is_file() or p.stat().st_size > MAX_DB_SIZE):
        raise ValueError("Existing regular bounded file required")
    if p.resolve(strict=True) != p:
        raise ValueError("Source symlinked")
    return p


def _vacant(filename, suffix):
    if not isinstance(filename, (str, pathlib.Path)):
        raise ValueError("Explicit destination required")
    p = pathlib.Path(filename)
    if not p.is_absolute() or p.suffix != suffix or (
            p.exists() or p.is_symlink()):
        raise ValueError("Destination must not already exist")
    parent = p.parent
    if not parent.is_dir() or parent.is_symlink() or parent.resolve() != parent:
        raise ValueError("Destination directory must already exist and be direct")
    return p


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(65536)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _verified_view(filename):
    p = _existing(filename, ".sqlite3")
    con = sqlite3.connect("file:" + quote(str(p), safe="/") + "?mode=ro",
                          uri=True, timeout=3)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA query_only=ON")
        if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        tables = {x[0] for x in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        triggers = {x[0] for x in con.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'")}
        if tables != {"settings", "journal", "sqlite_sequence"} or (
                triggers != TRIGGERS):
            raise ValueError("Not the expected append-only synthetic schema")
        frozen = con.execute(
            "SELECT freeze_utc,format FROM settings WHERE id=1").fetchall()
        if len(frozen) != 1 or frozen[0]["format"] != JOURNAL_MODE:
            raise ValueError("Unexpected journal freeze")
        freeze = frozen[0]["freeze_utc"]
        utc(freeze)
        journal = OfflineJournal.__new__(OfflineJournal)
        journal.db, journal.freeze_utc = con, freeze
        events, head = journal.verify()
        if len(events) > MAX_ROWS:
            raise ValueError("Too many journal rows")
        result = journal.summary()
        if (result["signal"] != "WAIT" or result["executable"] is not False
                or result["ledgerHashChainChecked"] is not True
                or result["rows"] != len(events)
                or result["providerRequestsMade"] != 0
                or result["brokerOrdersSent"] != 0
                or result["paperOrdersSent"] != 0):
            raise ValueError("Unsafe or invalid journal summary")
        return {
            "freezeUTC": freeze,
            "rows": len(events),
            "closedTrades": result["closedPaperTrades"],
            "headDigest": head,
            "lastObservedUTC": events[-1]["observedUTC"] if events else None,
        }
    finally:
        con.close()


def _temp(parent, suffix):
    fd, raw = tempfile.mkstemp(prefix=".paper-checkpoint-", suffix=suffix,
                               dir=parent)
    os.fchmod(fd, 0o600)
    os.close(fd)
    return pathlib.Path(raw)


def _fsync_file(filename):
    with open(filename, "rb") as handle:
        os.fsync(handle.fileno())


def _fsync_dir(folder):
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def snapshot(existing_db, snapshot_db, manifest_path):
    """Never overwrites either output. No automatic scheduling or upload."""
    original = _existing(existing_db, ".sqlite3")
    snapshot_dest = _vacant(snapshot_db, ".sqlite3")
    manifest_dest = _vacant(manifest_path, ".json")
    if snapshot_dest == original or manifest_dest == snapshot_dest:
        raise ValueError("Source and destinations must differ")
    before = _verified_view(original)
    temp_db = _temp(snapshot_dest.parent, ".sqlite3")
    temp_manifest = None
    published_db = False
    try:
        src = sqlite3.connect(
            "file:" + quote(str(original), safe="/") + "?mode=ro",
            uri=True, timeout=4)
        try:
            dest = sqlite3.connect(str(temp_db), timeout=4)
            try:
                src.backup(dest, pages=128, sleep=0.01)
                dest.commit()
                # Backup is a self-contained file and not dependent on
                # the original live WAL or SHM sidecars.
                dest.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                dest.execute("PRAGMA journal_mode=DELETE")
                dest.commit()
            finally:
                dest.close()
        finally:
            src.close()
        _fsync_file(temp_db)
        after = _verified_view(temp_db)
        # If the source advanced mid-copy, refuse to label this as the
        # preverified snapshot; retry explicitly after the writer settles.
        if after != before:
            raise ValueError("Journal changed during snapshot preflight")
        if temp_db.stat().st_size > MAX_DB_SIZE:
            raise ValueError("Oversized snapshot")
        manifest = {
            "format": FORMAT, "journalOrigin": JOURNAL_MODE,
            "snapshotFile": snapshot_dest.name,
            "sha256": _sha256(temp_db),
            **after,
            "externallyDurableOrReplicated": False,
            "independentHoldoutValidated": False,
            "marketDataOrTradingEnabled": False,
        }
        temp_manifest = _temp(manifest_dest.parent, ".json")
        temp_manifest.write_text(json.dumps(manifest, sort_keys=True,
                                           separators=(",", ":")) + "\n",
                                 encoding="utf-8")
        _fsync_file(temp_manifest)
        # Hard links are atomic and refuse overwrite, unlike os.replace.
        os.link(temp_db, snapshot_dest)
        published_db = True
        os.link(temp_manifest, manifest_dest)
        _fsync_dir(snapshot_dest.parent)
        if snapshot_dest.parent != manifest_dest.parent:
            _fsync_dir(manifest_dest.parent)
        return {
            "status": "LOCAL_SNAPSHOT_VERIFIED_OFFSITE_NOT_ATTESTED",
            "rows": after["rows"], "closedTrades": after["closedTrades"],
            "headDigest": after["headDigest"],
            "signal": "WAIT", "executable": False, "brokerOrdersSent": 0,
        }
    except Exception:
        if published_db:
            snapshot_dest.unlink(missing_ok=True)
        raise
    finally:
        temp_db.unlink(missing_ok=True)
        if temp_manifest:
            temp_manifest.unlink(missing_ok=True)


def restore(snapshot_db, manifest_path, new_db):
    """Explicit recovery into a NONEXISTENT file, never overwrite live DB."""
    source = _existing(snapshot_db, ".sqlite3")
    meta = _existing(manifest_path, ".json")
    dest = _vacant(new_db, ".sqlite3")
    if source == dest:
        raise ValueError("Cannot restore onto source")
    raw = meta.read_text(encoding="utf-8")
    if len(raw) > 4096:
        raise ValueError("Oversized manifest")
    data = json.loads(raw)
    fields = {"format", "journalOrigin", "snapshotFile", "sha256",
              "freezeUTC", "rows", "closedTrades", "headDigest",
              "lastObservedUTC", "externallyDurableOrReplicated",
              "independentHoldoutValidated", "marketDataOrTradingEnabled"}
    if not isinstance(data, dict) or set(data) != fields or (
            data["format"] != FORMAT or data["journalOrigin"] != JOURNAL_MODE
            or data["snapshotFile"] != source.name
            or data["externallyDurableOrReplicated"] is not False
            or data["independentHoldoutValidated"] is not False
            or data["marketDataOrTradingEnabled"] is not False
            or not isinstance(data["sha256"], str)
            or len(data["sha256"]) != 64
            or data["sha256"] != _sha256(source)):
        raise ValueError("Manifest identity or checksum invalid")
    checked = _verified_view(source)
    if any(data.get(k) != v for k, v in checked.items()):
        raise ValueError("Manifest journal head or freeze mismatch")
    tmp = _temp(dest.parent, ".sqlite3")
    try:
        shutil.copyfile(source, tmp)
        _fsync_file(tmp)
        if _sha256(tmp) != data["sha256"] or _verified_view(tmp) != checked:
            raise ValueError("Restored journal failed independent verification")
        os.link(tmp, dest)
        _fsync_dir(dest.parent)
        return {
            "status": "OFFLINE_SYNTHETIC_JOURNAL_RESTORED",
            "rows": checked["rows"],
            "closedTrades": checked["closedTrades"],
            "headDigest": checked["headDigest"],
            "signal": "WAIT", "executable": False, "brokerOrdersSent": 0,
        }
    finally:
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic SQLite offline backup/restore; manual only")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("snapshot")
    a.add_argument("existing_db")
    a.add_argument("new_snapshot_db")
    a.add_argument("new_manifest_json")
    b = sub.add_parser("restore")
    b.add_argument("existing_snapshot_db")
    b.add_argument("existing_manifest_json")
    b.add_argument("new_empty_destination_db")
    args = parser.parse_args()
    try:
        result = snapshot(args.existing_db, args.new_snapshot_db,
                          args.new_manifest_json) if args.command == "snapshot" else restore(
            args.existing_snapshot_db, args.existing_manifest_json,
            args.new_empty_destination_db)
        sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    except Exception:
        sys.stderr.write("OFFLINE_SYNTHETIC_BACKUP_OR_RESTORE_UNVERIFIED\n")
        sys.exit(2)
