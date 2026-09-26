"""Bounded readonly export; retain immutable chunks and a verified local prefix."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import requests

BASE='https://scalp-finalprod-clean-v1-production.up.railway.app'


def fetch(offset, limit, run_id):
    response=requests.get(BASE+'/research/common-export',params=dict(offset=offset,limit=limit,run_id=run_id),timeout=40)
    response.raise_for_status()
    raw=response.content
    headers=response.headers
    if (int(headers['x-evidence-offset'])!=offset or
            int(headers['x-evidence-next-offset'])!=offset+len(raw) or
            hashlib.sha256(raw).hexdigest()!=headers['x-evidence-sha256']):
        raise ValueError('Evidence export range/hash mismatch')
    return raw,dict(headers)


def download(directory, run_id, max_chunks=4):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    journal=directory/'common_verified_prefix.gz'
    offset=journal.stat().st_size if journal.exists() else 0
    if offset:
        raw,_=fetch(0,min(offset,65536),run_id)
        with journal.open('rb') as stream:
            if raw!=stream.read(len(raw)):
                raise ValueError('Retained run prefix changed; do not merge identities')
    for _ in range(max_chunks):
        raw,headers=fetch(offset,4_000_000,run_id)
        if not raw:break
        end=offset+len(raw);sha=hashlib.sha256(raw).hexdigest()
        name=f'chunk_{offset:012d}_{end:012d}_{sha}.gzpart'
        chunk=directory/name
        if chunk.exists():
            if chunk.read_bytes()!=raw:raise ValueError('Immutable chunk changed')
        else:
            with chunk.open('xb') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            meta=dict(offset=offset,end=end,sha256=sha,retrieved_utc=datetime.now(timezone.utc).isoformat(),headers=headers)
            with (directory/(name+'.json')).open('x') as stream:json.dump(meta,stream,indent=2)
        # Cache is reconstructible from immutable chunks; originals are retained.
        with journal.open('ab') as stream:
            if stream.tell()!=offset:raise ValueError('Concurrent export writer')
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        offset=end
        if end>=int(headers['x-evidence-total-bytes']):break
    return dict(path=str(journal),run_id=run_id,verified_prefix_bytes=offset,orders=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path)
    parser.add_argument('--run-id', required=True)
    args=parser.parse_args();print(json.dumps(download(args.directory,args.run_id)))
