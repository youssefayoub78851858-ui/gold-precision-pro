"""Offline, quarantined MBO order-book replay.

The input is already-decoded Databento-shaped records in original source order.
This module does not decode files, request data, or connect to strategy/trading
engines. Every output remains test-only and non-executable.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


F_LAST = 1 << 7
F_TOB = 1 << 6
F_SNAPSHOT = 1 << 5
F_MBP = 1 << 4
F_BAD_TS_RECV = 1 << 3
F_MAYBE_BAD_BOOK = 1 << 2
F_PUBLISHER_SPECIFIC = 1 << 1
UNDEF_PRICE = (1 << 63) - 1
PRICE_SCALE = 1_000_000_000

BOOK_ACTIONS = {"A", "M", "C", "R", "T", "F", "N"}
SIDES = {"B", "A", "N"}
NON_BOOK_ACTIONS = {"T", "F", "N"}


@dataclass
class Order:
    order_id: int
    side: str
    price: int
    size: int
    priority_source_index: int


@dataclass
class InstrumentBook:
    publisher_id: int
    instrument_id: int
    channel_id: int
    symbol: str | None
    orders: dict[int, Order]
    last_ts_event: int | None = None
    snapshot_open: bool = False
    snapshot_complete: bool = False
    needs_snapshot: bool = True
    last_event_closed: bool = False
    blockers: set[str] | None = None

    def __post_init__(self):
        if self.blockers is None:
            self.blockers = set()


def _uint(row: dict, name: str, maximum: int) -> int:
    value = row.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= maximum:
        raise ValueError(f"MBO_{name.upper()}_RANGE")
    return value


def _price_size(row: dict, action: str) -> tuple[int, int]:
    price = _uint(row, "price", UNDEF_PRICE)
    size = _uint(row, "size", (1 << 32) - 1)
    if action == "R":
        if price != UNDEF_PRICE or size != 0:
            raise ValueError("MBO_CLEAR_SHAPE")
    elif action in NON_BOOK_ACTIONS and action == "N":
        if size != 0 and (price == 0 or price == UNDEF_PRICE):
            raise ValueError("MBO_NOOP_PRICE")
    elif price in (0, UNDEF_PRICE) or size == 0:
        raise ValueError("MBO_PRICE_SIZE")
    return price, size


def _coverage_ok(coverage: dict | None) -> bool:
    gap_count = coverage.get("gapCount") if isinstance(coverage, dict) else None
    return bool(
        isinstance(coverage, dict)
        and coverage.get("status") == "VERIFIED_COMPLETE"
        and coverage.get("scope") == "CHANNEL"
        and isinstance(gap_count, int)
        and not isinstance(gap_count, bool)
        and gap_count == 0
        and isinstance(coverage.get("evidenceReference"), str)
        and coverage["evidenceReference"].strip()
    )


def _levels(orders: dict[int, Order], side: str, depth: int) -> list[dict[str, int]]:
    totals: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for order in orders.values():
        if order.side == side:
            totals[order.price][0] += order.size
            totals[order.price][1] += 1
    prices = sorted(totals, reverse=(side == "B"))[:depth]
    return [{"price": price, "size": totals[price][0], "orderCount": totals[price][1]} for price in prices]


def replay_mbo(
    rows: list[dict[str, Any]],
    *,
    as_of_event_ns: int,
    coverage: dict | None = None,
    depth: int = 10,
    data_origin: str = "SYNTHETIC_TEST_ONLY",
) -> dict:
    """Replay MBO rows without sorting; a completed flagged snapshot is mandatory.

    Sequence values must be non-decreasing in the supplied source order. Equal
    values and equal timestamps are retained as received. A missing/failed
    channel coverage attestation keeps the final state blocked even if a local
    snapshot was structurally replayed.
    """
    if not isinstance(rows, list) or not rows:
        raise ValueError("MBO_ROWS_REQUIRED")
    if not isinstance(as_of_event_ns, int) or isinstance(as_of_event_ns, bool) or as_of_event_ns < 0:
        raise ValueError("MBO_AS_OF_REQUIRED")
    if not isinstance(depth, int) or isinstance(depth, bool) or not 1 <= depth <= 10:
        raise ValueError("MBO_DEPTH_RANGE")

    books: dict[tuple[int, int, int], InstrumentBook] = {}
    channel_sequences: dict[tuple[int, int], int] = {}
    trace: list[dict] = []

    for source_index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("MBO_ROW_SHAPE")
        required = {"ts_event", "publisher_id", "instrument_id", "channel_id", "sequence",
                    "action", "side", "order_id", "price", "size", "flags"}
        if not required.issubset(row):
            raise ValueError("MBO_ROW_FIELDS")
        ts_event = _uint(row, "ts_event", (1 << 64) - 1)
        publisher_id = _uint(row, "publisher_id", (1 << 16) - 1)
        instrument_id = _uint(row, "instrument_id", (1 << 32) - 1)
        channel_id = _uint(row, "channel_id", (1 << 8) - 1)
        sequence = _uint(row, "sequence", (1 << 32) - 1)
        order_id = _uint(row, "order_id", (1 << 64) - 1)
        flags = _uint(row, "flags", (1 << 8) - 1)
        action, side = row["action"], row["side"]
        if not isinstance(action, str) or not isinstance(side, str) or action not in BOOK_ACTIONS or side not in SIDES:
            raise ValueError("MBO_ACTION_OR_SIDE")
        if ts_event > as_of_event_ns:
            raise ValueError("MBO_FUTURE_EVENT")
        if flags & (F_MBP | F_TOB | F_PUBLISHER_SPECIFIC):
            raise ValueError("MBO_UNSUPPORTED_AGGREGATED_OR_PUBLISHER_FLAG")
        price, size = _price_size(row, action)

        scope = (publisher_id, instrument_id, channel_id)
        channel_scope = (publisher_id, channel_id)
        book = books.get(scope)
        if book is None:
            book = InstrumentBook(publisher_id, instrument_id, channel_id,
                                  str(row["symbol"]) if row.get("symbol") is not None else None, {})
            books[scope] = book
        elif row.get("symbol") is not None and book.symbol is not None and str(row["symbol"]) != book.symbol:
            raise ValueError("MBO_SYMBOL_MISMATCH")
        starts_snapshot = action == "R" and bool(flags & F_SNAPSHOT)
        if starts_snapshot:
            # A fresh replay snapshot is a new state/sequence baseline. Keep its
            # records in file order; do not compare its synthetic sequence/time
            # baseline against the invalid segment it is replacing.
            channel_sequences.pop(channel_scope, None)
            book.last_ts_event = None
        if book.last_ts_event is not None and ts_event < book.last_ts_event and not book.snapshot_open:
            raise ValueError("MBO_REVERSED_EVENT_TIME")
        previous_sequence = channel_sequences.get(channel_scope)
        if previous_sequence is not None and sequence < previous_sequence:
            raise ValueError("MBO_REVERSED_CHANNEL_SEQUENCE")
        # Same sequence/timestamp can describe multiple normalized records; do not reorder.
        channel_sequences[channel_scope] = sequence
        book.last_ts_event = ts_event
        book.last_event_closed = bool(flags & F_LAST)

        if flags & F_MAYBE_BAD_BOOK:
            book.orders.clear()
            book.snapshot_open = False
            book.snapshot_complete = False
            book.needs_snapshot = True
            book.blockers.add("F_MAYBE_BAD_BOOK")
            trace.append({"sourceIndex": source_index, "publisher_id": publisher_id,
                          "instrument_id": instrument_id, "channel_id": channel_id,
                          "sequence": sequence, "ts_event": ts_event, "action": action,
                          "flags": flags, "eventBoundary": bool(flags & F_LAST),
                          "applied": False, "reason": "BOOK_GAP_REQUIRES_SNAPSHOT"})
            continue

        snapshot_flag = bool(flags & F_SNAPSHOT)
        if flags & F_BAD_TS_RECV and not snapshot_flag:
            book.orders.clear()
            book.snapshot_complete = False
            book.snapshot_open = False
            book.needs_snapshot = True
            book.blockers.add("BAD_TS_RECV_OUTSIDE_SNAPSHOT")
            trace.append({"sourceIndex": source_index, "publisher_id": publisher_id,
                          "instrument_id": instrument_id, "channel_id": channel_id,
                          "sequence": sequence, "ts_event": ts_event, "action": action,
                          "flags": flags, "eventBoundary": bool(flags & F_LAST),
                          "applied": False, "reason": "BAD_TS_RECV"})
            continue

        if starts_snapshot:
            book.orders.clear()
            book.snapshot_open = True
            book.snapshot_complete = False
            book.needs_snapshot = False
            book.blockers.discard("F_MAYBE_BAD_BOOK")
            book.blockers.discard("BAD_TS_RECV_OUTSIDE_SNAPSHOT")
        elif snapshot_flag and not book.snapshot_open:
            raise ValueError("MBO_SNAPSHOT_MUST_BEGIN_WITH_CLEAR")

        if book.snapshot_open:
            if not snapshot_flag:
                raise ValueError("MBO_SNAPSHOT_INTERRUPTED")
            if action not in {"A", "R"}:
                raise ValueError("MBO_SNAPSHOT_ACTION")
        elif book.needs_snapshot:
            # Keep source trace for diagnosis, but never apply incremental updates
            # to an unknown or invalid state.
            book.blockers.add("MBO_SNAPSHOT_REQUIRED")
            trace.append({"sourceIndex": source_index, "publisher_id": publisher_id,
                          "instrument_id": instrument_id, "channel_id": channel_id,
                          "sequence": sequence, "ts_event": ts_event, "action": action,
                          "flags": flags, "eventBoundary": bool(flags & F_LAST),
                          "applied": False, "reason": "MBO_SNAPSHOT_REQUIRED"})
            continue

        applied = True
        if action == "R" and snapshot_flag:
            # Snapshot CLEAR seeds an empty state before snapshot Adds follow.
            # Keep snapshot_open until its F_LAST record closes the event.
            pass
        elif action == "R":
            book.orders.clear()
            book.snapshot_complete = False
            book.snapshot_open = False
            book.needs_snapshot = True
            book.blockers.add("CLEAR_REQUIRES_FRESH_SNAPSHOT")
            applied = False
        elif action == "A":
            if order_id == 0 or order_id in book.orders or side not in {"B", "A"}:
                raise ValueError("MBO_ADD_ORDER_ID_OR_SIDE")
            book.orders[order_id] = Order(order_id, side, price, size, source_index)
        elif action == "M":
            existing = book.orders.get(order_id)
            if existing is None:
                raise ValueError("MBO_MODIFY_UNKNOWN_ORDER")
            if side != existing.side:
                raise ValueError("MBO_MODIFY_SIDE_MISMATCH")
            if price != existing.price or size > existing.size:
                existing.priority_source_index = source_index
            existing.price, existing.size = price, size
        elif action == "C":
            existing = book.orders.get(order_id)
            if existing is None:
                raise ValueError("MBO_CANCEL_UNKNOWN_ORDER")
            if side != existing.side or price != existing.price:
                raise ValueError("MBO_CANCEL_ORDER_MISMATCH")
            if size > existing.size:
                raise ValueError("MBO_CANCEL_EXCEEDS_ORDER")
            remaining = existing.size - size
            if remaining:
                existing.size = remaining
            else:
                del book.orders[order_id]
        elif action in {"T", "F", "N"}:
            # Per Databento semantics these do not mutate resting order state.
            pass

        if book.snapshot_open and flags & F_LAST:
            book.snapshot_open = False
            book.snapshot_complete = True
            book.needs_snapshot = False
        elif action == "R" and not snapshot_flag:
            pass

        trace.append({"sourceIndex": source_index, "publisher_id": publisher_id,
                      "instrument_id": instrument_id, "channel_id": channel_id,
                      "sequence": sequence, "ts_event": ts_event, "action": action,
                      "flags": flags, "eventBoundary": bool(flags & F_LAST),
                      "applied": applied, "reason": None if applied else "CLEAR_REQUIRES_SNAPSHOT"})

    coverage_ok = _coverage_ok(coverage)
    output_books = []
    for scope, book in books.items():
        bids = _levels(book.orders, "B", depth)
        asks = _levels(book.orders, "A", depth)
        crossed = bool(bids and asks and bids[0]["price"] >= asks[0]["price"])
        blockers = set(book.blockers or set())
        if book.needs_snapshot or not book.snapshot_complete:
            blockers.add("MBO_SNAPSHOT_REQUIRED")
        if book.snapshot_open or not book.last_event_closed:
            blockers.add("MBO_EVENT_INCOMPLETE")
        if not coverage_ok:
            blockers.add("CHANNEL_CONTINUITY_UNVERIFIED")
        if crossed:
            blockers.add("CROSSED_BOOK")
        ready = (book.snapshot_complete and not book.snapshot_open and not book.needs_snapshot
                 and book.last_event_closed and coverage_ok and not crossed)
        output_books.append({
            "publisher_id": book.publisher_id,
            "instrument_id": book.instrument_id,
            "channel_id": book.channel_id,
            "symbol": book.symbol,
            "snapshotComplete": book.snapshot_complete,
            "bookReady": ready,
            "bestBid": bids[0] if bids else None,
            "bestAsk": asks[0] if asks else None,
            "bids": bids,
            "asks": asks,
            "orders": [
                {"order_id": order.order_id, "side": order.side, "price": order.price,
                 "size": order.size, "prioritySourceIndex": order.priority_source_index}
                for order in sorted(book.orders.values(), key=lambda order: order.priority_source_index)
            ],
            "orderCount": len(book.orders),
            "blockers": sorted(blockers),
        })

    return {
        "mode": "OFFLINE_MBO_ORDER_BOOK_REPLAY",
        "dataOrigin": data_origin,
        "sourceOrderPreserved": True,
        "eventsProcessed": len(rows),
        "eventTrace": trace,
        "books": output_books,
        "continuity": coverage if isinstance(coverage, dict) else {"status": "UNVERIFIED"},
        "status": "SYNTHETIC_TEST_ONLY" if data_origin == "SYNTHETIC_TEST_ONLY" else "LOCAL_FIXTURE_TEST_ONLY",
        "researchEligible": False,
        "feedEmitted": False,
        "signal": "WAIT",
        "executable": False,
    }
