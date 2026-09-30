"""Detached bounded original-packet spool; no producer ACK or strategy imports."""
import argparse
from collections import OrderedDict
import gzip
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import socket
import threading
import time
import uuid
from urllib.parse import urlparse,parse_qs

MAX_PACKET=196608
MAX_CHUNK=2*1024*1024
MAX_STREAMS=65536


class Accounting:
    """Complete, immutable paginated status snapshots; at most two retained."""
    def __init__(self,root):
        self.root=Path(root);self.lock=threading.Lock();self.snapshots=OrderedDict()

    def capture(self,heads):
        records={};populations=[];errors=[]
        for pattern,limit in [('population-*.json',8),('transport-*.json',MAX_STREAMS)]:
            for index,path in enumerate(self.root.glob(pattern)):
                if index>=limit:
                    errors.append('ACCOUNTING_FILE_LIMIT:'+pattern);break
                try:
                    value=json.loads(path.read_text())
                    if pattern.startswith('population'):populations.append(value)
                    else:
                        pid=value['producer_id']
                        if pid in records:errors.append('DUPLICATE_STATUS:'+pid)
                        records[pid]=dict(value,received_sequence=heads.get(pid,0))
                except Exception:errors.append('UNREADABLE_STATUS:'+path.name)
        missing=sorted(set(heads)-set(records))
        if missing:errors.append('RECEIVER_STREAM_WITHOUT_STATUS')
        if not populations:errors.append('POPULATION_STATUS_UNAVAILABLE')
        for p in populations:
            own=[v for v in records.values() if v['process_id']==p['process_id']]
            if len(own)!=p['created']:errors.append('POPULATION_REPORT_COUNT:'+str(p['process_id']))
            if p['created']!=p['active']+p['retired']:errors.append('POPULATION_COUNTER_IDENTITY')
            if p['fault'] or p['admission_rejected']:errors.append('POPULATION_FAULT:'+str(p['process_id']))
        known={p['process_id'] for p in populations}
        if any(v['process_id'] not in known for v in records.values()):errors.append('UNACCOUNTED_PROCESS')
        incomplete=[pid for pid,v in records.items() if v['finished'] and
                    (not v['complete'] or v['delivered']!=heads.get(pid,0))]
        if incomplete:errors.append('TERMINAL_STREAM_INCOMPLETE')
        values=[records[k] for k in sorted(records)]
        sid=uuid.uuid4().hex
        summary=dict(snapshot_id=sid,total=len(values),page_size=128,complete=not errors,
                     errors=errors,missing_streams=missing,incomplete_streams=incomplete,
                     receiver_streams=len(heads),populations=populations,
                     created=sum(p['created'] for p in populations),active=sum(p['active'] for p in populations),
                     retired=sum(p['retired'] for p in populations),
                     retired_flushed=sum(p['retired_flushed'] for p in populations),
                     retired_incomplete=sum(p['retired_incomplete'] for p in populations),
                     offered=sum(v['offered'] for v in values),delivered=sum(v['delivered'] for v in values),
                     dropped=sum(v['producer_dropped'] for v in values),retried=sum(v['retry_eagain'] for v in values),
                     pending=sum(v['pending_packets'] for v in values),
                     reporting_basis='ALL_CREATED_STREAMS; ACTIVE_COUNTERS_ARE_CONCURRENT_SNAPSHOTS')
        with self.lock:
            self.snapshots[sid]=values
            while len(self.snapshots)>2:self.snapshots.popitem(last=False)
        return summary

    def page(self,sid,offset,limit):
        if offset<0 or not 1<=limit<=128:raise ValueError('RANGE')
        with self.lock:
            values=self.snapshots[sid]
            if offset>len(values):raise ValueError('OFFSET')
            end=min(offset+limit,len(values))
            return dict(snapshot_id=sid,total=len(values),offset=offset,records=values[offset:end],
                        next_offset=end if end<len(values) else None)


def packet(raw,c):
    value=json.loads(raw);event=value['event'];ident=event['identity']
    canonical=json.dumps(event,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if not hmac.compare_digest(value['mac'],hmac.new(bytes.fromhex(c['key']),canonical,hashlib.sha256).hexdigest()):
        raise ValueError('AUTHENTICATION')
    if value['sha256']!=hashlib.sha256(canonical).hexdigest(): raise ValueError('HASH')
    if ident['run_id']!=c['run_id'] or ident['build_sha']!=c['build'] or ident['source_sha256'] not in c['source_hashes']:
        raise ValueError('BINDING')
    if event['orders'] is not False or event['signal_only'] is not True:raise ValueError('SAFETY')
    return event


def run(config_path):
    c=json.loads(Path(config_path).read_text());root=Path(c['directory']);path=root/'packets.jsonl.gz'
    stats=dict(status='STARTING',packets=0,received_valid=0,invalid=0,bytes=0,groups=0,producer_drop_observed=False,
               native_action_authority=False,source_clock_certified=False,orders=False,
               sequence_gaps=[],streams={})
    public={k:v for k,v in c.items() if k not in {'key'}}
    accounting=Accounting(root)
    def health():
        result=dict(stats);heads=dict(stats['streams'])
        result['transport_accounting']=accounting.capture(heads)
        result['streams_count']=len(heads)
        result['streams_paged']=len(heads)>256
        result['streams']=heads if len(heads)<=256 else {}
        return result
    slots=threading.BoundedSemaphore(2)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if not slots.acquire(False): self.send_error(429);return
            try:
                route=urlparse(self.path);headers={}
                if route.path=='/ground-zero/manifest':
                    data=json.dumps(dict(manifest=public,health=health())).encode()
                elif route.path=='/ground-zero/transports':
                    q=parse_qs(route.query)
                    data=json.dumps(accounting.page(q['snapshot'][0],int(q.get('offset',['0'])[0]),
                                                   int(q.get('limit',['128'])[0]))).encode()
                elif route.path=='/ground-zero/chunk':
                    q=parse_qs(route.query);offset=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',['1048576'])[0])
                    if offset<0 or not 1<=limit<=MAX_CHUNK:raise ValueError('RANGE')
                    with path.open('rb') as stream:
                        size=os.fstat(stream.fileno()).st_size
                        if offset>size:raise ValueError('OFFSET')
                        stream.seek(offset);data=stream.read(min(limit,size-offset))
                    headers={'X-Capture-Offset':str(offset),'X-Capture-Total':str(size),
                             'X-Capture-SHA256':hashlib.sha256(data).hexdigest()}
                else:self.send_error(404);return
                self.send_response(200);self.send_header('Content-Type','application/octet-stream' if headers else 'application/json')
                self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
                for k,v in headers.items():self.send_header(k,v)
                self.end_headers();self.wfile.write(data)
            except Exception:self.send_error(503)
            finally:slots.release()
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',c.get('port',8769)),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);sock.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4*1024*1024)
    sock.bind(c['socket']);sock.setblocking(False);os.chmod(c['socket'],0o600)
    stats['status']='RECORDING_OPERATIONAL_UNCERTIFIED'
    started=time.monotonic();last_sync=started
    with path.open('xb') as out:
        try:
            while time.monotonic()-started<c['max_seconds']:
                if not select.select([sock],[],[],.1)[0]:continue
                batch=[];size=0;until=time.monotonic()+.01
                while size<MAX_CHUNK and len(batch)<512 and time.monotonic()<until:
                    try:raw=sock.recv(MAX_PACKET+1)
                    except BlockingIOError:
                        # Fill one bounded batch instead of gzip+flush on nearly
                        # every packet, while the producer FIFO absorbs stalls.
                        remaining=until-time.monotonic()
                        if remaining>0:select.select([sock],[],[],remaining)
                        continue
                    try:
                        if len(raw)>MAX_PACKET:raise ValueError('OVERSIZE')
                        event=packet(raw,c)
                    except Exception:stats['invalid']+=1;continue
                    batch.append(raw+b'\n');size+=len(raw)+1;stats['received_valid']+=1
                    pid=event['identity']['producer_id'];seq=event['sequence']
                    if pid not in stats['streams'] and len(stats['streams'])>=MAX_STREAMS:
                        raise RuntimeError('STREAM_BOUND')
                    expected=stats['streams'].get(pid,0)+1
                    if seq!=expected:
                        stats['sequence_gaps'].append(dict(producer_id=pid,expected=expected,received=seq))
                        stats['sequence_gaps']=stats['sequence_gaps'][-128:]
                        stats['producer_drop_observed']=True
                    stats['streams'][pid]=seq
                    if event['prior_dropped']:stats['producer_drop_observed']=True
                if not batch:continue
                member=gzip.compress(b''.join(batch),compresslevel=1,mtime=0)
                if out.tell()+len(member)>c['quota_bytes']:
                    stats['status']='UNAVAILABLE_QUOTA';break
                out.write(member);out.flush();stats['bytes']=out.tell();stats['groups']+=1;stats['packets']+=len(batch)
                if time.monotonic()-last_sync>=1:
                    os.fsync(out.fileno());last_sync=time.monotonic()
            else:stats['status']='BOUNDED_CAPTURE_ENDED'
            out.flush();os.fsync(out.fileno())
        except Exception as exc:stats['status']='UNAVAILABLE_STORAGE_'+type(exc).__name__
    sock.close()
    (root/'final_health.json').write_text(json.dumps(health()))
    # Keep only the independent read endpoint available after the bounded run.
    while True:time.sleep(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);run(p.parse_args().config)
