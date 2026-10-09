"""Authorized one-time legacy information archive. No endpoint or trading code.

Bounded-memory dry compression precedes any archive write. A durable attempt
marker prevents automatic retries. Any failed gate preserves the original.
"""
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import stat
import time
from urllib.request import urlopen
import zlib

TARGET = Path('/data/btc15_information_frames_v1.jsonl')
EXPECTED_BYTES = 2636133318
RESERVE = 1024**3
HEADROOM = 64*1024**2
CHUNK = 1024**2


class Abort(RuntimeError):
    pass


def log(event, **fields):
    print('BTC15 ARCHIVE | '+json.dumps(dict(event=event, at=time.time(),
          signal_only=True, orders=False, **fields), separators=(',', ':')), flush=True)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def save_receipt(path, value):
    tmp = Path(str(path)+'.tmp')
    with tmp.open('w') as out:
        json.dump(value, out, sort_keys=True, indent=2)
        out.flush(); os.fsync(out.fileno())
    os.replace(tmp, path)
    sync_directory(path.parent)
    log(value['status'], receipt=value)


def identity(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def no_writers(source, processes=None):
    wanted = (source.st_dev, source.st_ino)
    for process in Path('/proc').iterdir() if processes is None else processes:
        if not process.name.isdecimal(): continue
        try:
            for fd in (process/'fd').iterdir():
                try:
                    opened = fd.stat()
                    if (opened.st_dev, opened.st_ino) != wanted: continue
                    info = (process/'fdinfo'/fd.name).read_text()
                    flags = next(int(s.split()[1], 8) for s in info.splitlines()
                                 if s.startswith('flags:'))
                    if flags & os.O_ACCMODE in (os.O_WRONLY, os.O_RDWR):
                        raise Abort('ORIGINAL_HAS_ACTIVE_WRITER:'+process.name)
                except (FileNotFoundError, ProcessLookupError): pass
        except (FileNotFoundError, ProcessLookupError): pass


def fingerprint(lines, limit=None):
    digest = hashlib.sha256(); size = records = 0
    for line in lines:
        digest.update(line); size += len(line); records += line.count(b'\n')
        if limit is not None and records >= limit: break
    return dict(bytes=size, records=records, sha256=digest.hexdigest())


def archive_once(path, expected_bytes, reserve, health, pause=.01):
    """Only called for TARGET in production; parameters permit focused fixtures."""
    path = Path(path)
    archive = Path(str(path)+'.gz')
    partial = Path(str(archive)+'.archive-20261009.partial')
    receipt_path = Path(str(path)+'.archive-20261009.receipt.json')
    attempt = Path(str(path)+'.archive-20261009.attempt')
    lock = Path(str(path)+'.archive-20261009.lock')
    with lock.open('a') as lock_stream:
        fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if attempt.exists():
            log('ALREADY_ATTEMPTED', receipt_path=str(receipt_path))
            return
        fd = os.open(attempt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, b'Authorized one-time legacy information archive 20261009\n')
            os.fsync(fd)
        finally: os.close(fd)
        sync_directory(path.parent)
        receipt = dict(schema='BTC15_LEGACY_ARCHIVE_20261009', status='STARTED',
                       source=str(path), archive=str(archive), reserve_bytes=reserve,
                       deployment=os.getenv('RAILWAY_DEPLOYMENT_ID'),
                       build=os.getenv('RAILWAY_GIT_COMMIT_SHA'))
        owned_partial = False
        try:
            if path.is_symlink() or archive.exists() or partial.exists():
                raise Abort('SOURCE_SYMLINK_OR_ARCHIVE_ALREADY_EXISTS')
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as source:
                original = os.fstat(source.fileno())
                if (not stat.S_ISREG(original.st_mode) or original.st_nlink != 1
                    or original.st_size != expected_bytes):
                    raise Abort('UNEXPECTED_ORIGINAL_FILE')
                def unchanged():
                    if (identity(os.fstat(source.fileno())) != identity(original)
                        or identity(path.stat()) != identity(original)):
                        raise Abort('ORIGINAL_CHANGED')
                health(); no_writers(original)
                time.sleep(5 if pause else 0)
                unchanged(); no_writers(original)
                receipt['source_identity'] = identity(original)
                receipt['original_allocated_bytes'] = original.st_blocks*512
                receipt['free_before_bytes'] = shutil.disk_usage(path.parent).free
                log('MEASURING_WITHOUT_ARCHIVE_WRITE', original_bytes=original.st_size,
                    free_bytes=receipt['free_before_bytes'], reserve_bytes=reserve)

                def compress(output=None, expected=None):
                    source.seek(0)
                    encoder = zlib.compressobj(6, zlib.DEFLATED, 31)
                    raw_hash = hashlib.sha256(); encoded_hash = hashlib.sha256()
                    raw_size = count = compressed_size = 0; last = b''
                    next_health = time.monotonic()
                    def emit(data):
                        nonlocal compressed_size
                        compressed_size += len(data); encoded_hash.update(data)
                        if output is not None:
                            if compressed_size > expected: raise Abort('SIZE_CHANGED')
                            remaining = expected-(compressed_size-len(data))
                            if shutil.disk_usage(path.parent).free < reserve+HEADROOM+remaining:
                                raise Abort('OPERATING_RESERVE_THREATENED')
                            output.write(data)
                    while True:
                        block = source.read(CHUNK)
                        if not block: break
                        raw_hash.update(block); raw_size += len(block)
                        count += block.count(b'\n'); last = block[-1:]
                        emit(encoder.compress(block))
                        if time.monotonic() >= next_health:
                            health(); unchanged(); no_writers(original)
                            next_health = time.monotonic()+5
                        if pause: time.sleep(pause)
                    emit(encoder.flush())
                    unchanged(); no_writers(original)
                    if last != b'\n': raise Abort('INCOMPLETE_ORIGINAL_JSONL')
                    return dict(bytes=raw_size, records=count, sha256=raw_hash.hexdigest(),
                                compressed_bytes=compressed_size,
                                compressed_sha256=encoded_hash.hexdigest())

                measured = compress()
                receipt.update(measured)
                available = shutil.disk_usage(path.parent).free
                receipt['free_after_measurement_bytes'] = available
                receipt['required_free_bytes'] = measured['compressed_bytes']+reserve+HEADROOM
                log('MEASURED', **measured, free_bytes=available,
                    required_free_bytes=receipt['required_free_bytes'])
                if available < receipt['required_free_bytes']:
                    raise Abort('INSUFFICIENT_SPACE_WITH_RESERVE')
                with partial.open('xb') as output:
                    owned_partial = True
                    os.chmod(partial, 0o600)
                    written = compress(output, measured['compressed_bytes'])
                    output.flush(); os.fsync(output.fileno())
                if written != measured or partial.stat().st_size != measured['compressed_bytes']:
                    raise Abort('COMPRESSION_PASSES_DIFFER')
                log('VERIFYING_FULL_DECOMPRESSION', **measured)
                source.seek(0)
                decoded_hash = hashlib.sha256(); count = size = 0
                with gzip.open(partial, 'rb') as decoded:
                    while True:
                        raw = source.read(CHUNK); restored = decoded.read(CHUNK)
                        if raw != restored: raise Abort('DECOMPRESSION_BYTES_DIFFER')
                        if not raw: break
                        decoded_hash.update(restored); size += len(restored)
                        count += restored.count(b'\n')
                        if pause: time.sleep(pause)
                expected = {k: measured[k] for k in ('bytes', 'records', 'sha256')}
                verified = dict(bytes=size, records=count, sha256=decoded_hash.hexdigest())
                if verified != expected: raise Abort('DECOMPRESSION_DIGEST_DIFFERS')
                unchanged(); no_writers(original); health()
                # link fails if another archive appeared; never overwrite evidence.
                os.link(partial, archive)
                partial.unlink(); owned_partial = False
                sync_directory(path.parent)
                archived_identity = identity(archive.stat())
                from btc15_information_journal_v1 import information_lines
                reader = fingerprint(information_lines(archive))
                if reader != expected: raise Abort('ARCHIVE_READER_DIFFERS')
                receipt.update(status='VERIFIED', decompression=verified, reader=reader,
                               archive_allocated_bytes=archive.stat().st_blocks*512)
                save_receipt(receipt_path, receipt)
                unchanged(); no_writers(original); health()
                no_writers(archive.stat())
                if identity(archive.stat()) != archived_identity:
                    raise Abort('VERIFIED_ARCHIVE_CHANGED')
                if shutil.disk_usage(path.parent).free < reserve:
                    raise Abort('RESERVE_LOST_BEFORE_REMOVAL')
                # Every byte is already verified in the durable archive and reader.
                path.unlink()
                sync_directory(path.parent)
            # Closing our original FD releases its blocks; verify the fallback used
            # by the existing historical reader, before it reaches new segments.
            fallback = fingerprint(information_lines(path), measured['records'])
            if fallback != expected: raise Abort('POST_ARCHIVE_READER_DIFFERS')
            health()
            receipt.update(status='COMPLETED', fallback_reader=fallback,
                           free_after_bytes=shutil.disk_usage(path.parent).free,
                           file_bytes_reclaimed=measured['bytes']-measured['compressed_bytes'],
                           allocated_bytes_reclaimed=receipt['original_allocated_bytes']-
                               receipt['archive_allocated_bytes'], completed_at=time.time())
            save_receipt(receipt_path, receipt)
            return receipt
        except BaseException as exc:
            if owned_partial:
                partial.unlink(); sync_directory(path.parent)
            receipt.update(status='ABORTED' if path.exists() else 'POST_ARCHIVE_CHECK_FAILED',
                           error=type(exc).__name__+':'+str(exc),
                           original_exists=path.exists(), archive_exists=archive.exists(),
                           free_after_bytes=shutil.disk_usage(path.parent).free)
            save_receipt(receipt_path, receipt)
            return receipt


def main():
    expected = dict(RAILWAY_PROJECT_ID='baea4e22-d004-4434-b2c5-81a7fbc05086',
                    RAILWAY_ENVIRONMENT_ID='61775c5d-c583-4dfc-af41-f25578856fd9',
                    RAILWAY_SERVICE_ID='ab28dca6-7bea-4956-bdb9-dbb7b4c74635',
                    RAILWAY_VOLUME_ID='6ced6b1a-3755-4518-a240-c895e936d443',
                    RAILWAY_VOLUME_MOUNT_PATH='/data', BTC15_ARCHIVE_LEGACY_ONCE='20261009',
                    BTC15_INFORMATION_COMPRESS_NEW='1')
    if any(os.getenv(k) != v for k, v in expected.items()) or not os.path.ismount('/data'):
        log('ABORTED_WRONG_SERVICE_OR_VOLUME'); return
    os.nice(19)
    resource.setrlimit(resource.RLIMIT_AS, (256*1024**2, 256*1024**2))
    def interrupted(*_): raise Abort('SERVICE_STOPPING')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    def health():
        for pid in os.environ['BTC15_ARCHIVE_OWNED_PIDS'].split(','):
            os.kill(int(pid), 0)
        with urlopen('http://127.0.0.1:'+os.getenv('PORT', '8080')+'/health', timeout=2) as r:
            if r.status != 200 or json.load(r).get('ok') is not True:
                raise Abort('MAIN_HEALTH_NOT_READY')
    for _ in range(60):
        try: health(); break
        except Exception: time.sleep(1)
    else:
        log('ABORTED_MAIN_NOT_READY'); return
    archive_once(TARGET, EXPECTED_BYTES, RESERVE, health)


if __name__ == '__main__': main()
