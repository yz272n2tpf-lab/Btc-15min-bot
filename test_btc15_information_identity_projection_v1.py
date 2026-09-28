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

if __name__=='__main__':unittest.main()
