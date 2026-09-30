"""Authenticated bounded batch transport; original canonical event archive retained.

Only capture workers call serialization/compression. The writer authenticates a
small stream/sequence header and compressed member, without decoding every event.
"""
import base64
from dataclasses import asdict
import gzip
import hashlib
import hmac
import json
import struct
import sys
import math
from datetime import datetime
from sprint_evidence.passive_capture import pack,digest,MAX_PACKET

MAX_FRAME=262144
MAX_BATCH=64
MAX_BATCH_RAW=196608
PREFIX=struct.Struct('!4sII32s')
MAGIC=b'GZB3'


def owned_size(value):
    """Conservative retained heap charge; shared immutable scalars counted again."""
    size=sys.getsizeof(value)
    if type(value) is dict:
        return size+sum(sys.getsizeof(k)+owned_size(v) for k,v in value.items())
    if type(value) in (tuple,list):return size+sum(owned_size(v) for v in value)
    return size


def freeze(value):
    """One bounded copy/heap-accounting traversal; no JSON/base64/hash work."""
    nodes=4096;text=140000
    def copy(x,depth=0):
        nonlocal nodes,text
        nodes-=1
        if nodes<0 or depth>12:raise ValueError('OBJECT_BUDGET')
        typ=type(x)
        if x is None or typ is bool:return x,sys.getsizeof(x)
        if typ is int:
            if x.bit_length()>128:raise ValueError('INTEGER_BUDGET')
            return x,sys.getsizeof(x)
        if typ is float:
            if math.isfinite(x):return x,sys.getsizeof(x)
            return copy(dict(status='UNAVAILABLE',reason='NONFINITE_SCALAR',value=None),depth+1)
        if typ is str:
            text-=len(x)
            if text<0:raise ValueError('TEXT_BUDGET')
            return x,sys.getsizeof(x)
        if typ is dict:
            if len(x)>4096:raise ValueError('OBJECT_BUDGET')
            out={};charge=0
            for k,v in x.items():
                if type(k) is not str:raise ValueError('KEY_TYPE')
                text-=len(k)
                if text<0:raise ValueError('TEXT_BUDGET')
                cv,size=copy(v,depth+1);out[k]=cv;charge+=sys.getsizeof(k)+size
            return out,sys.getsizeof(out)+charge
        if typ in (tuple,list):
            if len(x)>4096:raise ValueError('OBJECT_BUDGET')
            out=[];charge=0
            for v in x:
                cv,size=copy(v,depth+1);out.append(cv);charge+=size
            return out,sys.getsizeof(out)+charge
        pd=sys.modules.get('pandas');np=sys.modules.get('numpy')
        if typ is datetime or (pd is not None and typ is getattr(pd,'Timestamp',None)):
            return copy(dict(representation='datetime.isoformat',observed_value=x.isoformat()),depth+1)
        if np is not None and typ in (np.float64,np.float32,np.int64,np.int32,np.bool_):return copy(x.item(),depth+1)
        return copy(dict(status='UNAVAILABLE',reason='UNSUPPORTED_SCALAR_TYPE',value=None,type=typ.__name__),depth+1)
    return copy(value)


def prepare(event):
    event=dict(event,body=dict(event['body']))
    raw=event.pop('_capture_raw_quote',None)
    if raw is not None:
        emission=dict(event['body']['emission']);event['body']['emission']=emission
        data=raw.encode('utf-8') if type(raw) is str else raw
        if len(data)>96000:emission['status']='UNAVAILABLE_OVERSIZE'
        else:emission.update(raw_base64=base64.b64encode(data).decode('ascii'),raw_sha256=digest(data),raw_bytes=len(data))
    member=event.pop('_capture_common_member',None)
    if member is not None:
        event['body'].update(member_base64=base64.b64encode(member).decode(),sha256=digest(member))
    if event['kind'] in ('PROTECTED_GENERATION','PROTECTED_FILE_WRITE_COMPLETED'):
        body=event['body'];state=body['state'];state_hash=digest(pack(state));body['state_sha256']=state_hash
        origin=event.pop('_capture_origin_sequence',None)
        gid=digest(pack([event['identity'],origin,state_hash])) if origin is not None else None
        body['generation_id']=gid
        if event['kind']=='PROTECTED_GENERATION':
            body.update(eligible_opportunity_id=gid if (state.get('early') or {}).get('ready') is True else None,
                        opportunity_basis='ACTUAL_PROTECTED_ELIGIBILITY_OBSERVATION',
                        opportunity_generated_utc=state.get('generated_utc'),original_source_utc=state.get('source_timestamp_utc'),
                        upstream_final_origin_id=None,upstream_final_origin_status='NOT_EMITTED_BY_THIS_PRODUCER')
    return event


def envelope(event,key):
    raw=pack(prepare(event))
    # Same canonical envelope bytes as pack(dict(event=...,mac=...,sha256=...)),
    # without serializing the entire event a second time.
    result=b'{"event":'+raw+b',"mac":"'+hmac.digest(key,raw,'sha256').hex().encode()+b'","sha256":"'+digest(raw).encode()+b'"}'
    if len(result)>MAX_PACKET:raise ValueError('DATAGRAM_BUDGET')
    return result


def frame(rows,identity,key):
    header=pack(dict(identity=identity,sequences=[e['sequence'] for e,r in rows],
                     prior_dropped=max(e['prior_dropped'] for e,r in rows),
                     raw_bytes=sum(len(r)+1 for e,r in rows)))
    payload=gzip.compress(b''.join(r+b'\n' for e,r in rows),compresslevel=1,mtime=0)
    mac=hmac.digest(key,header+payload,'sha256')
    result=PREFIX.pack(MAGIC,len(header),len(payload),mac)+header+payload
    if len(result)>MAX_FRAME:raise ValueError('FRAME_BUDGET')
    return result


def unframe(raw,c):
    if not PREFIX.size<len(raw)<=MAX_FRAME:raise ValueError('FRAME_SIZE')
    magic,hs,ps,mac=PREFIX.unpack_from(raw)
    if magic!=MAGIC or not 1<=hs<=16384 or PREFIX.size+hs+ps!=len(raw):raise ValueError('FRAME_HEADER')
    header=raw[PREFIX.size:PREFIX.size+hs];payload=raw[PREFIX.size+hs:]
    if not hmac.compare_digest(mac,hmac.digest(bytes.fromhex(c['key']),header+payload,'sha256')):raise ValueError('FRAME_AUTH')
    h=json.loads(header);ident=h['identity'];seq=h['sequences']
    if ident['run_id']!=c['run_id'] or ident['build_sha']!=c['build'] or ident['source_sha256'] not in c['source_hashes']:raise ValueError('BINDING')
    if not isinstance(ident['producer_id'],str) or not 1<=len(ident['producer_id'])<=160:raise ValueError('PRODUCER_ID')
    if not 1<=len(seq)<=MAX_BATCH or any(type(n) is not int or n<=0 for n in seq):raise ValueError('SEQUENCES')
    if not 0<h['raw_bytes']<=MAX_BATCH_RAW or type(h['prior_dropped']) is not int or h['prior_dropped']<0:raise ValueError('COUNTERS')
    return h,payload
