"""Detached SQLite exports using existing backup method, local fixture only.

Real MAIN/Admin export remains blocked by absent remote filesystem action. No
raw-copy, WAL checkpoint, writer restart, scorer, or live export endpoint.
"""
from contextlib import closing
from pathlib import Path
import json,sqlite3,time
from .policy import local_root
from .evidence import file_sha
from candidates.early_recording_20261012.archive import canonical

def snapshot(source,destination,*,kind,identity):
    if identity.get('evidence_class')!='FIXTURE':raise ValueError('REMOTE_READ_ACCESS_NOT_AVAILABLE')
    source=local_root(source);destination=local_root(destination)
    if destination.exists() or destination.is_relative_to(source.parent):raise ValueError('NEW_OFF_SOURCE_DESTINATION')
    if kind=='MAIN':
        from ops.btc15_v2_scoring.bridge import snapshot as existing_snapshot
        return existing_snapshot(source,destination,'main',identity,evidence_class='FIXTURE')
    if kind!='ADMIN':raise ValueError('SNAPSHOT_KIND')
    # Same mode=ro + bounded SQLite backup method; Admin has its own schema.
    start=time.monotonic();destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb'):pass
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as db,closing(sqlite3.connect(destination)) as out:
        def progress(*_):
            if time.monotonic()-start>30:raise TimeoutError('SNAPSHOT_DEADLINE')
        db.backup(out,pages=128,progress=progress,sleep=.02)
    with closing(sqlite3.connect(destination.as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('ADMIN_INTEGRITY')
        fields=[r[1] for r in db.execute('PRAGMA table_info(evidence)')]
        if fields!=['seq','at','sha256','body']:raise ValueError('ADMIN_SCHEMA')
        lo,hi,n=db.execute('SELECT min(seq),max(seq),count(*) FROM evidence').fetchone()
        previous=None
        for seq,digest,body in db.execute('SELECT seq,sha256,body FROM evidence ORDER BY seq'):
            from candidates.early_recording_20261012.archive import sha
            if sha(body.encode())!=digest:raise ValueError('ADMIN_RECORD_HASH')
            if previous is not None and seq!=previous+1:raise ValueError('ADMIN_SEQUENCE')
            previous=seq
    receipt=dict(schema='BTC15_ADMIN_DETACHED_SNAPSHOT_V1',identity=identity,evidence_class='FIXTURE',
        method='sqlite3.Connection.backup',source_open_mode='ro',source=str(source),snapshot_sha256=file_sha(destination),
        minimum_sequence=lo,maximum_sequence=hi,event_count=n,fields=fields,integrity_check='ok')
    Path(str(destination)+'.receipt.json').write_bytes(canonical(receipt));return receipt
