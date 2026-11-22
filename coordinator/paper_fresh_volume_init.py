"""Prepare an EMPTY local synthetic paper ledger on an existing volume.

This module is an internal sub-step invoked ONLY by the separately gated
paper_volume_bootstrap.js operator command. It does not connect to a data
vendor, create a Render disk, subscribe, start a worker, or place trades.
No existing file is overwritten. ALL results remain OFFLINE SYNTHETIC ONLY.

The external disk mount is verified by the invoking Node preflight; an
ungated direct call to this module is NOT an entitlement/persistence proof.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from offline_paper_outcome_journal import OfflineJournal
from offline_paper_snapshot_recovery import snapshot
from paper_startup_recovery_check import attest


def prepare(directory, journal_name, backup_name, manifest_name):
    root = pathlib.Path(directory)
    if (not root.is_absolute() or not root.is_dir() or root.is_symlink()
            or root.resolve() != root):
        raise ValueError("Existing absolute direct directory required")
    names = [journal_name, backup_name, manifest_name]
    if (len(set(names)) != 3 or any(
            not isinstance(x, str) or not x or pathlib.Path(x).name != x
            or x.startswith(".") for x in names)
            or not journal_name.endswith(".sqlite3")
            or not backup_name.endswith(".sqlite3")
            or not manifest_name.endswith(".json")):
        raise ValueError("Invalid distinct file names")
    destinations = [root / name for name in names]
    if any(p.exists() or p.is_symlink() for p in destinations):
        raise ValueError("Refuse overwriting initialized or partial journal")
    journal, backup, manifest = destinations
    # An explicit empty ledger is a schema/bootstrap exercise, never a real
    # source or a declaration that the external mount survives restarts.
    recorder = OfflineJournal(journal)
    try:
        s = recorder.summary()
        if (s["rows"] != 0 or s["closedPaperTrades"] != 0
                or s["signal"] != "WAIT" or s["executable"] is not False):
            raise ValueError("Empty synthetic journal could not be verified")
    finally:
        recorder.close()
    checkpoint = snapshot(journal, backup, manifest)
    proof = attest(journal, backup, manifest)
    if (checkpoint["rows"] != 0 or proof["journalRows"] != 0
            or proof["checkpointRows"] != 0
            or proof["status"] != "LOCAL_JOURNAL_CHECKPOINT_ANCESTRY_VERIFIED"):
        raise ValueError("Initial checkpoint verification failed")
    return {
        "status": "EMPTY_SYNTHETIC_LEDGER_CHECKPOINT_PREPARED",
        "journalRows": 0, "checkpointRows": 0,
        "paperResultsDisplayAllowed": False,
        "paperAutoRecordingEnabled": False,
        "externalStorageAndBackupServiceProvisioned": False,
        "dataSourceLicensed": False,
        "liveMarketDataConnected": False,
        "independentHoldoutValidated": False,
        "brokerOrdersSent": 0,
        "providerRequestsMade": 0,
        "signal": "WAIT", "executable": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline empty paper ledger bootstrap - internal gated utility")
    parser.add_argument("root")
    parser.add_argument("journal_name")
    parser.add_argument("checkpoint_name")
    parser.add_argument("manifest_name")
    args = parser.parse_args()
    try:
        result = prepare(args.root, args.journal_name,
                         args.checkpoint_name, args.manifest_name)
        sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
    except Exception:
        sys.stderr.write("OFFLINE_PAPER_VOLUME_INITIALIZATION_REJECTED\n")
        sys.exit(2)
