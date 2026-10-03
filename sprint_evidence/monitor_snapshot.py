"""Bounded consumer-owned monitoring view; monitors never open active SQLite.

Call publish only in the sole receiver thread after accept returns. Snapshot
replacement is atomic. This is a diagnostic view, not immutable primary evidence
or a clock certificate. Original authenticated bytes remain in the archive.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from .passive_capture import Receiver, digest, pack, strict

MAX_SNAPSHOT = 1024 * 1024
MAX_EVENTS = 64


def publish(archive, destination, receipt):
    archive, destination = Path(archive), Path(destination)
    if archive.resolve() == destination.resolve() or destination.is_symlink():
        raise ValueError('SNAPSHOT_PATH_MUST_BE_SEPARATE')
    events, used = [], 0
    # Sole receiver invocation, after BOTH original transactions return.
    with closing(sqlite3.connect(archive.resolve().as_uri()+'?mode=ro', uri=True, timeout=0)) as db:
        for (raw,) in db.execute('SELECT raw FROM producer_events ORDER BY rowid DESC LIMIT ?', (MAX_EVENTS,)):
            if used + len(raw) > MAX_SNAPSHOT // 2:
                break
            events.append(strict(raw)); used += len(raw)
    payload = dict(schema='BTC15_MONITOR_SNAPSHOT_V1', clock_qualified=False,
        diagnostic_only=True, created_wall_ns=time.time_ns(), receipt=receipt,
        events=list(reversed(events)), bounded_tail=True,
        full_history_or_coverage_proven=False)
    raw = pack(dict(payload=payload, sha256=digest(pack(payload))))
    if len(raw) > MAX_SNAPSHOT:
        raise ValueError('SNAPSHOT_BYTE_LIMIT')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.monitor-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return dict(status='PUBLISHED_DIAGNOSTIC_SNAPSHOT', bytes=len(raw), events=len(events))


def read(path):
    with open(path, 'rb') as stream:
        raw = stream.read(MAX_SNAPSHOT+1)
    if len(raw) > MAX_SNAPSHOT:
        raise ValueError('SNAPSHOT_BYTE_LIMIT')
    envelope = strict(raw); payload = envelope['payload']
    if envelope['sha256'] != digest(pack(payload)):
        raise ValueError('SNAPSHOT_HASH_MISMATCH')
    if payload['schema'] != 'BTC15_MONITOR_SNAPSHOT_V1' or payload['clock_qualified'] is not False:
        raise ValueError('SNAPSHOT_NOT_CLOCK_CERTIFICATE')
    return payload


class SnapshotReceiver(Receiver):
    """Same receiver, with a separate bounded diagnostic view after persistence.

    No retry/ACK/upstream callback. Disk failure affects this consumer only.
    External processes must use the JSON view, never the active archive.
    """
    def __init__(self, *args, snapshot_path, **kwargs):
        super().__init__(*args, **kwargs)
        self.snapshot_path = Path(snapshot_path)

    def accept(self, packet):
        receipt = super().accept(packet)
        try:
            snapshot = publish(self.path, self.snapshot_path, receipt)
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
            self.status = 'UNAVAILABLE'
            return dict(status='UNAVAILABLE', reason='MONITOR_SNAPSHOT_FAILED:'+str(exc),
                        acquisition_receipt=receipt, orders=False)
        return dict(receipt, monitoring_snapshot=snapshot)


def inspect(path, **expected):
    from .health_detectors import inspect_events
    try:
        payload = read(path)
        result = inspect_events(payload['events'], **expected)
        result.update(acquisition_receipt=payload['receipt'],
            snapshot_created_wall_ns=payload['created_wall_ns'],
            snapshot_clock_qualified=False, snapshot_freshness_qualified=False)
        return result
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return dict(state='UNAVAILABLE', reason='MONITOR_SNAPSHOT_UNAVAILABLE', detail=str(exc))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.snapshot), sort_keys=True))
