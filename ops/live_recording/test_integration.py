"""New live-boundary tests only. No old suites, model inference or network."""
import ast,copy,gzip,json,os,sqlite3,tempfile,threading,time,types,unittest,zlib
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from .policy import BASES,SERVICES,VOLUMES,canonical,sha,file_sha,PROFILES,atomic,MiB
from .capture import Capture
from .adapters import Adapters,bind_journal,bind_outcomes
from .finish import finish,validate_seals
from .reader import CampaignVerifier,budgets
from ops.recording_workflow.evidence import lines,index_run
from btc15_quote_proof_offpath_v1 import Witness
from btc15_kalshi_quote_provenance_v1 import Book
from btc15_ladder_journal_v1 import digest

BASE=1577836800
CANDIDATE='BTC15_INTEGRATED_FINISH_20261006'
def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
def config(root):
 return dict(schema='BTC15_LIVE_CAMPAIGN_V1',run_id='new-integration-fixture',root=str(root),profile='preflight',duration_seconds=1200,capture_enabled=True,signal_only=True,orders=False,roles={r:dict(base_release=BASES['main' if r=='information' else r],service=SERVICES['main' if r=='information' else r],volume=VOLUMES['main' if r=='information' else r],build='a'*40,deployment='00000000-0000-4000-8000-000000000001',manifest_sha256='b'*64,ssh_target='offline-not-used@ssh.railway.com') for r in ('main','v81','information')})
def envelopes(root):
 return [r for p in root.rglob('*.jsonl.gz') for _,r,_ in lines(p)]
def emit_doc(c,k,z,**kw):c.emit(k,raw=canonical(z),**kw)
def native(c,n,seq):c.emit('NATIVE_RECORD',raw=canonical(n),original_journal='journal-'+c.role,sequence=seq,committed_at=n['published_ts']+.01,record_basis='POST_ORIGINAL_COMMIT',lane=c.role)
def fixture(root,candle_late=False,quote_rebase=False,input_unpublished=False):
 """New actual-schema observations. Literal fixture decisions; no processors run."""
 c=config(root);caps={r:Capture(c,r,offline=True) for r in c['roles']};main=caps['main'];v81=caps['v81'];info=caps['information'];ticker='FIXTURE-LIVE-A';at=BASE+895
 try:
  for t in range(775,906):
   for asset,add,epoch in [('BTC',0,main.archive.session),('BRTI',1,'shared-owner')]:main.observer.source(asset,100000+t+add,BASE+t-.2,BASE+t-.1,epoch)
  candle=[float(BASE+780),float(BASE+720),100000.,100002.,99998.,100001.,12.]
  emit_doc(main,'ORIGINAL_RESPONSE',[[BASE+720,99998,100002,100000,100001,12]],endpoint='https://api.exchange.coinbase.com/products/BTC-USD/candles',received_at=BASE+790,status_code=200)
  emit_doc(main,'CANDLE_ACCEPTANCE',[candle],accepted_at=BASE+896 if candle_late else BASE+791,basis='NATIVE_COMPLETED_CACHE_ACCEPTANCE')
  metadata=dict(market=dict(ticker=ticker,event_ticker=ticker,open_time=iso(BASE),close_time=iso(BASE+900),floor_strike=100000,strike_type='greater',rules_primary='SYNTHETIC',rules_secondary=''))
  for cap in (main,v81):
   for received in (BASE+800,BASE+801):cap.emit('HTTP_RESPONSE',raw=canonical(metadata),endpoint='/trade-api/v2/markets/'+ticker,received_at=received,receipt_basis='HTTP_GET_RETURN_BEFORE_NATIVE_DECODE',source='EXISTING_KALSHI_HTTP')
  proof_value=None;frame=None
  for cap in (main,v81):
   epoch='quote-'+cap.role
   events=[dict(type='orderbook_snapshot',sid=7,seq=1,msg=dict(market_ticker=ticker,market_id='market-A',yes_dollars_fp=[['0.4','100.25']],no_dollars_fp=[['0.59','110.50']])),dict(type='orderbook_delta',sid=7,seq=2,msg=dict(market_ticker=ticker,market_id='market-A',side='yes',price_dollars='0.4',delta_fp='0.25',ts_ms=int((at-.15)*1000)))]
   cap.emit('STREAM_START',ticker=ticker,epoch=epoch,observed_at=at-.2)
   book=Book(ticker)
   for i,e in enumerate(events):
    received=at-.14+i*.01;raw=canonical(e);cap.observer.quote_receive(raw,ticker,epoch,received,i);cap.observer.quote_accept(raw,ticker,epoch,received,received+.001);book.apply(e)
   if quote_rebase:
    request=dict(id=2,cmd='update_subscription',params=dict(sid=7,market_tickers=[ticker],action='get_snapshot'))
    cap.emit('QUOTE_REQUEST',raw=canonical(request),ticker=ticker,epoch=epoch,sent_at=at-.12,receipt_basis='EXISTING_WS_SEND_RETURN')
    ack=dict(id=2,type='ok');raw=canonical(ack);cap.observer.quote_receive(raw,ticker,epoch,at-.11,3);cap.observer.quote_accept(raw,ticker,epoch,at-.11,at-.109)
    snapshot=copy.deepcopy(events[0]);snapshot.update(seq=3,id=2);delta=copy.deepcopy(events[1]);delta['seq']=4;delta['msg']['ts_ms']=int((at-.05)*1000);events=[snapshot,delta];book=Book(ticker)
    for i,e in enumerate(events):
     received=at-.04+i*.01;raw=canonical(e);cap.observer.quote_receive(raw,ticker,epoch,received,i+4);cap.observer.quote_accept(raw,ticker,epoch,received,received+.001);book.apply(e)
   w=Witness(ticker,iso(at),epoch,int(at*1000),book.market_id,book.sid,book.seq,book.ts_ms,int((BASE+900)*1000));quotes=list(book.quotes(w.consumed_ms,w.close_ms))
   proof=dict(source_time=w.source_time,ticker=ticker,epoch=epoch,consumed_ms=w.consumed_ms,identity=w.identity,events=events)
   cap.emit('PROOF_BYTES',raw=json.dumps(proof,separators=(',',':')).encode(),witness_json=json.dumps(vars(w),separators=(',',':')))
   if cap is main:
    proof_value=proof
    frame=dict(kind='NATIVE_DECISION',candidate=CANDIDATE,native_epoch='native-A',native_sequence=1,captured_ts=at+.01,feature_cutoff=at,contract=ticker,official_open=BASE,official_close=BASE+900,target=100000,btc_price=100895,btc_source=at-.2,btc_received=at-.1,brti=dict(value=100896,cf_ts=at-.2,ready=True,delivery=dict(observed_ts=at-.1,owner_epoch='shared-owner')),quote=dict(vars(w),quotes=quotes),up_bid=quotes[0],up_ask=quotes[1],down_bid=quotes[2],down_ask=quotes[3],fair=None,artifact='FIXTURE_NO_MODEL',weights='FIXTURE_NO_MODEL')
    n=dict(schema='BTC15_LADDER_JOURNAL_V1',candidate=CANDIDATE,kind='NATIVE_DECISION',contract=ticker,published_ts=at+.02,evidence=frame,final=dict(publication_id=digest([CANDIDATE,'FINAL',['native-A',1]]),state='PASS',ready=False),product=dict(attempt_id='attempt-main',lane='main'),signal_only=True,orders=False)
    native(main,n,1)
    admin=dict(schema='BTC15_PUBLICATION_TIMING_R1',lane='main',attempt_id='attempt-main',journal_sequence=1,contract=ticker,processed_ts=at+.02,committed_ts=at+.03,signal_only=True,orders=False)
    main.emit('NATIVE_RECORD',raw=canonical(admin),original_journal='admin-main',sequence=50,committed_at=at+.04,record_basis='POST_ADMIN_COMMIT_APPLICATION_CLOCK',lane='main')
   else:
    b=dict(value=100896,source_ts_ms=int((at-.2)*1000),owner_epoch='shared-owner',sequence=895,status='PRIMARY_OK',clean_for_qualification=True)
    q=dict(ticker=ticker,epoch=epoch,market_id='market-A',sid=7,sequence=w.seq,source_ts_ms=w.exchange_ts_ms,validated_at_ms=int(at*1000),transport='timestamped_contiguous_ws',**dict(zip(('up_bid','up_ask','down_bid','down_ask'),quotes)))
    p=dict(schema='V81_TIMESTAMPED_INPUTS_V1',ticker=ticker,open_ts=BASE,close_ts=BASE+900,target=100000,quote=q,brti=b,btc_source_utc=iso(at-.2),signal_only=True,orders=False)
    row=dict(ts=at+.002,ticker=ticker,left=4.998,target=100000,btc=100895,brti=100896,input_provenance=p,**{k:q[k] for k in ('up_bid','up_ask','down_bid','down_ask')})
    emit_doc(v81,'ORIGINAL_RESPONSE',dict(time=iso(at-.2),price='100895'),endpoint='https://api.exchange.coinbase.com/products/BTC-USD/ticker',received_at=at-.1,status_code=200)
    emit_doc(v81,'BRTI_READ',b,received_at=at-.09,receipt_basis='EXISTING_SHARED_CONSUMER_RETURN')
    emit_doc(v81,'V81_INPUT',row,accepted_at=at+.003,receipt_basis='AFTER_EXISTING_REQUIRE_QUALIFIED',btc_response_sha256=sha(canonical(dict(time=iso(at-.2),price='100895'))),btc_received_at=at-.1,brti_observation_sha256=sha(canonical(b)),brti_received_at=at-.09,attempt_id='attempt-v81')
    native(v81,dict(schema='BTC15_LADDER_JOURNAL_V1',candidate=CANDIDATE,kind='SCALP_OBSERVATION',contract=ticker,published_ts=at+.02,provenance=p,guidance='WATCH',origin_id=None,product=dict(attempt_id='attempt-v81',lane='v81'),signal_only=True,orders=False),1)
  a=dict(schema='BTC15_NATIVE_INFORMATION_ANCHOR_V1',epoch='export-main',decision=at,captured=at+.01,ticker=ticker,opened=BASE,closed=BASE+900,target=100000,btc=dict(value=100895,source=at-.2,received=at-.1),completed=[candle],ticks=[[BASE+t-.2,BASE+t-.1,100000+t] for t in range(775,896)],probability_up=.5,seconds_left=5,artifact='FIXTURE_NO_MODEL',weights='FIXTURE_NO_MODEL')
  f=dict(schema='BTC15_INFORMATION_INPUT_V1',anchor=a,anchor_id=sha(canonical(a)),cut=at+.015,brti=dict(value=100896,source=at-.2,received=at-.1,epoch='shared-owner'),proof=proof_value,quote_received=at+.012)
  info.emit('INFORMATION_INPUT',raw=canonical(f),frame_id=None if input_unpublished else 'fixture-frame',published=not input_unpublished)
  if input_unpublished:info.emit('INFORMATION_FAILURE',reason='INPUT_NOT_PUBLISHED')
  from btc15_ladder_settlement_v2 import receipt
  outcome_raw=copy.deepcopy(metadata);outcome_raw['market'].update(status='finalized',result='yes',is_provisional=False)
  out=receipt(ticker,BASE,outcome_raw,BASE+905.1)
  emit_doc(main,'ORIGINAL_RESPONSE',outcome_raw,endpoint='https://external-api.kalshi.com/trade-api/v2/markets/'+ticker,received_at=BASE+905.05,status_code=200)
  emit_doc(main,'OUTCOME_ACCEPTANCE',out,response_sha256=sha(canonical(outcome_raw)),accepted_at=BASE+905.11)
  native(main,dict(schema='BTC15_LADDER_JOURNAL_V1',candidate=CANDIDATE,kind='SETTLEMENT',contract=ticker,published_ts=BASE+905.2,settlement=out,signal_only=True,orders=False),2)
  closeout=dict(contract=ticker,target=100000,final60_count=60,final60_average=100001.,final60_side='UP',final60_complete=True)
  emit_doc(main,'CLOSEOUT_ACCEPTANCE',dict(cohort=dict(brti=closeout),original_parity=dict(final60_count='60',timestamp_utc=iso(BASE+900))),accepted_at=BASE+905.3,basis='EXISTING_CLOSEOUT_PRODUCER_AFTER_COHORT_FSYNC')
  native(main,dict(schema='BTC15_LADDER_JOURNAL_V1',candidate=CANDIDATE,kind='BRTI_CLOSEOUT',contract=ticker,published_ts=BASE+905.4,brti_closeout=closeout,signal_only=True,orders=False),3)
 finally:
  for cap in caps.values():cap.stop()
 return c

class LocalTransport:
 def __init__(self,c):self.c=c;self.calls=0;self.corrupt=False;self.fail=False
 def seals(self):
  return {r:dict(sha256=file_sha(Path(self.c['root'])/r/'seal.json'),seal=json.loads((Path(self.c['root'])/r/'seal.json').read_bytes())) for r in self.c['roles']}
 def object(self,role,seal,name,size):
  self.calls+=1
  if self.fail:raise OSError('OFFLINE_INJECTED_TRANSFER_FAILURE')
  raw=(Path(self.c['root'])/role/name).read_bytes();return raw+b'bad' if self.corrupt else raw

def verify_fixture(root,out,partition=8192,**fixture_args):
 c=fixture(root,**fixture_args);transport=LocalTransport(c);seals=validate_seals(c,transport.seals());merged=out/'run';merged.mkdir(parents=True)
 for role,item in seals.items():
  for e in item['seal']['files']:
   if e['path'].endswith('.gz'):
    p=merged/('information.segments' if role=='information' else 'source.segments')/(role+'-'+Path(e['path']).name);p.parent.mkdir(exist_ok=True);os.link(root/role/e['path'],p)
 atomic(merged/'campaign-scope.json',dict(schema='BTC15_CAMPAIGN_SCOPE_V1',run_id=c['run_id'],seals=[x['seal'] for x in seals.values()]))
 index_run(merged,out/'index',profile='preflight');b=budgets('preflight');b.update(partition_bytes=partition,record_bytes=partition)
 v=CampaignVerifier(merged,out/'index',out/'verification',b);return v.run()

class NewIntegration(unittest.TestCase):
 def test_rollout_deployment_attested_with_exact_build(self):
  from .policy import validate,runtime_identity,PROJECT,ENVIRONMENT
  c=config(Path('/data/btc15_recordings/new-integration-fixture'));r=c['roles']['main'];r['deployment']='ATTEST_AT_START'
  env=dict(RAILWAY_PROJECT_ID=PROJECT,RAILWAY_ENVIRONMENT_ID=ENVIRONMENT,RAILWAY_SERVICE_ID=r['service'],RAILWAY_VOLUME_ID=r['volume'],RAILWAY_GIT_COMMIT_SHA=r['build'],RAILWAY_DEPLOYMENT_ID='12345678-0000-4000-8000-000000000001',RAILWAY_VOLUME_MOUNT_PATH='/data')
  with patch.dict(os.environ,env,clear=True):
   self.assertEqual(validate(c,'main'),Path(c['root'])/'main');self.assertEqual(runtime_identity(c,'main')['deployment'],env['RAILWAY_DEPLOYMENT_ID'])
   with patch.dict(os.environ,{'RAILWAY_GIT_COMMIT_SHA':'c'*40}):
    with self.assertRaisesRegex(ValueError,'RUNTIME_IDENTITY_DRIFT'):validate(c,'main')
   r['deployment']='00000000-0000-4000-8000-000000000001'
   with self.assertRaisesRegex(ValueError,'RUNTIME_DEPLOYMENT_DRIFT'):validate(c,'main')
 def test_attested_cross_role_deployment_drift_rejected(self):
  from .policy import PROJECT,ENVIRONMENT
  with tempfile.TemporaryDirectory() as d:
   c=fixture(Path(d)/'raw');s=LocalTransport(c).seals()
   for role,item in s.items():
    c['roles'][role]['deployment']='ATTEST_AT_START'
   for role,item in s.items():
    i=item['seal']['identity'];r=c['roles'][role];i.update(identity=r,configuration_sha256=sha(canonical(c)),mode='NATIVE_CAPTURE',runtime=dict(project=PROJECT,environment=ENVIRONMENT,service=r['service'],volume=r['volume'],build=r['build'],deployment='12345678-0000-4000-8000-000000000001'));item['sha256']=sha(canonical(item['seal']))
   validate_seals(c,s)
   s['information']['seal']['identity']['runtime']['deployment']='12345678-0000-4000-8000-000000000002';s['information']['sha256']=sha(canonical(s['information']['seal']))
   with self.assertRaisesRegex(ValueError,'MAIN_INFORMATION_DEPLOYMENT_MISMATCH'):validate_seals(c,s)
 def test_default_off_has_no_side_effects(self):
  from .bootstrap import start
  with patch.dict(os.environ,{},clear=True),patch('threading.Thread.start',side_effect=AssertionError('thread')),patch('pathlib.Path.read_bytes',side_effect=AssertionError('read')):self.assertIsNone(start('main'))
 def test_wrong_config_fails_without_native_stop(self):
  from .bootstrap import start
  with patch.dict(os.environ,{'BTC15_RECORDING_ENABLED':'1','BTC15_RECORDING_CONFIG':'/no-such-config'},clear=True):self.assertIsNone(start('main'))
 def test_soft_stop_preserves_later_wrapper_and_result(self):
  with tempfile.TemporaryDirectory() as d:
   c=Capture(config(Path(d)/'run'),'main',offline=True);a=Adapters(c);calls=[]
   delivery=types.SimpleNamespace(accept=lambda *x:True,fail=lambda *x:False,remember=lambda *x:None)
   ns=dict(get_btc_spot=lambda:42,_btc_spot_provenance=dict(price=42,source_utc=datetime.now(timezone.utc),observed_utc=datetime.now(timezone.utc)),_brti_delivery=delivery)
   pool=types.SimpleNamespace(providers=[],factory=lambda:None)
   def later(ns,pool):
    old=ns['get_btc_spot']
    def cadence():calls.append('cadence');return old()
    ns['get_btc_spot']=cadence
   a.prepare_main(later,ns,pool);wrapper=ns['get_btc_spot'];c.stop();before=c.archive.seq
   self.assertEqual(ns['get_btc_spot'](),42);self.assertIs(ns['get_btc_spot'],wrapper);self.assertEqual(c.archive.seq,before);self.assertEqual(calls,['cadence']);self.assertFalse(c.control.is_alive())
 def test_committed_bytes_match_original_sqlite(self):
  from btc15_v2_product.journal import ORIGINAL_JOURNAL
  from btc15_v2_product.admin import Admin
  old=ORIGINAL_JOURNAL.commit;admin=Admin.run
  with tempfile.TemporaryDirectory() as d:
   c=Capture(config(Path(d)/'run'),'main',offline=True)
   try:
    bind_journal(c);j=ORIGINAL_JOURNAL(Path(d)/'native.sqlite3','main');n=dict(schema='BTC15_LADDER_JOURNAL_V1',kind='UNAVAILABLE',published_ts=BASE,contract=None,unavailable_reason='FIXTURE',signal_only=True,orders=False)
    seq=j.commit(n,{});raw=j.db.execute('SELECT body FROM events WHERE seq=?',(seq,)).fetchone()[0];c.stop();j.close()
    mirror=next(r['payload'] for r in envelopes(c.root) if r['kind']=='NATIVE_RECORD');self.assertEqual(mirror['raw'].encode(),zlib.decompress(raw));self.assertEqual(mirror['sequence'],seq)
   finally:ORIGINAL_JOURNAL.commit=old;Admin.run=admin;c.stop()
 def test_quota_failure_seals_incomplete_without_deleting(self):
  with tempfile.TemporaryDirectory() as d:
   c=Capture(config(Path(d)/'run'),'main',offline=True)
   deadline=time.monotonic()+1
   while not c.archive.seq and time.monotonic()<deadline:time.sleep(.001)
   c.archive.journal.max_total_bytes=1024
   c.emit('RECORDING_HEALTH',observed_at=1,detail='x'*900);c.writer.queue.join();c.stop()
   s=json.loads((c.root/'seal.json').read_bytes());self.assertEqual(s['status'],'INCOMPLETE');self.assertTrue(list(c.root.rglob('*.gz')))
 def test_drain_timeout_never_seals_mutable_files(self):
  with tempfile.TemporaryDirectory() as d:
   c=Capture(config(Path(d)/'run'),'main',offline=True);release=threading.Event();entered=threading.Event();old=c.archive.observe
   def stalled(*a):entered.set();release.wait(2);return old(*a)
   c.archive.observe=stalled;c.emit('RECORDING_HEALTH',observed_at=1);self.assertTrue(entered.wait(1));c.stop(timeout=.01);self.assertFalse((c.root/'seal.json').exists());release.set();c.writer._thread.join(3);c.stop();self.assertFalse(c.writer._thread.is_alive());self.assertEqual(json.loads((c.root/'seal.json').read_bytes())['status'],'INCOMPLETE')
 def test_exact_candles_v81_admin_outcomes_across_partitions(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);r=verify_fixture(d/'raw',d/'read');self.assertTrue(r['complete_supplied_scope'],r);self.assertGreater(r['partitions'],10);self.assertEqual(r['metrics']['scalp_associations'],1);self.assertEqual(r['metrics']['admin_associations'],1);self.assertEqual(r['metrics']['outcome_associations'],2);self.assertEqual(r['metrics']['original_completed_candles'],1);self.assertFalse(r['actual_production_complete'])
 def test_late_candle_acceptance_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);r=verify_fixture(d/'raw',d/'read',candle_late=True);self.assertFalse(r['complete_supplied_scope']);self.assertEqual(r['issue_counts'].get('INFORMATION_ASSOCIATION'),1)
 def test_original_snapshot_request_ack_and_rebase_chain(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);r=verify_fixture(d/'raw',d/'read',quote_rebase=True);self.assertTrue(r['complete_supplied_scope'],r);self.assertEqual(r['metrics']['verified_snapshot_rebases'],2);self.assertEqual(r['metrics']['unsequenced_snapshot_acknowledgements'],2)
 def test_unpublished_information_is_not_missing_recording(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);r=verify_fixture(d/'raw',d/'read',input_unpublished=True);self.assertTrue(r['complete_supplied_scope'],r);self.assertEqual(r['metrics']['information_not_published'],1)
 def test_one_operation_and_verified_retry(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);c=fixture(d/'raw');t=LocalTransport(c);t.fail=True;r=finish(c,d/'result',t);self.assertEqual(r['status'],'INCOMPLETE');self.assertTrue((d/'result/BTC15_Findings.pdf').exists());t.fail=False;r=finish(c,d/'result',t);self.assertEqual(r['status'],'VERIFIED_SUPPLIED_SCOPE',r);self.assertFalse(r['live_retrieval']);self.assertTrue((d/'result/recovery.zip').exists())
 def test_transfer_corruption_and_identity_drift_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);c=fixture(d/'raw');t=LocalTransport(c);s=t.seals();s['v81']['seal']['identity']['identity']['build']='c'*40;s['v81']['sha256']=sha(canonical(s['v81']['seal']))
   with self.assertRaisesRegex(ValueError,'EXACT_CONFIG'):validate_seals(c,s)
   t.corrupt=True;r=finish(c,d/'bad',t);self.assertEqual(r['status'],'INCOMPLETE');self.assertIn('TRANSFER_HASH',r['failure'])
 def test_live_root_and_run_restart_guards(self):
  with tempfile.TemporaryDirectory() as d:
   c=config(Path(d)/'run');cap=Capture(c,'main',offline=True);cap.stop()
   with self.assertRaises(FileExistsError):Capture(c,'main',offline=True)
   with self.assertRaisesRegex(ValueError,'CAMPAIGN_ROOT'):Capture(c,'v81')
if __name__=='__main__':unittest.main(verbosity=2)
