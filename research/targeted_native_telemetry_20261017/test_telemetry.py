"""Small, explicitly synthetic call/equivalence fixtures; no native capture."""
import copy
import json
from pathlib import Path
import tempfile
import time
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from btc15_information_service_v1 import DurablePublisher
from btc15_information_v1 import Unavailable
from ops.live_recording.telemetry import publisher_class,check_outcome,OUTCOME_COUNT,OUTCOME_TOTAL
from ops.live_recording.capture import Capture,Gate
from ops.live_recording.policy import canonical,sha
from candidates.early_recording_20261012.archive import read_archive
from research.early_reader_qualification_20261016.test_restart_and_drain import config
from research.main_closeout_incremental_20261015.test_recorder_burst_batch_research import archive,writer_for
from test_btc15_information_v1 import Rig,FrozenRuntime,completed

VALUES=dict(probability_up=.6,probability_down=.4,model_flip_probability=.4,
 probability_up_change_since_native=.01,preferred_side='UP',brti_side='UP',
 brti_agrees=True,range5=10.,dist_over_range5=.5)
def outcome(v):return json.loads(b''.join(v['outcome_%02d'%i] for i in range(v['outcome_parts'])))
class Sink:
 def __init__(self):self.active=True;self.rows=[];self.gaps=[]
 def submit_observation(self,kind,**fields):self.rows.append((kind,fields));return True
 def gap(self,reason):self.gaps.append(reason);self.active=False

class TelemetryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  rig=Rig(FrozenRuntime(completed()));cls.raw=rig.export.capture();cls.health=rig.export.health();cls.at=rig.at
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
 def pair(self,mode='success',repeat=False):
  results=[]
  for traced in (False,True):
   calls=[];count=dict(health=0,clock=0);sink=Sink()
   def health():
    calls.append('health');count['health']+=1
    if mode=='health_exception':raise Unavailable('HEALTH_UNAVAILABLE')
    h=copy.deepcopy(self.health)
    if mode=='health_reject':h['ready']=False
    if mode=='post_health_reject' and count['health']==2:h['ready']=False
    return h
   def clock():
    calls.append('clock');count['clock']+=1
    if mode=='clock_exception':raise RuntimeError('clock exploded')
    return self.at+(6 if mode=='post_stale' and count['clock']==2 else 0)
   def evaluate(f,q):
    calls.append('evaluate')
    if mode=='evaluation_exception':raise RuntimeError('evaluation exploded')
    if mode=='evaluation_reject':raise Unavailable('FEATURE_SUPPORT_UNAVAILABLE')
    return {} if mode=='schema_reject' else dict(VALUES)
   cls=publisher_class(DurablePublisher,sink) if traced else DurablePublisher
   p=cls(SimpleNamespace(evaluate=evaluate),journal_path=self.root/('observed' if traced else 'original'))
   outputs=[]
   for _ in range(2 if repeat else 1):
    try:
     if mode=='journal_exception':
      with patch('btc15_information_service_v1.os.fsync',side_effect=OSError('journal failure')):value=p.offer(self.raw,health,clock)
     else:value=p.offer(self.raw,health,clock)
     outputs.append(('return',value))
    except Exception as e:outputs.append(('exception',type(e).__name__,e.args))
   results.append(dict(calls=calls,outputs=outputs,frames=list(p.frames.items()),latest=p.latest,key=p.key,reason=p.reason,
                       journal=p.journal_path.read_bytes() if p.journal_path.exists() else b'',sink=sink,publisher=p))
  for key in ('calls','outputs','frames','latest','key','reason','journal'):self.assertEqual(results[0][key],results[1][key],(mode,key))
  records=[v for k,v in results[1]['sink'].rows if k=='INFORMATION_INPUT']
  self.assertEqual(len(records),2 if repeat else 1)
  for v in records:
   check_outcome(outcome(v),sha(v['raw']),v['published'],v['frame_id'])
  return results[1],list(map(outcome,records))
 def test_success_exact_original_bytes_and_call_order(self):
  r,t=self.pair();t=t[0]
  self.assertEqual(r['calls'],['health','clock','evaluate','health','clock'])
  self.assertEqual([x['value'] for x in t['health']],[self.health,self.health])
  self.assertEqual([x['value'] for x in t['clocks']],[self.at,self.at])
  self.assertEqual(t['evaluation_calls'],1);self.assertEqual(t['stage'],'DURABLE_PUBLISHED')
  self.assertEqual(t['native_frame_id'],r['latest']);self.assertIsNone(t['prior_native_frame_id'])
 def test_no_progress_preserves_false_and_prior_publication_identity(self):
  r,t=self.pair(repeat=True)
  self.assertEqual(r['outputs'],[('return',True),('return',False)])
  self.assertEqual(t[1]['outcome'],'NO_PROGRESS');self.assertEqual(t[1]['evaluation_calls'],0)
  self.assertEqual(t[1]['prior_native_frame_id'],t[0]['native_frame_id'])
  self.assertEqual(t[1]['prior_source_key'],json.loads(canonical(r['key'])))
  self.assertIn(('INFORMATION_FAILURE',{'reason':'INPUT_NOT_PUBLISHED'}),r['sink'].rows)
 def test_actual_rejection_reasons_and_stages(self):
  expected={'health_exception':('HEALTH_UNAVAILABLE','PRE_HEALTH'),
            'health_reject':('SOURCE_HEALTH_OR_OWNER_CHANGED','PRE_VALIDATION'),
            'post_health_reject':('SOURCE_HEALTH_OR_OWNER_CHANGED','POST_VALIDATION'),
            'post_stale':('BRTI_STALE_OR_NONCAUSAL','POST_VALIDATION'),
            'evaluation_reject':('FEATURE_SUPPORT_UNAVAILABLE','EVALUATION'),
            'schema_reject':('ASSESSMENT_SCHEMA','ASSESSMENT_SCHEMA')}
  for mode,(reason,stage) in expected.items():
   with self.subTest(mode=mode):
    # Separate paths keep each native journal isolated within this test.
    old=self.root;self.root=old/mode;self.root.mkdir()
    r,t=self.pair(mode);self.root=old;t=t[0]
    self.assertEqual(t['native_rejection_reason'],reason);self.assertEqual(t['stage'],stage)
    self.assertEqual(t['outcome'],'REJECTED');self.assertIs(t['return_value'],False)
 def test_exceptions_are_original_and_journal_failure_retains_native_frame(self):
  for mode,stage in [('clock_exception','PRE_CLOCK'),('evaluation_exception','EVALUATION'),('journal_exception','DURABLE_JOURNAL')]:
   with self.subTest(mode=mode):
    old=self.root;self.root=old/mode;self.root.mkdir();r,t=self.pair(mode);self.root=old;t=t[0]
    self.assertEqual(t['stage'],stage);self.assertEqual(t['outcome'],'EXCEPTION')
    self.assertIsNone(t['return_value']);self.assertFalse(t['published'])
    self.assertEqual(t['exception']['args'],list(r['outputs'][0][2]))
    if mode=='journal_exception':self.assertIsNotNone(t['native_frame_id'])
 def test_snapshot_does_not_alias_health_mutation(self):
  sink=Sink();h=copy.deepcopy(self.health);n=0
  def health():return h
  def evaluate(f,q):h['ready']=False;return dict(VALUES)
  p=publisher_class(DurablePublisher,sink)(SimpleNamespace(evaluate=evaluate),journal_path=self.root/'native')
  self.assertFalse(p.offer(self.raw,health,lambda:self.at))
  t=outcome(sink.rows[0][1])
  self.assertTrue(t['health'][0]['value']['ready']);self.assertFalse(t['health'][1]['value']['ready'])
 def test_trace_stays_with_input_under_native_worker_serialization(self):
  sink=Sink();entered=threading.Event();release=threading.Event()
  def evaluate(f,q):entered.set();self.assertTrue(release.wait(2));return dict(VALUES)
  p=publisher_class(DurablePublisher,sink)(SimpleNamespace(evaluate=evaluate),journal_path=self.root/'native')
  result=[]
  def offer():result.append(p.offer(self.raw,lambda:copy.deepcopy(self.health),lambda:self.at))
  a=threading.Thread(target=offer);b=threading.Thread(target=offer)
  a.start();self.assertTrue(entered.wait(2));b.start();release.set();a.join(3);b.join(3)
  self.assertFalse(a.is_alive() or b.is_alive());self.assertEqual(sorted(result),[False,True])
  traces=[outcome(v) for k,v in sink.rows if k=='INFORMATION_INPUT']
  yes=next(t for t in traces if t['return_value']);no=next(t for t in traces if t['return_value'] is False)
  self.assertEqual(no['prior_native_frame_id'],yes['native_frame_id']);self.assertEqual(no['evaluation_calls'],0)
 def test_bounds_close_capture_without_changing_native_return(self):
  for bound in ('count','total'):
   sink=Sink();p=publisher_class(DurablePublisher,sink)(SimpleNamespace(evaluate=lambda f,q:dict(VALUES)),journal_path=self.root/bound)
   setattr(p.evidence_archive,bound,OUTCOME_COUNT if bound=='count' else OUTCOME_TOTAL)
   self.assertTrue(p.offer(self.raw,lambda:copy.deepcopy(self.health),lambda:self.at))
   self.assertFalse(sink.active);self.assertEqual(sink.gaps,['CAPTURE_ERROR'])
   self.assertFalse(sink.rows)
 def test_reader_refuses_wrong_input_and_frame_telemetry_links(self):
  r,t=self.pair();t=t[0]
  from ops.live_recording.reader import CampaignVerifier
  v=CampaignVerifier.__new__(CampaignVerifier)
  for field,wrong in [('input_sha256','0'*64),('native_frame_id','0'*64)]:
   changed=dict(t,**{field:wrong})
   row=dict(kind='INFORMATION_INPUT',session='test',sequence=1,_part=0,
            payload=dict(publication_outcome=changed,input_sha256=sha(self.raw),published=True,frame_id=r['latest']))
   with self.assertRaisesRegex(ValueError,'PUBLICATION_.*LINK'):v.record(row)
 def test_outcome_charge_batch_drain_and_seal_are_exact(self):
  c=config(self.root/'capture');c['roles']['information']=dict(c['roles']['main'])
  cap=Capture(c,'information',offline=True);self.addCleanup(cap.stop)
  p=publisher_class(DurablePublisher,cap.gate)(SimpleNamespace(evaluate=lambda f,q:dict(VALUES)),journal_path=self.root/'native')
  self.assertTrue(p.offer(self.raw,lambda:copy.deepcopy(self.health),lambda:self.at))
  self.assertFalse(p.offer(self.raw,lambda:copy.deepcopy(self.health),lambda:self.at))
  s=cap.stop();self.assertTrue(s['writer']['terminal_accounting_complete'])
  rows=read_archive(cap.root/'information')['records'];ins=[x['payload'] for x in rows if x['kind']=='INFORMATION_INPUT']
  self.assertEqual(len(ins),2)
  for v in ins:check_outcome(v['publication_outcome'],v['input_sha256'],v['published'],v['frame_id'])
  self.assertEqual(len([r for r in rows if r['kind']=='INFORMATION_FAILURE']),1)
 def test_quote_overrun_identity_cpu_wall_and_guard(self):
  sink=Sink();sink.gap=lambda why:None;g=Gate(sink);g.local.outcome='ADMITTED'
  event=dict(recorder_hook_id=7,epoch='original-epoch',ticker='original-ticker',received_at=100.,role='main',session='s')
  with patch('ops.live_recording.capture.time.perf_counter_ns',return_value=6000001),patch('ops.live_recording.capture.time.thread_time_ns',return_value=1001):
   g.overhead(0,'QUOTE_ACCEPT',1,event,True)
  self.assertFalse(g.active);self.assertEqual(g.reason,'HOOK_OVER_5MS:QUOTE_ACCEPT')
  t=g.overruns[0];self.assertEqual(t['recorder_hook_id'],7)
  self.assertEqual((t['wall_ns'],t['thread_cpu_ns'],t['off_cpu_ns']),(6000001,1000,5999001))
  self.assertEqual(t['admission'],'ADMITTED')
 def test_queue_mutex_rejection_remains_loss_and_exact_admission_outcome(self):
  a=archive(self.root/'quote');w=writer_for(self.root,a);g=Gate(w)
  with w.queue.mutex:
   self.assertFalse(g.submit_observation('QUOTE_RECEIVE',raw='{}',ticker='t',epoch='e',received_at=1.))
  self.assertEqual(g.local.outcome,'QUEUE_MUTEX_BUSY');self.assertFalse(g.active)
  self.assertEqual(w.status()['losses']['ADMISSION_BUSY'],1);w.close(timeout=3)
 def test_overrun_storage_bound_and_incomplete_hook_drain(self):
  sink=Sink();g=Gate(sink);g.local.outcome='REJECTED'
  for n in range(9):
   with patch('ops.live_recording.capture.time.perf_counter_ns',return_value=100),patch('ops.live_recording.capture.time.thread_time_ns',return_value=100):
    g.overhead(0,'QUOTE_RECEIVE',0,dict(recorder_hook_id=n),False)
  self.assertEqual(len(g.overruns),8);self.assertEqual(g.overrun_overflow,1);self.assertFalse(g.active)
  cap=Capture(config(self.root/'capture'),'main',offline=True);cap.gate.inflight.add(1)
  s=cap.stop();self.assertEqual(s['status'],'INCOMPLETE');self.assertEqual(s['failure'],'HOOK_DRAIN_TIMEOUT')
 def test_quote_event_id_survives_archive_and_overrun_is_durable(self):
  cap=Capture(config(self.root/'capture'),'main',offline=True);self.addCleanup(cap.stop)
  original=cap.observer.emit
  # Delay inside the measured original admission, not the native quote owner.
  submit=cap.gate.submit_observation
  def delayed(*a,**k):r=submit(*a,**k);time.sleep(.007);return r
  cap.gate.submit_observation=delayed
  cap.observer.quote_accept('{}','t','e',100.,100.01)
  s=cap.stop();self.assertEqual(s['status'],'INCOMPLETE');self.assertEqual(len(s['hook_overruns']),1)
  self.assertTrue(s['writer']['terminal_accounting_complete'])
  rows=read_archive(cap.root/'source')['records']
  event=next(r['payload'] for r in rows if r['kind']=='QUOTE_ACCEPT')
  sample=next(r['payload']['samples'][0] for r in rows if r['kind']=='RECORDING_HEALTH' and r['payload'].get('schema')=='BTC15_HOOK_OVERRUN_V1')
  self.assertEqual(sample['recorder_hook_id'],event['recorder_hook_id'])
  self.assertEqual(sample['received_at'],event['received_at']);self.assertEqual(sample['accepted_at'],event['accepted_at'])

if __name__=='__main__':unittest.main()
