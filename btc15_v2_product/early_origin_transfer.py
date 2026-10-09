"""One-time MAIN checkpoint handoff from the verified production predecessor.

Copies no market publication and grants no freshness. The old journal is opened
read-only; its cohort and immutable historical rows remain untouched.
"""
import json
from pathlib import Path
import sqlite3
import time

PREDECESSOR = '2d1ca61c-51b5-415d-8cca-02ed86a7cb69'
BUILD = 'b8bd240b4e27a949e7db0388b8fc9bae24d83ef5'


def transfer(journal, path, now=None):
    from . import REVISION
    from .directional import Directional
    from .directional_authority import digest
    if journal.get('state') is not None or journal.get('origin_transfer') is not None:
        return
    now=time.time() if now is None else now
    prior=Path(path).parent.parent/PREDECESSOR/'main.sqlite3'
    if Path(path).resolve()==prior.resolve():
        return
    with sqlite3.connect(prior.resolve().as_uri()+'?mode=ro',uri=True) as db:
        meta=dict(db.execute('SELECT k,v FROM meta'))
    if any(meta.get(k)!=v for k,v in dict(product_revision=REVISION,
            deployment=PREDECESSOR,build=BUILD,lane='main').items()):
        raise ValueError('EARLY_PREDECESSOR_JOURNAL_IDENTITY')
    saved=json.loads(meta.get('state','{}'))
    probe=Directional();probe.restore(saved)
    origin=probe.origin
    active=bool(origin and origin['official_open']<=now<origin['official_close'])
    receipt=dict(predecessor_deployment=PREDECESSOR,predecessor_build=BUILD,
        original_checkpoint_digest=digest(saved),origin_id=origin['origin_id'] if active else None,
        imported_at=now,active_origin_imported=active,publication_imported=False)
    with journal.db:
        if active:
            # Restore marks the path incomplete across restart. Entry metadata,
            # protection latch and accepted source times remain genuine.
            journal.db.execute('INSERT INTO meta VALUES (?,?)',('state',json.dumps(probe.checkpoint())))
        journal.db.execute('INSERT INTO meta VALUES (?,?)',('origin_transfer',json.dumps(receipt)))
    print('EARLY ORIGIN TRANSFER | '+json.dumps(receipt,sort_keys=True),flush=True)
