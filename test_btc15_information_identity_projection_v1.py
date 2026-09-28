#!/usr/bin/env python3
"""Adversarial tests for closed informational identity projection."""
import copy
import json
import unittest
from unittest.mock import mock_open, patch

FIELDS = ['schema','authority','status','reason','signal_only','orders','checked_ts','native_epoch','anchor_id','ticker']
with patch('pathlib.Path.read_text', return_value=json.dumps(FIELDS)):
    import btc15_information_proxy_v1 as proxy

def frame(now=1000.0):
    return dict(schema='BTC15_INFORMATION_V1',authority='INFORMATIONAL_READ_ONLY',status='AVAILABLE',
                reason=None,signal_only=True,orders=False,checked_ts=now,
                native_epoch='epoch-a',anchor_id='a'*64,ticker='KXBTC15M-TEST')

class IdentityProjectionTests(unittest.TestCase):
    def test_available_fresh_minimal_projection(self):
        out=proxy.identity_projection(frame(),1000.5)
        self.assertEqual(set(out),{'schema','ticker','native_epoch','anchor_id','observed_ts','signal_only','orders'})
        self.assertEqual(out['schema'],'BTC15_INFORMATION_IDENTITY_V1')
        self.assertTrue(out['signal_only']);self.assertFalse(out['orders'])
    def test_wait_fails_closed(self):
        x=frame();x['status']='WAIT'
        with self.assertRaises(ValueError):proxy.identity_projection(x,1000.1)
    def test_stale_lease_fails_closed(self):
        with self.assertRaises(ValueError):proxy.identity_projection(frame(),1001.000001)
    def test_future_clock_fails_closed(self):
        with self.assertRaises(ValueError):proxy.identity_projection(frame(),999.9)
    def test_missing_or_blank_identity_fails_closed(self):
        for key in ('native_epoch','anchor_id','ticker'):
            x=frame();x[key]=''
            with self.assertRaises(ValueError):proxy.identity_projection(x,1000.1)
    def test_wrong_authority_or_order_safety_fails_closed(self):
        for key,value in [('authority','AUTHORITATIVE_ACTION_STATE'),('signal_only',False),('orders',True)]:
            x=frame();x[key]=value
            with self.assertRaises(ValueError):proxy.identity_projection(x,1000.1)
    def test_unexpected_schema_field_fails_closed(self):
        x=frame();x['extra']='nope'
        with self.assertRaises(ValueError):proxy.identity_projection(x,1000.1)
    def test_identity_change_is_not_hidden(self):
        a=proxy.identity_projection(frame(),1000.1)
        x=frame();x['ticker']='KXBTC15M-NEXT';x['native_epoch']='epoch-b';x['anchor_id']='b'*64
        b=proxy.identity_projection(x,1000.1)
        self.assertNotEqual((a['ticker'],a['native_epoch'],a['anchor_id']),(b['ticker'],b['native_epoch'],b['anchor_id']))


class Headers:
    def __init__(self, nonce='a'*32): self.nonce=nonce
    def get(self,key,default=''): return self.nonce if key=='X-BTC15-Information-Nonce' else default

class Handler:
    def __init__(self,path,nonce='a'*32):
        self.path=path;self.headers=Headers(nonce);self.code=None;self.kind=None;self.body=None;self.response_headers={}
    def _send(self,code,kind,body): self.code=code;self.kind=kind;self.body=body
    def send_response(self,code): self.code=code
    def send_header(self,key,value): self.response_headers[key]=value
    def end_headers(self): pass
    class W:
        def __init__(self,owner): self.owner=owner
        def write(self,body): self.owner.body=body
    @property
    def wfile(self): return self.W(self)

class Response:
    def __init__(self,body): self.body=body
    def __enter__(self): return self
    def __exit__(self,*_): return False
    def read(self,_): return self.body

def full_frame(now=1000.0,status='AVAILABLE'):
    x={k:None for k in proxy.FIELDS}
    x.update(schema='BTC15_INFORMATION_V1',authority='INFORMATIONAL_READ_ONLY',status=status,reason=None,
             signal_only=True,orders=False,checked_ts=now,native_epoch='epoch-a',anchor_id='a'*64,
             ticker='KXBTC15M-TEST',expires_at=now+2,display_until=now+2,brti_source_ts=now-.2)
    if status=='WAIT':
        return x
    # closed() only imposes clock/authority constraints on AVAILABLE; remaining
    # informational fields may be inert test values while preserving exact schema.
    return x

class IdentityRouteTests(unittest.TestCase):
    def setUp(self):
        proxy.TOKENS=20.;proxy.NEXT=0.
    def call(self,row,path='/information/identity',nonce='a'*32,now=1000.0):
        raw=json.dumps(row).encode();h=Handler(path,nonce)
        with patch.object(proxy,'urlopen',return_value=Response(raw)), patch.object(proxy.time,'time',return_value=now):
            self.assertTrue(proxy.serve(h))
        return h
    def test_route_projects_minimal_identity_and_nonce(self):
        h=self.call(full_frame())
        self.assertEqual(h.code,200);self.assertEqual(h.response_headers.get('X-BTC15-Information-Nonce'),'a'*32)
        out=json.loads(h.body);self.assertEqual(set(out),{'schema','ticker','native_epoch','anchor_id','observed_ts','signal_only','orders'})
    def test_route_wait_fails_closed(self):
        h=self.call(full_frame(status='WAIT'));self.assertEqual(h.code,503)
    def test_route_stale_upstream_fails_closed(self):
        x=full_frame();x['brti_source_ts']=994.0
        h=self.call(x);self.assertEqual(h.code,503)
    def test_route_closed_contract_cannot_be_bypassed(self):
        x=full_frame();x['orders']=True
        h=self.call(x);self.assertEqual(h.code,503)
    def test_route_uses_internal_information_path(self):
        seen=[]
        def fake(url,timeout): seen.append(url);return Response(json.dumps(full_frame()).encode())
        h=Handler('/information/identity')
        with patch.object(proxy,'urlopen',side_effect=fake),patch.object(proxy.time,'time',return_value=1000.0):
            proxy.serve(h)
        self.assertEqual(seen,['http://127.0.0.1:8767/information'])
    def test_invalid_nonce_rejected(self):
        h=self.call(full_frame(),nonce='bad');self.assertEqual(h.code,400)
    def test_ordinary_information_remains_full_contract(self):
        h=self.call(full_frame(),path='/information')
        out=json.loads(h.body);self.assertEqual(set(out),set(proxy.FIELDS));self.assertEqual(out['ticker'],'KXBTC15M-TEST')

if __name__=='__main__':unittest.main()
