import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import os
import threading
import urllib.request
import urllib.error
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import btc15_common_observer_v1 as module


class CommonEvidence(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path=self.root/'evidence.jsonl.gz'

    def test_restart_append_preserves_each_complete_member(self):
        first=dict(record_type='OBSERVATION',sources=[dict(service='main',error_type='Timeout')],orders=False)
        module.append_record(self.path,first);original=self.path.read_bytes()
        module.append_record(self.path,dict(record_type='SNAPSHOT_INPUT',brti_source_ts_ms=123,orders=False))
        self.assertTrue(self.path.read_bytes().startswith(original))
        records=[json.loads(line) for line in gzip.decompress(self.path.read_bytes()).splitlines()]
        self.assertEqual(records[0],first);self.assertEqual(records[1]['brti_source_ts_ms'],123)

    def test_observation_loop_uses_one_second_cached_reads_only(self):
        class Stop:
            waits=[]
            def is_set(self):return bool(self.waits)
            def wait(self,seconds):self.waits.append(seconds)
        stop=Stop()
        with patch.object(module,'read_source',side_effect=lambda item:dict(service=item[0],state={})) as read, \
             patch.object(module.time,'monotonic',side_effect=[10.,10.2]),patch.object(module,'append_record') as append:
            module.observe_forever(self.path,'new-run',stop)
        self.assertAlmostEqual(stop.waits[0],.8)
        self.assertEqual(read.call_count,4)
        self.assertEqual({call.args[0][1] for call in read.call_args_list},set(module.URLS.values()))
        record=append.call_args.args[1]
        self.assertEqual(record['sampling_seconds'],1.)
        self.assertTrue(record['observer_epoch']);self.assertFalse(record['orders'])

    def test_sampler_cannot_remain_at_one_stale_five_second_phase(self):
        # Reproduces the measured4.7s observer phase against a5s producer.
        # Available states with true source age<5 occupied the early cycle.
        old_phases=[(4.7+5*i)%5 for i in range(20)]
        new_phases=[(4.7+module.OBSERVATION_INTERVAL_SECONDS*i)%5 for i in range(20)]
        self.assertFalse(any(phase<2 for phase in old_phases))
        self.assertTrue(any(phase<2 for phase in new_phases))

    def test_bounded_incremental_export_reassembles_identical_bytes(self):
        module.append_record(self.path,dict(value='first',orders=False))
        m,a=module.export_chunk(self.path,0,10)
        n,b=module.export_chunk(self.path,m['next_offset'])
        self.assertEqual(a+b,self.path.read_bytes())
        self.assertEqual(m['sha256'],hashlib.sha256(a).hexdigest())
        self.assertEqual(n['next_offset'],n['total_bytes'])
        for offset,limit in [(-1,10),(0,4000001),(1000000,10),(0,0)]:
            with self.subTest(offset=offset,limit=limit),self.assertRaises(ValueError):
                module.export_chunk(self.path,offset,limit)

    def test_concurrent_detector_and_observer_appends_are_intact(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda n:module.append_record(self.path,dict(sequence=n)),range(24)))
        records=[json.loads(line) for line in gzip.decompress(self.path.read_bytes()).splitlines()]
        self.assertEqual(sorted(r['sequence'] for r in records),list(range(24)))

    def test_failed_source_is_recorded_and_does_not_fetch_authenticated_upstream(self):
        with patch.object(module.requests,'get',side_effect=TimeoutError) as get:
            record=module.read_source(('owner',module.URLS['owner']))
        self.assertEqual(record['error_type'],'TimeoutError')
        self.assertNotIn('state',record)
        self.assertIn('response_received_utc',record)
        self.assertEqual(get.call_args.args[0],module.URLS['owner'])
        self.assertNotIn('Authorization',get.call_args.kwargs['headers'])

    def test_real_http_export_preserves_bytes_hash_and_range_checks(self):
        from http.server import ThreadingHTTPServer
        import scalp_path_export_bridge_v1 as bridge
        module.append_record(self.path,dict(orders=False,value='saved evidence'))
        with patch.object(bridge,'TOKEN',''),patch.object(bridge,'EXPORT_ENABLE',True),patch.dict(os.environ,BTC15_COMMON_OBSERVATIONS=str(self.path)):
            server=ThreadingHTTPServer(('127.0.0.1',0),bridge.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                url='http://127.0.0.1:'+str(server.server_port)+'/research/common-export'
                with urllib.request.urlopen(url+'?offset=0&limit=10') as response:
                    first=response.read();offset=response.headers['X-Evidence-next-offset']
                    self.assertEqual(response.headers['X-Evidence-sha256'],hashlib.sha256(first).hexdigest())
                with urllib.request.urlopen(url+'?offset='+offset) as response:rest=response.read()
                self.assertEqual(first+rest,self.path.read_bytes())
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(url+'?offset=-1')
                self.assertEqual(error.exception.code,400)
            finally:
                server.shutdown();server.server_close();thread.join()


if __name__ == '__main__':unittest.main()
