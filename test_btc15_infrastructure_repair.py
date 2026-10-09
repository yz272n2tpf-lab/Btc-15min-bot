"""Bounded local infrastructure regressions. No feeds, signals or shadow run."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import urlopen

from test_btc15_information_identity_projection_v1 import proxy, Handler, Response, full_frame
from btc15_information_service_v1 import server_for, response, HealthMirror
from btc15_information_v1 import wait_view, Unavailable
from btc15_information_journal_v1 import CompressedJournal, information_lines
from btc15_v2_product.worker import install_revalidation_route


class DeliveryTests(unittest.TestCase):
    def call(self, raw=None, error=None):
        proxy.TOKENS=20.;proxy.NEXT=0.
        handler=Handler('/information')
        with patch.object(proxy,'urlopen',side_effect=error,return_value=Response(raw)), \
             patch.object(proxy.time,'time',return_value=1000.):
            proxy.serve(handler)
        return handler

    def test_transport_expiry_is_redacted_source_wait_without_new_lease(self):
        frame=full_frame();frame['display_until']=999.99
        handler=self.call(json.dumps(frame).encode())
        value=json.loads(handler.body)
        self.assertEqual(handler.code,200)
        self.assertEqual(value['reason'],'SOURCE_EXPIRED_IN_TRANSIT')
        self.assertEqual(value['status'],'WAIT')
        self.assertEqual(set(value),set(proxy.FIELDS))
        for name in set(value)-{'schema','authority','status','reason','signal_only','orders','checked_ts'}:
            self.assertIsNone(value[name],name)
        self.assertEqual(handler.response_headers['X-BTC15-Information-Nonce'],'a'*32)

    def test_fresh_value_preserves_original_expiration(self):
        frame=full_frame()
        handler=self.call(json.dumps(frame).encode())
        self.assertEqual(handler.code,200)
        self.assertEqual(json.loads(handler.body)['expires_at'],frame['expires_at'])

    def test_malformed_internal_output_is_not_source_wait(self):
        frame=full_frame();frame['orders']=True
        handler=self.call(json.dumps(frame).encode())
        self.assertEqual(handler.code,502)
        self.assertEqual(json.loads(handler.body)['error'],'INFORMATION_INVALID_RESPONSE')

    def test_timeouts_are_identified_without_replaying_old_information(self):
        handler=self.call(error=URLError(TimeoutError()))
        self.assertEqual(handler.code,503)
        self.assertEqual(json.loads(handler.body)['error'],'INFORMATION_WORKER_TIMEOUT')
        self.assertNotIn('frame_id',json.loads(handler.body))

    def test_internal_read_error_stays_a_server_error(self):
        def broken(*args): raise RuntimeError('private details must not escape')
        code,body=response(SimpleNamespace(read=broken),SimpleNamespace(health=lambda:{}),'/information')
        self.assertEqual(code,500)
        self.assertNotIn(b'private',body)

    def test_source_loss_and_internal_health_failure_are_distinct(self):
        def source_down(): raise Unavailable('SOURCE_DOWN')
        mirror=HealthMirror(SimpleNamespace(health=source_down));mirror.refresh()
        code,body=response(None,mirror,'/information')
        self.assertEqual(code,200);self.assertEqual(json.loads(body)['status'],'WAIT')
        def broken(): raise RuntimeError('broken sampler')
        mirror.ingress=SimpleNamespace(health=broken);mirror.refresh()
        self.assertEqual(response(None,mirror,'/information')[0],500)

    def test_information_is_served_while_actual_revalidation_wait_is_blocked(self):
        waiting=threading.Event();release=threading.Event()
        class WaitingCondition:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def wait_for(self,predicate,timeout):
                waiting.set();release.wait(2)
        publisher=SimpleNamespace(read=lambda health,now,frame_id:wait_view(now,'INPUT_UNAVAILABLE'))
        server=server_for(publisher,SimpleNamespace(health=lambda:{}))
        install_revalidation_route(server,SimpleNamespace(latest=None),WaitingCondition())
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with ThreadPoolExecutor(2) as pool:
                pending=pool.submit(lambda:urlopen(base+'/revalidation?binding=expected',timeout=3).read())
                self.assertTrue(waiting.wait(1))
                try:
                    with urlopen(base+'/information',timeout=.4) as result:
                        self.assertEqual(result.status,200)
                        self.assertEqual(json.load(result)['status'],'WAIT')
                finally:release.set()
                self.assertIn(b'REVALIDATION_STARTING',pending.result())
        finally:
            release.set();server.shutdown();server.server_close();thread.join(1)


class EvidenceTests(unittest.TestCase):
    def test_production_evidence_reader_includes_both_formats(self):
        from btc15_cohort_evidence_v1 import read_information, REQUIRED_INFORMATION
        with TemporaryDirectory() as directory:
            path=Path(directory)/'frames.jsonl'
            frame=dict.fromkeys(REQUIRED_INFORMATION)
            frame.update(frame_id='old',signal_only=True,orders=False)
            old=json.dumps(dict(schema='BTC15_INFORMATION_JOURNAL_V1',frame_id='old',frame=frame)).encode()+b'\n'
            path.write_bytes(old)
            frame=dict(frame,frame_id='new')
            new=json.dumps(dict(schema='BTC15_INFORMATION_JOURNAL_V1',frame_id='new',frame=frame)).encode()+b'\n'
            CompressedJournal(path).append(new)
            self.assertEqual([f['frame_id'] for f in read_information(path)],['old','new'])

    def test_legacy_plus_new_segments_lossless_across_restart_and_day_change(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'frames.jsonl'
            old=b'{"historical":"keep exactly"}\n';path.write_bytes(old)
            now=[1791514000.]
            first=CompressedJournal(path,clock=lambda:now[0])
            lines=[json.dumps({'frame_id':str(i),'frame':{'padding':'abc'*1000}}).encode()+b'\n' for i in range(4)]
            first.append(lines[0]);first.append(lines[1]);now[0]+=86400;first.append(lines[2])
            second=CompressedJournal(path,clock=lambda:now[0]);second.append(lines[3])
            self.assertEqual(path.read_bytes(),old)
            self.assertEqual(list(information_lines(path))[0],old)
            self.assertCountEqual(list(information_lines(path))[1:],lines)
            self.assertEqual(len(list(first.directory.glob('*.gz'))),3)
            self.assertLess(first.stored_bytes,first.raw_bytes/2)

    def test_partial_os_writes_are_completed(self):
        import os
        original=os.write
        with TemporaryDirectory() as directory:
            path=Path(directory)/'frames.jsonl';writer=CompressedJournal(path)
            line=b'{"preserve":"all bytes"}\n'
            with patch('btc15_information_journal_v1.os.write',side_effect=lambda fd,data:original(fd,data[:7])):
                writer.append(line)
            self.assertEqual(list(information_lines(path)),[line])

    def test_corrupt_segment_is_not_silently_dropped(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'frames.jsonl';writer=CompressedJournal(path)
            writer.append(b'{"frame":1}\n')
            with writer.path.open('ab') as stream:stream.write(b'broken member')
            with self.assertRaises((gzip.BadGzipFile,EOFError)):
                list(information_lines(path))

    def test_failed_segment_rejects_later_append(self):
        with TemporaryDirectory() as directory:
            writer=CompressedJournal(Path(directory)/'frames.jsonl')
            with patch('btc15_information_journal_v1.os.write',side_effect=OSError('full')):
                with self.assertRaises(OSError):writer.append(b'{}\n')
            with self.assertRaises(OSError):writer.append(b'{}\n')


if __name__=='__main__':unittest.main()
