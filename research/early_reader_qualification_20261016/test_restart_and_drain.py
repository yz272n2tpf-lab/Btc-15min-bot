"""Process-kill and shutdown tests; no production process is touched."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from candidates.early_recording_20261012.archive import read_archive
from ops.live_recording.capture import Capture
from ops.live_recording.policy import BASES,SERVICES,VOLUMES,file_sha
from ops.recording_workflow.evidence import streaming_window_inventory
from research.main_closeout_incremental_20261015.test_recorder_burst_batch_research import archive,writer_for
from research.early_reader_qualification_20261016.test_main_reader import fixture


def config(root):
    return dict(schema='BTC15_LIVE_CAMPAIGN_V1',root=str(root),run_id='isolated',
                profile='preflight',duration_seconds=1200,capture_enabled=True,
                signal_only=True,orders=False,roles={r:dict(service=SERVICES[r],volume=VOLUMES[r],
                base_release=BASES[r],build='0'*40) for r in ('main','v81')})


class RestartAndDrainTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_closing_backlog_keeps_batched_fsync(self):
        a=archive(self.root/'capture');gate=threading.Event();entered=threading.Event()
        original=a.observe
        def blocked(kind,fields):
            entered.set()
            if not gate.wait(5):raise RuntimeError('TEST_GATE_TIMEOUT')
            original(kind,fields)
        a.observe=blocked;w=writer_for(self.root,a)
        self.assertTrue(w.submit_observation('RECORDING_HEALTH',n=0));self.assertTrue(entered.wait(2))
        for i in range(1,1024):self.assertTrue(w.submit_observation('RECORDING_HEALTH',n=i))
        self.assertFalse(w.close(timeout=0))
        gate.set();self.assertTrue(w.close(timeout=10))
        s=w.status();self.assertEqual(s['losses'],{})
        self.assertLess(s['durable_batch']['committed_batches'],12)
        records=read_archive(self.root/'capture')
        self.assertEqual(len(records['records']),1026);self.assertEqual(records['gaps'],[])

    def test_late_seal_preserves_failure_and_adds_no_false_closed_loss(self):
        c=Capture(config(self.root/'campaign'),'main',offline=True)
        c.stop_event.set()  # The test owns shutdown timing, not the .5s watchdog.
        entered=threading.Event();release=threading.Event();original=c.archive.observe
        def blocked(kind,fields):
            entered.set()
            if not release.wait(5):raise RuntimeError('TEST_GATE_TIMEOUT')
            original(kind,fields)
        c.archive.observe=blocked
        c.emit('RECORDING_HEALTH',test=True);self.assertTrue(entered.wait(2))
        c.failure='RECORDER_LOSS_OR_FAILURE'
        first=c.stop('RECORDER_LOSS_OR_FAILURE',timeout=0)
        self.assertFalse(first['stopped']);release.set();c.late_sealer.join(5)
        self.assertFalse(c.late_sealer.is_alive())
        end=json.loads((c.root/'terminal-status.json').read_bytes())
        seal=json.loads((c.root/'seal.json').read_bytes())
        self.assertEqual(end['failure'],'RECORDER_LOSS_OR_FAILURE')
        self.assertTrue(end['drain_timed_out']);self.assertEqual(end['reason'],'RECORDER_LOSS_OR_FAILURE')
        self.assertEqual(seal['status'],'INCOMPLETE')
        self.assertNotIn('CLOSED',c.writer.status()['losses'])
        records=read_archive(c.root/'source')['records']
        self.assertEqual(sum(x['kind']=='RECORDING_BOUNDARY' for x in records),1)
        before=file_sha(c.root/'seal.json');c.stop();self.assertEqual(file_sha(c.root/'seal.json'),before)

    def test_graceful_seal_persists_and_restart_refuses_existing_campaign(self):
        cfg=config(self.root/'campaign');c=Capture(cfg,'main',offline=True)
        self.assertTrue(c.emit('RECORDING_HEALTH',test=True))
        status=c.stop(timeout=10);self.assertEqual(status['status'],'SEALED')
        original={str(p):file_sha(p) for p in c.root.rglob('*') if p.is_file()}
        with self.assertRaises(FileExistsError):Capture(cfg,'main',offline=True)
        self.assertEqual(original,{str(p):file_sha(p) for p in c.root.rglob('*') if p.is_file()})

    def test_sigkill_never_creates_false_seal_or_overwrites_old_capture(self):
        cfg=config(self.root/'killed')
        code='''import json,os,signal,sys,time
from ops.live_recording.capture import Capture
c=Capture(json.loads(sys.argv[1]),'main',offline=True)
c.emit('RECORDING_HEALTH',test=True)
assert c.writer.close(5)
os.kill(os.getpid(),signal.SIGKILL)
'''
        p=subprocess.run([sys.executable,'-c',code,json.dumps(cfg)],capture_output=True,timeout=10)
        self.assertEqual(p.returncode,-9)
        root=Path(cfg['root'])/'main'
        self.assertFalse((root/'seal.json').exists())
        prior={str(p):file_sha(p) for p in root.rglob('*') if p.is_file()}
        with self.assertRaises(FileExistsError):Capture(cfg,'main',offline=True)
        self.assertEqual(prior,{str(p):file_sha(p) for p in root.rglob('*') if p.is_file()})

    def test_reader_process_crash_no_verdict_replay_from_original_is_identical(self):
        src=self.root/'source';src.mkdir();fixture(src)
        before={str(p):file_sha(p) for p in src.rglob('*.gz')}
        code='''import os,sys
from ops.recording_workflow.evidence import streaming_window_inventory
from ops.live_recording.quote_window_handoff_research import QuoteWindowHandoff
class Crash(QuoteWindowHandoff):
 def accept(self,role,record):
  if record['sequence']==10:os._exit(77)
  return super().accept(role,record)
streaming_window_inventory(sys.argv[1],sys.argv[2],max_window_records=1,quote_handoff=Crash())
'''
        p=subprocess.run([sys.executable,'-c',code,str(src),str(self.root/'interrupted')],capture_output=True,timeout=10)
        self.assertEqual(p.returncode,77,p.stderr.decode())
        self.assertFalse((self.root/'interrupted/window_inventory_manifest.json').exists())
        partial=file_sha(self.root/'interrupted/windows.jsonl')
        from ops.live_recording.quote_window_handoff_research import QuoteWindowHandoff
        baseline=streaming_window_inventory(src,self.root/'baseline',max_window_records=1,quote_handoff=QuoteWindowHandoff())
        replay=streaming_window_inventory(src,self.root/'replayed',max_window_records=1,quote_handoff=QuoteWindowHandoff())
        self.assertEqual(baseline,replay)
        self.assertEqual(partial,file_sha(self.root/'interrupted/windows.jsonl'))
        self.assertEqual(before,{str(p):file_sha(p) for p in src.rglob('*.gz')})
        self.assertFalse(replay['quote_state_handoff']['quote_state_restart_checkpoint_verified'])


if __name__=='__main__':unittest.main()
