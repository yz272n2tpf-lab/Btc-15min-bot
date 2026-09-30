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
import subprocess
import sys
import time
import uuid
from urllib.parse import urlparse,parse_qs

from capture2.wire import unframe,MAX_FRAME

MAX_PACKET=196608
MAX_CHUNK=2*1024*1024
MAX_STREAMS=65536


class Accounting:
    """Complete, immutable paginated status snapshots; at most two retained."""
    def __init__(self,root):
        self.root=Path(root);self.lock=threading.Lock();self.snapshots=OrderedDict();self.retired_cache={}

    def capture(self,heads):
        records={};populations=[];errors=[]
        # Each atomic population file defines one complete census cut. Active
        # counters are embedded in that cut; retired reports are immutable and
        # published before their paths enter the census. Never mix a newer glob
        # of transport files with an older created/retired aggregate.
        for index,path in enumerate(self.root.glob('population-*.json')):
            if index>=8:errors.append('ACCOUNTING_PROCESS_LIMIT');break
            try:
                p=json.loads(path.read_text())
                if p.get('census_version')!=1:raise ValueError('CENSUS_VERSION')
                active=p.pop('active_records');retired=p.pop('retired_reports')
                populations.append(p)
                if len(active)!=p['active'] or len(retired)!=p['retired']:
                    errors.append('CENSUS_COUNTER_IDENTITY')
                values=list(active)
                for ref in retired:
                    name=ref['path']
                    if not name or Path(name).name!=name:raise ValueError('REPORT_PATH')
                    value=self.retired_cache.get(name)
                    if value is None:
                        value=json.loads((self.root/name).read_text())
                        if len(self.retired_cache)>=MAX_STREAMS:raise ValueError('CACHE_BOUND')
                        self.retired_cache[name]=value
                    if value['producer_id']!=ref['producer_id'] or not value['finished']:
                        raise ValueError('RETIRED_REPORT_IDENTITY')
                    values.append(value)
                if len(values)>MAX_STREAMS:raise ValueError('ACCOUNTING_STREAM_LIMIT')
                for value in values:
                    pid=value['producer_id']
                    if pid in records:errors.append('DUPLICATE_STATUS:'+pid)
                    records[pid]=dict(value,received_sequence=heads.get(pid,0))
            except Exception as exc:errors.append('CENSUS_UNAVAILABLE:'+path.name+':'+type(exc).__name__)
        missing=sorted(set(heads)-set(records))
        if missing:errors.append('RECEIVER_STREAM_AFTER_OR_MISSING_FROM_CENSUS')
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
        lossy=[pid for pid,v in records.items() if v['producer_dropped'] or v['rejected'] or v['last_transport_error']]
        if lossy:errors.append('STREAM_LOSS_OR_TRANSPORT_ERROR')
        values=[records[k] for k in sorted(records)]
        sid=uuid.uuid4().hex
        summary=dict(snapshot_id=sid,total=len(values),page_size=128,complete=not errors,
                     errors=errors,missing_streams=missing,incomplete_streams=incomplete,lossy_streams=lossy,
                     receiver_streams=len(heads),populations=populations,
                     created=sum(p['created'] for p in populations),active=sum(p['active'] for p in populations),
                     retired=sum(p['retired'] for p in populations),
                     retired_flushed=sum(p['retired_flushed'] for p in populations),
                     retired_incomplete=sum(p['retired_incomplete'] for p in populations),
                     offered=sum(v['offered'] for v in values),delivered=sum(v['delivered'] for v in values),
                     dropped=sum(v['producer_dropped'] for v in values),retried=sum(v['retry_eagain'] for v in values),
                     pending=sum(v['pending_packets'] for v in values),
                     reporting_basis='ATOMIC_PER_PROCESS_CENSUS; RECEIVER_AHEAD_OF_CENSUS_FAILS_CLOSED')
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


def read_server(config_path):
    c=json.loads(Path(config_path).read_text());root=Path(c['directory']);path=root/'packets.jsonl.gz'
    public={k:v for k,v in c.items() if k!='key'};accounting=Accounting(root)
    def health():
        # Separate process: full census/HTTP work cannot hold the writer GIL.
        result=json.loads((root/'writer_health.json').read_text());heads=result['streams']
        result['transport_accounting']=accounting.capture(heads)
        result['streams_count']=len(heads);result['streams_paged']=len(heads)>256
        result['streams']=heads if len(heads)<=256 else {}
        from capture2.qualification import read_state
        try:result['qualification']=read_state(root,c)
        except Exception as exc:
            result['qualification']=dict(qualification_state='UNQUALIFIED',scoring_admissible=False,
                reason_codes=['CAPTURE_FAILURE'],detail='QUALIFICATION_STATE_UNAVAILABLE:'+type(exc).__name__)
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
    server.serve_forever()


def run(config_path):
    c=json.loads(Path(config_path).read_text());root=Path(c['directory']);path=root/'packets.jsonl.gz'
    cpu_start=time.process_time_ns()
    stats=dict(status='STARTING',packets=0,received_valid=0,received_frames=0,invalid=0,bytes=0,groups=0,
        producer_drop_observed=False,native_action_authority=False,source_clock_certified=False,orders=False,
        sequence_gaps=[],gap_count=0,missing_packets=0,uncommitted_valid=0,streams={},
        auth_ns=0,persist_ns=0,sync_ns=0,status_ns=0,writer_service_ns=0,
        pending_batch_high_water_bytes=0,pending_batch_high_water_packets=0,
        batch_byte_limit=MAX_CHUNK,batch_record_limit=4096,datagram_byte_limit=MAX_FRAME,
        reader_process_isolated=True,per_packet_json_decode=False,per_packet_compression=False)
    def publish(final=False):
        before=time.monotonic_ns();stats['writer_cpu_ns']=time.process_time_ns()-cpu_start;stats['observed_boot_ns']=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        tmp=root/'writer_health.tmp';tmp.write_text(json.dumps(stats));os.replace(tmp,root/'writer_health.json')
        if final:(root/'final_health.json').write_text(json.dumps(stats))
        stats['status_ns']+=time.monotonic_ns()-before
    publish()
    reader=subprocess.Popen([sys.executable,'-B','-m','capture2.writer','--reader','--config',str(config_path)])
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);sock.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4*1024*1024)
    sock.bind(c['socket']);sock.setblocking(False);os.chmod(c['socket'],0o600)
    stats['status']='RECORDING_OPERATIONAL_UNCERTIFIED'
    started=time.monotonic();last_sync=last_report=started
    # Same five-second drain allowance; no larger producer FIFO or retry window.
    deadline=started+c['max_seconds']+5
    with path.open('xb') as out:
        try:
            while time.monotonic()<deadline:
                if (root/'drain.stop').exists():
                    # Qualification-only orderly stop. Producers must already be
                    # closed; never consulted by native strategy execution.
                    deadline=min(deadline,time.monotonic()+.2)
                if not select.select([sock],[],[],.05)[0]:
                    if time.monotonic()-last_report>=.25:publish();last_report=time.monotonic()
                    continue
                batch=[];size=count=0;until=min(deadline,time.monotonic()+.05)
                while size<MAX_CHUNK-MAX_FRAME and count<4096-64 and time.monotonic()<until:
                    try:raw=sock.recv(MAX_FRAME+1)
                    except BlockingIOError:
                        remaining=until-time.monotonic()
                        if remaining>0:select.select([sock],[],[],remaining)
                        continue
                    before=time.monotonic_ns()
                    try:meta,member=unframe(raw,c)
                    except Exception:stats['invalid']+=1;continue
                    finally:stats['auth_ns']+=time.monotonic_ns()-before
                    batch.append((meta,member));size+=len(member);count+=len(meta['sequences'])
                    stats['received_valid']+=len(meta['sequences']);stats['received_frames']+=1
                    stats['uncommitted_valid']+=len(meta['sequences'])
                if not batch:continue
                stats['pending_batch_high_water_bytes']=max(stats['pending_batch_high_water_bytes'],size)
                stats['pending_batch_high_water_packets']=max(stats['pending_batch_high_water_packets'],count)
                if out.tell()+size>c['quota_bytes']:stats['status']='UNAVAILABLE_QUOTA';break
                before=time.monotonic_ns();out.write(b''.join(member for meta,member in batch));out.flush()
                stats['persist_ns']+=time.monotonic_ns()-before
                stats['bytes']=out.tell();stats['groups']+=1;stats['packets']+=count
                for meta,member in batch:
                    pid=meta['identity']['producer_id']
                    if pid not in stats['streams'] and len(stats['streams'])>=MAX_STREAMS:raise RuntimeError('STREAM_BOUND')
                    for seq in meta['sequences']:
                        expected=stats['streams'].get(pid,0)+1
                        if seq!=expected:
                            stats['gap_count']+=1;stats['missing_packets']+=max(0,seq-expected)
                            stats['sequence_gaps'].append(dict(producer_id=pid,expected=expected,received=seq))
                            stats['sequence_gaps']=stats['sequence_gaps'][-128:];stats['producer_drop_observed']=True
                        stats['streams'][pid]=seq
                    if meta['prior_dropped']:stats['producer_drop_observed']=True
                stats['uncommitted_valid']-=count
                if time.monotonic()-last_sync>=1:
                    before=time.monotonic_ns();os.fsync(out.fileno());stats['sync_ns']+=time.monotonic_ns()-before;last_sync=time.monotonic()
                if time.monotonic()-last_report>=.25:publish();last_report=time.monotonic()
                stats['writer_service_ns']=stats['auth_ns']+stats['persist_ns']+stats['sync_ns']+stats['status_ns']
            else:stats['status']='BOUNDED_CAPTURE_ENDED'
            before=time.monotonic_ns();out.flush();os.fsync(out.fileno());stats['sync_ns']+=time.monotonic_ns()-before
        except Exception as exc:stats['status']='UNAVAILABLE_STORAGE_'+type(exc).__name__;stats['error']=str(exc)[:160]
    sock.close();stats['elapsed_seconds']=time.monotonic()-started
    stats['writer_service_ns']=stats['auth_ns']+stats['persist_ns']+stats['sync_ns']+stats['status_ns']
    stats['final_fsync_completed']=True if stats['status']=='BOUNDED_CAPTURE_ENDED' else False
    publish(final=True)
    # Closed-interval bookkeeping only, after transport and final persistence end.
    # Pending/missing/failed qualification is never admitted by scoring consumers.
    from capture2.qualification import qualify
    try:qualify(root,c)
    except Exception:pass  # Missing/invalid checkpoint remains non-admissible.
    # Bounded recorder is finished. Its independent reader remains available.
    reader.wait()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--reader',action='store_true');args=p.parse_args()
    (read_server if args.reader else run)(args.config)
