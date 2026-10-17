"""128 small synthetic calls; measures instrumentation, not native inference."""
import copy,json,statistics,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from research.targeted_native_telemetry_20261017.test_telemetry import TelemetryTests,VALUES,Sink,outcome
from ops.live_recording.telemetry import publisher_class
from ops.live_recording.capture import Capture
from ops.live_recording.policy import canonical
from btc15_information_service_v1 import DurablePublisher
from research.early_reader_qualification_20261016.test_restart_and_drain import config

def stats(ns):
 x=sorted(ns);return dict(calls=len(x),median_ns=statistics.median(x),p99_ns=x[int(.99*(len(x)-1))],max_ns=max(x))
TelemetryTests.setUpClass();t=TelemetryTests
result=dict(workload='128 SYNTHETIC INPUTS; STUB EVALUATOR/JOURNAL; NO NATIVE PERFORMANCE CLAIM',publication={})
with tempfile.TemporaryDirectory() as td:
 root=Path(td)
 for observed in (False,True):
  sink=Sink();counts=dict(health=0,clock=0,evaluate=0,journal=0)
  def health():counts['health']+=1;return copy.deepcopy(t.health)
  def clock():counts['clock']+=1;return t.at
  def evaluate(f,q):counts['evaluate']+=1;return dict(VALUES)
  def append(raw):counts['journal']+=1
  cls=publisher_class(DurablePublisher,sink) if observed else DurablePublisher
  p=cls(SimpleNamespace(evaluate=evaluate),journal_path=root/str(observed));p.compressed_journal=SimpleNamespace(append=append)
  times=[]
  for i in range(128):
   f=json.loads(t.raw);f['brti']['source']+=i*.001;raw=canonical(f)
   started=time.perf_counter_ns();ok=p.offer(raw,health,clock);times.append(time.perf_counter_ns()-started);assert ok
  assert counts==dict(health=256,clock=256,evaluate=128,journal=128)
  v=dict(stats(times),native_calls=counts)
  if observed:v['max_outcome_bytes']=max(len(canonical(outcome(f))) for k,f in sink.rows if k=='INFORMATION_INPUT')
  result['publication']['observed' if observed else 'original']=v
 cap=Capture(config(root/'capture'),'main',offline=True)
 def admitted(*args,**kwargs):cap.gate.local.outcome='ADMITTED';return True
 cap.gate.submit_observation=admitted
 times=[]
 for i in range(128):
  start=time.perf_counter_ns();cap.observer.quote_accept('{}','synthetic-ticker','synthetic-epoch',100+i*.01,100+i*.01);times.append(time.perf_counter_ns()-start)
 result['quote_wrapper_without_queue_io']=dict(stats(times),guard_failure=cap.gate.reason)
 cap.stop()
Path('research/targeted_native_telemetry_20261017/overhead.json').write_bytes(canonical(result));print(json.dumps(result,indent=2))
