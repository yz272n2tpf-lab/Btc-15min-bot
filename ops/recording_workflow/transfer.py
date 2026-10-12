"""Private filesystem delivery adapter. Remote routes deliberately unavailable.

Immutable content-addressed objects, resumable partial bytes, hash verification
in independent reader processes. No sockets, credentials, public endpoints or
spool deletion. Existing retained evidence can never be a transfer destination.
"""
from pathlib import Path
import json,os
from .evidence import file_sha
from .policy import local_root
from candidates.early_recording_20261012.archive import canonical,sha
CHUNK=256*1024

def private_store(path):
    root=local_root(path)
    root.mkdir(parents=True,exist_ok=True)
    marker=root/'LOCAL_PRIVATE_REVIEW_STORE'
    if not marker.exists():
        if any(root.iterdir()):raise ValueError('NONEMPTY_DESTINATION_NOT_OWNED')
        marker.write_text('OFFLINE FIXTURE STORE; NOT PRODUCTION DELIVERY\n')
    return root

def transfer(source,store,*,expected_sha256,quota,interrupt_after=None):
    source=Path(source);store=private_store(store);size=source.stat().st_size
    if file_sha(source)!=expected_sha256:raise ValueError('SOURCE_HASH')
    obj=store/expected_sha256;part=store/(expected_sha256+'.part')
    if obj.exists():
        if obj.stat().st_size!=size or file_sha(obj)!=expected_sha256:raise ValueError('DESTINATION_CORRUPTION')
        return dict(sha256=expected_sha256,size=size,resumed=False,duplicate=True)
    offset=part.stat().st_size if part.exists() else 0
    if offset>size:raise ValueError('PARTIAL_OVERSIZE')
    used=sum(p.stat().st_size for p in store.iterdir() if p.is_file())
    if used+size-offset>quota:raise OSError('EXPORT_QUOTA')
    with source.open('rb') as src:
        if offset:
            with part.open('rb') as old:
                left=offset
                while left:
                    n=min(left,CHUNK)
                    if old.read(n)!=src.read(n):raise ValueError('PARTIAL_CORRUPTION')
                    left-=n
        with part.open('ab') as dst:
            transferred=0
            for b in iter(lambda:src.read(CHUNK),b''):
                dst.write(b);transferred+=len(b)
                dst.flush();os.fsync(dst.fileno())
                if interrupt_after is not None and transferred>=interrupt_after:raise InterruptedError('TEST_INTERRUPTED_TRANSFER')
    if part.stat().st_size!=size or file_sha(part)!=expected_sha256:raise ValueError('TRANSFER_HASH')
    # Single transfer worker per private store. Never overwrite existing object.
    os.link(part,obj);part.unlink()
    fd=os.open(store,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return dict(sha256=expected_sha256,size=size,resumed=bool(offset),duplicate=False)

def package(root,index,store,*,quota,identity,report):
    root=local_root(root);store=private_store(store);index=local_root(index)
    idx=json.loads((index/'index_manifest.json').read_bytes());entries=[]
    sources=[(root/e['path'],e['path'],'RAW_EVIDENCE') for e in idx['files']]
    sources += [(index/'index.sqlite3','index.sqlite3','INDEX'),(index/'index_manifest.json','index_manifest.json','INDEX'),
                (root/'identity.json','identity.json','RUN_IDENTITY'),(report,'quality.json','REPORT')]
    scope=root/'verification_scope.json'
    if scope.exists():
        if scope.stat().st_size>4*1024**2:raise ValueError('SCOPE_MANIFEST_BUDGET')
        value=json.loads(scope.read_bytes());sources.append((scope,'verification_scope.json','DECLARED_FIXTURE_SCOPE'))
        for entry in value.get('journals',[]):
            name=entry['path'];p=root/name
            if not name.startswith('detached/') or not p.resolve().is_relative_to(root) or p.is_symlink():raise ValueError('DETACHED_PACKAGE_PATH')
            if file_sha(p)!=entry['sha256']:raise ValueError('DETACHED_PACKAGE_HASH')
            sources.append((p,name,'DETACHED_FIXTURE_JOURNAL'))
    whole=Path(report).parent/'whole-run'
    for name in ('summary.json','partitions.jsonl','partition_results.jsonl','issues.jsonl','associations.jsonl'):
        p=whole/name
        if p.exists():sources.append((p,'verification/'+name,'WHOLE_RUN_VERIFICATION'))
    if len(sources)>8192 or sum(Path(p).stat().st_size for p,_,_ in sources)>quota:raise OSError('PACKAGE_AGGREGATE_BUDGET')
    if file_sha(index/'index.sqlite3')!=idx['index_sha256']:raise ValueError('PACKAGE_INDEX_HASH')
    for e in idx['files']:
        if file_sha(root/e['path'])!=e['sha256']:raise ValueError('PACKAGE_SEGMENT_HASH')
    for p,name,kind in sources:
        digest=file_sha(p);transfer(p,store,expected_sha256=digest,quota=quota)
        entries.append(dict(path=name,sha256=digest,size=Path(p).stat().st_size,kind=kind))
    manifest=dict(schema='BTC15_PRIVATE_EVIDENCE_PACKAGE_V1',entries=entries,identity=identity,
        fixture_only=True,remote_production_delivery=False,original_index_sha256=sha(canonical(idx)))
    raw=canonical(manifest)
    if len(raw)>4*1024**2:raise ValueError('PACKAGE_MANIFEST_BUDGET')
    digest=sha(raw);destination=store/(digest+'.manifest.json')
    if destination.exists() and destination.read_bytes()!=raw:raise ValueError('MANIFEST_COLLISION')
    if not destination.exists():
        if sum(p.stat().st_size for p in store.iterdir() if p.is_file())+len(raw)>quota:raise OSError('PACKAGE_MANIFEST_QUOTA')
        with destination.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return dict(manifest=str(destination),sha256=digest,files=len(entries),total_bytes=sum(e['size'] for e in entries))

def restore(manifest,destination,*,expected_sha256,max_bytes=2*1024**3):
    manifest=Path(manifest);store=manifest.parent
    if manifest.stat().st_size>64*1024**2:raise ValueError('MANIFEST_BUDGET')
    raw=manifest.read_bytes()
    if sha(raw)!=expected_sha256:raise ValueError('MANIFEST_HASH')
    value=json.loads(raw)
    if value.get('schema')!='BTC15_PRIVATE_EVIDENCE_PACKAGE_V1':raise ValueError('PACKAGE_SCHEMA')
    destination=local_root(destination)
    if destination.exists():raise ValueError('RESTORE_REQUIRES_NEW_DIRECTORY')
    names=set();total=0
    if len(value['entries'])>100000:raise ValueError('ENTRY_BUDGET')
    for e in value['entries']:
        digest=e['sha256']
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('OBJECT_NAME')
        name=e['path'];p=Path(name)
        if p.is_absolute() or '..' in p.parts or name in names:raise ValueError('UNSAFE_MEMBER')
        names.add(name);total+=e['size']
        if total>max_bytes:raise ValueError('RESTORE_BYTE_BUDGET')
        src=store/e['sha256']
        if not src.is_file() or src.is_symlink() or src.stat().st_size!=e['size'] or file_sha(src)!=e['sha256']:raise ValueError('OBJECT_HASH')
    destination.mkdir(parents=True)
    for e in value['entries']:
        p=destination/e['path'];p.parent.mkdir(parents=True,exist_ok=True)
        with (store/e['sha256']).open('rb') as src,p.open('xb') as dst:
            for b in iter(lambda:src.read(CHUNK),b''):dst.write(b)
        if file_sha(p)!=e['sha256']:raise ValueError('RESTORED_HASH')
    return dict(verified_files=len(names),bytes=total,manifest_sha256=expected_sha256,fixture_only=value['fixture_only'])
