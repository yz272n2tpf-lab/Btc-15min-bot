"""Only the import-order and bounded transport regressions; no ladder fixtures."""
import ast
import errno
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

from capture2.install import add_imports,assemble_main,NATIVE_SHA,ROOT
from capture2.runtime import CaptureProducer
from sprint_evidence.passive_capture import Identity,Producer


def identity(name='fixture'):
    return Identity(name,'build',NATIVE_SHA,'run','domain','boot')


class HeldSocket:
    def __init__(self):self.ready=False;self.raw=[];self.threads=set();self.fatal=False
    def setblocking(self,*a):pass
    def setsockopt(self,*a):pass
    def close(self):pass
    def sendto(self,raw,*args):
        self.threads.add(threading.get_ident())
        if self.fatal:raise OSError(errno.ECONNREFUSED,'receiver gone')
        if not self.ready:raise BlockingIOError(errno.EAGAIN,'receiver queue full')
        self.raw.append(raw);return len(raw)


def wait_for(fn,timeout=3):
    end=time.monotonic()+timeout
    while not fn() and time.monotonic()<end:time.sleep(.002)
    if not fn():raise AssertionError('DRAIN_TIMEOUT')


class RepairUnitTests(unittest.TestCase):
    def test_future_imports_stay_before_hooks_with_or_without_docstring(self):
        for prefix in ('','"""module documentation"""\n'):
            raw=prefix+'from __future__ import annotations\nfrom __future__ import division\nx=1\n'
            tree=add_imports(ast.parse(raw),'from capture2.runtime import Proxy\ny=2')
            compile(tree,'generated','exec');compile(ast.unparse(tree),'unparsed','exec')
            futures=[i for i,n in enumerate(tree.body) if isinstance(n,ast.ImportFrom) and n.module=='__future__']
            hook=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.ImportFrom) and n.module=='capture2.runtime')
            self.assertLess(max(futures),hook)

    def test_all_generated_main_python_files_compile(self):
        with tempfile.TemporaryDirectory() as d:
            target=assemble_main(Path(d));paths=list(target.glob('*.py'))
            self.assertGreater(len(paths),3)
            for p in paths:compile(p.read_bytes(),str(p),'exec')

    def make(self,sock,**kwargs):
        return CaptureProducer('x',identity(),b'a'*32,sock=sock,
                               end_boot_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME)+5_000_000_000,**kwargs)

    def test_stalled_receiver_retries_off_thread_and_retains_every_packet(self):
        sink=HeldSocket();p=self.make(sink)
        try:
            for i in range(2000):self.assertTrue(p.offer('OBSERVED',{'index':i}),p.last_error)
            wait_for(lambda:p.sock.retries>0)
            self.assertEqual(p.dropped,0);self.assertLessEqual(p.sock.high_water_bytes,p.sock.max_bytes)
            sink.ready=True;wait_for(lambda:len(sink.raw)==2000)
            rows=[json.loads(x)['event'] for x in sink.raw]
            self.assertEqual([r['sequence'] for r in rows],list(range(1,2001)))
            self.assertEqual([r['body']['index'] for r in rows],list(range(2000)))
            self.assertNotIn(threading.get_ident(),sink.threads)
        finally:p.close();p.sock.thread.join(3)

    def test_full_buffer_rejects_without_wait_and_loss_remains_visible(self):
        sink=HeldSocket();p=self.make(sink,max_packets=2,max_bytes=4096)
        try:
            self.assertTrue(p.offer('OBSERVED',{'index':0}));self.assertTrue(p.offer('OBSERVED',{'index':1}))
            self.assertFalse(p.offer('OBSERVED',{'index':2}));self.assertEqual(p.dropped,1)
            self.assertIn('CAPTURE_BUFFER_FULL',p.last_error);self.assertEqual(p.sock.rejected,1)
            sink.ready=True;wait_for(lambda:len(sink.raw)==2)
            self.assertTrue(p.offer('OBSERVED',{'index':3}));wait_for(lambda:len(sink.raw)==3)
            last=json.loads(sink.raw[-1])['event'];self.assertEqual(last['sequence'],4);self.assertEqual(last['prior_dropped'],1)
        finally:p.close();p.sock.thread.join(3)

    def test_terminal_delivery_failure_is_explicit_even_without_later_packet(self):
        sink=HeldSocket();sink.fatal=True
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'transport-test.json';p=self.make(sink,status_path=path)
            try:
                self.assertTrue(p.offer('OBSERVED',{'index':0}));wait_for(lambda:p.sock.finished)
                value=json.loads(path.read_text());self.assertEqual(value['pending_packets'],1)
                self.assertEqual(value['delivered'],0);self.assertIn('receiver gone',value['last_transport_error'])
                self.assertFalse(p.offer('OBSERVED',{'index':1}));self.assertEqual(p.dropped,1)
            finally:p.close();p.sock.thread.join(3)


class RepairKernelTests(unittest.TestCase):
    def test_kernel_queue_reproduces_old_eagain_and_buffer_preserves_burst(self):
        with tempfile.TemporaryDirectory() as d:
            address=str(Path(d)/'events.sock');receiver=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
            receiver.bind(address);receiver.settimeout(3)
            old=Producer(address,identity('old'),b'a'*32)
            try:
                qlen=int(Path('/proc/sys/net/unix/max_dgram_qlen').read_text())
                while old.sent<max(10000,qlen+2) and old.offer('OBSERVED',{'index':old.sent}):pass
                self.assertGreater(old.dropped,0);self.assertIn('BlockingIOError',old.last_error)
                self.assertLessEqual(old.sent,qlen+1)
                print('ROOT_CAUSE',json.dumps({'kernel_max_dgram_qlen':qlen,'old_sent':old.sent,'old_error':old.last_error}),flush=True)
                for _ in range(old.sent):receiver.recv(196609)
                p=CaptureProducer(address,identity('new'),b'a'*32,end_boot_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME)+8_000_000_000)
                try:
                    for i in range(2000):self.assertTrue(p.offer('OBSERVED',{'index':i}),p.last_error)
                    records=[json.loads(receiver.recv(196609))['event'] for _ in range(2000)]
                    wait_for(lambda:p.sock.delivered==2000)
                    self.assertEqual([x['sequence'] for x in records],list(range(1,2001)))
                    self.assertEqual(p.dropped,0);self.assertGreater(p.sock.retries,0)
                    print('BUFFER_BURST',json.dumps(p.sock.snapshot()),flush=True)
                finally:p.close();p.sock.thread.join(3)
            finally:old.close();receiver.close()

    def test_repaired_writer_retains_10000_unpaced_packets(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);address=str(root/'events.sock');end=time.clock_gettime_ns(time.CLOCK_BOOTTIME)+8_000_000_000
            c=dict(directory=d,socket=address,key=(b'a'*32).hex(),run_id='run',build='build',source_hashes=[NATIVE_SHA],max_seconds=5,quota_bytes=64*1024*1024,port=0)
            cp=root/'config.json';cp.write_text(json.dumps(c))
            proc=subprocess.Popen([sys.executable,'-B','-m','capture2.writer','--config',str(cp)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                wait_for(lambda:Path(address).exists() or proc.poll() is not None)
                self.assertTrue(Path(address).exists(),proc.communicate(timeout=1)[1].decode() if proc.poll() is not None else 'START')
                p=CaptureProducer(address,identity(),b'a'*32,end_boot_ns=end,status_path=root/'transport-test.json')
                try:
                    for i in range(10000):self.assertTrue(p.offer('OBSERVED',{'index':i,'quote':str(i)*200}),p.last_error)
                    wait_for(lambda:p.sock.delivered==10000,4);p.close();p.sock.thread.join(3)
                    wait_for(lambda:(root/'final_health.json').exists(),7)
                    h=json.loads((root/'final_health.json').read_text())
                    rows=[json.loads(x)['event'] for x in gzip.decompress((root/'packets.jsonl.gz').read_bytes()).splitlines()]
                    self.assertEqual([r['sequence'] for r in rows],list(range(1,10001)))
                    self.assertEqual([r['body']['index'] for r in rows],list(range(10000)))
                    self.assertEqual(h['invalid'],0);self.assertEqual(h['sequence_gaps'],[]);self.assertFalse(h['producer_drop_observed'])
                    self.assertEqual(p.dropped,0);self.assertLessEqual(p.sock.high_water_bytes,p.sock.max_bytes)
                    print('WRITER_STRESS',json.dumps({'packets':h['packets'],'groups':h['groups'],'bytes':h['bytes'],'transport':p.sock.snapshot()}),flush=True)
                finally:p.close();p.sock.thread.join(3)
            finally:proc.terminate();proc.communicate(timeout=5)


if __name__=='__main__':unittest.main()
