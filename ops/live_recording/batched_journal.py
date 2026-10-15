"""Private recorder-only gzip batching; original native journals stay unchanged.

No input sampling, dropping, pruning, source polling, trade or network actions.
The off-path worker appends the *exact* canonical JSONL records in order. Only
the gzip member boundary and disk-fsync granularity differ. A crash before a
batch fsync makes that capture unsealed/incomplete, never a complete history.
"""
from datetime import datetime, timezone
import gzip
import os
import time
import uuid

from btc15_information_journal_v1 import CompressedJournal


class BatchedCompressedJournal(CompressedJournal):
    # Bound memory even if the writer sees a multi-megabyte observation.
    # A 256 KiB batch amortizes compression/syscalls/fsync without imposing
    # any wait, I/O, or extra work on the native signal/quote decision path.
    BATCH_RAW_BYTES = 256 * 1024
    MAX_LINGER_SECONDS = .25

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pending = []
        self.pending_raw_bytes = 0
        self.pending_records = 0
        self.durable_records = 0
        self._last_flush = time.monotonic()

    def append(self, line):
        if not isinstance(line, bytes) or not line.endswith(b'\n'):
            raise ValueError('Complete journal line required')
        if self.max_record_bytes is not None and len(line) > self.max_record_bytes:
            raise ValueError('Evidence record budget exceeded')
        with self.lock:
            if self.failed:
                raise OSError('Recorder journal requires process restart')
            if self._pending and self.pending_raw_bytes + len(line) > self.BATCH_RAW_BYTES:
                self._flush_locked()
            self._pending.append(line)
            self.pending_raw_bytes += len(line)
            self.pending_records += 1
            # Logical counts are not durability receipts: only durable_records
            # counts lines fsynced to the volume.
            self.records += 1
            self.raw_bytes += len(line)
            if self.pending_raw_bytes >= self.BATCH_RAW_BYTES or time.monotonic() - self._last_flush >= self.MAX_LINGER_SECONDS:
                self._flush_locked()

    def flush_due(self):
        with self.lock:
            if self._pending and time.monotonic() - self._last_flush >= self.MAX_LINGER_SECONDS:
                self._flush_locked()

    def flush(self):
        with self.lock:
            self._flush_locked()

    def _flush_locked(self):
        if not self._pending:
            return
        if self.failed:
            raise OSError('Recorder journal requires process restart')
        encoded = gzip.compress(b''.join(self._pending), compresslevel=6, mtime=0)
        try:
            if self.segment_bytes is not None and len(encoded) > self.segment_bytes:
                raise ValueError('Evidence batch exceeds segment budget')
            day = datetime.fromtimestamp(self.clock(), timezone.utc).strftime('%Y%m%d')
            self.directory.mkdir(parents=True, exist_ok=True)
            if self.total_bytes is None:
                self.total_bytes = (
                    sum(p.stat().st_size for p in self.directory.glob('*.jsonl.gz'))
                    if self.max_total_bytes is not None else 0
                )
            if self.max_total_bytes is not None and self.total_bytes + len(encoded) > self.max_total_bytes:
                raise OSError('Evidence disk budget exhausted; no automatic pruning')
            rotate = (self.segment_bytes is not None and self.path is not None
                      and self.path.exists() and self.path.stat().st_size + len(encoded) > self.segment_bytes)
            if self.day != day or rotate:
                self.day = day
                self.path = self.directory / (
                    day + '-' + self.session + '-' + uuid.uuid4().hex[:8] + '.jsonl.gz')
            created = not self.path.exists()
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                remaining = memoryview(encoded)
                while remaining:
                    written = os.write(fd, remaining)
                    if not written:
                        raise OSError('Journal short write')
                    remaining = remaining[written:]
                os.fsync(fd)
                if created:
                    directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
            finally:
                os.close(fd)
            self.stored_bytes += len(encoded)
            self.total_bytes += len(encoded)
            self.durable_records += self.pending_records
            self.pending_records = 0
            self.pending_raw_bytes = 0
            self._pending.clear()
            self._last_flush = time.monotonic()
        except BaseException:
            # Prevent writes after a possibly torn gzip member. No auto-retry,
            # deletion, replacement, or concealment of an incomplete session.
            self.failed = True
            raise
