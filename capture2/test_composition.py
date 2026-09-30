import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from capture2.install import main_tree,assemble_main,PROTECTED_SHA,NATIVE_SHA,ROOT
from capture2.writer import packet
from sprint_evidence.passive_capture import Producer,Identity,pack


class RemoveCapture(ast.NodeTransformer):
    def visit_ImportFrom(self,n):
        return None if n.module and n.module.startswith('capture2') else n
    def visit_Assign(self,n):
        if any(isinstance(t,ast.Name) and t.id=='_sprint_producer' for t in n.targets):return None
        return self.generic_visit(n)
    def visit_Expr(self,n):
        v=n.value
        if isinstance(v,ast.Call) and isinstance(v.func,ast.Attribute) and isinstance(v.func.value,ast.Name) and v.func.value.id in {'_sprint_producer','_sprint_sources'}:
            return None
        return self.generic_visit(n)


class CompositionTests(unittest.TestCase):
    def test_composed_native_tree_preserves_every_original_statement(self):
        raw=(ROOT/'bot_two_output_build_v4_13_profit_protection_shadow.py').read_bytes()
        composed=main_tree(raw)
        self.assertEqual(ast.dump(RemoveCapture().visit(composed)),ast.dump(ast.parse(raw)))

    def test_existing_information_and_cohort_hooks_retained_once(self):
        import btc15_information_native_offpath_candidate as original
        raw=(ROOT/'bot_two_output_build_v4_13_profit_protection_shadow.py').read_bytes()
        combined=original.instrument(main_tree(raw))
        baseline=original.instrument(ast.parse(raw))
        self.assertEqual(ast.dump(RemoveCapture().visit(combined)),ast.dump(baseline))

    def test_protected_assembly_preserves_original_strategy_ast(self):
        import btc15_information_install_v1 as original
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            left=original.assemble(Path(a));right=assemble_main(Path(b))
            name='BTC15_DASHBOARD_STATE_V2.py'
            self.assertEqual(hashlib.sha256((left/name).read_bytes()).hexdigest(),PROTECTED_SHA)
            self.assertEqual(ast.dump(ast.parse((left/name).read_bytes())),ast.dump(RemoveCapture().visit(ast.parse((right/name).read_bytes()))))
            self.assertIn('capture2/native_entry.py',(right/'btc15_run_with_rescue_v2_shadow_v1.py').read_text())

    def test_invalid_native_source_fails_before_execution(self):
        raw=(ROOT/'bot_two_output_build_v4_13_profit_protection_shadow.py').read_bytes()
        with self.assertRaises(ValueError):main_tree(raw+b'\n')

    def test_original_packet_authentication_binding_and_tamper(self):
        class Sink:
            def sendto(self,b,*a):self.raw=b;return len(b)
        sink=Sink();p=Producer('x',Identity('fixture','build',NATIVE_SHA,'run','domain','boot'),b'a'*32,sock=sink)
        c=dict(key=(b'a'*32).hex(),run_id='run',build='build',source_hashes=[NATIVE_SHA])
        p.native({'ticker':'A','now_ts':1})
        self.assertEqual(packet(sink.raw,c)['body']['ticker'],'A')
        bad=json.loads(sink.raw);bad['event']['body']['ticker']='B'
        with self.assertRaises(ValueError):packet(pack(bad),c)
        with self.assertRaises(ValueError):packet(sink.raw,dict(c,run_id='other'))

    def test_real_detached_writer_preserves_all_offered_packets(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sock=str(root/'events.sock')
            c=dict(directory=d,socket=sock,key=(b'a'*32).hex(),run_id='run',build='build',source_hashes=[NATIVE_SHA],max_seconds=2,quota_bytes=8*1024*1024,port=0)
            cp=root/'config.json';cp.write_text(json.dumps(c))
            proc=subprocess.Popen([sys.executable,'-B','-m','capture2.writer','--config',str(cp)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+5
                while not Path(sock).exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(Path(sock).exists(), proc.communicate(timeout=1)[1].decode() if proc.poll() is not None else 'WRITER_START_TIMEOUT')
                p=Producer(sock,Identity('fixture','build',NATIVE_SHA,'run','domain','boot'),b'a'*32)
                for i in range(500):
                    self.assertTrue(p.offer('NATIVE_CYCLE',{'ticker':'A','index':i}),p.last_error)
                    time.sleep(.001)
                p.close()
                deadline=time.monotonic()+5
                while not (root/'final_health.json').exists() and time.monotonic()<deadline:time.sleep(.01)
                health=json.loads((root/'final_health.json').read_text())
                rows=[json.loads(s) for s in gzip.decompress((root/'packets.jsonl.gz').read_bytes()).splitlines()]
                self.assertEqual(len(rows),500);self.assertEqual(health['packets'],500)
                self.assertFalse(health['producer_drop_observed']);self.assertEqual(health['invalid'],0)
                self.assertEqual([r['event']['body']['index'] for r in rows],list(range(500)))
            finally:
                proc.terminate();proc.communicate(timeout=5)


if __name__=='__main__':unittest.main()
