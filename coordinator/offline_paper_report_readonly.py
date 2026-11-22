"""One-shot READ-ONLY private viewer of an existing SYNTHETIC paper journal.

Never creates tables/files, never records outcomes, never opens broker feeds.
The caller supplies an operator-configured absolute path, never a browser
path. Source is an existing local synthetic ledger, NOT future live results.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import sqlite3
import sys
from urllib.parse import quote

from offline_paper_outcome_journal import MODE as JOURNAL_MODE, OfflineJournal, utc
from offline_paper_periodic_reports import make_report
from paper_startup_recovery_check import attest


def inspect(file, checkpoint=None, manifest=None):
    if (checkpoint is None) != (manifest is None):
        raise ValueError("Both snapshot and manifest are required")
    if checkpoint is not None:
        # Verify the journal's latest state against the frozen checkpoint,
        # not just against the process's cached boot-time check.
        attest(file, checkpoint, manifest)
    p = pathlib.Path(file)
    if not p.is_absolute() or p.suffix != ".sqlite3" or not p.is_file() or p.is_symlink():
        raise ValueError("Missing existing explicit synthetic journal")
    con = sqlite3.connect("file:" + quote(str(p), safe="/") + "?mode=ro",
                          uri=True, timeout=2)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA query_only=ON")
        # This is a viewer, not a background journal job; bound runtime and
        # avoid unbounded subprocesses for per-week/per-five reports.
        row = con.execute("SELECT freeze_utc,format FROM settings WHERE id=1").fetchone()
        if row is None or row["format"] != JOURNAL_MODE:
            raise ValueError("Unrecognized synthetic journal")
        freeze = row["freeze_utc"]
        utc(freeze)
        count = con.execute("SELECT COUNT(*) FROM journal").fetchone()[0]
        closed = con.execute(
            "SELECT COUNT(*) FROM journal WHERE kind='PAPER_CLOSED'"
        ).fetchone()[0]
        if not (0 <= closed <= 100 and 0 <= count <= 500):
            raise ValueError("Report snapshot capacity exceeded")
        journal = OfflineJournal.__new__(OfflineJournal)
        journal.db = con
        journal.freeze_utc = freeze
        report = make_report(journal)  # internally re-verifies chain and costs
        if (report.get("mode") != "GOLD_OFFLINE_SYNTHETIC_PAPER_REPORTS_V1"
                or report.get("signal") != "WAIT"
                or report.get("executable") is not False
                or report.get("realMarketDataConnected") is not False
                or report.get("paperOrderExecutionEnabled") is not False
                or report.get("liveOrderExecutionEnabled") is not False
                or report.get("brokerOrdersSent") != 0
                or report.get("paperOrdersSent") != 0
                or report.get("journalRows") != count
                or report["cumulative"]["closedTrades"] != closed):
            raise ValueError("Unsafe synthetic report")
        if checkpoint is not None:
            # Detect a rollback or checkpoint replacement while assembling
            # the report. Never return a result from a rejected ancestry.
            attest(file, checkpoint, manifest)
        return report
    finally:
        con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("existing_synthetic_sqlite_file")
    parser.add_argument("existing_checkpoint", nargs="?")
    parser.add_argument("existing_manifest", nargs="?")
    args = parser.parse_args()
    try:
        sys.stdout.write(json.dumps(inspect(
            args.existing_synthetic_sqlite_file,
            args.existing_checkpoint,
            args.existing_manifest
        ), allow_nan=False, separators=(",", ":")) + "\n")
    except Exception:
        sys.stderr.write("SYNTHETIC_PAPER_JOURNAL_UNVERIFIED\n")
        sys.exit(2)
