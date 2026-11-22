"""Event-driven, OFFLINE-ONLY synthetic paper observation recorder.

This is a dormant integration component, not a running polling service.
A caller explicitly supplies an existing OfflineJournal, a separately
attested local startup/checkpoint gate, and a SANITIZED synthetic packet.
No market feed, broker calls, account credentials, timers, remote storage,
automatic synthetic trades, or paid resources. NEVER accept a real feed.

On reconnection, TWO consecutive closed synthetic observations after the
last outage are required before accepting a separately supplied synthetic
paper-close record. A gap >20 minutes forces SOURCE_BLOCKED. SQLite computes
the decision against the *latest journal under BEGIN IMMEDIATE*, so
concurrent retries/restarts cannot bypass the quarantine.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re

from offline_paper_outcome_journal import (
    OfflineJournal, ORIGIN, canon, utc
)

MODE = "GOLD_OFFLINE_SYNTHETIC_PAPER_AUTO_RECORDER_V1"
STATES = frozenset(("OBSERVED_CLOSED", "SOURCE_DOWN", "PAPER_CLOSE"))
MAX_GAP_SECONDS = 20 * 60
KEYS = frozenset((
    "observedUTC", "observationId", "dataOrigin", "simulationOnly",
    "sourceState", "signal", "executable"
))
IDENTITY = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def gate_ok(gate):
    return isinstance(gate, dict) and (
        gate.get("mode") == "GOLD_PAPER_STARTUP_RECOVERY_GATE_V1"
        and gate.get("status") == "STARTUP_LOCAL_CHECKPOINT_READ_ONLY_VERIFIED"
        and gate.get("checkpointSafe") is True
        and gate.get("paperResultsDisplayAllowed") is True
        and gate.get("backupOffsiteVerified") is False
        and gate.get("independentHoldoutValidated") is False
        and gate.get("marketDataConnected") is False
        and gate.get("paperOrdersAllowed") is False
        and gate.get("liveOrdersAllowed") is False
        and gate.get("providerRequestsMade") == 0
        and gate.get("brokerOrdersSent") == 0
        and gate.get("signal") == "WAIT"
        and gate.get("executable") is False
    )


def validate(packet):
    if not isinstance(packet, dict):
        raise ValueError("Offline synthetic packet required")
    kind = packet.get("sourceState")
    wanted = KEYS | ({"trade"} if kind == "PAPER_CLOSE" else set())
    if (set(packet) != wanted or kind not in STATES
            or not isinstance(packet.get("observationId"), str)
            or not IDENTITY.fullmatch(packet["observationId"])
            or packet.get("dataOrigin") != ORIGIN
            or packet.get("simulationOnly") is not True
            or packet.get("signal") != "WAIT"
            or packet.get("executable") is not False):
        raise ValueError("Only exact non-executable synthetic observations")
    utc(packet.get("observedUTC"))
    if kind == "PAPER_CLOSE":
        OfflineJournal.validate_event({
            "eventId": "validated_close",
            "observedUTC": packet["observedUTC"],
            "kind": "PAPER_CLOSED",
            "dataOrigin": ORIGIN,
            "simulationOnly": True,
            "trade": packet["trade"]
        })
    return packet


def _kind_for(events, packet):
    state = packet["sourceState"]
    if state == "SOURCE_DOWN":
        return "SOURCE_BLOCKED"
    timestamp = utc(packet["observedUTC"])
    if events:
        elapsed = (timestamp - utc(events[-1]["observedUTC"])).total_seconds()
        if elapsed > MAX_GAP_SECONDS:
            return "SOURCE_BLOCKED"
    # Require two post-outage (or initial) closed observations. Any
    # PAPER_CLOSED requires a NEW pair of explicit observations afterward.
    recent = 0
    for item in reversed(events):
        if item["kind"] != "WAIT":
            break
        recent += 1
        if recent >= 2:
            break
    if state == "OBSERVED_CLOSED":
        return "WAIT"
    return "PAPER_CLOSED" if recent >= 2 else "SOURCE_BLOCKED"


def _event(packet, kind):
    # Hash the COMPLETE packet. A modified replay cannot reuse the same
    # eventId even if it reuses the source observationId and UTC instant.
    identifier = hashlib.sha256(canon(packet).encode()).hexdigest()[:32]
    value = {
        "eventId": "auto_" + identifier,
        "observedUTC": packet["observedUTC"],
        "kind": kind,
        "dataOrigin": ORIGIN,
        "simulationOnly": True,
    }
    if kind == "PAPER_CLOSED":
        value["trade"] = packet["trade"]
    return value


def record(journal, startup_gate, packet):
    if not isinstance(journal, OfflineJournal):
        raise ValueError("Only existing local SQLite journal")
    if not gate_ok(startup_gate):
        # A missing persistent disk/checkpoint must not create any record.
        raise ValueError("Persistent local startup verification required")
    validate(packet)
    if utc(packet["observedUTC"]) <= utc(journal.freeze_utc):
        raise ValueError("Packet predates frozen test start")
    existing, _ = journal.verify()
    event_id = _event(packet, "WAIT")["eventId"]
    already = next((e for e in existing if e["eventId"] == event_id), None)
    if already is not None:
        # A repeated packet always yields an exact no-op after restart;
        # never reinterpret it using the newer recovery state.
        result = journal.append(already)
        if result != {"duplicate": True, "recorded": False}:
            raise ValueError("Non-idempotent existing observation")
        return _result("DUPLICATE_SKIPPED", already["kind"], False)
    chosen = _kind_for(existing, packet)
    proposed = _event(packet, chosen)
    def guard(new_events, candidate):
        # Recompute under the actual SQLite write lock (BEGIN IMMEDIATE).
        if _kind_for(new_events, packet) != candidate["kind"]:
            raise ValueError("Journal changed since observation; retry")
        if packet["sourceState"] == "PAPER_CLOSE":
            ids = {e["trade"]["id"] for e in new_events
                   if e["kind"] == "PAPER_CLOSED"}
            if packet["trade"]["id"] in ids:
                raise ValueError("Duplicate paper trade ID")
    committed = journal.append(proposed, prior_guard=guard)
    if not committed["recorded"]:
        return _result("DUPLICATE_SKIPPED", chosen, False)
    return _result("OFFLINE_EVENT_RECORDED", chosen, True)


def _result(status, kind, recorded):
    return {
        "mode": MODE,
        "status": status,
        "recorded": recorded,
        "eventKind": kind,
        "dataOrigin": ORIGIN,
        "realMarketDataConnected": False,
        "independentHoldoutValidated": False,
        "paperOrdersAllowed": False,
        "liveOrdersAllowed": False,
        "providerRequestsMade": 0,
        "brokerOrdersSent": 0,
        "paperOrdersSent": 0,
        "signal": "WAIT",
        "executable": False,
    }
