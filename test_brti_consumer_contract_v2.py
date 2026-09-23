import os
import time
import unittest
from unittest.mock import patch
from btc15_brti_shared_consumer_v1 import read_shared_brti, read_shared_brti_ticks

class ConsumerContract(unittest.TestCase):
    def setUp(self):
        self.now=1780000000.
        self.state=dict(schema_version=2,index_id='BRTI',owner_epoch='epoch',orders=False,
                        signal_only=True,source_ts_ms=int(self.now*1000)-1000,value=100000.,
                        sequence=1,status='PRIMARY_OK',clean_for_qualification=True)
        self.enterContext(patch.dict(os.environ,BTC15_BRTI_TRANSPORT='legacy_shared_http'))
        self.enterContext(patch('time.time',return_value=self.now))

    def test_source_age_is_used_instead_of_reported_age(self):
        with patch('btc15_brti_shared_consumer_v1._legacy_get',return_value=self.state):
            self.assertEqual(read_shared_brti()['age_seconds'],1.)
            self.state.update(source_ts_ms=int(self.now*1000)-6000,age_ms=0)
            with self.assertRaises(RuntimeError): read_shared_brti()

    def test_bad_metadata_current_status_and_future_time_rejected(self):
        for change in [dict(orders=True),dict(signal_only=False),dict(schema_version=1),
                       dict(status='PRIMARY_ERROR'),dict(clean_for_qualification=False),
                       dict(source_ts_ms=int(self.now*1000)+1),dict(value=float('nan'))]:
            with self.subTest(change=change),patch('btc15_brti_shared_consumer_v1._legacy_get',return_value=self.state|change):
                with self.assertRaises(RuntimeError): read_shared_brti()

    def test_history_epoch_and_conflicts_rejected(self):
        history=self.state|dict(ticks=[dict(index_id='BRTI',source_ts_ms=int(self.now*1000)-1000,value=100000.)])
        with patch('btc15_brti_shared_consumer_v1._legacy_get',return_value=history):
            self.assertEqual(len(read_shared_brti_ticks(owner_epoch='epoch')),1)
            with self.assertRaises(RuntimeError): read_shared_brti_ticks(owner_epoch='old')
            history['ticks'].append(history['ticks'][0]|dict(value=100001.))
            with self.assertRaises(RuntimeError): read_shared_brti_ticks()

if __name__=='__main__':unittest.main()
