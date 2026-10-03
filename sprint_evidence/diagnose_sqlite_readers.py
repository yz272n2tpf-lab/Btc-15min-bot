"""Focused recovery diagnostic: a real read transaction versus zero-wait writes.

No socket, network, source evaluation, clock admission or strategy action.
This intentionally exercises the actual unchanged Receiver and SQLite engine.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch

from test_sprint_capture import IDENTITY, MemorySocket
from test_btc15_external_evidence_admission_v1 import POLICY, KEY
from round2_evidence.capture import initialize, DetachedRecorder
from round2_evidence.test_round2 import artifact
from sprint_evidence.passive_capture import Producer, Receiver, add_event_store


def setup(path):
    initialize(path, POLICY); add_event_store(path)
    sock = MemorySocket()
    producer = Producer('unused', IDENTITY, KEY, sock=sock)
    receiver = Receiver(path, [IDENTITY], {(IDENTITY.producer_id, IDENTITY.run_id): KEY},
        common_recorder=DetachedRecorder(path, POLICY, acquisition_key=KEY))
    return sock, producer, receiver


def read_lock(path):
    reader = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=0)
    reader.execute('BEGIN')
    reader.execute('SELECT * FROM meta').fetchall()
    return reader


def diagnose():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'before-event.sqlite'
        sock, producer, receiver = setup(path)
        reader = read_lock(path)
        assert producer.offer('NATIVE_CYCLE', {'synthetic': True})
        rejected = receiver.accept(sock.packets[-1])
        assert rejected['status'] == 'UNAVAILABLE' and 'locked' in rejected['reason']
        reader.rollback(); reader.close()
        with sqlite3.connect(path) as db:
            assert db.execute('SELECT COUNT(*) FROM producer_events').fetchone()[0] == 0
        assert producer.offer('NATIVE_CYCLE', {'synthetic': True, 'next': True})
        successor = receiver.accept(sock.packets[-1])
        assert successor['status'] == 'RECORDED_UNAVAILABLE_GAP'
        producer.close()

        second = Path(directory)/'after-event.sqlite'
        sock, producer, receiver = setup(second)
        member = artifact()[0]
        assert producer.common_member(member, 0)
        packet = sock.packets[-1]
        original_common = receiver._common
        def reader_between_commits(event):
            reader = read_lock(second)
            try:
                return original_common(event)
            finally:
                reader.rollback(); reader.close()
        with patch.object(receiver, '_common', side_effect=reader_between_commits):
            bridge_failure = receiver.accept(packet)
        assert bridge_failure['status'] == 'UNAVAILABLE' and 'locked' in bridge_failure['reason']
        with sqlite3.connect(second) as db:
            assert db.execute('SELECT COUNT(*) FROM producer_events').fetchone()[0] == 1
            assert db.execute('SELECT COUNT(*) FROM members').fetchone()[0] == 0
        repair = receiver.accept(packet)  # exact consumer-local packet, no upstream read
        assert repair['status'] == 'DUPLICATE_RECORDED'
        with sqlite3.connect(second) as db:
            assert db.execute('SELECT original FROM members').fetchone()[0] == member
            assert db.execute('SELECT COUNT(*) FROM producer_events').fetchone()[0] == 1
        producer.close()
        return dict(schema='BTC15_SQLITE_READER_DIAGNOSIS_V1', assertions_pass=True,
            conclusion='REAL_CONSUMER_CONCURRENCY_HAZARD_NOT_PROVEN_TEST_DRIVER_ONLY',
            reader_mode='ro', journal_mode='delete', timeout_seconds=0,
            before_event_commit=rejected, successor_after_loss=successor,
            between_event_and_member_commit=bridge_failure, exact_local_replay=repair,
            upstream_callbacks=0, new_source_reads=0, orders=0,
            implication='Positive smoke passes when inspection follows completion. Continuous monitoring must not read the active archive concurrently without a qualified consumer-side contention design. The prior failed smoke omitted receipts, so its exact failure cause cannot be proved retrospectively.',
            activation_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = diagnose()
    with open(args.output, 'x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True); stream.write('\n')
    print(json.dumps(report, sort_keys=True))
