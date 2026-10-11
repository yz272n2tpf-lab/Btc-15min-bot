#!/usr/bin/env python3
"""BTC15 real snapshot handoff gate: read-only source, in-memory destination."""
import copy
import json
from pathlib import Path
import sqlite3
import sys

# When executed through `git show ... | python3`, stdin has no repository path.
# Explicitly add the Codespace checkout instead of relying on shell PYTHONPATH.
checkout = Path('/workspaces/Btc-15min-bot')
if not (checkout / 'btc15_v2_product').is_dir():
    raise SystemExit('BLOCKED: BTC15_CHECKOUT_NOT_FOUND')
sys.path.insert(0, str(checkout))

from btc15_v2_product.directional import Directional
from btc15_v2_product.early_origin_transfer import PREDECESSORS, transfer

def main():
    folders=sorted(Path('/workspaces').glob('btc15-phasea-20261010.*/receipt/main.consistent.sqlite3'))
    if not folders:
        raise SystemExit('BLOCKED: NO_EXISTING_SNAPSHOT; no downloads attempted')
    deployment,build=PREDECESSORS['main']
    results=[]
    for snapshot in folders:
        root=snapshot.parent.parent
        with sqlite3.connect(snapshot.resolve().as_uri()+'?mode=ro',uri=True) as db:
            db.execute('PRAGMA query_only=ON')
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            meta=dict(db.execute('SELECT k,v FROM meta'))
            assert meta['deployment']==deployment and meta['build']==build
            saved=json.loads(meta['state'])
            old=Directional();old.restore(copy.deepcopy(saved))
            count,last=db.execute('SELECT count(*),max(seq) FROM events').fetchone()
            assert count>0 and last==int(meta['sequence'])
        # Use a copy in a temporary filesystem, never the historical original.
        # A transfer reads the predecessor path and writes ONLY to :memory:.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            prior=Path(td)/deployment
            prior.mkdir()
            local=prior/'main.sqlite3'
            src=sqlite3.connect(snapshot.resolve().as_uri()+'?mode=ro',uri=True)
            dst=sqlite3.connect(local)
            try:
                src.backup(dst)
            finally:
                src.close();dst.close()
            class MemoryJournal:
                def __init__(self):
                    self.db=sqlite3.connect(':memory:')
                    self.db.execute('CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)')
                    self.db.execute('INSERT INTO meta VALUES (?,?)',('lane','main'))
                    self.db.commit()
                def get(self,key):
                    row=self.db.execute('SELECT v FROM meta WHERE k=?',(key,)).fetchone()
                    return json.loads(row[0]) if row and row[0].startswith(('{','[','"')) else row[0] if row else None
            journal=MemoryJournal()
            try:
                transfer(journal,Path(td)/'new-deployment'/'main.sqlite3',now=1791663252)
                after=Directional();after.restore(journal.get('state'))
                old_by={r['origin_id']:r for r in old.signal_history}
                new_by={r['origin_id']:r for r in after.signal_history}
                assert len(old_by)==len(old.signal_history),'DUPLICATE_PREDECESSOR_IDS'
                assert len(new_by)==len(after.signal_history),'DUPLICATE_IMPORTED_IDS'
                assert set(old_by)<=set(new_by),'HANDOFF_MISSING_HISTORY'
                keys=('contract','side','original_ask','signal_ts','open_ts','close_ts','target')
                for oid,oldrow in old_by.items():
                    newrow=new_by[oid]
                    assert all(newrow[k]==oldrow[k] for k in keys),'HANDOFF_HISTORY_IDENTITY:'+oid
                    assert newrow.get('terminal')==oldrow.get('terminal'),'HANDOFF_EXIT_HISTORY_CHANGED:'+oid
                receipt=journal.get('origin_transfer')
                assert receipt['predecessor_deployment']==deployment
                assert receipt['predecessor_build']==build
                results.append(dict(snapshot=str(snapshot),events=count,last_seq=last,
                                    saved_history=len(old_by),imported_history=len(new_by),
                                    historical_buy_exit_identities_preserved=True))
            finally:
                journal.db.close()
    print(json.dumps(dict(status='PASS',handoff_missing_history_resolved=True,
                          snapshots=results,source_modified=False,railway_modified=False),indent=2))
if __name__=='__main__':
    main()
