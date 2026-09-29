"""Exact decoded HTTP body in the EXISTING observer CSV append; not V2 evidence.

This module performs no I/O, threading, queue operations or lifecycle calls.
Its nonzero producer cost is measured and remains part of the isolation gate.
"""
import base64
import hashlib
import json

SCHEMA = 'BTC15_PROTECTED_HTTP_BYTES_V1'
MAX_BODY_BYTES = 131072


def envelope(body):
    if type(body) is not bytes or not 0 < len(body) <= MAX_BODY_BYTES:
        raise ValueError('PROTECTED_BODY_UNAVAILABLE_OR_OVERSIZE')
    return dict(schema=SCHEMA, encoding='base64', body=base64.b64encode(body).decode('ascii'),
                sha256=hashlib.sha256(body).hexdigest(), byte_count=len(body),
                basis='EXISTING_HTTP_RESPONSE_DECODED_BODY_BYTES', v2_admitted=False)


def _pairs(items):
    result={}
    for key,value in items:
        if key in result:
            raise ValueError('DUPLICATE_JSON_KEY')
        result[key]=value
    return result


def strict_json(raw):
    def reject(value):raise ValueError('NONFINITE_JSON:'+value)
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=reject)


def decode(record):
    packet=record.get('protected_publication_bytes')
    if not isinstance(packet,dict) or packet.get('schema')!=SCHEMA:
        raise ValueError('FULL_PROTECTED_PUBLICATION_UNAVAILABLE')
    if (packet.get('encoding')!='base64' or packet.get('v2_admitted') is not False
            or packet.get('basis')!='EXISTING_HTTP_RESPONSE_DECODED_BODY_BYTES'
            or type(packet.get('body')) is not str or len(packet['body'])>MAX_BODY_BYTES*2):
        raise ValueError('INVALID_HANDOFF')
    body=base64.b64decode(packet['body'],validate=True)
    if (not 0<len(body)<=MAX_BODY_BYTES or packet.get('byte_count')!=len(body)
            or packet.get('sha256')!=hashlib.sha256(body).hexdigest()):
        raise ValueError('HANDOFF_BYTES_CONFLICT')
    raw=strict_json(body.decode('utf-8'))
    if (not isinstance(raw,dict) or raw.get('contract')!=record.get('contract')
            or raw.get('source_timestamp_utc')!=record.get('source_timestamp_utc')):
        raise ValueError('HANDOFF_PUBLICATION_IDENTITY_CONFLICT')
    return raw,body
