"""Isolated, event-driven M15 research rehearsal. Never activates market data.

A caller delivers a synthetic packet; only a newly closed M15 bar invokes
the existing V3/r2 pipeline. State is process-local, not durable, and a
gap or conflicting revision latches the instance closed. No orders,
network, scheduler, or market feed authorization.
"""
import datetime as dt
import hashlib
import json
import os
from ultimate_paper import PaperAccount, evaluate
from xauusd_feed_gate import SourcePolicy, intake_payload, parse_utc
from xauusd_research_pipeline import run_research_pipeline

WIDTH = dt.timedelta(minutes=15)

class OfflineM15Cycle:
    def __init__(self, *, paper_rehearsal=False):
        self.last_close = None
        self.last_digest = None
        self.blocked = False
        self.calls = 0
        self.paper = None
        if paper_rehearsal is True:
            if os.environ.get('GPP_SYNTHETIC_TEST_SIMULATION') != '1':
                raise ValueError('Explicit isolated test process required')
            self.paper = PaperAccount(':memory:')

    def close(self):
        if self.paper is not None:
            self.paper.close()
            self.paper = None

    def lock(self):
        self.blocked = True
        if self.paper is not None:
            self.paper.kill()

    def report(self, status, reviewed=False):
        summary = self.paper.summary() if self.paper is not None else None
        return dict(status=status, engineInvocations=self.calls,
                    enginesReviewed=reviewed, signal="WAIT", executable=False,
                    paperOrdersAllowed=False, liveOrdersAllowed=False,
                    realMarketDataConnected=False, providerRequestsMade=0,
                    syntheticPaperOnly=summary is not None,
                    syntheticPending=len(summary['pending']) if summary else 0,
                    syntheticOpen=len(summary['position']) if summary else 0,
                    syntheticClosed=len(summary['trades']) if summary else 0)

    def accept(self, packet, context, now):
        if self.blocked:
            return self.report("REQUALIFICATION_REQUIRED")
        if not isinstance(packet, dict) or packet.get("mode") != "synthetic":
            return self.report("SYNTHETIC_ONLY")
        try:
            now = parse_utc(now.isoformat())
            checked = intake_payload(packet, now, SourcePolicy())
            if checked["status"] != "SYNTHETIC_TEST_ONLY":
                return self.report("INTAKE_REJECTED")
            latest = checked["frames"]["15min"]["candles"][-1]
            close = parse_utc(latest["openTime"]) + WIDTH
            digest = hashlib.sha256(json.dumps(
                checked["frames"]["15min"]["candles"], sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            return self.report("INTAKE_REJECTED")
        if self.last_close is not None:
            if close == self.last_close:
                if digest != self.last_digest:
                    self.lock()
                    return self.report("CONFLICTING_CLOSED_HISTORY")
                return self.report("DUPLICATE_SKIPPED")
            if close != self.last_close + WIDTH:
                self.lock()
                return self.report("GAP_OR_REVERSED_CLOSE")
        if not dt.timedelta(0) <= now-close <= dt.timedelta(seconds=30):
            return self.report("NOT_FRESH_M15_CLOSE")
        # Consume once even if the engine fails: no replay with later
        # context masquerading as evidence available at the original close.
        self.last_close, self.last_digest = close, digest
        self.calls += 1
        result = run_research_pipeline(packet, now, SourcePolicy(), context,
                                       allow_synthetic_simulation=True)
        reviewed = (result.get("signal") == "WAIT"
                    and result.get("executable") is False
                    and result.get("engines", {}).get("v3") == "REVIEWED"
                    and result.get("engines", {}).get("ultimateR2") == "REVIEWED")
        if self.paper is not None:
            # Exact-close fixtures only. Never retrospectively fill a next
            # bar open that occurred before a late decision.
            if (not reviewed or now != close
                    or os.environ.get('GPP_SYNTHETIC_TEST_SIMULATION') != '1'
                    or result.get('simulationOnly') is not True
                    or result.get('paperSimulationAllowed') is not True):
                self.lock()
                return self.report("SYNTHETIC_PAPER_REQUALIFICATION_REQUIRED")
            snapshot = result.get('paperSnapshot')
            if not isinstance(snapshot, dict):
                self.lock()
                return self.report("SYNTHETIC_PAPER_SNAPSHOT_MISSING")
            agreement = result.get('engineCandidates', {})
            # Re-evaluate V3 with persisted account risk, then veto any
            # disagreement. Never promote the public WAIT decision.
            def evaluate_agreement(supplied):
                decision = evaluate(supplied)
                side = decision.get('researchCandidate')
                if (side not in ('BUY', 'SELL')
                        or agreement.get('v3') != side
                        or agreement.get('ultimateR2') != side):
                    decision = {**decision, 'researchCandidate': 'NONE'}
                return decision
            try:
                bar = snapshot['frames']['M15'][-1]
                if bar.get('dataOrigin') != 'SYNTHETIC_TEST_ONLY':
                    raise ValueError('Synthetic bar required')
                self.paper.step(bar, snapshot, evaluator=evaluate_agreement)
            except Exception:
                self.lock()
                return self.report("SYNTHETIC_PAPER_FAILURE")
        return self.report("OFFLINE_CYCLE_REVIEWED" if reviewed
                           else "ENGINE_NOT_REVIEWED", reviewed)
