"""Offline owner→HTTP→consumer acceptance, no credentials/upstream."""
import os
import threading
import time
import unittest
from unittest.mock import Mock, patch
import requests
from brti_shared_feed_v1 import SharedBrtiPoller, brti_publications, make_server
from btc15_brti_shared_consumer_v1 import read_shared_brti, read_shared_brti_ticks


def point(ts, value=100000.):
    return dict(index_id='BRTI', source_ts_ms=ts, value=value)


class SourceIntegrity(unittest.TestCase):
    def setUp(self):
        self.clock = 1780000000.
        self.wall = self.enterContext(patch('time.time', return_value=self.clock))
        self.fetch = Mock(return_value=[point(int(self.clock*1000)-1000)])
        self.owner = SharedBrtiPoller(self.fetch, poll_interval_s=2,
                                      max_qualification_age_s=5, jitter_s=0)

    def test_receipt_cannot_refresh_repeated_source(self):
        self.owner.poll_once(force=True)
        first = self.owner.snapshot()
        self.wall.return_value += 6
        self.owner.poll_once(force=True)
        last = self.owner.snapshot()
        self.assertEqual(last['sequence'], first['sequence'])
        self.assertEqual(last['source_ts_ms'], first['source_ts_ms'])
        self.assertEqual(last['age_ms'], 7000)
        self.assertFalse(last['clean_for_qualification'])

    def test_actual_per_second_history_retained_at_two_second_poll(self):
        self.fetch.return_value = [point(int(self.clock*1000)-1000*i) for i in range(1,61)]
        self.owner.poll_once(force=True)
        self.assertEqual(len(self.owner.history()['ticks']), 60)
        for _ in range(50):
            self.owner.snapshot(); self.owner.history()
        self.fetch.assert_called_once()

    def test_missing_future_and_invalid_source_fail_closed(self):
        for data in (100000., [], [point(int(self.clock*1000)+1)],
                     [point(int(self.clock*1000), float('nan'))],
                     [dict(value=100000.)]):
            with self.subTest(data=data):
                self.fetch.return_value = data
                self.owner.poll_once(force=True)
                self.assertFalse(self.owner.snapshot()['clean_for_qualification'])

    def test_conflicting_publication_and_regression_fail_closed(self):
        self.owner.poll_once(force=True)
        ts = self.owner.snapshot()['source_ts_ms']
        for batch in ([point(ts,100001.)], [point(ts-1000)]):
            self.fetch.return_value = batch
            self.owner.poll_once(force=True)
            self.assertFalse(self.owner.snapshot()['clean_for_qualification'])
        self.assertEqual(self.owner.history()['ticks'], [point(ts)])

    def test_429_immediate_fail_closed_capped_backoff_and_recovery(self):
        self.owner.poll_once(force=True)
        response = requests.Response(); response.status_code=429
        self.fetch.side_effect = requests.HTTPError('sensitive response not logged',response=response)
        with patch('time.monotonic',return_value=100.):
            for _ in range(10):
                self.owner.poll_once(force=True)
            state=self.owner.snapshot()
            self.assertFalse(state['clean_for_qualification'])
            self.assertEqual(state['next_poll_in_ms'],30000)
            self.assertEqual(state['http_429'],10)
            self.assertNotIn('sensitive',state['last_error_text'])
            self.assertFalse(self.owner.poll_once())
        self.fetch.side_effect=None
        self.fetch.return_value=[point(int(self.clock*1000))]
        self.owner.poll_once(force=True)
        self.assertTrue(self.owner.snapshot()['clean_for_qualification'])

    def test_poll_interval_cannot_expand_five_second_freshness(self):
        owner=SharedBrtiPoller(self.fetch,poll_interval_s=20,max_qualification_age_s=100)
        owner.poll_once(force=True)
        self.wall.return_value+=5
        self.assertFalse(owner.snapshot()['clean_for_qualification'])

    def test_clock_regression_fails_closed(self):
        self.owner.poll_once(force=True)
        self.wall.return_value-=2
        self.assertFalse(self.owner.snapshot()['clean_for_qualification'])

    def test_cold_restart_has_new_epoch_and_no_qualified_retained_state(self):
        self.owner.poll_once(force=True)
        restarted=SharedBrtiPoller(self.fetch)
        self.assertNotEqual(restarted.owner_epoch,self.owner.owner_epoch)
        self.assertFalse(restarted.snapshot()['clean_for_qualification'])
        self.assertEqual(restarted.history()['ticks'],[])

    def test_strict_payload_preserves_source_time_and_orders_by_timestamp(self):
        result=brti_publications({'data':{'id':'BRTI','payload':[
            {'time':1780000000000,'value':'100001'},
            {'time':1779999999000,'value':'100000'}]}})
        self.assertEqual(result,[point(1779999999000),point(1780000000000,100001.)])
        for obj in ({'value':100000}, {'payload':[{'value':100000}]},
                    {'id':'ETHUSD_RTI','payload':[{'time':1780000000000,'value':100000}]}):
            with self.assertRaises(ValueError): brti_publications(obj)

    def test_http_consumers_recover_sixty_publications(self):
        self.fetch.return_value=[point(int(self.clock*1000)-1000*i) for i in range(1,61)]
        self.owner.poll_once(force=True)
        server=make_server(self.owner,'127.0.0.1',0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with patch.dict(os.environ,BTC15_USE_SHARED_BRTI='1',BTC15_BRTI_TRANSPORT='legacy_shared_http',BTC15_BRTI_SHARED_URL=base):
                state=read_shared_brti()
                self.assertEqual(state['source_ts_ms'],int(self.clock*1000)-1000)
                self.assertEqual(len(read_shared_brti_ticks(owner_epoch=state['owner_epoch'])),60)
                with self.assertRaises(RuntimeError): read_shared_brti_ticks(owner_epoch='old')
                self.fetch.assert_called_once()
                self.wall.return_value+=6
                with self.assertRaises(RuntimeError): read_shared_brti()
                # Retained source history is available for closeout, never qualified as current.
                self.assertEqual(len(read_shared_brti_ticks()),60)
        finally:
            server.shutdown();server.server_close();thread.join(2)

    def test_legacy_receipt_timestamp_only_schema_is_rejected(self):
        with patch('btc15_brti_shared_consumer_v1._legacy_get',return_value={
            'orders':False,'value':100000.,'success_timestamp_utc':'2026-09-23T00:00:00Z',
            'clean_for_qualification':True,'status':'PRIMARY_OK'}), \
             patch.dict(os.environ,BTC15_BRTI_TRANSPORT='legacy_shared_http'):
            with self.assertRaises(RuntimeError): read_shared_brti()

if __name__=='__main__': unittest.main()
