"""Lossless storage for NEW informational evidence; existing files are untouched.

Each append is a complete gzip member followed by fsync. A process restart or
UTC day change starts another segment, so it never appends after a torn member.
The separate, explicitly authorized maintenance job can archive the legacy file.
This writer never prunes or migrates evidence.
"""
from datetime import datetime, timezone
import gzip
import os
from pathlib import Path
import threading
import time
import uuid


class CompressedJournal:
    def __init__(self, legacy_path, clock=time.time):
        self.directory = Path(str(legacy_path)+'.segments')
        self.clock = clock
        self.session = uuid.uuid4().hex
        self.path = None
        self.day = None
        self.lock = threading.Lock()
        self.failed = False
        self.raw_bytes = self.stored_bytes = self.records = 0

    def append(self, line):
        if not isinstance(line, bytes) or not line.endswith(b'\n'):
            raise ValueError('Complete journal line required')
        encoded = gzip.compress(line, compresslevel=6, mtime=0)
        with self.lock:
            if self.failed:
                raise OSError('Journal segment requires process restart')
            day = datetime.fromtimestamp(self.clock(), timezone.utc).strftime('%Y%m%d')
            self.directory.mkdir(parents=True, exist_ok=True)
            if self.day != day:
                self.day = day
                self.path = self.directory/(day+'-'+self.session+'-'+uuid.uuid4().hex[:8]+'.jsonl.gz')
            created = not self.path.exists()
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                remaining = memoryview(encoded)
                while remaining:
                    written = os.write(fd, remaining)
                    if not written: raise OSError('Journal short write')
                    remaining = remaining[written:]
                os.fsync(fd)
                if created:
                    directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
                    try: os.fsync(directory_fd)
                    finally: os.close(directory_fd)
            except BaseException:
                # Never put later valid evidence behind an incomplete member.
                self.failed = True
                raise
            finally:
                os.close(fd)
            self.records += 1
            self.raw_bytes += len(line)
            self.stored_bytes += len(encoded)
            if self.records == 1 or self.records % 1000 == 0:
                import json
                print('BTC15 INFORMATION STORAGE | '+json.dumps(dict(
                    path=str(self.path), records=self.records, raw_bytes=self.raw_bytes,
                    stored_bytes=self.stored_bytes, historical_files_untouched=True,
                    signal_only=True, orders=False), separators=(',', ':')), flush=True)


def information_lines(legacy_path):
    """Read the exact legacy journal and its new segments without a full-file copy.

    Corruption or an incomplete gzip member is an evidence error, never silently
    skipped or presented as complete coverage.
    """
    path = Path(legacy_path)
    # One volume / one writer: last-write times preserve process/day segment
    # order, whereas the random session suffix does not order same-day restarts.
    segments = sorted(Path(str(path)+'.segments').glob('*.jsonl.gz'),
                      key=lambda p: (p.stat().st_mtime_ns, p.name))
    if path.suffix == '.gz':
        stream = gzip.open(path, 'rb')
    else:
        try:
            stream = path.open('rb')
        except FileNotFoundError:
            archive = Path(str(path)+'.gz')
            try:
                stream = gzip.open(archive, 'rb')
            except FileNotFoundError:
                if not segments: raise FileNotFoundError(path) from None
                stream = None
    # Prefer the plain representation while both exist during verification.
    # Opening it directly also makes the atomic unlink/fallback transition safe.
    if stream is not None:
        with stream:
            yield from stream
    for segment in segments:
        with gzip.open(segment, 'rb') as stream:
            yield from stream
