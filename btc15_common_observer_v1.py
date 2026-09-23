"""Append-only cross-lane evidence. Read-only HTTP; no upstream BRTI polling.

One independently compressed JSON record per gzip member keeps storage bounded
and each completed append recoverable. Recording a signal never executes it.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import requests

URLS = {
    'main': 'https://btc-15min-bot-production.up.railway.app/dashboard_state.json',
    'owner': 'https://brti-shared-feed-v1-production.up.railway.app/state',
    'v81': 'https://v81-live-diagnostics-production.up.railway.app/state',
    'serial': 'https://scalp-move-shadow-v1-production.up.railway.app/state',
}
MAX_RESPONSE_BYTES = 250_000
MAX_EXPORT_BYTES = 4_000_000
APPEND_LOCK = threading.Lock()


def utc_now(): return datetime.now(timezone.utc).isoformat()


def read_source(item):
    name,url=item
    record=dict(service=name,request_started_utc=utc_now())
    try:
        with requests.get(url,timeout=(1,2),stream=True,headers={'Cache-Control':'no-cache'}) as response:
            response.raise_for_status()
            chunks=[];size=0
            for chunk in response.iter_content(65536):
                size+=len(chunk)
                if size>MAX_RESPONSE_BYTES:raise ValueError('response too large')
                chunks.append(chunk)
            record.update(response_received_utc=utc_now(),http_status=response.status_code,
                          state=json.loads(b''.join(chunks)))
    except Exception as exc:
        record.update(response_received_utc=utc_now(),error_type=type(exc).__name__)
    return record


def append_record(path, record):
    raw=json.dumps(record,separators=(',',':'),allow_nan=False).encode()+b'\n'
    member=gzip.compress(raw,compresslevel=3,mtime=0)
    with APPEND_LOCK, Path(path).open('ab') as stream:
        stream.write(member);stream.flush();os.fsync(stream.fileno())
    return len(member)


def export_chunk(path, offset=0, limit=MAX_EXPORT_BYTES):
    """Fixed known file only; caller selects offset/size, never a filesystem path."""
    if type(offset) is not int or type(limit) is not int or offset<0 or not 1<=limit<=MAX_EXPORT_BYTES:
        raise ValueError('Invalid bounded export range')
    path=Path(path)
    if not path.exists():return dict(exists=False,offset=offset,total_bytes=0),b''
    with path.open('rb') as stream:
        size=os.fstat(stream.fileno()).st_size
        if offset>size:raise ValueError('Offset exceeds retained evidence')
        stream.seek(offset);raw=stream.read(min(limit,size-offset))
    return dict(exists=True,offset=offset,next_offset=offset+len(raw),total_bytes=size,
                sha256=hashlib.sha256(raw).hexdigest(),append_only=True,orders=False),raw


def observe_forever(path, run_id, stop=None):
    stop=stop or threading.Event()
    sequence=0
    with ThreadPoolExecutor(max_workers=len(URLS)) as pool:
        while not stop.is_set():
            began=time.monotonic();sequence+=1
            states=list(pool.map(read_source,URLS.items()))
            record=dict(schema_version=1,record_type='OBSERVATION',run_id=run_id,
                        recorded_utc=utc_now(),sequence_in_process=sequence,sources=states,
                        sampling_seconds=5,actual_browser_delivery_verified=False,
                        signal_only=True,orders=False)
            append_record(path,record)
            if sequence%12==1:
                print('COMMON OBSERVER | '+json.dumps(dict(run_id=run_id,sequence=sequence,
                    source_successes=sum('state' in x for x in states),sources=len(URLS),orders=False)),flush=True)
            stop.wait(max(.1,5-(time.monotonic()-began)))


def start(path, run_id):
    # A failed append must be visible and restart the evidence worker; the
    # detector/collector remains independent and never places an order.
    def supervise():
        while True:
            try:observe_forever(path,run_id)
            except Exception as exc:
                print('COMMON OBSERVER UNAVAILABLE | '+type(exc).__name__+' | NO ORDERS',flush=True)
                time.sleep(5)
    thread=threading.Thread(target=supervise,name='common-evidence-observer',daemon=True)
    thread.start();return thread
