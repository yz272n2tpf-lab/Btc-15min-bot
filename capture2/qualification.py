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
# Evidence-only capacity profile, qualified against the Oct 3 measured bursts.
LIMITS = {
    'main': ((100, 2250), (250, 4500), (1000, 7000), (5000, 15000), (10000, 22500)),
    'v81': ((100, 2250), (250, 4500), (1000, 7000), (5000, 15000), (10000, 22500)),
}
REASONS = frozenset(('RATE_ENVELOPE_EXCEEDED', 'SEQUENCE_GAP', 'CAPTURE_BUFFER_FULL',
                     'CENSUS_MISMATCH', 'INCOMPLETE_FLUSH', 'CAPTURE_FAILURE'))
MAX_RECORDS = 5_000_000
MAX_ARCHIVE = 3*1024*1024*1024
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
                limits_ms_packets=LIMITS.get(c.get('mode')), scoring_admissible=False)

def read_state(root, c):
    path = Path(root)/'qualification.json'
    if not path.exists():
        return pending(c)
    value = json.loads(path.read_bytes())
    state = value['state']
    mac = hmac.digest(bytes.fromhex(c['key']), canonical(state), 'sha256').hex()
    if not hmac.compare_digest(mac, value['mac']) or state['schema'] != SCHEMA or state['binding'] != binding(c):
        raise ValueError('QUALIFICATION_BINDING_OR_AUTHENTICATION')
    if state['limits_ms_packets'] != json.loads(json.dumps(LIMITS.get(c.get('mode')))):
        raise ValueError('QUALIFICATION_POLICY_CHANGED')
    return state

class Latch:
    def __init__(self, root, c):
        self.root, self.c = Path(root), c
        try:
            self.state = read_state(root, c)
        except Exception as exc:
            self.state = pending(c)
            self.fail('CAPTURE_FAILURE', detail='QUALIFICATION_CHECKPOINT:'+type(exc).__name__)
        if c.get('mode') not in LIMITS:
            self.fail('CAPTURE_FAILURE', detail='MODE_UNAVAILABLE')

    def save(self):
        state = self.state
        value = dict(state=state, mac=hmac.digest(bytes.fromhex(self.c['key']), canonical(state), 'sha256').hex())
        path = self.root/'qualification.json'
        temporary = self.root/'qualification.tmp'
        with temporary.open('wb') as out:
            out.write(canonical(value)); out.flush(); os.fsync(out.fileno())
        os.replace(temporary, path)
        fd = os.open(self.root, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)

    def fail(self, code, *, stream_id=None, source=None, boot_ns=None, wall_ns=None,
             measured=None, limit=None, window_ms=None, detail=None,
             timestamp_basis='UNAVAILABLE'):
        if code not in REASONS:
            raise ValueError('REASON_CODE')
        self.state['qualification_state'] = 'UNQUALIFIED'
        self.state['scoring_admissible'] = False
        # Immutable first causal witness for each reason; bounded to six records.
        if code not in self.state['reason_codes']:
            self.state['reason_codes'].append(code)
            self.state['reasons'].append(dict(code=code, stream_id=stream_id, source=source,
                boot_ns=boot_ns, wall_ns=wall_ns, timestamp_basis=timestamp_basis,
                measured=measured, limit=limit, window_ms=window_ms, detail=detail))
            self.save()

    def finish(self, archive):
        self.state.update(closed=True, archive=archive)
        if not self.state['reason_codes']:
            self.state['qualification_state'] = 'QUALIFIED'
            self.state['scoring_admissible'] = True
        self.save()
        return self.state

    def integrity(self, h, a, records):
        witness = dict(boot_ns=h.get('observed_boot_ns'), timestamp_basis='STATUS_OBSERVATION_NOT_EVENT_ORIGIN')
        if h.get('gap_count') or h.get('missing_packets'):
            gap = next(iter(h.get('sequence_gaps', [])), {})
            self.fail('SEQUENCE_GAP', stream_id=gap.get('producer_id'), measured=h.get('missing_packets'),
                      limit=0, detail=gap, **witness)
        ids = [r.get('producer_id') for r in records]
        if (a.get('created') != len(set(ids)) or a.get('total') != len(ids)
            or len(set(ids)) != len(ids) or a.get('created') != a.get('active', 0)+a.get('retired', 0)
            or set(ids) != set(h.get('streams', {})) or not a.get('complete')
            or a.get('errors') or a.get('missing_streams')):
            self.fail('CENSUS_MISMATCH', measured=dict(created=a.get('created'), unique=len(set(ids)),
                total=a.get('total')), detail=a.get('errors'), **witness)
        if (h.get('status') != 'BOUNDED_CAPTURE_ENDED' or h.get('invalid')
            or h.get('producer_drop_observed') or a.get('dropped')):
            self.fail('CAPTURE_FAILURE', detail=h.get('status'), measured=dict(invalid=h.get('invalid'),
                dropped=a.get('dropped')), limit=0, **witness)
        if (not h.get('final_fsync_completed') or h.get('uncommitted_valid') or a.get('pending')
            or a.get('active') or a.get('retired_incomplete') or a.get('retired_flushed') != a.get('created')):
            self.fail('INCOMPLETE_FLUSH', detail='TERMINAL_AGGREGATE', measured=a.get('pending'), limit=0, **witness)
        for r in records:
            pid = r['producer_id']
            reject = r.get('first_rejection') or {}
            if r.get('rejected_full'):
                self.fail('CAPTURE_BUFFER_FULL', stream_id=pid, boot_ns=reject.get('boot_ns'),
                    timestamp_basis='TRANSPORT_REJECTION', measured=r['rejected_full'], limit=0, detail=reject)
            if r.get('producer_dropped') or r.get('rejected') or r.get('last_transport_error'):
                self.fail('CAPTURE_FAILURE', stream_id=pid, detail=r.get('last_transport_error') or r.get('producer_last_error'), **witness)
            if (r.get('finished') is not True or r.get('flushed') is not True or r.get('complete') is not True
                or r.get('pending_packets') != 0 or r.get('pending_bytes') != 0
                or r.get('offered') != r.get('accepted') or r.get('accepted') != r.get('delivered')
                or r.get('delivered') != h.get('streams', {}).get(pid)):
                self.fail('INCOMPLETE_FLUSH', stream_id=pid, detail='TERMINAL_STREAM', **witness)

def qualify(root, c):
    """Evaluate the final immutable interval; no automatic promotion of prefixes."""
    from capture2.writer import Accounting, packet
    root = Path(root)
    latch = Latch(root, c)
    final = root/'final_health.json'
    if not final.exists():
        latch.save()
        return latch.state
    archive = None
    try:
        h = json.loads(final.read_bytes())
        accountant = Accounting(root)
        a = accountant.capture(h['streams'])
        records = []
        offset = 0
        while offset is not None:
            page = accountant.page(a['snapshot_id'], offset, 128)
            records.extend(page['records']); offset = page['next_offset']
            if len(records) > MAX_STREAMS: raise ValueError('CENSUS_BOUND')
        latch.integrity(h, a, records)
        path = root/'packets.jsonl.gz'
        size = path.stat().st_size
        if not 0 < size <= min(c.get('quota_bytes', MAX_ARCHIVE), MAX_ARCHIVE):
            raise ValueError('ARCHIVE_BOUND')
        # A private bounded snapshot prevents admission/qualification TOCTOU.
        with tempfile.TemporaryDirectory(prefix='btc15-qualification-') as scratch:
            snapshot = Path(scratch)/'archive.gz'
            digest = hashlib.sha256()
            with path.open('rb') as src, snapshot.open('wb') as out:
                for chunk in iter(lambda: src.read(1024*1024), b''):
                    if out.tell()+len(chunk) > size: raise ValueError('ARCHIVE_CHANGED')
                    digest.update(chunk); out.write(chunk)
            if snapshot.stat().st_size != size: raise ValueError('ARCHIVE_CHANGED')
            archive = dict(bytes=size, sha256=digest.hexdigest())
            old = latch.state.get('archive')
            if old and (old['bytes'] != size or old['sha256'] != archive['sha256']):
                latch.fail('CAPTURE_FAILURE', detail='SEALED_INTERVAL_CHANGED')
            # Disk-backed timestamp ordering handles interleaved producer streams.
            # This is post-capture bookkeeping, never receiver/writer hot-path work.
            with sqlite3.connect(str(Path(scratch)/'ordering.sqlite')) as db:
                db.executescript('PRAGMA cache_size=-2048; PRAGMA temp_store=FILE; PRAGMA max_page_count=131072;'
                                 'CREATE TABLE events(t INTEGER, wall INTEGER, pid INTEGER, seq INTEGER);')
                heads = {}; sources = {}; identities = []; batch = []; rows = 0; domain = None
                with gzip.open(snapshot, 'rb') as stream:
                    while True:
                        raw = stream.readline(196609)
                        if not raw: break
                        if len(raw) > 196608 or not raw.endswith(b'\n'): raise ValueError('RECORD_BOUND')
                        e = packet(raw, c); ident = e['identity']; pid = ident['producer_id']; seq = e['sequence']
                        if pid not in sources:
                            if len(sources) >= MAX_STREAMS: raise ValueError('STREAM_BOUND')
                            sources[pid] = len(identities); identities.append(ident)
                        elif identities[sources[pid]] != ident: raise ValueError('STREAM_IDENTITY_CHANGED')
                        expected = heads.get(pid, 0)+1
                        stamp = e['hook_read']; t = stamp['before_boot_ns']; wall = stamp['wall_ns']
                        if type(t) is not int or t < 0 or type(wall) is not int: raise ValueError('CAUSAL_TIME_UNAVAILABLE')
                        clock = (ident['clock_domain'], ident['boot_id'])
                        if domain is None: domain = clock
                        if clock != domain: raise ValueError('INCOMPARABLE_CAPTURE_TIME_DOMAINS')
                        if seq != expected:
                            latch.fail('SEQUENCE_GAP', stream_id=pid, source=ident['source_sha256'],
                                boot_ns=t, wall_ns=wall, measured=seq, limit=expected, timestamp_basis='PRODUCER_HOOK')
                        heads[pid] = seq
                        if e['prior_dropped']:
                            latch.fail('CAPTURE_FAILURE', stream_id=pid, source=ident['source_sha256'],
                                boot_ns=t, wall_ns=wall, measured=e['prior_dropped'], limit=0, timestamp_basis='PRODUCER_HOOK')
                        rows += 1
                        if rows > MAX_RECORDS: raise ValueError('RECORD_COUNT_BOUND')
                        batch.append((t, wall, sources[pid], seq))
                        if len(batch) == 1000:
                            db.executemany('INSERT INTO events VALUES (?,?,?,?)', batch); batch.clear()
                db.executemany('INSERT INTO events VALUES (?,?,?,?)', batch); db.commit()
                if not rows or rows != h['packets'] or rows != h['received_valid'] or rows != a['offered'] or heads != h['streams']:
                    latch.fail('CENSUS_MISMATCH', measured=rows, limit=h.get('packets'), detail='ARCHIVE_COUNTERS_AND_HEADS')
                windows = [(ms, limit, deque()) for ms, limit in LIMITS[c['mode']]]
                for t, wall, index, seq in db.execute('SELECT t,wall,pid,seq FROM events ORDER BY t,pid,seq'):
                    if 'RATE_ENVELOPE_EXCEEDED' in latch.state['reason_codes']: break
                    for ms, limit, queue in windows:
                        while queue and queue[0] <= t-ms*1000000: queue.popleft()
                        queue.append(t)
                        if len(queue) > limit:
                            ident = identities[index]
                            latch.fail('RATE_ENVELOPE_EXCEEDED', stream_id=ident['producer_id'],
                                source=ident['source_sha256'], boot_ns=t, wall_ns=wall, window_ms=ms,
                                measured=len(queue), limit=limit, detail=dict(sequence=seq, scope='ALL_STREAMS_THIS_SIDE'),
                                timestamp_basis='PRODUCER_HOOK')
                            break
                archive['records'] = rows
        if size != h['bytes'] or path.stat().st_size != size:
            latch.fail('CAPTURE_FAILURE', detail='ARCHIVE_SIZE_BINDING')
    except Exception as exc:
        latch.fail('CAPTURE_FAILURE', detail=type(exc).__name__+':'+str(exc)[:160])
    return latch.finish(archive)

def admitted_events(root, c, ladder):
    """Sole qualified prospective capture admission for EARLY, FINAL and SCALP.

Transport-complete alone is never admissible. Diagnostic readers remain separate.
This integrity gate does not waive ladder-specific source/clock/closeout checks.
"""
    from capture2.writer import packet
    if ladder not in ('EARLY', 'FINAL', 'SCALP'): raise ValueError('LADDER')
    state = read_state(root, c)
    if (state['qualification_state'] != 'QUALIFIED' or not state['closed']
        or not state['scoring_admissible'] or state['reason_codes'] or not state['archive']):
        raise ValueError('EVIDENCE_NOT_QUALIFIED:'+state['qualification_state'])
    expected = state['archive']; digest = hashlib.sha256(); size = 0
    with tempfile.TemporaryFile() as snapshot, (Path(root)/'packets.jsonl.gz').open('rb') as source:
        for chunk in iter(lambda: source.read(1024*1024), b''):
            size += len(chunk)
            if size > min(expected['bytes'], MAX_ARCHIVE): raise ValueError('QUALIFIED_ARCHIVE_CHANGED')
            digest.update(chunk); snapshot.write(chunk)
        if size != expected['bytes'] or digest.hexdigest() != expected['sha256']:
            raise ValueError('QUALIFIED_ARCHIVE_CHANGED')
        snapshot.seek(0)
        with gzip.GzipFile(fileobj=snapshot) as stream:
            for raw in stream:
                yield packet(raw, c)
