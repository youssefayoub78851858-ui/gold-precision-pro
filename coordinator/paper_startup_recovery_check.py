"""Read-only boot recovery attestation for a synthetic paper journal.

Verifies that an explicitly configured, already-existing live SQLite journal
contains an entire locally signed-by-checksum snapshot prefix, with the
immutable frozen date and append-only hash-chain intact. This is NOT
evidence of off-site durability, a trusted signature, source licensing,
independent holdout, or broker prices. Never performs restoration or writes.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
from urllib.parse import quote

from offline_paper_snapshot_recovery import (
    FORMAT, JOURNAL_MODE, MAX_DB_SIZE, _existing, _sha256, _verified_view
)

MODE = "GOLD_SYNTHETIC_PAPER_STARTUP_RECOVERY_GATE_V1"
MANIFEST_FIELDS = frozenset((
    "format", "journalOrigin", "snapshotFile", "sha256",
    "freezeUTC", "rows", "closedTrades", "headDigest",
    "lastObservedUTC", "externallyDurableOrReplicated",
    "independentHoldoutValidated", "marketDataOrTradingEnabled"
))


def attest(database_path, checkpoint_path, manifest_path):
    live = _existing(database_path, ".sqlite3")
    backup = _existing(checkpoint_path, ".sqlite3")
    manifest = _existing(manifest_path, ".json")
    if len({str(live), str(backup), str(manifest)}) != 3:
        raise ValueError("Distinct input files required")
    if manifest.stat().st_size > 4096 or backup.stat().st_size > MAX_DB_SIZE:
        raise ValueError("Oversized checkpoint metadata")
    meta = json.loads(manifest.read_text(encoding="utf8"))
    if (not isinstance(meta, dict) or set(meta) != MANIFEST_FIELDS
            or meta["format"] != FORMAT
            or meta["journalOrigin"] != JOURNAL_MODE
            or meta["snapshotFile"] != backup.name
            or meta["externallyDurableOrReplicated"] is not False
            or meta["independentHoldoutValidated"] is not False
            or meta["marketDataOrTradingEnabled"] is not False
            or not isinstance(meta["sha256"], str)
            or len(meta["sha256"]) != 64
            or meta["sha256"] != _sha256(backup)):
        raise ValueError("Checkpoint manifest checksum or scope invalid")
    snapshot = _verified_view(backup)
    if any(meta.get(k) != value for k, value in snapshot.items()):
        raise ValueError("Checkpoint metadata not backed by the snapshot")
    current = _verified_view(live)
    if current["freezeUTC"] != snapshot["freezeUTC"]:
        raise ValueError("Journal epoch changed")
    if current["rows"] < snapshot["rows"]:
        raise ValueError("Live journal rolled back behind checkpoint")
    # A newer journal can be accepted only if the checkpoint digest is
    # literally present at the original sequence boundary. Timestamps or
    # totals alone cannot prove this append-only ancestry.
    if snapshot["rows"] > 0:
        con = sqlite3.connect(
            "file:" + quote(str(live), safe="/") + "?mode=ro",
            uri=True, timeout=3
        )
        try:
            con.execute("PRAGMA query_only=ON")
            row = con.execute(
                "SELECT digest FROM journal WHERE seq=?",
                (snapshot["rows"],)
            ).fetchone()
        finally:
            con.close()
        if row is None or row[0] != snapshot["headDigest"]:
            raise ValueError("Journal diverged from checkpoint")
    elif snapshot["headDigest"] != "0" * 64:
        raise ValueError("Empty checkpoint has invalid digest")
    if current["closedTrades"] < snapshot["closedTrades"]:
        raise ValueError("Paper close history lost")
    return {
        "mode": MODE,
        "status": "LOCAL_JOURNAL_CHECKPOINT_ANCESTRY_VERIFIED",
        "journalRows": current["rows"],
        "checkpointRows": snapshot["rows"],
        "closedPaperTrades": current["closedTrades"],
        "checkpointClosedPaperTrades": snapshot["closedTrades"],
        "externallyDurableOrReplicated": False,
        "independentHoldoutValidated": False,
        "realMarketDataConnected": False,
        "paperOrdersAllowed": False,
        "liveOrdersAllowed": False,
        "providerRequestsMade": 0,
        "brokerOrdersSent": 0,
        "signal": "WAIT",
        "executable": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="One-shot read-only startup paper checkpoint audit")
    p.add_argument("existing_live_journal")
    p.add_argument("existing_local_checkpoint")
    p.add_argument("existing_checkpoint_manifest")
    args = p.parse_args()
    try:
        output = attest(args.existing_live_journal,
                        args.existing_local_checkpoint,
                        args.existing_checkpoint_manifest)
        sys.stdout.write(json.dumps(output, separators=(",", ":"),
                                    allow_nan=False) + "\n")
    except Exception:
        # Do not include paths, raw trades, sensitive values or exception text.
        sys.stderr.write("PAPER_JOURNAL_STARTUP_RECOVERY_NOT_VERIFIED\n")
        sys.exit(2)
