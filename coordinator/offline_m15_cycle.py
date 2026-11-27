"""Isolated, event-driven M15 research rehearsal. Never activates market data.

A caller delivers a synthetic packet; only a newly closed M15 bar invokes
the existing V3/r2 pipeline. Optional test-only SQLite stores checkpoints, and a
gap or conflicting revision latches the instance closed. No orders,
network, scheduler, or market feed authorization.
"""
import datetime as dt
import hashlib
import json
import os
import pathlib
import stat
from ultimate_paper import PaperAccount, evaluate
from xauusd_feed_gate import SourcePolicy, intake_payload, parse_utc
from xauusd_research_pipeline import run_research_pipeline

WIDTH = dt.timedelta(minutes=15)

class OfflineM15Cycle:
    def __init__(self, *, paper_rehearsal=False, paper_database=None):
        self.last_close = None
        self.last_digest = None
        self.last_frames = None
        self.blocked = False
        self.calls = 0
        self.paper = None
        self.persistent_rehearsal = paper_database is not None
        if self.persistent_rehearsal and paper_rehearsal is not True:
            raise ValueError('Explicit synthetic paper mode required')
        if paper_rehearsal is True:
            if os.environ.get('GPP_SYNTHETIC_TEST_SIMULATION') != '1':
                raise ValueError('Explicit isolated test process required')
            if self.persistent_rehearsal:
                path = pathlib.Path(paper_database)
                if (not path.is_absolute() or path.name != 'synthetic-m15-rehearsal.sqlite3'
                        or path.parent.resolve() != path.parent or path.is_symlink()
                        or not path.parent.is_dir() or stat.S_IMODE(path.parent.stat().st_mode) & 0o077):
                    raise ValueError('Dedicated private test directory required')
                if path.exists() and (not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077):
                    raise ValueError('Unsafe rehearsal database')
                if not path.exists():
                    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    os.close(fd)
                self.paper = PaperAccount(path)
                try:
                    self.restore_checkpoint()
                except Exception:
                    self.paper.close()
                    self.paper = None
                    raise
            else:
                self.paper = PaperAccount(':memory:')

    def restore_checkpoint(self):
        summary = self.paper.summary()
        self.blocked = bool(summary['account']['killed'])
        rows = self.paper.db.execute('SELECT open_ms,digest,payload FROM observations ORDER BY open_ms').fetchall()
        if not rows:
            if summary['account']['last_ms'] is not None:
                raise ValueError('Missing rehearsal checkpoint')
            return
        if summary['account']['last_ms'] != rows[-1]['open_ms']:
            raise ValueError('Rehearsal checkpoint head mismatch')
        for row in rows:
            if hashlib.sha256(row['payload'].encode()).hexdigest() != row['digest']:
                raise ValueError('Observation checksum mismatch')
            data = json.loads(row['payload'])
            snapshot = data.get('snapshot')
            checkpoint = snapshot.get('syntheticCycleCheckpoint') if isinstance(snapshot, dict) else None
            if (data['bar'].get('dataOrigin') != 'SYNTHETIC_TEST_ONLY'
                    or not isinstance(checkpoint, dict)
                    or set(checkpoint) != {'15min','1h','4h'}):
                raise ValueError('Not a dedicated synthetic cycle ledger')
            close = dt.datetime.fromtimestamp(row['open_ms']/1000, dt.timezone.utc) + WIDTH
            frames = {k: {'candles': v, 'expectedOpenTimes': [x['openTime'] for x in v]}
                      for k,v in checkpoint.items()}
            packet = dict(provider='SYNTHETIC_RESTORE',instrument='XAU/USD',mode='synthetic',
                          receivedUTC=close.isoformat(),frames=frames)
            checked = intake_payload(packet,close,SourcePolicy())
            if (checked['status'] != 'SYNTHETIC_TEST_ONLY' or
                    parse_utc(checkpoint['15min'][-1]['openTime']) + WIDTH != close):
                raise ValueError('Invalid stored cycle checkpoint')
        self.last_close = close
        self.last_digest = hashlib.sha256(json.dumps(checkpoint,sort_keys=True,
            separators=(',',':'),allow_nan=False).encode()).hexdigest()
        self.last_frames = {k: {x['openTime']:x for x in v} for k,v in checkpoint.items()}
        self.calls = len(rows)


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
                {k: v["candles"] for k, v in checked["frames"].items()}, sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            return self.report("INTAKE_REJECTED")
        frames = {k: {row["openTime"]: row for row in v["candles"]}
                  for k, v in checked["frames"].items()}
        if self.last_close is not None:
            if close == self.last_close:
                if digest != self.last_digest:
                    self.lock()
                    return self.report("CONFLICTING_CLOSED_HISTORY")
                return self.report("DUPLICATE_SKIPPED")
            if close != self.last_close + WIDTH:
                self.lock()
                return self.report("GAP_OR_REVERSED_CLOSE")
            for interval, previous in self.last_frames.items():
                current = frames[interval]
                common = previous.keys() & current.keys()
                # A sliding window may drop older bars, but each family
                # must still contain its previous latest bar unchanged.
                if (not common or max(previous) not in current
                        or any(previous[k] != current[k] for k in common)):
                    self.lock()
                    return self.report("CONFLICTING_CLOSED_HISTORY")
        if not dt.timedelta(0) <= now-close <= dt.timedelta(seconds=30):
            return self.report("NOT_FRESH_M15_CLOSE")
        # Consume once even if the engine fails: no replay with later
        # context masquerading as evidence available at the original close.
        self.last_close, self.last_digest = close, digest
        self.last_frames = frames
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
                # Test metadata belongs in the stored snapshot, not in the frozen evaluator.
                decision = evaluate({k: v for k, v in supplied.items()
                                     if k != 'syntheticCycleCheckpoint'})
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
                checkpoint = {k: v['candles'] for k,v in checked['frames'].items()}
                if self.persistent_rehearsal:
                    snapshot = {**snapshot, 'syntheticCycleCheckpoint': checkpoint}
                self.paper.step(bar, snapshot, evaluator=evaluate_agreement)
            except Exception:
                self.lock()
                return self.report("SYNTHETIC_PAPER_FAILURE")
        return self.report("OFFLINE_CYCLE_REVIEWED" if reviewed
                           else "ENGINE_NOT_REVIEWED", reviewed)
