"""New current-release producer/stop/SSH protocol boundary checks."""
import ast,base64,copy,json,os,sqlite3,subprocess,sys,tempfile,threading,time,types,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
from .test_integration import config,envelopes,fixture,LocalTransport,BASE
from .capture import Capture
from .adapters import Adapters,bind_journal,bind_outcomes
from .policy import canonical,sha
from .remote import finish as remote_finish,object_path
from .finish import SSH

class ProducerSeams(unittest.TestCase):
 def test_admission_timeout_refuses_seal_until_gate_quiescent(self):
  with tempfile.TemporaryDirectory() as d:
   c=Capture(config(Path(d)/'run'),'main',offline=True);c.gate.lock.acquire()
   try:c.stop(timeout=.1);self.assertFalse((c.root/'seal.json').exists())
   finally:c.gate.lock.release()
   c.admission_recovery.join(3);self.assertFalse(c.admission_recovery.is_alive());self.assertEqual(json.loads((c.root/'seal.json').read_bytes())['status'],'INCOMPLETE')
 def test_non_json_http_keeps_original_bytes_and_owner_exceptions(self):
  with tempfile.TemporaryDirectory() as d:
   c=Capture(config(Path(d)/'run'),'main',offline=True);a=Adapters(c);r=types.SimpleNamespace(content=b'\xff<html>upstream failed',status_code=503)
   try:
    self.assertIs(a.http_get(lambda *a,**k:r,'https://external-api.kalshi.com/trade-api/v2/markets/T'),r)
    with self.assertRaisesRegex(RuntimeError,'original'):
     a.brti(lambda:(_ for _ in ()).throw(RuntimeError('original')))
   finally:c.stop()
   rows=envelopes(c.root);p=next(x['payload'] for x in rows if x['kind']=='ORIGINAL_RESPONSE');self.assertEqual(base64.b64decode(p['raw_base64']),r.content);self.assertFalse(c.writer.archive_failed);self.assertTrue(any(x['kind']=='SOURCE_GAP' for x in rows))
 def test_original_http_bytes_and_same_response(self):
  with tempfile.TemporaryDirectory() as d:
   c=Capture(config(Path(d)/'run'),'main',offline=True);a=Adapters(c);response=types.SimpleNamespace(content=b'{ "price" : "100000", "time" : "2026-10-13T12:00:00Z" }',status_code=200)
   try:self.assertIs(a.http_get(lambda *a,**k:response,'https://api.exchange.coinbase.com/products/BTC-USD/ticker'),response)
   finally:c.stop()
   row=next(r['payload'] for r in envelopes(c.root) if r['kind']=='ORIGINAL_RESPONSE');self.assertEqual(base64.b64decode(row['raw_base64']),response.content);self.assertEqual(row['sha256'],sha(response.content));self.assertEqual(row['receipt_basis'],'HTTP_GET_RETURN_BEFORE_NATIVE_DECODE')
 def test_real_v81_snapshot_keeps_original_row_and_clock(self):
  from btc15_v81_qualified_inputs_v1 import QualifiedInputs
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'BTC15_USE_SHARED_BRTI':'1'}):
   c=Capture(config(Path(d)/'run'),'v81',offline=True);a=Adapters(c);now=time.time();opened=int(now//900)*900;closed=opened+900
   ticker='KXBTC15M-'+datetime.fromtimestamp(closed,timezone.utc).astimezone(ZoneInfo('America/New_York')).strftime('%y%b%d%H%M-%M').upper()
   q=dict(ticker=ticker,epoch='wire-original',market_id='market-original',sid=4,sequence=72,source_ts_ms=int((now-.1)*1000),validated_at_ms=int(now*1000),transport='timestamped_contiguous_ws',up_bid=.4,up_ask=.41,down_bid=.59,down_ask=.6)
   brti=dict(value=100001.,source_ts_ms=int((now-.1)*1000),owner_epoch='brti-original',sequence=88,status='PRIMARY_OK',clean_for_qualification=True)
   body=dict(price='100000.5',time=datetime.fromtimestamp(now-.1,timezone.utc).isoformat())
   response=types.SimpleNamespace(content=canonical(body),status_code=200,raise_for_status=lambda:None,json=lambda:body)
   get=lambda *a,**k:response
   market=dict(ticker=ticker,open_time=datetime.fromtimestamp(opened,timezone.utc).isoformat(),close_time=datetime.fromtimestamp(closed,timezone.utc).isoformat())
   pool=types.SimpleNamespace(providers=[],factory=lambda:None,frame=lambda *a:q)
   owner=QualifiedInputs(lambda:market,lambda x:100000,get,'https://api.exchange.coinbase.com/products/BTC-USD/ticker',provider=pool,brti_read=lambda:brti)
   ns=dict(_qualified_inputs=owner,requests=types.SimpleNamespace(get=get))
   try:
    a.prepare_v81(lambda ns,p:None,ns,pool);row=owner.snapshot();self.assertIs(row['input_provenance']['quote'],q);self.assertEqual(row['input_provenance']['brti']['sequence'],88)
   finally:c.stop()
   captured=next(json.loads(r['payload']['raw']) for r in envelopes(c.root) if r['kind']=='V81_INPUT');self.assertEqual(captured,row)
 def test_exact_admin_commit_and_queue_preserved(self):
  from btc15_v2_product.admin import Admin
  from btc15_v2_product.journal import ORIGINAL_JOURNAL
  old=Admin.run;commit=ORIGINAL_JOURNAL.commit
  with tempfile.TemporaryDirectory() as d:
   c=Capture(config(Path(d)/'run'),'main',offline=True);admin=None
   try:
    bind_journal(c);admin=Admin(Path(d)/'owner','main');q=admin.queue
    record=dict(schema='BTC15_NATIVE_ATTEMPT_R1',lane='main',attempt_id='native:1',stages=[],outcome='NATIVE_EXCEPTION',signal_only=True,orders=False)
    admin.offer(record);admin.queue.join();self.assertIs(admin.queue,q);c.stop()
    with sqlite3.connect(Path(d)/'owner/main.admin.sqlite3') as db:seq,at,h,raw=db.execute('SELECT seq,at,sha256,body FROM evidence').fetchone()
    mirror=next(r['payload'] for r in envelopes(c.root) if r['kind']=='NATIVE_RECORD');self.assertEqual((mirror['sequence'],mirror['committed_at'],mirror['sha256'],mirror['raw']),(seq,at,h,raw))
   finally:
    if admin:admin.queue.put(None);admin.thread.join(2)
    c.stop();Admin.run=old;ORIGINAL_JOURNAL.commit=commit
 def test_settlement_original_response_and_acceptance(self):
  import btc15_ladder_settlement_v2 as m
  oldinit,oldonce=m.SettlementReader.__init__,m.SettlementReader.once
  with tempfile.TemporaryDirectory() as d:
   c=Capture(config(Path(d)/'run'),'v81',offline=True);a=Adapters(c)
   try:
    bind_outcomes(c,a);opened=int(time.time()//900)*900-900;market=dict(ticker='FIXTURE-OUTCOME',open_time=datetime.fromtimestamp(opened,timezone.utc).isoformat(),close_time=datetime.fromtimestamp(opened+900,timezone.utc).isoformat(),status='finalized',result='no',floor_strike=100000)
    body=dict(market=market);response=types.SimpleNamespace(content=canonical(body),status_code=200,raise_for_status=lambda:None,json=lambda:body)
    with sqlite3.connect(Path(d)/'v81.sqlite3') as db:db.execute('CREATE TABLE contracts(ticker,opened,settlement_status,settlement_checked)');db.execute('INSERT INTO contracts VALUES (?,?,?,?)',('FIXTURE-OUTCOME',opened,'PENDING',0))
    offered=[];reader=m.SettlementReader(d,'v81',lambda v:offered.append(v) or True,get=lambda *a,**k:response);reader.once();c.stop()
    rows=envelopes(c.root);accepted=next(r['payload'] for r in rows if r['kind']=='OUTCOME_ACCEPTANCE');self.assertEqual(json.loads(accepted['raw']),offered[0]['settlement']);self.assertEqual(accepted['response_sha256'],sha(response.content))
   finally:c.stop();m.SettlementReader.__init__,m.SettlementReader.once=oldinit,oldonce
 def test_snapshot_requests_same_bytes_and_original_proof_queue(self):
  from ops.recording_workflow.rehearsal import fixture_provider
  with tempfile.TemporaryDirectory() as d:
   c=Capture(config(Path(d)/'run'),'v81',offline=True);a=Adapters(c);p=fixture_provider(Path(d)/'original-proof','T',time.time()+100);pool=types.SimpleNamespace(providers=[],factory=lambda:p);writer=p.proof_writer;queue=writer.queue
   try:
    a.bind_pool(pool);self.assertIs(pool.factory(),p);self.assertIs(p.proof_writer,writer);self.assertIs(p.proof_writer.queue,queue)
    sent=[];raw='{"id":2,"cmd":"update_subscription","params":{"sid":7,"market_tickers":["T"],"action":"get_snapshot"}}'
    self.assertEqual(c.observer.send(lambda x:sent.append(x) or 'same',raw,'T','e'),'same');self.assertEqual(sent,[raw]);c.stop();self.assertIs(p.proof_writer.queue,queue)
    self.assertTrue(any(x['kind']=='QUOTE_REQUEST' for x in envelopes(c.root)))
   finally:c.stop();writer.close()
 def test_remote_stop_protocol_and_sealed_object_bounds_offline(self):
  with tempfile.TemporaryDirectory() as d:
   c=config(Path(d)/'run');caps={r:Capture(c,r,offline=True) for r in c['roles']}
   try:
    with patch('ops.live_recording.remote.validate',side_effect=lambda c,r:caps[r].root),patch('ops.live_recording.remote.runtime_identity',return_value=None):
     result=remote_finish(c,list(caps));self.assertEqual(set(result['seals']),set(caps));item=result['seals']['main'];p=object_path(c,'main',item['sha256'],'identity.json');self.assertEqual(json.loads(p.read_bytes())['role'],'main')
     with self.assertRaisesRegex(ValueError,'OBJECT_NOT_IN_SEAL'):object_path(c,'main',item['sha256'],'../../other')
   finally:
    for cap in caps.values():cap.stop()
 def test_ssh_argv_private_host_and_output_bounds_with_local_pipe(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);c=config(d/'run');key=d/'key';key.write_text('OFFLINE DUMMY');key.chmod(0o600);hosts=d/'known_hosts';hosts.write_text('OFFLINE DUMMY');c.update(ssh_key=str(key),known_hosts=str(hosts));original=subprocess.Popen;seen=[]
   def local(argv,**kw):seen.append(argv);return original([sys.executable,'-c','import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(b"abc")'],**kw)
   with patch('ops.live_recording.finish.subprocess.Popen',side_effect=local):
    self.assertEqual(SSH(c,time.monotonic()+5).call('main',['finish','--roles','main'],3),b'abc')
    with self.assertRaisesRegex(ValueError,'SSH_OUTPUT_BOUND'):SSH(c,time.monotonic()+5).call('main',['finish'],2)
   self.assertIn('-oStrictHostKeyChecking=yes',seen[0]);self.assertIn('-oBatchMode=yes',seen[0]);self.assertEqual(seen[0][0],'ssh');self.assertTrue(seen[0][-1].startswith('cd /app && exec python -B -m ops.live_recording.remote '))
if __name__=='__main__':unittest.main(verbosity=2)
