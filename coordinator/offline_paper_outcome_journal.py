"""Offline-only, durable synthetic paper outcome journal.

No background worker, network, provider feed, account token, or order API.
Explicit database paths only; no automatic Render/database creation.
The journal is an append-only *local integrity check*, not cryptographic
proof against a privileged attacker able to rewrite the whole database.
Every posted close is also checked by the existing JS prospective cost/time
auditor BEFORE the SQLite transaction is committed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import re
import sqlite3
import subprocess

ORIGIN = "SYNTHETIC_TEST_ONLY"
MODE = "OFFLINE_SYNTHETIC_FORWARD_PAPER_JOURNAL_V1"
JS_ORIGIN = "UNATTESTED_SANITIZED_PAPER_LEDGER"
AUDITOR = pathlib.Path(__file__).with_name("prospective_paper_holdout_audit.js")
ZERO = "0" * 64
KINDS = frozenset(("WAIT", "SOURCE_BLOCKED", "PAPER_CLOSED"))
EVENT_KEYS = frozenset(("eventId", "observedUTC", "kind", "dataOrigin",
                        "simulationOnly", "trade"))
TRADE_KEYS = frozenset((
    "id", "side", "decisionUTC", "entryUTC", "exitUTC",
    "firstObservedClosedUTC", "signalClosedUTC", "signalFirstObservedUTC",
    "contextClosedUTC", "contextFirstObservedUTC", "grossPnLUsd",
    "spreadUsd", "slippageUsd", "commissionUsd", "initialRiskUsd",
    "grossPnLConvention", "initialRiskConvention"
))
ISO = re.compile(r"^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def utc(value):
    if not isinstance(value, str) or not ISO.fullmatch(value):
        raise ValueError("Canonical UTC timestamp required")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid UTC timestamp") from exc
    if parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("Non-UTC timestamp")
    return parsed


def canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False)


def digest(previous, data):
    return hashlib.sha256((previous + "\n" + data).encode("utf-8")).hexdigest()


def local_audit(trades, freeze_utc, as_of_utc):
    """Delegate outcome arithmetic and lookahead/cost rules to frozen JS."""
    payload = {"dataOrigin": JS_ORIGIN, "freezeUTC": freeze_utc,
               "asOfUTC": as_of_utc, "trades": trades}
    response = subprocess.run(
        ["node", str(AUDITOR)], input=canon(payload),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=8, check=True
    )
    data = json.loads(response.stdout)
    if data.get("signal") != "WAIT" or data.get("executable") is not False or (
        data.get("paperOrdersAllowed") is not False
        or data.get("liveOrdersAllowed") is not False
        or data.get("providerRequestsMade") != 0
        or data.get("independentHoldoutValidated") is not False
        or data.get("sourceRightsVerified") is not False
    ):
        raise ValueError("Unsafe paper outcome evaluator")
    return data


class OfflineJournal:
    def __init__(self, database, freeze_utc="2026-11-18T00:00:00Z"):
        self.freeze_utc = freeze_utc
        utc(freeze_utc)
        if utc(freeze_utc) < utc("2026-11-18T00:00:00Z"):
            raise ValueError("Freeze predates allowed preapproval window")
        if not isinstance(database, (str, pathlib.Path)) or (
            not str(database) or str(database) == ":memory:"
        ):
            raise ValueError("Explicit local file required")
        self.db = sqlite3.connect(str(database), timeout=10,
                                  isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS settings(
            id INTEGER PRIMARY KEY CHECK(id=1),
            freeze_utc TEXT NOT NULL,
            format TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS journal(
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            observed_utc TEXT NOT NULL,
            kind TEXT NOT NULL,
            document TEXT NOT NULL,
            previous_digest TEXT NOT NULL,
            digest TEXT NOT NULL
          );
          CREATE TRIGGER IF NOT EXISTS no_journal_update
          BEFORE UPDATE ON journal BEGIN
            SELECT RAISE(ABORT, 'append-only journal');
          END;
          CREATE TRIGGER IF NOT EXISTS no_journal_delete
          BEFORE DELETE ON journal BEGIN
            SELECT RAISE(ABORT, 'append-only journal');
          END;
          CREATE TRIGGER IF NOT EXISTS no_settings_update
          BEFORE UPDATE ON settings BEGIN
            SELECT RAISE(ABORT, 'immutable freeze');
          END;
          CREATE TRIGGER IF NOT EXISTS no_settings_delete
          BEFORE DELETE ON settings BEGIN
            SELECT RAISE(ABORT, 'immutable freeze');
          END;
        """)
        self.db.execute(
            "INSERT OR IGNORE INTO settings VALUES(1,?,?)",
            (freeze_utc, MODE)
        )
        stored = self.db.execute("SELECT freeze_utc,format FROM settings").fetchall()
        if (len(stored) != 1 or stored[0]["freeze_utc"] != freeze_utc
                or stored[0]["format"] != MODE):
            self.db.close()
            raise ValueError("Journal freeze is immutable")
        self.verify()

    def close(self):
        self.db.close()

    def verify(self):
        previous = ZERO
        last_observed = utc(self.freeze_utc)
        events = []
        for index, row in enumerate(self.db.execute(
                "SELECT * FROM journal ORDER BY seq"), 1):
            if row["seq"] != index or row["previous_digest"] != previous:
                raise ValueError("Journal sequence/hash chain broken")
            obj = json.loads(row["document"])
            if (canon(obj) != row["document"]
                    or obj.get("eventId") != row["event_id"]
                    or obj.get("observedUTC") != row["observed_utc"]
                    or obj.get("kind") != row["kind"]
                    or digest(previous, row["document"]) != row["digest"]):
                raise ValueError("Journal content digest mismatch")
            self.validate_event(obj)
            stamp = utc(row["observed_utc"])
            if stamp <= last_observed:
                raise ValueError("Journal observation times not monotonic")
            last_observed = stamp
            previous = row["digest"]
            events.append(obj)
        return events, previous

    @staticmethod
    def validate_event(event):
        if not isinstance(event, dict) or (
            set(event) != EVENT_KEYS - {"trade"}
            and set(event) != EVENT_KEYS
        ):
            raise ValueError("Only sanctioned sanitized event fields")
        if (not isinstance(event.get("eventId"), str)
                or not IDENTIFIER.fullmatch(event["eventId"])
                or event.get("dataOrigin") != ORIGIN
                or event.get("simulationOnly") is not True
                or event.get("kind") not in KINDS):
            raise ValueError("Synthetic isolated events only")
        utc(event.get("observedUTC"))
        trade = event.get("trade")
        if event["kind"] == "PAPER_CLOSED":
            if not isinstance(trade, dict) or set(trade) != TRADE_KEYS:
                raise ValueError("Complete sanitized paper close required")
            if not isinstance(trade["id"], str) or (
                not IDENTIFIER.fullmatch(trade["id"])):
                raise ValueError("Invalid trade ID")
            # The closure and first observation must both PRECEDE logging.
            if utc(trade["firstObservedClosedUTC"]) > utc(event["observedUTC"]):
                raise ValueError("Cannot log outcome before first observation")
        elif "trade" in event:
            raise ValueError("WAIT/outage cannot carry trade data")

    def append(self, event, prior_guard=None):
        """Append atomically. Optional safety guard runs INSIDE the write lock.

        The guard receives the already-verified journal and proposed event,
        so a parallel writer cannot change recovery state between the safety
        decision and the new row. No guard = legacy manual offline behavior.
        """
        self.validate_event(event)
        if utc(event["observedUTC"]) <= utc(self.freeze_utc):
            raise ValueError("Observation not after frozen start")
        serialized = canon(event)
        if len(serialized) > 8192:
            raise ValueError("Journal row too large")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            events, previous = self.verify()
            already = next((old for old in events
                            if old["eventId"] == event["eventId"]), None)
            if already is not None:
                if already != event:
                    raise ValueError("Conflicting event ID")
                self.db.execute("COMMIT")
                return {"duplicate": True, "recorded": False}
            if events and utc(event["observedUTC"]) <= utc(events[-1]["observedUTC"]):
                raise ValueError("Out-of-order event")
            if prior_guard is not None:
                prior_guard(events, event)
            candidates = [entry["trade"] for entry in events
                          if entry["kind"] == "PAPER_CLOSED"]
            if event["kind"] == "PAPER_CLOSED":
                candidates.append(event["trade"])
                result = local_audit(candidates, self.freeze_utc, event["observedUTC"])
                if (result.get("status") != "UNATTESTED_PAPER_ARITHMETIC_ONLY"
                        or result.get("closedTrades") != len(candidates)):
                    raise ValueError("Cost, chronology or research audit rejected paper close")
            self.db.execute(
                "INSERT INTO journal(event_id,observed_utc,kind,document,previous_digest,digest)"
                " VALUES(?,?,?,?,?,?)",
                (event["eventId"], event["observedUTC"], event["kind"],
                 serialized, previous, digest(previous, serialized))
            )
            self.db.execute("COMMIT")
            return {"duplicate": False, "recorded": True}
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def summary(self):
        events, head = self.verify()
        trades = [obj["trade"] for obj in events if obj["kind"] == "PAPER_CLOSED"]
        audit = local_audit(trades, self.freeze_utc,
                            events[-1]["observedUTC"] if events else
                            "2026-11-18T00:00:01Z"
                            if self.freeze_utc == "2026-11-18T00:00:00Z"
                            else (utc(self.freeze_utc) +
                                  dt.timedelta(seconds=1)).isoformat().replace("+00:00", "Z"))
        # The report never leaks a trade side, entry/stop/target, price or token.
        return {
            "mode": MODE,
            "status": "SYNTHETIC_LOCAL_ONLY_NOT_FORWARD_PERFORMANCE",
            "rows": len(events),
            "closedPaperTrades": len(trades),
            "waitEvents": sum(e["kind"] == "WAIT" for e in events),
            "blockedSourceEvents": sum(e["kind"] == "SOURCE_BLOCKED" for e in events),
            "ledgerHashChainChecked": True,
            "lastDigest": head,
            "outcomeAuditStatus": audit["status"],
            "modeledNetUsd": audit.get("statistics", {}).get(
                "totalGrossMinusModeledCostsUsd"
            ) if audit.get("statistics") else None,
            "doubleCostStressNetUsd": audit.get("statistics", {}).get(
                "modeledCostDoubleStress", {}).get("netUsd"
            ) if audit.get("statistics") else None,
            "independentHoldoutValidated": False,
            "realMarketDataConnected": False,
            "licensedDataOrBrokerFillsVerified": False,
            "paperOrderExecutionEnabled": False,
            "liveOrderExecutionEnabled": False,
            "signal": "WAIT",
            "executable": False,
            "providerRequestsMade": 0,
            "brokerOrdersSent": 0,
            "paperOrdersSent": 0
        }
