"""Consumer-owned durable reader. No native imports, requests, source polls or ACK.

Input must be an independently provisioned read-only downstream CSV publication.
Input/storage/process isolation is a deployment precondition, not asserted by a
directory name or environment flag. Local execution is offline review only.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from btc15_directional_signal_authority_v1 import Authority, build_identity, pack, utc, unavailable
from btc15_directional_signal_publication_v1 import signal_view
from btc15_protected_publication_handoff_v1 import decode, strict_json
from btc15_qualified_forward_observer_v1 import FIELDS

MAX_RECORD_BYTES=1048576
csv.field_size_limit(MAX_RECORD_BYTES)


class Consumer:
    def __init__(self, input_path, ledger, checkpoint, *, epoch, build, clock=None):
        self.input=Path(input_path)
        self.ledger=Path(ledger)
        self.checkpoint=Path(checkpoint)
        if len({p.resolve() for p in (self.input,self.ledger,self.checkpoint)})!=3:
            raise ValueError('INPUT_AND_CONSUMER_STORAGE_MUST_DIFFER')
        self.authority=Authority(self.ledger,runtime_epoch=epoch,build=build)
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        # Cursor is consumer-owned. A lost cursor may replay; immutable authority
        # uniqueness/watermarks still prevent a duplicate BUY after restart.
        with sqlite3.connect(self.checkpoint) as db:
            db.execute('CREATE TABLE IF NOT EXISTS cursor(id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO cursor VALUES (1,?)',(pack(dict(offset=0,identity=None,raw=None,status='NO_INPUT')),))

    def _load(self):
        with sqlite3.connect(self.checkpoint) as db:
            return json.loads(db.execute('SELECT payload FROM cursor WHERE id=1').fetchone()[0])

    def _save(self,value):
        with sqlite3.connect(self.checkpoint) as db:
            db.execute('UPDATE cursor SET payload=? WHERE id=1',(pack(value),))

    def _unavailable(self,reason,cursor,*,offset=None):
        now=self.clock()
        result=self.authority.consume(None,{},now_utc=now,receipt_utc=now)
        cursor.update(status=reason,raw=None)
        if offset is not None:cursor['offset']=offset
        self._save(cursor)
        return dict(status='UNAVAILABLE',reason=reason,record_id=result['record_id'])

    def step(self):
        """At most one bounded existing downstream record; no upstream feedback."""
        cursor=self._load()
        try:
            # O_RDONLY. Never truncate, rewrite, filter or ACK the input journal.
            with self.input.open('rb') as stream:
                stat=os.fstat(stream.fileno());identity=[stat.st_dev,stat.st_ino]
                if cursor['identity'] is not None and cursor['identity']!=identity:
                    return self._unavailable('INPUT_IDENTITY_CHANGED',cursor)
                if stat.st_size<cursor['offset']:
                    return self._unavailable('INPUT_TRUNCATED',cursor)
                stream.seek(cursor['offset'])
                line=stream.readline(MAX_RECORD_BYTES+1)
                if not line:return dict(status='IDLE',offset=cursor['offset'])
                if len(line)>MAX_RECORD_BYTES:
                    return self._unavailable('OVERSIZE_RECORD_BLOCKED',cursor)
                if not line.endswith(b'\n'):
                    return self._unavailable('PARTIAL_RECORD_WAIT',cursor)
                end=stream.tell()
                cursor['identity']=identity
                cells=next(csv.reader(io.StringIO(line.decode('utf-8')),strict=True))
                if cursor['offset']==0:
                    if cells!=FIELDS:return self._unavailable('INVALID_CSV_HEADER',cursor)
                    cursor['offset']=end;self._save(cursor)
                    return dict(status='HEADER')
                if len(cells)!=len(FIELDS):
                    return self._unavailable('MALFORMED_CSV_RECORD',cursor,offset=end)
                outer=dict(zip(FIELDS,cells));record=strict_json(outer['payload'])
                if (not isinstance(record,dict) or any(outer[k]!=str(record.get(k,''))
                        for k in FIELDS[:-1])):
                    return self._unavailable('CSV_PAYLOAD_IDENTITY_CONFLICT',cursor,offset=end)
                if record.get('record_type')!='OBSERVATION':
                    return self._unavailable('PUBLISHED_SOURCE_UNAVAILABLE',cursor,offset=end)
                raw,body=decode(record)
                receipt=utc(record['observed_utc'])
                # Consumer clock is real current time, never the publication clock.
                result=self.authority.consume(raw,record,now_utc=self.clock(),receipt_utc=receipt)
                cursor.update(offset=end,raw=raw,status=result['status'],
                              publication_sha256=record['protected_publication_bytes']['sha256'])
                self._save(cursor) # after authority commit; crash replay is idempotent
                return result
        except (ValueError,UnicodeError,csv.Error,KeyError,TypeError) as exc:
            return self._unavailable(type(exc).__name__+':'+str(exc),cursor,
                                     offset=locals().get('end'))
        except OSError as exc:
            return self._unavailable('INPUT_UNAVAILABLE:'+type(exc).__name__,cursor)

    def view(self):
        try:
            cursor=self._load()
            if cursor['status'] not in ('AVAILABLE','PASS') or cursor['raw'] is None:
                return unavailable(cursor['status'])
            return signal_view(cursor['raw'],self.ledger,self.clock())
        except (OSError,sqlite3.Error,ValueError,KeyError):
            return unavailable('CONSUMER_STORAGE_UNAVAILABLE')


def server_for(consumer,host='127.0.0.1',port=0):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!='/directional_signal.json':
                self.send_error(404);return
            body=pack(consumer.view()).encode()
            self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    return ThreadingHTTPServer((host,port),Handler)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--ledger',type=Path,required=True)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8091)
    parser.add_argument('--offline-review',action='store_true',required=True)
    args=parser.parse_args()
    consumer=Consumer(args.input,args.ledger,args.checkpoint,epoch=str(uuid.uuid4()),
                      build=build_identity(Path(__file__).parent) | {
                          name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                          for name in ('btc15_isolated_lifecycle_consumer_v1.py','btc15_protected_publication_handoff_v1.py')})
    server=server_for(consumer,port=args.port)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    while True:
        try:consumer.step()
        except (OSError,sqlite3.Error):pass # lease expires; never signal upstream
        time.sleep(.1) # downstream file read only; never a market/source poll


if __name__=='__main__':main()
