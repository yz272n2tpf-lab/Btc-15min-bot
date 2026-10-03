"""Evidence-only closed-interval qualification and mandatory scoring admission.

One bounded capture run is one interval; all its contracts inherit the latch.
Collection remains PENDING (never scoreable). Evaluation runs after final fsync,
outside producer/transport hot paths. Any observed failure is persisted at once.
Raw evidence is never rewritten, removed, or filtered. No strategy imports.
"""
from collections import deque
import gzip
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import tempfile

SCHEMA = 'BTC15_EVIDENCE_QUALIFICATION_V1'
LIMITS = {
    'main': ((100, 1100), (250, 2250), (1000, 4000), (5000, 10000), (10000, 20000)),
    'v81': ((100, 700), (250, 1500), (1000, 5000), (5000, 12500), (10000, 20000)),
}
REASONS = frozenset(('RATE_ENVELOPE_EXCEEDED', 'SEQUENCE_GAP', 'CAPTURE_BUFFER_FULL',
                     'CENSUS_MISMATCH', 'INCOMPLETE_FLUSH', 'CAPTURE_FAILURE'))
MAX_RECORDS = 4_000_000
MAX_ARCHIVE = 1024*1024*1024
MAX_STREAMS = 65536

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def binding(c):
    return {k: c.get(k) for k in ('run_id', 'build', 'mode', 'capture_files', 'clock_domain', 'boot_id')}

def pending(c):
    return dict(schema=SCHEMA, binding=binding(c), interval_id=c['run_id'],
                scope='ENTIRE_CAPTURE_RUN_ALL_CONTRACTS', qualification_state='PENDING',
                reason_codes=[], reasons=[], closed=False, archive=None,
                rate_basis='ALL_CAPTURE_PACKETS_AGGREGATED_PER_SIDE; PRODUCER_HOOK_BOOTTIME',
                rolling_window='(event_boot_ns-window_ns,event_boot_ns]',