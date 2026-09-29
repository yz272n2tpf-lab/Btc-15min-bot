"""Passive producer -> nonblocking datagram -> independent unified archive.

No GET, protected evaluation, ACK, retry, strategy mutation, order or native disk
write. Only new optional launchers invoke these hooks. Existing files are intact.
"""
from __future__ import annotations
import argparse
import ast
import base64
import binascii
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import socket
import sqlite3
import struct
import sys
import time
import uuid
import zlib

SCHEMA = 'BTC15_SPRINT_PASSIVE_EVENT_V1'
MAX_PACKET = 196_608
MAX_NODES = 4096
MAX_DEPTH = 12
MAX_TEXT = 140_000
MAX_MEMBER = 100_000  # Oversized member is a visible gap, never split/truncated.
NATIVE_FIELDS = ('now', 'now_ts', 'ticker', 'market', 'target', 'close_dt',
                 'seconds_left', 'snap', '_btc_spot_provenance', '_brti_contract',
                 '_brti_row', '_ec_row', '_ec_live', '_unified_rows',
                 '_true_scalp_pending', '_profit_shadow_pending')
GATE_FIELDS = ('tier1_ready', 'final_ready', 'scalp_ready',
               'direct_brti_authority_ready', 'direct_brti_agrees', 'required_gap',
               'pref_side', 'pref_fair', 'pref_edge', 'pref_ask', 'pref_bid',
               'minutes_left', 'abs_gap', 'ratio', 'brti_age', 'brti_gap', 'brti_side')


def pack(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def strict(raw):
    def pairs(values):
        out = {}
        for key, value in values:
            if key in out: raise ValueError('DUPLICATE_KEY')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE')))


def observed_copy(value):
    """Bound traversal before serialization; never call arbitrary repr/__str__.

    Unrepresentable/nonfinite scalar is explicitly unavailable. Whole object
    fails if size/depth budget is exceeded; no truncated evidence is qualified.
    """
    left = [MAX_NODES]
    text_left = [MAX_TEXT]
    def copy(x, depth=0):
        left[0] -= 1
        if left[0] < 0 or depth > MAX_DEPTH: raise ValueError('OBJECT_BUDGET')
        if x is None or type(x) is bool: return x
        if type(x) is int:
            if x.bit_length() > 128: raise ValueError('INTEGER_BUDGET')
            return x
        if type(x) is float:
            return x if math.isfinite(x) else {'status': 'UNAVAILABLE', 'reason': 'NONFINITE_SCALAR', 'value': None}
        if type(x) is str:
            text_left[0] -= len(x)
            if text_left[0] < 0: raise ValueError('TEXT_BUDGET')
            return x
        # Native datetime labels are observed labels, never new source witnesses.
        if type(x) is datetime or (sys.modules.get('pandas') is not None and type(x) is getattr(sys.modules['pandas'], 'Timestamp', None)):
            return {'representation': 'datetime.isoformat', 'observed_value': x.isoformat()}
        np=sys.modules.get('numpy')
        if np is not None and type(x) in (np.float64,np.float32,np.int64,np.int32,np.bool_):
            return copy(x.item(),depth+1)
        if type(x) is dict:
            if len(x) > MAX_NODES: raise ValueError('OBJECT_BUDGET')
            out = {}
            for k, v in x.items():
                if type(k) is not str: raise ValueError('KEY_TYPE')
                text_left[0] -= len(k)
                if text_left[0] < 0: raise ValueError('TEXT_BUDGET')
                out[k] = copy(v, depth + 1)
            return out
        if type(x) in (tuple, list):
            if len(x) > MAX_NODES: raise ValueError('OBJECT_BUDGET')
            return [copy(v, depth + 1) for v in x]
        return {'status': 'UNAVAILABLE', 'reason': 'UNSUPPORTED_SCALAR_TYPE', 'value': None,
                'type': type(x).__name__}
    return copy(value)


@dataclass(frozen=True)
class Identity:
    producer_id: str
    build_sha: str
    source_sha256: str
    run_id: str
    clock_domain: str
    boot_id: str

    def validate(self):
        for k, v in asdict(self).items():
            if type(v) is not str or not 1 <= len(v) <= 160: raise ValueError('IDENTITY:'+k)
        if len(self.source_sha256) != 64: raise ValueError('SOURCE_HASH')


class Producer:
    """Single producing thread per instance. One nonblocking send, no retry.

    Queue storage is the kernel's bounded socket buffer. A separate process owns
    receiver/disk/clock admission. Slow/absent consumer can only lose evidence.
    The process scheduler can still delay this work: hosted timing gate required.
    """
    def __init__(self, address, identity, key, *, enabled=True, sock=None):
        identity.validate()
        if type(key) is not bytes or len(key) < 32: raise ValueError('KEY_REQUIRED')
        self.address, self.identity, self.key, self.enabled = str(address), identity, key, enabled
        self.sequence = self.dropped = self.offered = self.sent = 0
        self.last_error = None
        self.last_generation = None
        self.sock = sock
        if enabled and self.sock is None:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self.sock.setblocking(False)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, MAX_PACKET)

    def close(self):
        if self.sock is not None: self.sock.close()

    def offer(self, kind, body):
        if not self.enabled: return False
        self.sequence += 1
        self.offered += 1
        try:
            # A paired read bounds reading work locally; trust comes exclusively
            # from a separately qualified certificate. These are not source time.
            before = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
            wall = time.time_ns()
            after = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
            event = dict(schema=SCHEMA, identity=asdict(self.identity), sequence=self.sequence,
                         kind=kind, hook_read=dict(wall_ns=wall, before_boot_ns=before, after_boot_ns=after,
                         clock_qualified=False), prior_dropped=self.dropped,
                         signal_only=True, orders=False, body=observed_copy(body))
            raw = pack(event)
            envelope = pack(dict(event=event, sha256=digest(raw), mac=hmac.new(self.key, raw, hashlib.sha256).hexdigest()))
            if len(envelope) > MAX_PACKET: raise ValueError('DATAGRAM_BUDGET')
            if self.sock.sendto(envelope, socket.MSG_DONTWAIT, self.address) != len(envelope):
                raise OSError('SHORT_DATAGRAM')
            self.sent += 1
            self.last_error = None
            return True
        except Exception as exc:
            self.dropped += 1
            self.last_error = type(exc).__name__ + ':' + str(exc)[:120]
            return False

    def native(self, namespace, kind='NATIVE_CYCLE'):
        try:
            body = {k: namespace.get(k) for k in NATIVE_FIELDS}
            body['absence'] = [k for k in NATIVE_FIELDS if k not in namespace]
            body['witness_limits'] = {
                'native_consumption_completed_utc': None,
                'native_publication_completed_utc': None,
                'exchange_quote_source_witness': None,
                'actual_accepted_early_origin': None,
                'actual_v81_lifecycle': None,
                'native_cutoff_basis': 'EXISTING_now_ts_UNMODIFIED; hook_read_IS_NOT_CUTOFF',
                'shadow_objects_are_live_actions': False}
            return self.offer(kind, body)
        except Exception:
            return False

    def fair_input(self, local_values, global_values):
        try:
            return self.offer('NATIVE_FAIR_INPUT', dict(
                ticker=local_values.get('ticker'), target=local_values.get('target'),
                decision_cutoff=local_values.get('_cut'), btc_source=local_values.get('btc_source_utc'),
                btc_observed=local_values.get('btc_observed_utc'), btc_price=local_values.get('btc_spot'),
                features=local_values.get('_snap'), feature_order=global_values.get('_fair_features'),
                weights_sha256=global_values.get('_fair_model_weights_sha256'),
                artifact_sha256=global_values.get('_fair_model_artifact_sha256'),
                basis='EXISTING_record_model_input_RETURNED_BEFORE_INFERENCE'))
        except Exception:return False

    def protected(self, state, local_values):
        try:
            # Generation identity is producer-issued before the existing file
            # write; it is not an accepted strategy/research origin.
            state_hash = digest(pack(observed_copy(state)))
            gid = digest(pack([asdict(self.identity), self.sequence+1, state_hash]))
            okay = self.offer('PROTECTED_GENERATION', dict(
                state=state, gate_values={k: local_values.get(k) for k in GATE_FIELDS},
                generation_id=gid, state_sha256=state_hash,
                completed_delivery_utc=None, accepted_origin_id=None,
                basis='EXISTING_build_state_RETURN_NO_REEVALUATION'))
            self.last_generation = (state, state_hash, gid) if okay else None
            return okay
        except Exception:
            self.last_generation = None
            return False

    def published(self, state):
        # Called only AFTER the existing OUT.write_text returned successfully.
        try:
            h = digest(pack(observed_copy(state)))
            prior = self.last_generation
            linked = prior is not None and prior[0] is state and prior[1] == h
            return self.offer('PROTECTED_FILE_WRITE_COMPLETED', dict(
                state=state, browser_delivery_utc=None, state_sha256=h,
                generation_id=prior[2] if linked else None,
                linkage_status='OBSERVED_SAME_OBJECT_UNCHANGED' if linked else 'UNAVAILABLE_GENERATION_LINK',
                basis='EXISTING_LOCAL_FILE_WRITE_RETURNED_NOT_BROWSER_DELIVERY'))
        except Exception: return False

    def common_member(self, member, offset):
        try:
            if type(member) is not bytes or not 0 < len(member) <= MAX_MEMBER:
                raise ValueError('COMMON_MEMBER_BUDGET')
            return self.offer('COMMON_MEMBER', dict(member_base64=base64.b64encode(member).decode(),
                original_offset=offset, byte_count=len(member), sha256=digest(member),
                basis='EXISTING_APPEND_FSYNC_COMPLETED_MEMBER_UNCHANGED'))
        except Exception:
            # Count attempted oversized member as missing sequence.
            self.sequence += 1; self.offered += 1; self.dropped += 1
            self.last_error = 'COMMON_MEMBER_BUDGET'
            return False

    def lifecycle(self, result):
        # Only already emitted authority objects may be supplied, never a call
        # to authority.consume/evaluate. No inference of an origin from FINAL.
        return self.offer('LIFECYCLE_EMISSION', dict(emission=result,
            basis='ALREADY_EMITTED_OBJECT; upstream_ids_REQUIRED_FOR_LINKAGE'))


def instrument_native(source, expected_sha256, *, enabled=True):
    """Pinned additive hook after existing body + genuine WAIT/error paths."""
    if digest(source) != expected_sha256: raise ValueError('SOURCE_CHANGED')
    tree = ast.parse(source)
    if not enabled: return tree
    loops = [n for n in tree.body if isinstance(n, ast.While) and isinstance(n.test, ast.Name) and n.test.id == 'running']
    if len(loops) != 1: raise ValueError('NATIVE_LOOP_SEAM')
    blocks = [n for n in loops[0].body if isinstance(n, ast.Try)]
    if len(blocks) != 1: raise ValueError('NATIVE_TRY_SEAM')
    block = blocks[0]
    fair_functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_live_fair_shadow']
    if len(fair_functions)!=1:raise ValueError('NATIVE_FAIR_INPUT_SEAM')
    body=fair_functions[0].body
    calls=[i for i,n in enumerate(body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='record_model_input']
    if len(calls)!=1:raise ValueError('NATIVE_FAIR_RECORD_SEAM')
    body.insert(calls[0]+1,ast.parse('_sprint_producer.fair_input(locals(), globals())').body[0])
    class Waits(ast.NodeTransformer):
        def visit_Continue(self, node):
            return [ast.parse("_sprint_producer.native(globals(), 'NATIVE_WAIT')").body[0], node]
        def visit_FunctionDef(self, node): return node
        def visit_While(self, node): return node
        def visit_For(self, node): return node
    block.body = [new for old in block.body for new in
                  (lambda v: v if isinstance(v, list) else [v])(Waits().visit(old))]
    block.body.append(ast.parse('_sprint_producer.native(globals())').body[0])
    for handler in block.handlers:
        handler.body.insert(0, ast.parse("_sprint_producer.native(globals(), 'NATIVE_ERROR')").body[0])
    return ast.fix_missing_locations(tree)


def instrument_protected(source, expected_sha256, *, enabled=True):
    if digest(source) != expected_sha256: raise ValueError('SOURCE_CHANGED')
    tree = ast.parse(source)
    if not enabled: return tree
    builds = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_state']
    if len(builds) != 1: raise ValueError('PROTECTED_BUILD_SEAM')
    returns = [n for n in builds[0].body if isinstance(n, ast.Return)]
    if len(returns) != 1 or not isinstance(returns[0].value, ast.Name) or returns[0].value.id != 'state':
        raise ValueError('PROTECTED_RETURN_SEAM')
    index = builds[0].body.index(returns[0])
    builds[0].body.insert(index, ast.parse('_sprint_producer.protected(state, locals())').body[0])
    writes = 0
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main']:
        for i in reversed(range(len(fn.body))):
            n = fn.body[i]
            if (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and
                isinstance(n.value.func, ast.Attribute) and n.value.func.attr == 'write_text' and
                isinstance(n.value.func.value, ast.Name) and n.value.func.value.id == 'OUT'):
                fn.body.insert(i+1, ast.parse('_sprint_producer.published(state)').body[0]); writes += 1
    if writes != 1: raise ValueError('PROTECTED_WRITE_SEAM')
    return ast.fix_missing_locations(tree)


def instrument_common(source, expected_sha256, *, enabled=True):
    if digest(source) != expected_sha256: raise ValueError('SOURCE_CHANGED')
    tree = ast.parse(source)
    if not enabled: return tree
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'append_record']
    if len(funcs) != 1: raise ValueError('COMMON_APPEND_SEAM')
    blocks = [n for n in funcs[0].body if isinstance(n, ast.With)]
    if len(blocks) != 1: raise ValueError('COMMON_WRITE_SEAM')
    # Existing append lock already held. tell observes actual append descriptor
    # position after its original flush/fsync, not an invented offset counter.
    blocks[0].body.append(ast.parse('try:\n    _sprint_producer.common_member(member, stream.tell()-len(member))\nexcept Exception:\n    pass').body[0])
    return ast.fix_missing_locations(tree)


def instrument_lifecycle(source, expected_sha256, *, enabled=True):
    """Capture already committed authoritative result; never evaluate twice."""
    if digest(source) != expected_sha256: raise ValueError('SOURCE_CHANGED')
    tree=ast.parse(source)
    if not enabled:return tree
    classes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Authority']
    funcs=[n for c in classes for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='consume']
    if len(funcs)!=1:raise ValueError('LIFECYCLE_CONSUME_SEAM')
    inserted=0
    class Hook(ast.NodeTransformer):
        def visit_Return(self,node):
            nonlocal inserted
            if isinstance(node.value,ast.Name) and node.value.id=='result':
                inserted+=1
                return [ast.parse('_sprint_producer.lifecycle(result)').body[0],node]
            raise ValueError('UNEXPECTED_LIFECYCLE_RETURN')
    Hook().visit(funcs[0])
    if inserted!=1:raise ValueError('LIFECYCLE_COMMIT_RETURN_SEAM')
    return ast.fix_missing_locations(tree)


def detached_authority_class(source, expected_sha256, producer):
    """Explicit isolated-consumer composition; no production imports changed."""
    raw=Path(source).read_bytes()
    scope=dict(__name__='sprint_evidence.detached_authority',__file__=str(source),_sprint_producer=producer)
    exec(compile(instrument_lifecycle(raw,expected_sha256),str(source),'exec'),scope)
    return scope['Authority']


def add_event_store(path, *, quota_bytes=64*1024*1024):
    """Add producer tables to the SAME preinitialized unified archive."""
    path = Path(path)
    if not path.is_file() or path.is_symlink(): raise ValueError('EXISTING_UNIFIED_STORE_REQUIRED')
    with sqlite3.connect(path) as db:
        if not db.execute("SELECT name FROM sqlite_master WHERE name='members'").fetchone():
            raise ValueError('UNIFIED_MEMBERS_TABLE_REQUIRED')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS producer_events(producer TEXT,run TEXT,seq INTEGER,digest TEXT,raw BLOB,status TEXT,reason TEXT,
          PRIMARY KEY(producer,run,seq));
        CREATE TABLE IF NOT EXISTS producer_heads(producer TEXT,run TEXT,seq INTEGER,gapped INTEGER,PRIMARY KEY(producer,run));
        CREATE TRIGGER IF NOT EXISTS no_producer_update BEFORE UPDATE ON producer_events BEGIN SELECT RAISE(ABORT,'immutable');END;
        CREATE TRIGGER IF NOT EXISTS no_producer_delete BEFORE DELETE ON producer_events BEGIN SELECT RAISE(ABORT,'immutable');END;
        ''')
        db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('sprint_quota', json.dumps(quota_bytes)))


class Receiver:
    """Independent consumer. Its slow disk, faults, backlog never call producer."""
    def __init__(self, path, identities, keys, *, common_recorder=None):
        self.path = Path(path)
        self.identities = {(i.producer_id, i.run_id): asdict(i) for i in identities}
        self.keys = keys
        self.common = common_recorder
        self.status = 'UNAVAILABLE_NO_INPUT'

    def _db(self):
        if self.path.is_symlink(): raise ValueError('STORE_SYMLINK')
        db = sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw', uri=True, timeout=0)
        db.execute('PRAGMA synchronous=FULL')
        return db

    def accept(self, packet):
        try:
            if type(packet) is not bytes or not 0 < len(packet) <= MAX_PACKET: raise ValueError('PACKET_SIZE')
            env = strict(packet)
            if set(env) != {'event','sha256','mac'}: raise ValueError('ENVELOPE_KEYS')
            if type(env) is not dict:raise ValueError('ENVELOPE_OBJECT')
            ev = env['event']
            if type(ev) is not dict:raise ValueError('EVENT_OBJECT')
            ident = ev['identity']
            if type(ident) is not dict:raise ValueError('IDENTITY_OBJECT')
            if type(ev.get('body')) is not dict:raise ValueError('BODY_OBJECT')
            key_id = (ident['producer_id'], ident['run_id'])
            if ident != self.identities.get(key_id): raise ValueError('UNREGISTERED_PRODUCER_BUILD_RUN')
            raw = pack(ev)
            if env['sha256'] != digest(raw) or not hmac.compare_digest(env['mac'], hmac.new(self.keys[key_id],raw,hashlib.sha256).hexdigest()):
                raise ValueError('PRODUCER_AUTHENTICATION')
            if ev['schema'] != SCHEMA or ev['signal_only'] is not True or ev['orders'] is not False: raise ValueError('NON_EVIDENCE')
            seq = ev['sequence']
            if type(seq) is not int or seq < 1 or type(ev['prior_dropped']) is not int or ev['prior_dropped'] < 0: raise ValueError('SEQUENCE')
            if ev['kind'] not in {'NATIVE_CYCLE','NATIVE_WAIT','NATIVE_ERROR','NATIVE_FAIR_INPUT','PROTECTED_GENERATION','PROTECTED_FILE_WRITE_COMPLETED','COMMON_MEMBER','LIFECYCLE_EMISSION'}:
                raise ValueError('PRODUCER_KIND')
            h = ev['hook_read']
            if type(h) is not dict:raise ValueError('HOOK_CLOCK_OBJECT')
            if any(type(h.get(k)) is not int for k in ('wall_ns','before_boot_ns','after_boot_ns')) or h['after_boot_ns'] < h['before_boot_ns'] or h['clock_qualified'] is not False:
                raise ValueError('HOOK_CLOCK_NOT_CERTIFICATE')
            with closing(self._db()) as db, db:
                db.execute('BEGIN IMMEDIATE')
                old = db.execute('SELECT digest FROM producer_events WHERE producer=? AND run=? AND seq=?',(*key_id,seq)).fetchone()
                if old:
                    if old[0] != env['sha256']: raise ValueError('REPLAY_CONFLICT')
                    db.commit()
                    if ev['kind'] == 'COMMON_MEMBER':
                        replay = self._common(ev)
                        if replay['status'] not in ('RECORDED_PARTIAL','DUPLICATE_RECORDED'):
                            self.status = 'UNAVAILABLE'; return replay
                    self.status = 'DUPLICATE_RECORDED'; return {'status': self.status}
                head = db.execute('SELECT seq,gapped FROM producer_heads WHERE producer=? AND run=?',key_id).fetchone()
                if head and seq <= head[0]: raise ValueError('REPLAY_OR_REORDER')
                gapped = bool(ev['prior_dropped'] or (head and head[1]) or seq != ((head[0]+1) if head else 1))
                status = 'RECORDED_UNAVAILABLE_GAP' if gapped else 'RECORDED_UNQUALIFIED_CLOCK'
                reason = 'SEQUENCE_GAP_OR_PRIOR_DROP' if gapped else 'CLOCK_ADMISSION_SEPARATE'
                quota = json.loads(db.execute("SELECT v FROM meta WHERE k='sprint_quota'").fetchone()[0])
                if self.path.stat().st_size + len(packet) + 16384 > quota: raise ValueError('STORE_QUOTA')
                db.execute('PRAGMA max_page_count='+str(quota//4096))
                db.execute('INSERT INTO producer_events VALUES (?,?,?,?,?,?,?)', (*key_id,seq,env['sha256'],packet,status,reason))
                db.execute('INSERT OR REPLACE INTO producer_heads VALUES (?,?,?,?)',(*key_id,seq,int(gapped)))
            # COMMON_MEMBER is also fed to unchanged Round-2 receiver. Failure is
            # not concealed; original packet remains for deterministic replay.
            if ev['kind'] == 'COMMON_MEMBER':
                result = self._common(ev)
                if result['status'] not in ('RECORDED_PARTIAL','DUPLICATE_RECORDED'):
                    self.status = 'UNAVAILABLE'; return dict(result, acquisition_status=status)
            self.status = status
            return dict(status=status, evidence_only=True, orders=False)
        except (ValueError, TypeError, KeyError, UnicodeError, OSError, sqlite3.Error, RecursionError, zlib.error, binascii.Error) as exc:
            self.status = 'UNAVAILABLE'
            return dict(status='UNAVAILABLE', reason=str(exc), evidence_only=True, orders=False)

    def _common(self, ev):
        if self.common is None: return dict(status='UNAVAILABLE',reason='COMMON_ARCHIVE_NOT_CONFIGURED')
        from btc15_external_evidence_admission_v1 import parsed_member, signature, SCHEMA as COMMON_SCHEMA
        b = ev['body']; data = base64.b64decode(b['member_base64'], validate=True)
        if b['sha256'] != digest(data) or b['byte_count'] != len(data) or type(b['original_offset']) is not int or b['original_offset'] < 0:
            raise ValueError('COMMON_MEMBER_INTEGRITY')
        r = parsed_member(data); policy = asdict(self.common.policy)
        m = {k:policy[k] for k in ('endpoint','service_id','run_id','observer_epoch','collector_commit','run_manifest_sha256','signer_id','stream_id')}
        m.update(fingerprints=dict(self.common.policy.fingerprints),schema=COMMON_SCHEMA,
            acquisition='DETACHED_IMMUTABLE_MEMBER', orders=False,v2_admitted=False,native_decision_id=None,
            offset=b['original_offset'],end_offset=b['original_offset']+len(data),sequence=r['sequence_in_process'],
            sha256=digest(data),byte_count=len(data))
        return self.common.accept(data,pack(dict(manifest=m,mac=signature(m,self.common.key))))


def serve(address, receiver, *, limit=None):
    """A separately launched process owns this socket. No native file polling."""
    address = Path(address)
    if address.exists(): raise ValueError('SOCKET_EXISTS_EXPLICIT_RECOVERY_REQUIRED')
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, MAX_PACKET*4)
    sock.bind(str(address)); os.chmod(address,0o600)
    count = 0
    try:
        while limit is None or count < limit:
            packet, _, flags, _ = sock.recvmsg(MAX_PACKET)
            result = dict(status='UNAVAILABLE',reason='TRUNCATED_DATAGRAM') if flags & socket.MSG_TRUNC else receiver.accept(packet)
            print(json.dumps(result,sort_keys=True),flush=True);count += 1
    finally:
        sock.close(); address.unlink(missing_ok=True)


def launch(source, kind, expected_sha256, producer):
    """Nonproduction opt-in launcher: no default runner or service is changed."""
    raw = Path(source).read_bytes()
    transforms = {'native':instrument_native,'protected':instrument_protected,'common':instrument_common}
    tree = transforms[kind](raw,expected_sha256,enabled=producer.enabled)
    scope = dict(__name__='__main__',__file__=str(source),_sprint_producer=producer)
    exec(compile(tree,str(source),'exec'),scope)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nonproduction',action='store_true',required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    run=sub.add_parser('producer')
    run.add_argument('--source',required=True)
    run.add_argument('--kind',choices=('native','protected','common'),required=True)
    run.add_argument('--identity-json',required=True)
    run.add_argument('--key-file',required=True)
    run.add_argument('--socket',required=True)
    rx=sub.add_parser('receiver')
    rx.add_argument('--registry-json',required=True)
    rx.add_argument('--archive',required=True)
    rx.add_argument('--socket',required=True)
    rx.add_argument('--monitor-snapshot',help='Separate receiver-owned JSON view; monitors must never read the active SQLite archive')
    args=parser.parse_args()
    if args.command=='producer':
        ident=Identity(**strict(Path(args.identity_json).read_bytes()))
        producer=Producer(args.socket,ident,Path(args.key_file).read_bytes())
        try:launch(args.source,args.kind,ident.source_sha256,producer)
        finally:producer.close()
    else:
        registry=strict(Path(args.registry_json).read_bytes())
        ids=[Identity(**row['identity']) for row in registry['producers']]
        keys={(row['identity']['producer_id'],row['identity']['run_id']):Path(row['key_file']).read_bytes() for row in registry['producers']}
        common=None
        if 'common' in registry:
            from btc15_external_evidence_admission_v1 import Policy
            from round2_evidence.capture import DetachedRecorder
            cfg=registry['common'];values=cfg['policy']
            values['fingerprints']=tuple(tuple(x) for x in values['fingerprints'])
            if 'clock_domains' in values:values['clock_domains']=tuple(tuple(x) for x in values['clock_domains'])
            common=DetachedRecorder(args.archive,Policy(**values),acquisition_key=Path(cfg['acquisition_key_file']).read_bytes())
        add_event_store(args.archive,quota_bytes=registry['quota_bytes'])
        if args.monitor_snapshot:
            from .monitor_snapshot import SnapshotReceiver
            receiver=SnapshotReceiver(args.archive,ids,keys,common_recorder=common,snapshot_path=args.monitor_snapshot)
        else:
            receiver=Receiver(args.archive,ids,keys,common_recorder=common)
        serve(args.socket,receiver)


if __name__=='__main__':main()
