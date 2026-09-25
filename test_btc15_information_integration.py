"""Installed topology and resource boundary tests; synthetic sources only."""
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from btc15_information_install_v1 import ROOT, assemble, terminate_group
from btc15_information_service_v1 import HealthMirror, response, server_for, step, LocalIngress
from btc15_information_native_v1 import server_for as native_server
from btc15_information_v1 import FairAssessment, InformationPublisher, FIELDS, pack, unpack, validate
from test_btc15_information_v1 import Rig, provider
from test_btc15_isolated_decision_v2 import completed, fixture, OPEN
from completion_audit.isolated_decision_v2 import FrozenRuntime, stable


def module(path):
    spec=importlib.util.spec_from_file_location('installed_'+path.stem,path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj


class InstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.d=assemble(Path(cls.temp.name))
        cls.proxy=module(cls.d/'btc15_information_proxy_v1.py')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_original_html_survives_exactly_with_one_independent_panel(self):
        manifest=json.loads((self.d/'manifest.json').read_text())
        text=(self.d/'BTC_Kalshi_App_Live_v13.html').read_text()
        panel=(ROOT/'btc15_information_panel_v1.html').read_text()+'\n'
        self.assertEqual(text.count(panel),1)
        self.assertEqual(hashlib.sha256(text.replace(panel,'',1).encode()).hexdigest(),manifest['original_patched_dashboard_sha256'])
        self.assertEqual(text.count('id="v81-inline-scalp-script"'),1)

    def test_full_supervisor_chain_only_changes_child_constants(self):
        names=('btc15_run_full_validation_v1.py','btc15_run_with_rescue_v2_and_parity_v1.py',
               'btc15_run_with_rescue_v2_shadow_v1.py')
        for name in names:
            a=ast.parse((ROOT/name).read_text());b=ast.parse((self.d/name).read_text())
            def remove(tree):
                tree.body=[n for n in tree.body if not (isinstance(n,ast.Assign) and
                    any(isinstance(t,ast.Name) and t.id in {'CORE','BOT'} for t in n.targets))]
                return ast.dump(tree,include_attributes=False)
            self.assertEqual(remove(a),remove(b))
        import BTC15_INSTALL_LIVE_DASHBOARD_V13 as original
        import gzip,base64
        self.assertEqual((self.d/'BTC15_DASHBOARD_STATE_V2.py').read_bytes(),
                         gzip.decompress(base64.b64decode(original.PAYLOADS['BTC15_DASHBOARD_STATE_V2.py'])))

    def test_repeated_assembly_has_exact_manifest(self):
        original=(self.d/'manifest.json').read_bytes();assemble(self.d)
        # Python import may create a directory; only installed files are hashed.
        self.assertEqual((self.d/'manifest.json').read_bytes(),original)

    def test_all_original_wrappers_and_installed_dashboard_self_tests(self):
        env=dict(os.environ,PYTHONPATH=str(ROOT),BTC15_ISOLATED_CANARY_LOCAL_DATA='1')
        for name in ('BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py',
                     'btc15_run_full_validation_v1.py','btc15_run_with_rescue_v2_and_parity_v1.py',
                     'btc15_run_with_rescue_v2_shadow_v1.py'):
            result=subprocess.run([sys.executable,str(self.d/name),'--self-test'],cwd=ROOT,env=env,
                                  text=True,capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_public_proxy_rejects_unknown_fields_future_or_expired_values(self):
        from btc15_information_v1 import wait_view
        p=wait_view(100,'test')
        self.assertEqual(set(unpack(self.proxy.closed(pack(p),100))),set(FIELDS))
        with self.assertRaises(ValueError):self.proxy.closed(pack(dict(p,exit='EXIT')),100)
        for change in ({'checked_ts':101},{'expires_at':99},{'display_until':99},{'brti_source_ts':94}):
            v=dict(p,status='AVAILABLE',checked_ts=100,expires_at=105,display_until=101,brti_source_ts=98)
            v.update(change)
            with self.assertRaises(ValueError):self.proxy.closed(pack(v),100)

    def test_public_transport_charges_latency_without_extending_deadline(self):
        from btc15_information_v1 import wait_view
        v=dict(wait_view(100,'test'),status='AVAILABLE',expires_at=103,display_until=101,brti_source_ts=98)
        out=unpack(self.proxy.closed(pack(v),100.4))
        self.assertEqual(out['checked_ts'],100.4);self.assertEqual(out['display_until'],101)
        self.assertEqual(out['expires_at'],103)

    def test_unknown_routes_cannot_proxy_native_or_action_api(self):
        class Handler:
            def _send(self,*args):self.reply=args
        for path in ('/information/input','/information/health','/information-input',
                     '/information?entry=1','/information/frame/latest','/information/../dashboard_state.json'):
            h=Handler();h.path=path
            result=self.proxy.serve(h)
            if result:self.assertEqual(h.reply[0],404)
            else:self.assertEqual(path,'/information-input') # Original dashboard returns 404.

    def test_repeated_clients_are_bounded_before_local_worker(self):
        class Handler:
            path='/information'
            def _send(self,*args):self.reply=args
        calls=[]
        def slow(*args,**kwargs):calls.append(1);time.sleep(.15);raise OSError('offline')
        self.proxy.NEXT=0
        with patch.object(self.proxy,'urlopen',slow),ThreadPoolExecutor(max_workers=30) as pool:
            handlers=[Handler() for _ in range(100)]
            list(pool.map(self.proxy.serve,handlers))
        self.assertLessEqual(len(calls),4)
        self.assertTrue(all(h.reply[0] in (429,503) for h in handlers))

    def test_worker_resource_limits_are_child_only_and_model_loads(self):
        before=os.sched_getaffinity(0)
        code='''from btc15_information_worker_v1 import configure
configure()
import os,resource,json
from btc15_information_v1 import InformationPublisher
p=InformationPublisher()
print(json.dumps(dict(affinity=len(os.sched_getaffinity(0)),nice=os.getpriority(os.PRIO_PROCESS,0),
as_limit=resource.getrlimit(resource.RLIMIT_AS)[0],rss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)))
'''
        out=json.loads(subprocess.check_output([sys.executable,'-c',code],cwd=ROOT,text=True,timeout=30))
        self.assertEqual(out['affinity'],1);self.assertGreaterEqual(out['nice'],10)
        self.assertEqual(out['as_limit'],2*1024**3);self.assertLess(out['rss_kb'],512*1024)
        self.assertEqual(os.sched_getaffinity(0),before)

    def test_process_group_cleanup_includes_orphan_descendants(self):
        with tempfile.TemporaryDirectory() as d:
            pidfile=Path(d)/'pid'
            code='import subprocess,sys,time; p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);open(sys.argv[1],"w").write(str(p.pid));time.sleep(60)'
            proc=subprocess.Popen([sys.executable,'-c',code,str(pidfile)],start_new_session=True)
            try:
                for _ in range(100):
                    if pidfile.exists():break
                    time.sleep(.01)
                pid=int(pidfile.read_text());terminate_group(proc,.5)
                status=Path(f'/proc/{pid}/stat')
                self.assertTrue(not status.exists() or status.read_text().split()[2]=='Z')
            finally:
                if proc.poll() is None:terminate_group(proc,.1)


class ConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.initial=FrozenRuntime(completed());cls.fair=FairAssessment()

    def test_thousand_display_reads_do_not_poll_or_extend_native_health(self):
        rig=Rig(self.initial);pub=InformationPublisher(self.fair);rig.publish(pub)
        mirror=HealthMirror(rig.export)
        with patch.object(rig.export,'health',wraps=rig.export.health) as read:
            mirror.refresh();original=mirror.raw
            for _ in range(1000):mirror.health()
            self.assertEqual(read.call_count,1);self.assertEqual(mirror.raw,original)
        self.assertEqual(unpack(response(pub,mirror,'/information',lambda:OPEN+301.01)[1])['status'],'WAIT')

    def test_mirror_outage_recovery_and_owner_restart_fail_closed(self):
        rig=Rig(self.initial);pub=InformationPublisher(self.fair);rig.publish(pub)
        mirror=HealthMirror(rig.export);mirror.refresh()
        rig.provider.book.valid=False;mirror.refresh()
        self.assertEqual(unpack(response(pub,mirror,'/information',lambda:rig.at)[1])['status'],'WAIT')
        rig.sources(301,epoch='new-owner');mirror.refresh()
        self.assertEqual(unpack(response(pub,mirror,'/information',lambda:rig.at)[1])['status'],'WAIT')
        self.assertTrue(rig.publish(pub))
        self.assertEqual(unpack(response(pub,mirror,'/information',lambda:rig.at)[1])['status'],'AVAILABLE')

    def test_slow_inference_source_expiry_does_not_block_reads_or_mutate_native(self):
        rig=Rig(self.initial);entered=threading.Event();release=threading.Event()
        fair=self.fair
        class Slow:
            def evaluate(self,f,q):entered.set();release.wait(5);return fair.evaluate(f,q)
        pub=InformationPublisher(Slow());before=stable(rig.runtime.snapshot())
        thread=threading.Thread(target=rig.publish,args=(pub,));thread.start();self.assertTrue(entered.wait(2))
        start=time.monotonic()
        self.assertEqual(rig.read(pub)['status'],'WAIT');self.assertLess(time.monotonic()-start,.5)
        rig.at=OPEN+306;release.set();thread.join(5)
        self.assertFalse(thread.is_alive());self.assertIsNone(pub.latest)
        self.assertEqual(stable(rig.runtime.snapshot()),before)

    def test_concurrent_source_publication_retains_exact_bytes_not_latest(self):
        rig=Rig(self.initial);raw=rig.export.capture();saved=deepcopy(unpack(raw));ready=threading.Event()
        def replace():
            for i in range(30):
                inp=fixture(300+i*.005,ask=.2+i*.01)
                with rig.provider.lock:
                    other=provider(inp,30000+i*2)
                    rig.provider.book=other.book;rig.provider.events=other.events
            ready.set()
        t=threading.Thread(target=replace);t.start();ready.wait(2);t.join()
        validate(raw,rig.export.health(),rig.at)
        self.assertEqual(unpack(raw),saved)
        self.assertNotEqual(unpack(rig.export.capture())['proof']['identity'],saved['proof']['identity'])

    def test_retention_bound_under_concurrent_readers_and_eviction(self):
        rig=Rig(self.initial);pub=InformationPublisher(self.fair,retention=2);rig.publish(pub);first=pub.latest
        before=stable(rig.runtime.snapshot())
        with ThreadPoolExecutor(max_workers=4) as pool:
            reads=[pool.submit(pub.read,rig.export.health(),rig.at,first) for _ in range(12)]
            for i in range(1,5):rig.sources(300+i*.1);rig.publish(pub)
            for task in reads:
                out=task.result();self.assertIn(out['frame_id'],(None,first))
        self.assertEqual(len(pub.frames),2)
        self.assertEqual(pub.read(rig.export.health(),rig.at,first)['status'],'WAIT')
        # Only source owner receipts change; information never mutates strategy.
        after=rig.runtime.snapshot();old=self.initial.fork()
        for key in ('history','_early_hist','_unified_hist','_profit_shadow_pending','_true_scalp_last_signal'):
            self.assertEqual(stable(after[key]),dict(before)[key])

    def test_duplicate_worker_cannot_bind_same_information_authority(self):
        rig=Rig(self.initial);pub=InformationPublisher(self.fair)
        server=server_for(pub,rig.export)
        try:
            with self.assertRaises(OSError):server_for(pub,rig.export,server.server_port)
        finally:server.server_close()


if __name__=='__main__':unittest.main()
