"""One bounded, read-only export from the EXISTING isolated research mount.

No subprocess, socket, SSH, producer access, evidence write or capture import.
The caller embeds the pinned allowlist in the exact reviewed start command.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import time

EXPECTED={
    'RAILWAY_PROJECT_ID':'87ad03d5-e1d6-47d6-b1ea-159cd7594686',
    'RAILWAY_ENVIRONMENT_ID':'12d241b7-23b4-4421-aafd-142e943555ee',
    'RAILWAY_SERVICE_ID':'1fff593b-8b09-4cc4-8c51-f9603082657f',
    'RAILWAY_VOLUME_ID':'2dba2ef6-b84d-4abf-9d04-58a1e77082c5',
    'RAILWAY_VOLUME_MOUNT_PATH':'/research-evidence',
    'RAILWAY_GIT_COMMIT_SHA':'950e4b5e401d501bb26b5a66473e06500e8c08ac',
}
ROOT=Path('/research-evidence/DIAG_20261017_e2294683_f7c32d04-reader/raw')
CHUNK=3072

def read_verified(root,item):
    path=root/item['path']
    if path.is_absolute() and not path.is_relative_to(root):
        raise ValueError('OUTSIDE_EXPORT_ROOT')
    if '..' in Path(item['path']).parts or any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('EXPORT_SYMLINK_OR_PARENT')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME)
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size!=item['size']:
            raise ValueError('EXPORT_SIZE_OR_TYPE:'+item['path'])
        raw=stream.read(item['size']+1)
        after=os.fstat(stream.fileno())
    if len(raw)!=item['size'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:
        raise ValueError('EXPORT_HASH:'+item['path'])
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('EXPORT_SOURCE_CHANGED')
    return raw

def export(plan):
    signal.alarm(175)
    started=time.monotonic()
    if any(os.environ.get(k)!=v for k,v in EXPECTED.items()):
        raise ValueError('ISOLATED_RESEARCH_IDENTITY')
    if not Path('/research-evidence').is_mount() or Path('/research-evidence').is_symlink():
        raise ValueError('RESEARCH_MOUNT_REQUIRED')
    if len(plan)!=12 or sum(x['size'] for x in plan)>11*1024**2:
        raise ValueError('EXPORT_TOTAL_BOUND')
    if len({x['path'] for x in plan})!=12:
        raise ValueError('DUPLICATE_EXPORT_OBJECT')
    blobs=[]
    for item in plan:
        parts=Path(item['path']).parts
        if parts[0] not in ('main','v81','information') or not (
            len(parts)==2 and parts[1] in ('identity.json','terminal-status.json','seal.json') or
            len(parts)==3 and parts[1] in ('source.segments','information.segments') and parts[2].endswith('.jsonl.gz')):
            raise ValueError('EXPORT_ALLOWLIST')
        blobs.append(read_verified(ROOT,item))
    print('BTC15_RAW_EXPORT_BEGIN '+json.dumps(dict(objects=plan,bytes=sum(map(len,blobs)),
          identity=EXPECTED,deadline_seconds=180,production_access=False,capture=False,orders=False)),flush=True)
    index=0
    for item,raw in zip(plan,blobs):
        for offset in range(0,len(raw),CHUNK):
            data=raw[offset:offset+CHUNK]
            row=dict(index=index,path=item['path'],offset=offset,size=len(data),
                     sha256=hashlib.sha256(data).hexdigest(),data=base64.b64encode(data).decode())
            print('BTC15_RAW_EXPORT g%02d '%(index//200)+json.dumps(row,separators=(',',':')),flush=True)
            index+=1
            time.sleep(.015)  # bounded log transport; no producer timing involved
    print('BTC15_RAW_EXPORT_END '+json.dumps(dict(objects=len(plan),chunks=index,
          bytes=sum(map(len,blobs)),elapsed_seconds=time.monotonic()-started,source_writes=0)),flush=True)

