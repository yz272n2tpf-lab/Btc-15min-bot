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

    @property
    def identity(self):
        return [self.market_id, self.sid, self.seq, self.exchange_ts_ms]

@dataclass(frozen=True)
class Capture:
    witness: Witness
    events: tuple

class OffPathProofWriter:
    """Bounded best-effort evidence writer; never blocks submit()."""
    def __init__(self, directory, validator, max_bytes, queue_size=2):
        self.directory = Path(directory)
        self.validator = validator
        self.max_bytes = int(max_bytes)
        self.queue = queue.Queue(maxsize=int(queue_size))
        self.dropped = 0
        self.published = 0
        self.rejected = 0
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="btc15-offpath-quote-proof")
        self._thread.start()

    def submit(self, witness, events):
        capture = Capture(witness=witness, events=tuple(events))
        try:
            self.queue.put_nowait(capture)
            return True
        except queue.Full:
            self.dropped += 1
            return False

    def _run(self):
        while True:
            capture = self.queue.get()
            try:
                self._materialize(capture)
            except Exception:
                self.rejected += 1
            finally:
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
        reconstructed = self.validator(proof, w)
        if list(reconstructed) != w.identity:
            raise ValueError("off-path proof identity mismatch")
        digest = hashlib.sha256(raw).hexdigest()
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
