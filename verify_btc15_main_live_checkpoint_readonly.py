"""Read-only pre-cutover verification of the current MAIN predecessor SQLite journal.

Run in an authorized environment with the existing /data volume mounted.
Does not write to the database, checkpoint, WAL, or archive.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from btc15_v2_product import REVISION
from btc15_v2_product.early_origin_transfer import PREDECESSORS
from btc15_v2_product.directional import Directional

deployment,build=PREDECESSORS['main']
root=Path('/data/btc15_v2_product')/REVISION/deployment
path=root/'main.sqlite3'
if not path.is_file():
    raise SystemExit('BLOCKED: CURRENT_MAIN_JOURNAL_NOT_FOUND')
uri=path.resolve().as_uri()+'?mode=ro'
with sqlite3.connect(uri,uri=True) as db:
    db.execute('PRAGMA query_only=ON')
    integrity=db.execute('PRAGMA quick_check').fetchone()[0]
    if integrity!='ok':
        raise SystemExit('BLOCKED: SQLITE_QUICK_CHECK_FAILED')
    meta=dict(db.execute('SELECT k,v FROM meta'))
    expected=dict(product_revision=REVISION,deployment=deployment,build=build,lane='main')
    for key,value in expected.items():
        if meta.get(key)!=value:
            raise SystemExit('BLOCKED: PREDECESSOR_IDENTITY_MISMATCH:'+key)
    checkpoint=json.loads(meta['state'])
    probe=Directional()
    probe.restore(checkpoint)
    count=db.execute('SELECT count(*) FROM events').fetchone()[0]
    last=db.execute('SELECT max(seq) FROM events').fetchone()[0]
    if not count:
        raise SystemExit('BLOCKED: EMPTY_PREDECESSOR_JOURNAL')
    print(json.dumps(dict(status='READ_ONLY_MAIN_CHECKPOINT_VERIFIED',
        predecessor_deployment=deployment,predecessor_build=build,
        events=count,last_seq=last,checkpoint_digest=hashlib.sha256(
            json.dumps(checkpoint,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        origin_id=(probe.origin or {}).get('origin_id'),
        terminal_origin_id=(probe.terminal or {}).get('origin_id'),
        history_count=len(probe.signal_history),
        database_quick_check=integrity,
        writes=False,orders=False),sort_keys=True))
