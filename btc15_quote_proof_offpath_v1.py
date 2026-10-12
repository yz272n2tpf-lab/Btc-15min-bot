"""Off-path quote-proof materializer candidate. SIGNAL ONLY / NO ORDERS.

This module deliberately does not change the authoritative quote/decision path.
The native path may enqueue only a small immutable witness plus references to
already-received event objects. Full JSON serialization and disk I/O happen on
a daemon worker. A proof is publishable only if an independent validator
reconstructs the exact witness identity. Queue overflow drops evidence, never
blocks strategy evaluation.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import queue
import threading
from collections import Counter
from itertools import count
import sys

GAP_REASONS={'QUEUE_OVERFLOW','QUEUE_BYTES','ADMISSION_BUSY','CLOSED',
             'INVALID_OBSERVATION','OVERSIZE','WRITER_FAILURE','PROOF_REJECTED','CAPTURE_ERROR'}

@dataclass(frozen=True)
class Observation:
    kind: str
    fields: tuple
    charge: int

@dataclass(frozen=True)
class Witness:
    ticker: str
    source_time: str
    epoch: str
    consumed_ms: int
    market_id: str
    sid: int
    seq: int
    exchange_ts_ms: int
    close_ms: int

    @property
    def identity(self):
        return [self.market_id, self.sid, self.seq, self.exchange_ts_ms]

@dataclass(frozen=True)
class Capture:
    witness: Witness
    events: tuple

class OffPathProofWriter:
    """Bounded best-effort evidence writer; never blocks submit()."""
    def __init__(self, directory, validator, max_bytes, queue_size=2, retain=32,
                 *, archive=None, queue_bytes=8*1024*1024, admission_limits=None):
        limits=admission_limits or dict(queue_size=64,queue_bytes=8*1024*1024)
        if (set(limits)!={'queue_size','queue_bytes'} or any(type(v) is not int for v in limits.values())
                or not 1<=limits['queue_size']<=16384 or not 1<=limits['queue_bytes']<=32*1024*1024):
            raise ValueError('Explicit archive admission limits')
        if archive is not None and not (1<=int(queue_size)<=limits['queue_size'] and 1<=int(queue_bytes)<=limits['queue_bytes']
                                       and 1<=int(max_bytes)<=2*1024*1024):
            raise ValueError('Isolated archive admission budget')
        self.directory = Path(directory)
        self.validator = validator
        self.max_bytes = int(max_bytes)
        self.queue = queue.Queue(maxsize=int(queue_size))
        self.retain = max(1, int(retain))
        self.dropped = 0
        self.published = 0
        self.rejected = 0
        self.archive = archive
        # Optional mirror receives validated bytes AFTER the existing cache is
        # published. Its queue/disk is never the proof queue used by MAIN safety.
        self.evidence_sink = None
        self.queue_bytes = int(queue_bytes)
        self.queued_bytes = 0
        self.peak_queued_bytes = 0
        self._admission = threading.Lock()
        self._loss_counters = {reason:count() for reason in GAP_REASONS}
        self._loss_reads = Counter()
        self._status_lock = threading.Lock()
        self._reported = Counter()
        self._closing = False
        self.archive_failed = False
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="btc15-offpath-quote-proof")
        self._thread.start()

    def submit(self, witness, events):
        if self.archive is not None and self.archive_failed:
            self.gap('WRITER_FAILURE');return False
        capture = Capture(witness=witness, events=tuple(events))
        accepted=self._enqueue(capture, self.max_bytes)
        if not accepted and self.evidence_sink is not None:
            try:self.evidence_sink.gap('PROOF_REJECTED')
            except Exception:pass
        return accepted

    def gap(self, reason):
        if reason not in GAP_REASONS:
            reason = 'CAPTURE_ERROR'
        next(self._loss_counters[reason])  # atomic C-level increment on target CPython

    def _loss_snapshot(self):
        # Only diagnostic/worker readers lock; source producers never wait here.
        with self._status_lock:
            result=Counter()
            for reason,counter in self._loss_counters.items():
                result[reason]=next(counter)-self._loss_reads[reason]
                self._loss_reads[reason]+=1
            return +result

    def submit_observation(self, kind, **fields):
        """Only immutable scalar/byte fields; no serialization, filesystem or network."""
        if self.archive is None:
            return False
        if self.archive_failed:
            self.gap('WRITER_FAILURE');return False
        try:
            if len(fields) > 32 or not isinstance(kind, str) or len(kind) > 64:
                raise ValueError('schema')
            charge = 512
            for key, value in fields.items():
                if not isinstance(key, str) or len(key) > 64 or type(value) not in (str, bytes, int, float, bool, type(None)):
                    raise ValueError('mutable observation')
                if key != 'raw' and isinstance(value,(str,bytes)) and len(value)>1024:
                    raise ValueError('identity budget')
                charge += len(value) * (4 if isinstance(value,str) else 1) if isinstance(value,(str,bytes)) else 32
            if charge > 4*1024*1024:
                self.gap('OVERSIZE'); return False
            return self._enqueue(Observation(kind,tuple(fields.items()),charge), charge)
        except Exception:
            self.gap('INVALID_OBSERVATION'); return False

    def _enqueue(self, capture, charge):
        if self._closing:
            self.gap('CLOSED'); return False
        if not self._admission.acquire(blocking=False):
            self.gap('ADMISSION_BUSY'); return False
        try:
            if self._closing:
                self.gap('CLOSED');return False
            if self.queued_bytes + charge > self.queue_bytes:
                self.dropped += 1; self.gap('QUEUE_BYTES'); return False
            try:
                self.queue.put_nowait((capture,charge))
                self.queued_bytes += charge
                self.peak_queued_bytes = max(self.peak_queued_bytes,self.queued_bytes)
                return True
            except queue.Full:
                self.dropped += 1; self.gap('QUEUE_OVERFLOW'); return False
        finally:
            self._admission.release()

    def _flush_gaps(self):
        if self.archive is None or self.archive_failed:
            return
        current = self._loss_snapshot()
        delta = current - self._reported
        if delta:
            self.archive.write('EVIDENCE_GAP',dict(reasons=dict(delta)))
            self._reported = current

    def _archive_error(self):
        first = not self.archive_failed
        self.archive_failed = True
        self.gap('WRITER_FAILURE')
        # A full/broken disk cannot guarantee a durable marker on that disk.
        # Memory status + worker diagnostic + unclosed session expose the gap.
        if first:print('BTC15 EVIDENCE GAP | WRITER_FAILURE | session incomplete',file=sys.stderr,flush=True)

    def close(self, timeout=5):
        """Explicit offline teardown. Never called by a trading decision."""
        with self._admission:self._closing = True
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def status(self):
        return dict(losses=dict(self._loss_snapshot()),archive_failed=self.archive_failed,
                    queued_bytes=self.queued_bytes,peak_queued_bytes=self.peak_queued_bytes,
                    queue_capacity=self.queue.maxsize,queue_byte_budget=self.queue_bytes)

    def _run(self):
        if self.archive is not None:
            try:self.archive.start()
            except Exception:self._archive_error()
        while True:
            try:item = self.queue.get(timeout=.05)
            except queue.Empty:
                try:self._flush_gaps()
                except Exception:self._archive_error()
                if self._closing:
                    if self.archive is not None:
                        try:
                            if not self.archive_failed:self.archive.write('STOP',dict(clean=True))
                        except Exception:self._archive_error()
                        finally:self.archive.close()
                    return
                continue
            capture,charge = item
            try:
                self._flush_gaps()
                if isinstance(capture, Observation):
                    if not self.archive_failed:
                        self.archive.observe(capture.kind,dict(capture.fields))
                else:
                    self._materialize(capture)
            except Exception:
                self.rejected += 1
                if self.archive is not None:self._archive_error()
            finally:
                with self._admission:self.queued_bytes -= charge
                self.queue.task_done()

    def _materialize(self, capture):
        w = capture.witness
        proof = {
            "source_time": w.source_time,
            "ticker": w.ticker,
            "epoch": w.epoch,
            "consumed_ms": w.consumed_ms,
            "identity": w.identity,
            "events": list(capture.events),
        }
        raw = json.dumps(proof, separators=(",", ":"), allow_nan=False).encode()
        if len(raw) > self.max_bytes:
            raise ValueError("oversized quote proof")
        # Validator must replay the payload and return the exact reconstructed
        # identity. Mutation, stale refs, cross-market data, gaps and restarts
        # therefore fail closed before anything is published.
        try:
            reconstructed = self.validator(proof, w)
        except Exception:
            self.gap('PROOF_REJECTED')
            if self.evidence_sink is not None:
                try:self.evidence_sink.gap('PROOF_REJECTED')
                except Exception:pass
            raise
        if list(reconstructed) != w.identity:
            raise ValueError("off-path proof identity mismatch")
        digest = hashlib.sha256(raw).hexdigest()
        if self.archive is not None:
            if not self.archive_failed:
                from dataclasses import asdict
                self.archive.proof(proof, asdict(w), raw, digest)
                self.published += 1
            # Archive mode replaces the rolling blob cache in this isolated
            # instance. Existing default instances retain their old behavior.
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        blob = self.directory / (digest + ".json")
        if not blob.exists():
            tmp = self.directory / (digest + ".tmp")
            tmp.write_bytes(raw)
            tmp.replace(blob)
        # The small index is written only after the content-addressed blob has
        # passed replay validation. It is evidence metadata, not strategy input.
        index = {
            "schema": "BTC15_QUOTE_PROOF_REF_V1",
            "sha256": digest,
            "bytes": len(raw),
            "ticker": w.ticker,
            "source_time": w.source_time,
            "epoch": w.epoch,
            "consumed_ms": w.consumed_ms,
            "identity": w.identity,
            "signal_only": True,
            "orders": False,
        }
        idx_raw = json.dumps(index, separators=(",", ":"), allow_nan=False).encode()
        idx = self.directory / "latest.json"
        tmp = self.directory / "latest.tmp"
        tmp.write_bytes(idx_raw)
        tmp.replace(idx)
        self.published += 1
        if self.evidence_sink is not None:
            try:
                from dataclasses import asdict
                self.evidence_sink.submit_observation('PROOF_BYTES', raw=raw,
                    witness_json=json.dumps(asdict(w),separators=(',',':')))
            except Exception:
                try:self.evidence_sink.gap('CAPTURE_ERROR')
                except Exception:pass
        # Bound disk growth. Keep newest validated content-addressed blobs only.
        blobs = sorted(self.directory.glob('*.json'), key=lambda p: p.stat().st_mtime_ns, reverse=True)
        blobs = [p for p in blobs if p.name != 'latest.json']
        for stale in blobs[self.retain:]:
            try: stale.unlink()
            except FileNotFoundError: pass
