"""Bounded read-only export of the existing causal feature journal. NO ORDERS.

Only the fixed journal and its closed schema can be served. No caller-selected
paths, model deserialization, outcomes, credentials, fitting or network polling.
"""
import hashlib
import json
import math
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from btc15_data_paths_v1 import _btc15_data_root
from btc15_decision_clock_v1 import utc

NAME = 'kalshi_fair_input_frames_v1.jsonl'
MAX_BYTES = 1024 * 1024
MAX_LINE = 32768
FEATURES = ['elapsed','remaining','current_side','dist_target','abs_dist_target','dist_target_pct',
            'move_from_start','move_from_start_pct','move1','move2','move3','move5',
            'support1','support2','support3','support5','range5','vol5','dist_per_min_remaining','dist_over_range5']
KEYS = {'schema','ticker','target','decision_utc','btc_source_utc','btc_observed_utc','btc_price',
        'features','feature_order','weights_sha256','artifact_sha256','signal_only','orders'}
ROUTES = {'/research/fair-input-manifest','/research/fair-input-export'}


def validate_record(raw):
    def unique_fields(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate field')
            result[key]=value
        return result
    row = json.loads(raw,object_pairs_hook=unique_fields)
    if (not isinstance(row,dict) or set(row) != KEYS or row['schema'] != 'BTC15_FAIR_INPUT_V1'
        or row['signal_only'] is not True or row['orders'] is not False
        or row['feature_order'] != FEATURES or set(row['features']) != set(FEATURES)
        or not re.fullmatch(r'KXBTC15M-[A-Z0-9-]+',row['ticker'])
        or any(not re.fullmatch(r'[0-9a-f]{64}',row[k]) for k in ('weights_sha256','artifact_sha256'))):
        raise ValueError('Unexpected feature schema')
    values=[row['target'],row['btc_price'],*row['features'].values()]
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in values):
        raise ValueError('Nonfinite feature')
    if not utc(row['btc_source_utc']) <= utc(row['btc_observed_utc']) <= utc(row['decision_utc']):
        raise ValueError('Noncausal clocks')
    return row


def response(request_path, root=None):
    parsed=urlsplit(request_path)
    if parsed.path not in ROUTES:return None
    root=Path(root) if root is not None else _btc15_data_root(legacy_cwd_fallback=True)
    path=root/NAME
    try:
        params=parse_qs(parsed.query,keep_blank_values=True,strict_parsing=True)
        allowed=set() if parsed.path.endswith('manifest') else {'offset','limit','identity'}
        if set(params)-allowed or any(len(v)!=1 for v in params.values()):raise ValueError('Invalid query')
        offset=int(params.get('offset',['0'])[0]);limit=int(params.get('limit',[str(MAX_BYTES)])[0])
        if offset < 0 or not 1 <= limit <= MAX_BYTES:raise ValueError('Range outside bounds')
        # O_NOFOLLOW prevents an accidental symlink from turning this route into
        # an arbitrary file export. The parent data root is runtime configuration.
        fd=os.open(path,os.O_RDONLY | getattr(os,'O_NOFOLLOW',0))
        with os.fdopen(fd,'rb') as f:
            stat=os.fstat(f.fileno());size=stat.st_size
            first=f.readline(MAX_LINE+1)
            if not first or not first.endswith(b'\n') or len(first)>MAX_LINE:
                raise ValueError('Journal first frame unavailable')
            validate_record(first)
            prefix=hashlib.sha256(first).hexdigest()
            identity=hashlib.sha256(f'{stat.st_dev}:{stat.st_ino}:{prefix}'.encode()).hexdigest()
            if parsed.path.endswith('manifest'):
                body=json.dumps(dict(schema='BTC15_FAIR_INPUT_EXPORT_V1',journal=NAME,identity=identity,
                    first_record_sha256=prefix,size_bytes=size,max_range_bytes=MAX_BYTES,
                    feature_order=FEATURES,serving_deployment=os.getenv('RAILWAY_DEPLOYMENT_ID'),
                    warning='Serving deployment does not relabel historical rows; segment by recorded decision times and release history',
                    signal_only=True,orders=False),separators=(',',':')).encode()
                return 200,'application/json',{},body
            if params.get('identity') != [identity]:raise LookupError('Journal identity changed or missing')
            if offset>size:raise ValueError('Offset beyond retained journal')
            if offset:
                f.seek(offset-1)
                if f.read(1)!=b'\n':raise ValueError('Offset must follow a complete frame')
            f.seek(offset);raw=f.read(min(limit,size-offset))
            # An append in progress never appears as a complete exported row.
            end=raw.rfind(b'\n')+1;body=raw[:end]
            if raw and not body:raise ValueError('Range has no complete frame; retry with maximum limit')
            count=0
            for line in body.splitlines(keepends=True):
                if len(line)>MAX_LINE:raise ValueError('Oversize feature frame')
                validate_record(line);count+=1
            headers={'X-BTC15-Identity':identity,'X-Range-SHA256':hashlib.sha256(body).hexdigest(),
                'X-Range-Offset':str(offset),'X-Range-Next-Offset':str(offset+len(body)),
                'X-Journal-Snapshot-Bytes':str(size),'X-Range-Records':str(count)}
            return 200,'application/x-ndjson',headers,body
    except FileNotFoundError:return 404,'application/json',{},b'{"error":"journal_unavailable"}'
    except LookupError:return 409,'application/json',{},b'{"error":"journal_identity_mismatch"}'
    except (ValueError,TypeError,KeyError,OverflowError,UnicodeError):
        return 400,'application/json',{},b'{"error":"invalid_range_or_feature_schema"}'
    except OSError:return 503,'application/json',{},b'{"error":"journal_read_unavailable"}'


def serve(handler):
    result=response(handler.path)
    if result is None:return False
    status,kind,headers,body=result
    handler.send_response(status)
    for key,value in {'Content-Type':kind,'Content-Length':str(len(body)),
                      'Cache-Control':'no-store, max-age=0','X-Content-Type-Options':'nosniff',**headers}.items():
        handler.send_header(key,value)
    handler.end_headers();handler.wfile.write(body)
    return True


def install_route(directory):
    """Patch only the extracted server hook; leave existing packaged payloads intact."""
    directory=Path(directory);server=directory/'BTC15_DASHBOARD_LIVE_SERVER_V1.py'
    text=server.read_text();marker='BTC15_FAIR_INPUT_EXPORT_ROUTE_V1'
    anchor='    def do_GET(self):\n'
    hook=anchor+f'        # {marker}\n        from btc15_fair_input_export_v1 import serve\n        if serve(self):\n            return\n'
    if marker not in text:
        if text.count(anchor)!=1:raise RuntimeError('Expected dashboard route anchor missing')
        server.write_text(text.replace(anchor,hook,1))
    source=Path(__file__).resolve().parent
    for name in ('btc15_fair_input_export_v1.py','btc15_decision_clock_v1.py','btc15_data_paths_v1.py'):
        (directory/name).write_bytes((source/name).read_bytes())
