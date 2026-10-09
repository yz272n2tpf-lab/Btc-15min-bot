"""Read-only predecessor checkpoint handoff for the existing production lanes.

Preserves immutable entries/terminal recommendations; copies no action lease.
The predecessor journals and compressed archives are never modified.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import zlib

PREDECESSORS = {
    'main': ('a73609f5-4d62-4f97-8513-17b0566d6811','6cc77cf1c0f8a30db52e3538614bc9c95662516c'),
    'v81': ('5171df0d-1134-4e1c-a338-f8a033b8a8f0','322ed2bdc5d0859a6f3f7824a9c3641f257d2a2e'),
}
# Retained aliases for existing offline callers.
PREDECESSOR, BUILD = PREDECESSORS['main']


def transfer(journal, path, now=None):
    from . import REVISION
    from .directional import Directional
    from .scalp import Scalp
    from .directional_authority import digest
    from .trade_clarity import remember
    if journal.get('state') is not None or journal.get('origin_transfer') is not None:return
    lane=journal.get('lane');deployment,build=PREDECESSORS[lane]
    now=time.time() if now is None else now
    prior=Path(path).parent.parent/deployment/(lane+'.sqlite3')
    if Path(path).resolve()==prior.resolve():return
    history=[];transitions=[];origins={}
    with sqlite3.connect(prior.resolve().as_uri()+'?mode=ro',uri=True) as db:
        meta=dict(db.execute('SELECT k,v FROM meta'))
        if any(meta.get(k)!=v for k,v in dict(product_revision=REVISION,
                deployment=deployment,build=build,lane=lane).items()):
            raise ValueError('PREDECESSOR_JOURNAL_IDENTITY')
        rows=db.execute('SELECT seq,sha256,body FROM events ORDER BY seq DESC LIMIT 2048').fetchall()
        for seq,sha,body in reversed(rows):
            raw=zlib.decompress(body)
            if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('PREDECESSOR_EVENT_INTEGRITY')
            r=json.loads(raw);o=r.get('origin');t=r.get('terminal')
            if o:origins[o['origin_id']]=o
            if t and t.get('origin'):origins[t['origin']['origin_id']]=t['origin']
            oid=r.get('origin_id') or (o or {}).get('origin_id') or (t or {}).get('origin_id')
            o=origins.get(oid)
            if o:history=remember(history,o,lane,r.get('guidance'),t)
            if r.get('event'):
                transitions.append(dict(seq=seq,at=r['published_ts'],event=r['event'],origin_id=oid,
                    side=(o or {}).get('side'),ask=(o or {}).get('original_ask'),
                    reason=(r.get('management') or t or {}).get('reason'),
                    evidence=(r.get('management') or t or {}).get('evidence')))
    saved=json.loads(meta.get('state','{}'));probe=Directional() if lane=='main' else Scalp();probe.restore(saved)
    if lane=='v81':
        # A quiet deployment may have no BUY in the bounded event window.
        # Preserve its durable display tail as well as more recent events.
        retained={r['origin_id']:r for r in probe.signal_history}
        for r in history:
            old=retained.get(r['origin_id'])
            if old and any(old[k]!=r[k] for k in ('contract','side','original_ask','signal_ts','target','open_ts','close_ts')):
                raise ValueError('PREDECESSOR_SIGNAL_HISTORY_CONFLICT')
            retained[r['origin_id']]=r
        history=sorted(retained.values(),key=lambda r:r['signal_ts'])[-8:]
    origin=probe.origin;active=bool(origin and (origin['official_open']<=now<origin['official_close'] if lane=='main' else origin['open_ts']<=now<origin['close_ts']))
    history=remember(history,origin,lane,terminal=probe.terminal)
    if not active:probe.restore({})
    probe.signal_history=history
    receipt=dict(predecessor_deployment=deployment,predecessor_build=build,lane=lane,
        original_checkpoint_digest=digest(saved),origin_id=origin['origin_id'] if active else None,
        imported_at=now,active_origin_imported=active,publication_imported=False,history_count=len(history))
    with journal.db:
        journal.db.execute('INSERT INTO meta VALUES (?,?)',('state',json.dumps(probe.checkpoint())))
        journal.db.execute('INSERT INTO meta VALUES (?,?)',('origin_transfer',json.dumps(receipt)))
    print('SIGNAL ORIGIN TRANSFER | '+json.dumps(receipt,sort_keys=True),flush=True)
    print('SIGNAL PREDECESSOR TRANSITIONS | '+json.dumps(dict(lane=lane,transitions=transitions[-16:]),sort_keys=True),flush=True)
