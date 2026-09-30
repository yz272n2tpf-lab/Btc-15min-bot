"""Detached bounded original-packet spool; no producer ACK or strategy imports."""
import argparse
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
from urllib.parse import urlparse,parse_qs

MAX_PACKET=196608
MAX_CHUNK=2*1024*1024


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
    slots=threading.BoundedSemaphore(2)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if not slots.acquire(False): self.send_error(429);return
            try:
                route=urlparse(self.path);headers={}
                if route.path=='/ground-zero/manifest':
                    data=json.dumps(dict(manifest=public,health=dict(stats))).encode()
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
                    except BlockingIOError:break
                    try:
                        if len(raw)>MAX_PACKET:raise ValueError('OVERSIZE')
                        event=packet(raw,c)
                    except Exception:stats['invalid']+=1;continue
                    batch.append(raw+b'\n');size+=len(raw)+1;stats['received_valid']+=1
                    pid=event['identity']['producer_id'];seq=event['sequence']
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
    (root/'final_health.json').write_text(json.dumps(stats))
    # Keep only the independent read endpoint available after the bounded run.
    while True:time.sleep(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);run(p.parse_args().config)
