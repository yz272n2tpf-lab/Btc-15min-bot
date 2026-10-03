"""Focused sender lifetime/accounting tests. No strategy or signal fixtures."""
import gzip
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import urlopen

from capture2.runtime import CaptureProducer,SenderPopulation
from capture2.writer import Accounting
from capture2.test_repairs import HeldSocket,identity,wait_for,NATIVE_SHA,ROOT


def end(seconds=15):return time.clock_gettime_ns(time.CLOCK_BOOTTIME)+int(seconds*1e9)


def stream(root,pop,name,sink=None,address='unused',count=3):
    p=CaptureProducer(address,identity(name),b'a'*32,end_boot_ns=pop.end_boot_ns,
                      status_path=root/('transport-'+name+'.json'),population=pop,sock=sink)
    for i in range(count):
        if not p.offer('OBSERVED',{'index':i}):raise AssertionError(p.last_error)
    return p


class LifetimeTests(unittest.TestCase):
    def test_origin_exit_drains_then_retires_and_breaks_owner_cycle(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pop=SenderPopulation(root,end());sink=HeldSocket();seen=[];origins=[]
            def run():origins.append(threading.get_ident());seen.append(stream(root,pop,'short',sink))
            t=threading.Thread(target=run);t.start();t.join()
            try:
                wait_for(lambda:seen[0].sock.retries>0)
                self.assertEqual(pop.snapshot()['active'],1);self.assertEqual(pop.snapshot()['retired'],0)
                sink.ready=True;wait_for(lambda:pop.snapshot()['retired']==1)
                p=seen[0];s=p.sock.snapshot()
                self.assertEqual([json.loads(x)['event']['sequence'] for x in sink.raw],[1,2,3])
                self.assertTrue(s['complete']);self.assertEqual(s['retirement_reason'],'ORIGIN_THREAD_EXITED')
                self.assertIsNone(p.sock.owner);self.assertFalse(p.sock.thread.is_alive())
                self.assertNotIn(origins[0],sink.threads)
                self.assertEqual(pop.snapshot()['active'],0)
                self.assertTrue(json.loads((root/'transport-short.json').read_text())['finished'])
            finally:pop.close();pop.thread.join(3)

    def test_terminal_loss_remains_explicit_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pop=SenderPopulation(root,end());sink=HeldSocket();sink.fatal=True
            t=threading.Thread(target=lambda:stream(root,pop,'failed',sink));t.start();t.join()
            try:
                wait_for(lambda:pop.snapshot()['retired']==1)
                s=json.loads((root/'transport-failed.json').read_text())
                self.assertFalse(s['complete']);self.assertEqual(s['pending_packets'],3)
                self.assertEqual(pop.snapshot()['retired_incomplete'],1)
                self.assertEqual(pop.fault,'RETIRED_INCOMPLETE')
            finally:pop.close();pop.thread.join(3)

    def test_admission_bounds_reject_with_complete_failure_accounting(self):
        for max_active,max_created,reason in [(1,10,'SENDER_LIMIT'),(10,1,'STREAM_LIMIT')]:
            with self.subTest(reason=reason),tempfile.TemporaryDirectory() as d:
                root=Path(d);pop=SenderPopulation(root,end(),max_active=max_active,max_created=max_created)
                sink=HeldSocket();p=stream(root,pop,'one',sink)
                try:
                    with self.assertRaisesRegex(RuntimeError,reason):stream(root,pop,'two',sink)
                    s=pop.snapshot();self.assertEqual(s['created'],1);self.assertEqual(s['active'],1)
                    self.assertEqual(s['admission_rejected'],1);self.assertEqual(s['fault'],reason)
                    self.assertEqual(s['rejected_attempts'][0]['producer_id'],'two')
                finally:sink.ready=True;p.close();pop.close();pop.thread.join(3)

    def test_1024_short_lived_streams_complete_paginated_accounting(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pop=SenderPopulation(root,end(30));heads={};sinks=[];errors=[]
            try:
                for wave in range(128):
                    def run(i):
                        try:
                            sink=HeldSocket();sink.ready=True;sinks.append(sink)
                            stream(root,pop,str(i),sink)
                        except Exception as exc:errors.append(str(exc))
                    threads=[threading.Thread(target=run,args=(wave*8+j,)) for j in range(8)]
                    for t in threads:t.start()
                    for t in threads:t.join()
                    wait_for(lambda:pop.snapshot()['active']==0)
                    self.assertFalse(errors,errors)
                    self.assertLessEqual(sum(t.name=='capture-datagram-drain' for t in threading.enumerate()),16)
                for sink in sinks:
                    rows=[json.loads(x)['event'] for x in sink.raw]
                    self.assertEqual([r['sequence'] for r in rows],[1,2,3])
                    heads[rows[0]['identity']['producer_id']]=3
                pop.close();pop.thread.join(3)
                a=Accounting(root);s=a.capture(heads);self.assertTrue(s['complete'],s['errors'])
                self.assertEqual((s['created'],s['active'],s['retired'],s['retired_flushed']),(1024,0,1024,1024))
                self.assertEqual((s['dropped'],s['pending'],s['delivered']),(0,0,3072))
                all_rows=[];offset=0
                while offset is not None:
                    page=a.page(s['snapshot_id'],offset,128);all_rows+=page['records'];offset=page['next_offset']
                self.assertEqual(len({r['producer_id'] for r in all_rows}),1024)
                self.assertLessEqual(pop.high_water,16)
                original=a.page(s['snapshot_id'],0,128)
                path=root/'transport-0.json';path.unlink()
                broken=a.capture(heads);self.assertFalse(broken['complete']);self.assertIn('0',broken['missing_streams'])
                self.assertEqual(original,a.page(s['snapshot_id'],0,128))
                a.capture(heads)
                with self.assertRaises(KeyError):a.page(s['snapshot_id'],0,128)
                print('CHURN',json.dumps({k:s[k] for k in ('created','active','retired','retired_flushed','delivered','dropped','pending')},sort_keys=True),
                      'HIGH_WATER',pop.high_water,flush=True)
            finally:pop.close();pop.thread.join(3)


class LifetimeKernelTests(unittest.TestCase):
    def test_real_writer_256_automatic_retirements_preserve_every_packet(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);address=str(root/'events.sock')
            port_socket=socket.socket();port_socket.bind(('127.0.0.1',0));port=port_socket.getsockname()[1];port_socket.close()
            c=dict(directory=d,socket=address,key=(b'a'*32).hex(),run_id='run',build='build',
                   source_hashes=[NATIVE_SHA],max_seconds=8,quota_bytes=16*1024*1024,port=port)
            cp=root/'config.json';cp.write_text(json.dumps(c))
            proc=subprocess.Popen([sys.executable,'-B','-m','capture2.writer','--config',str(cp)],cwd=ROOT,
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            pop=SenderPopulation(root,end(15));errors=[]
            try:
                wait_for(lambda:Path(address).exists() or proc.poll() is not None)
                self.assertTrue(Path(address).exists())
                for wave in range(32):
                    def run(i):
                        try:stream(root,pop,str(i),address=address,count=5)
                        except Exception as exc:errors.append(str(exc))
                    threads=[threading.Thread(target=run,args=(wave*8+j,)) for j in range(8)]
                    for t in threads:t.start()
                    for t in threads:t.join()
                    wait_for(lambda:pop.snapshot()['active']==0)
                    self.assertFalse(errors,errors)
                pop.close();pop.thread.join(3)
                wait_for(lambda:(root/'final_health.json').exists(),10)
                h=json.loads((root/'final_health.json').read_text());s=h['transport_accounting']
                rows=[json.loads(x)['event'] for x in gzip.decompress((root/'packets.jsonl.gz').read_bytes()).splitlines()]
                groups={}
                for row in rows:groups.setdefault(row['identity']['producer_id'],[]).append(row['sequence'])
                self.assertEqual(len(rows),1280);self.assertEqual(len(groups),256)
                self.assertTrue(all(v==[1,2,3,4,5] for v in groups.values()))
                self.assertEqual(h['sequence_gaps'],[]);self.assertEqual(h['invalid'],0)
                self.assertTrue(s['complete'],s['errors']);self.assertEqual(s['total'],256)
                self.assertEqual((s['created'],s['active'],s['retired']),(256,0,256))
                with urlopen(f'http://127.0.0.1:{port}/ground-zero/manifest') as response:
                    self.assertEqual(response.status,200);manifest=json.load(response)
                snapshot=manifest['health']['transport_accounting']['snapshot_id'];pages=[]
                for offset in (0,128):
                    with urlopen(f'http://127.0.0.1:{port}/ground-zero/transports?snapshot={snapshot}&offset={offset}') as response:
                        pages.extend(json.load(response)['records'])
                self.assertEqual(len({p['producer_id'] for p in pages}),256)
                self.assertTrue(all(p['finished'] and p['received_sequence']==5 for p in pages))
                print('KERNEL_CHURN',json.dumps({k:s[k] for k in ('created','active','retired','delivered','dropped','pending')}),flush=True)
            finally:pop.close();pop.thread.join(3);proc.terminate();proc.communicate(timeout=5)


if __name__=='__main__':unittest.main()
