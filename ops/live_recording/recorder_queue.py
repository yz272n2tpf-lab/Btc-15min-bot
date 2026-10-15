"""Recorder-local cumulative loss counters for off-path evidence admission.

The existing quote-proof owner's writer is deliberately unchanged. Its
_loss_snapshot() consumes itertools.count() and reports a DELTA; treating that
delta as a lifetime loss in a periodic recorder health check is incorrect, and
polls themselves advance the count iterator. This subclass returns only real
gap() increments as a cumulative counter. It never reduces/drop-filters input.
"""
from collections import Counter

from btc15_quote_proof_offpath_v1 import OffPathProofWriter


class RecorderOffPathProofWriter(OffPathProofWriter):
    def __init__(self, *args, **kwargs):
        # The base constructor launches the worker thread. Initialize this
        # before that thread can call our _loss_snapshot() override.
        self._snapshot_polls = Counter()
        super().__init__(*args, **kwargs)

    def _loss_snapshot(self):
        """Monotone count of real losses; polls are not recorded as losses."""
        with self._status_lock:
            current = Counter()
            for reason, counter in self._loss_counters.items():
                # next() advances the iterator both for actual gap() calls and
                # polls. Subtract the number of preceding polls, not preceding
                # losses. Both sources increment atomically on target CPython.
                observed = next(counter)
                real = observed - self._snapshot_polls[reason]
                self._snapshot_polls[reason] += 1
                if real < 0:
                    raise ValueError('LOSS_COUNTER_REGRESSION:' + reason)
                if real:
                    current[reason] = real
            return current
