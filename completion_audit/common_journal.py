"""Read immutable common-observer evidence without silently dropping damage.

Each gzip member must contain one JSON object. Recovery is an analysis operation:
the original bytes are never rewritten. All skipped ranges are reported.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zlib

MAGIC = b'\x1f\x8b\x08'
MAX_RECORD_BYTES = 1_000_000
MAX_MEMBER_BYTES = 2_000_000


def strict_json(raw):
    def reject(value):
        raise ValueError('Non-finite JSON: ' + value)
    value = json.loads(raw, parse_constant=reject)
    if not isinstance(value, dict):
        raise ValueError('Expected one record object')
    return value


def next_header(stream, start):
    stream.seek(start)
    carry = b''
    base = start
    while True:
        chunk = stream.read(65536)
        if not chunk:
            return None
        data = carry + chunk
        at = data.find(MAGIC)
        if at >= 0:
            return base - len(carry) + at
        base += len(chunk)
        carry = data[-2:]


def read_member(stream, offset):
    stream.seek(offset)
    decoder = zlib.decompressobj(31)
    raw = bytearray()
    consumed = 0
    while not decoder.eof:
        chunk = stream.read(65536)
        if not chunk:
            raise EOFError('Incomplete gzip member')
        raw.extend(decoder.decompress(chunk, MAX_RECORD_BYTES + 1 - len(raw)))
        consumed += len(chunk) - len(decoder.unused_data)
        if len(raw) > MAX_RECORD_BYTES or consumed > MAX_MEMBER_BYTES:
            raise ValueError('Evidence member exceeds bounded schema size')
    return offset + consumed, strict_json(bytes(raw))


def scan(path, damage):
    """Yield CRC-verified members; caller MUST retain the damage report."""
    size = Path(path).stat().st_size
    position = 0
    skipped = None
    reasons = set()
    with Path(path).open('rb') as stream:
        while position < size:
            try:
                end, record = read_member(stream, position)
            except (EOFError, ValueError, zlib.error, UnicodeError) as exc:
                if skipped is None:
                    skipped = position
                reasons.add(type(exc).__name__)
                candidate = next_header(stream, position + 1)
                if candidate is None:
                    position = size
                    break
                position = candidate
                continue
            if skipped is not None:
                damage.append(dict(start=skipped, end=position, reasons=sorted(reasons),
                                   kind='damaged_range_recovered_after'))
                skipped = None
                reasons = set()
            yield dict(offset=position, next_offset=end, record=record)
            position = end
    if skipped is not None:
        damage.append(dict(start=skipped, end=size, reasons=sorted(reasons),
                           kind='incomplete_or_damaged_tail'))


def report(path):
    from collections import Counter
    damage = []
    types = Counter()
    first = last = None
    count = 0
    for member in scan(path, damage):
        row = member['record']
        count += 1
        types[row.get('record_type', 'UNKNOWN')] += 1
        when = row.get('recorded_utc')
        if when:
            first = min(first, when) if first else when
            last = max(last, when) if last else when
    with Path(path).open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(bytes=Path(path).stat().st_size, sha256=sha, records=count,
                types=dict(types), first_recorded_utc=first, last_recorded_utc=last,
                damage=damage, complete_bytes_verified=not damage,
                continuous_availability_proven=False, orders=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path')
    args = parser.parse_args()
    print(json.dumps(report(args.path), indent=2))
