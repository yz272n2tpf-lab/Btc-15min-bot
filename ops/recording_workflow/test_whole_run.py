"""Schema-faithful synthetic original-record fixtures. No model or service launch."""
from pathlib import Path
from datetime import datetime,timezone
from copy import deepcopy
from contextlib import redirect_stderr
import argparse,base64,gzip,io,json,os,sqlite3,subprocess,sys,tempfile,time,unittest
from unittest.mock import patch
from .integration import Capture
from .policy import config
from .evidence import index_run,lines,file_sha
from .whole_run import verify_run,LIMITS
from .snapshots import snapshot
from .report import generate
from .staging import ROOT,make_target,install,rollback,allowlist
from candidates.early_recording_20261012.archive import canonical,sha,Archive
from btc15_ladder_journal_v1 import Journal,digest,SCHEMA
from btc15_quote_proof_offpath_v1 import Witness
from btc15_kalshi_quote_provenance_v1 import Book
from .rehearsal import fixture_provider

BASE=1577836800
CANDIDATE='BTC15_INTEGRATED_FINISH_20261006'

def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()

def fixture(out,large=False):
    """Static mechanical native lifecycle records, not research signals/trades.

    Native BUY/EXIT fields are fixture states only. No strategy/model is called.
    Information's probability field is a constant schema fixture (0.5), not a
    prediction. Original Journal.commit and recorder observation APIs store bytes.
    """
    out=Path(out);out.mkdir(parents=True,exist_ok=False);root=out/'run'
    cap=Capture(config(root,enabled=True,run_id='followup-fixture'))
    journal=Journal(out/'owner/main.sqlite3','main');cap.bind_journal(journal)
    info=cap.publisher_kwargs()['evidence_archive'];info.start()
    providers=[];origin=None;native_seq=0
    try:
        # Original source history is retained through the 900-second rollover.
        for t in range(775,906):
            at=BASE+t
            for asset,add,epoch in [('BTC',0,'fixture-btc'),('BRTI',1,'fixture-brti')]:
                cap.observer.source(asset,100000+t+add,at-.2,at-.1,epoch)
            if t%8==0:cap.writer.queue.join()
        cap.writer.queue.join()
        for ticker,opened in [('FIXTURE-A',BASE),('FIXTURE-B',BASE+900)]:
            cap.observer.clock=lambda opened=opened:opened-1
            cap.observer.http('/trade-api/v2/markets/'+ticker,canonical(dict(market=dict(ticker=ticker,event_ticker=ticker,
                open_time=iso(opened),close_time=iso(opened+900),floor_strike=100000,strike_type='greater',rules_primary='SYNTHETIC FIXTURE',rules_secondary=''))))
        cap.writer.queue.join()
        # A long but valid official-metadata string exercises decoded-byte bounds.
        # Distinct metadata-only contracts require no invented native decisions.
        if large:
            for i in range(260):
                ticker='FIXTURE-LARGE-'+str(i)
                raw=canonical(dict(market=dict(ticker=ticker,event_ticker=ticker,open_time=iso(BASE),close_time=iso(BASE+900),
                    floor_strike=100000,strike_type='greater',rules_primary='SYNTHETIC VALID FIELD '+('0123456789abcdef'*4096),rules_secondary='')))
                cap.observer.http('/trade-api/v2/markets/'+ticker,raw)
                if i%2==0:cap.writer.queue.join()
            cap.writer.queue.join()
        for t in (895,897,905):
            ticker='FIXTURE-A' if t<900 else 'FIXTURE-B';opened=BASE if t<900 else BASE+900;at=BASE+t;epoch='fixture-stream-'+str(t)
            events=[dict(type='orderbook_snapshot',sid=7,seq=1,msg=dict(market_ticker=ticker,market_id=ticker+'-id',yes_dollars_fp=[['0.4','100.25']],no_dollars_fp=[['0.59','110.50']])),
                dict(type='orderbook_delta',sid=7,seq=2,msg=dict(market_ticker=ticker,market_id=ticker+'-id',side='yes',price_dollars='0.4',delta_fp='0.25',ts_ms=int((at-.15)*1000)))]
            cap.observer.emit('STREAM_START',ticker=ticker,epoch=epoch,observed_at=at-.2)
            book=Book(ticker)
            for i,event in enumerate(events):
                receipt=at-.14+i*.01;accepted=receipt+.001;raw=canonical(event)
                cap.observer.quote_receive(raw,ticker,epoch,receipt,i);cap.observer.quote_accept(raw,ticker,epoch,receipt,accepted);book.apply(event)
            w=Witness(ticker,iso(at),epoch,int(at*1000),book.market_id,book.sid,book.seq,book.ts_ms,int((opened+900)*1000))
            provider=fixture_provider(out/('proof-'+str(t)),ticker,opened+900);providers.append(provider);cap.bind_provider(provider)
            require=provider.proof_writer.submit(w,events);assert require
            provider.proof_writer.queue.join();cap.writer.queue.join()
            proof=json.loads((out/('proof-'+str(t))/'latest.json').read_bytes());proof_value=dict(source_time=w.source_time,ticker=ticker,epoch=epoch,consumed_ms=w.consumed_ms,identity=w.identity,events=events)
            q=dict(vars(w),quotes=list(book.quotes(w.consumed_ms,w.close_ms)))
            native_seq+=1
            f=dict(kind='NATIVE_DECISION',candidate=CANDIDATE,native_epoch='fixture-native',native_sequence=native_seq,
                captured_ts=at+.01,feature_cutoff=at,contract=ticker,official_open=opened,official_close=opened+900,target=100000,
                btc_price=100000+t,btc_source=at-.2,btc_received=at-.1,
                brti=dict(value=100001+t,cf_ts=at-.2,ready=True,delivery=dict(observed_ts=at-.1,owner_epoch='fixture-brti')),
                quote=q,up_bid=q['quotes'][0],up_ask=q['quotes'][1],down_bid=q['quotes'][2],down_ask=q['quotes'][3],
                fair=None,artifact='FIXTURE_NO_MODEL',weights='FIXTURE_NO_MODEL')
            if t==895:
                origin=dict(origin_id=digest([CANDIDATE,ticker,['fixture-native',native_seq],'UP']),contract=ticker,side='UP',
                    original_ask=f['up_ask'],signal_timestamp_utc=iso(at+.02),source_timestamp_utc=iso(at),native_epoch='fixture-native',native_sequence=native_seq,
                    target=100000,official_open=opened,official_close=opened+900,entry_provenance=deepcopy(f),manual_fill=None)
                event='BUY';o=deepcopy(origin);management=dict(state='ENTER',terminal=None);terminal=None
            elif t==897:
                event='EXIT';o=None
                terminal=dict(state='EXIT',actionable_exit=True,origin_id=origin['origin_id'],contract=ticker,side='UP',original_ask=origin['original_ask'],decision_ts=f['captured_ts'],executable_exit_bid=f['up_bid'],quote=q,
                    reason='SYNTHETIC_TERMINAL_RECORD',manual_fill=None,realized_profit=None,closure_confirmed=False)
                management=dict(state='EXIT',terminal=terminal)
            else:event=None;o=None;origin=None;management=None;terminal=None
            n=dict(schema=SCHEMA,candidate=CANDIDATE,build='FIXTURE',kind='NATIVE_DECISION',contract=ticker,published_ts=at+.02,
                signal_only=True,orders=False,evidence=f,event=event,origin=o,origin_id=(origin or {}).get('origin_id'),management=management,terminal=terminal,
                final=dict(publication_id=digest([CANDIDATE,'FINAL',['fixture-native',native_seq]]),state='PASS',ready=False,early_origin_id=(origin or {}).get('origin_id')))
            journal.commit(n,{});cap.writer.queue.join()
            anchor=dict(schema='BTC15_NATIVE_INFORMATION_ANCHOR_V1',epoch='fixture-information-anchor',decision=at,captured=at+.01,ticker=ticker,
                opened=opened,closed=opened+900,target=100000,btc=dict(value=100000+t,source=at-.2,received=at-.1),completed=[],
                ticks=[[BASE+x-.2,BASE+x-.1,100000+x] for x in range(max(775,t-120),t+1)],probability_up=.5,seconds_left=opened+900-at,
                artifact='FIXTURE_NO_MODEL',weights='FIXTURE_NO_MODEL')
            inp=dict(schema='BTC15_INFORMATION_INPUT_V1',anchor=anchor,anchor_id=sha(canonical(anchor)),cut=at+.02,
                brti=dict(value=100001+t,source=at-.2,received=at-.1,epoch='fixture-brti'),proof=proof_value,quote_received=at)
            info.input(canonical(inp),frame_id=None,published=False)
            cap.observer.emit('STREAM_END',ticker=ticker,epoch=epoch,observed_at=at+.1,reason='FIXTURE_END',continuity=False)
        journal.commit(dict(schema=SCHEMA,candidate=CANDIDATE,kind='UNAVAILABLE',contract='FIXTURE-B',published_ts=BASE+905.03,
            unavailable_reason='SYNTHETIC_PUBLICATION_REJECTED',signal_only=True,orders=False),{});cap.writer.queue.join()
        snapshot(out/'owner/main.sqlite3',root/'detached/main.sqlite3',kind='MAIN',identity=dict(evidence_class='FIXTURE'))
        with sqlite3.connect(root/'detached/main.sqlite3') as db:
            jid=dict(db.execute('SELECT k,v FROM meta'))['journal_id'];lo,hi,n=db.execute('SELECT min(seq),max(seq),count(*) FROM events').fetchone()
        info.write('STOP',dict(clean=True));info.close()
    finally:
        for p in providers:p.proof_writer.close()
        cap.close();journal.close();info.close()
    assert cap.status()['status']=='CLOSED',cap.status()
    sessions={}
    for role in ('source','information'):
        for path in sorted((root/(role+'.segments')).glob('*.gz')):
            for _,r,_ in lines(path):
                e=sessions.setdefault(r['session'],dict(role=role,records=0,last_sha256=None))
                if r['sequence']>e['records']:e.update(records=r['sequence'],last_sha256=r['sha256'])
    scope=dict(schema='BTC15_FIXTURE_VERIFICATION_SCOPE_V1',evidence_class='FIXTURE',run_identity_sha256=file_sha(root/'identity.json'),
        sessions=sessions,native_decisions=3,source_windows={a:dict(start=BASE+775-.1,end=BASE+905-.1,max_gap=1) for a in ('BTC','BRTI')},
        journals=[dict(path='detached/main.sqlite3',journal_id=jid,first_sequence=lo,last_sequence=hi,records=n,sha256=file_sha(root/'detached/main.sqlite3'))],
        provenance='SYNTHETIC_MECHANICAL_ORIGINAL_INTERFACES; NO_MODEL_CALLS; NO_RESEARCH_SIGNALS',
        assertions_not_made=['native_consumed_information_input','native_consumed_HTTP_response','model_compatibility','fees','fills'])
    (root/'verification_scope.json').write_bytes(canonical(scope))
    index_run(root,out/'index');return root


def mutate(root,callback):
    """New fixture mutations only. Rehash envelope chain to isolate semantic checks."""
    sessions={};paths=list(root.glob('*.segments/*.gz'))
    for path in paths:
        for _,r,_ in lines(path):sessions.setdefault(r['session'],[]).append(r)
    for path in paths:path.unlink()
    scope=json.loads((root/'verification_scope.json').read_bytes())
    for s,rs in sessions.items():
        rs.sort(key=lambda r:r['sequence']);callback(rs);prev=None
        role=scope['sessions'][s]['role'];path=root/(role+'.segments')/(s+'.jsonl.gz')
        with gzip.open(path,'wb') as f:
            for n,r in enumerate(rs,1):
                r['sequence']=n;r['previous_sha256']=prev;r.pop('sha256',None);r['sha256']=sha(canonical(r));prev=r['sha256'];f.write(canonical(r)+b'\n')
        scope['sessions'][s].update(records=len(rs),last_sha256=prev)
    (root/'verification_scope.json').write_bytes(canonical(scope))


class WholeRun(unittest.TestCase):
    def setup_fixture(self,d):return fixture(Path(d)/'case')
    def verify(self,root,out,**budget):return verify_run(root,root.parent/'index',out,budget=budget or None)
    def test_complete_cross_partition_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.setup_fixture(d);r=self.verify(root,Path(d)/'verified',partition_bytes=8192,record_bytes=8192)
            self.assertTrue(r['fixture_complete'],r);self.assertGreater(r['partitions'],3)
            self.assertGreater(r['metrics']['cross_partition_associations'],0)
            self.assertEqual(r['metrics']['native_associations'],3);self.assertEqual(r['metrics']['terminal_associations'],1)
            self.assertEqual(r['metrics']['information_associations'],3);self.assertEqual(r['metrics']['legitimate_no_origin'],1)
            self.assertEqual(r['metrics']['legitimate_unavailable'],1);self.assertFalse(r['actual_production_complete'])
    def test_empty_and_unscoped_never_complete(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'run').mkdir();index_run(d/'run',d/'index');r=verify_run(d/'run',d/'index',d/'v')
            self.assertFalse(r['fixture_complete']);self.assertIn('EMPTY_ARCHIVE',r['issue_counts'])
    def test_semantic_missing_late_recovered_duplicate_and_unsupported(self):
        cases=('missing_source','late_source','recovered_source','duplicate_decision','missing_proof','wrong_contract','bad_input_hash','missing_terminal','unsupported')
        for case in cases:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as d:
                root=self.setup_fixture(d)
                def change(rs):
                    if case=='missing_source':rs[:]=[r for r in rs if not(r['kind']=='SOURCE' and r['payload']['source_ts']==BASE+895-.2 and r['payload']['asset']=='BRTI')]
                    if case in ('late_source','recovered_source'):
                        for r in rs:
                            p=r['payload']
                            if r['kind']=='SOURCE' and p['source_ts']==BASE+895-.2 and p['asset']=='BRTI':
                                if case=='late_source':p['available_at']=BASE+899
                                else:p.update(basis='RECOVERED',original_receipt_ts=None)
                                p.pop('observation_id');p['observation_id']=sha(canonical(p))
                    if case=='missing_proof':rs[:]=[r for r in rs if not(r['kind']=='QUOTE_PROOF' and r['payload']['witness']['ticker']=='FIXTURE-A')]
                    if case=='bad_input_hash':
                        for r in rs:
                            if r['kind']=='INFORMATION_INPUT':r['payload']['input_sha256']='0'*64;break
                    if case in ('duplicate_decision','wrong_contract','missing_terminal'):
                        for r in rs:
                            if r['kind']=='NATIVE_RECORD':
                                p=r['payload'];n=json.loads(p['raw'])
                                if n.get('event')=='EXIT':
                                    if case=='duplicate_decision':n['evidence']['native_sequence']=1
                                    if case=='wrong_contract':n['evidence']['contract']='OTHER'
                                    if case=='missing_terminal':n['terminal']=None
                                    p['raw']=canonical(n).decode();p['sha256']=sha(p['raw'].encode());break
                    if case=='unsupported' and rs:rs[len(rs)//2]['kind']='UNKNOWN_REQUIRED_KIND'
                mutate(root,change);index_run(root,Path(d)/'mutated-index');r=verify_run(root,Path(d)/'mutated-index',Path(d)/'v',budget=dict(partition_bytes=8192,record_bytes=8192))
                self.assertFalse(r['fixture_complete'],case);self.assertTrue(r['issue_counts'],case)
    def test_original_bytes_missing_duplicate_and_corruption(self):
        for case in ('missing_segment','duplicate_segment','corrupt_segment','torn_record','missing_stop'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as d:
                root=self.setup_fixture(d);p=next(root.glob('source.segments/*.gz'))
                if case=='missing_segment':p.rename(p.with_suffix('.withheld'))
                elif case=='duplicate_segment':p.with_name('copy.jsonl.gz').write_bytes(p.read_bytes())
                elif case=='corrupt_segment':p.write_bytes(p.read_bytes()[:-5]+b'xxxxx')
                else:
                    def change(rs):
                        if case=='missing_stop':rs[:]=[r for r in rs if r['kind']!='STOP']
                    mutate(root,change)
                    if case=='torn_record':
                        with gzip.open(next(root.glob('source.segments/*.gz')),'ab') as f:f.write(b'{')
                    index_run(root,Path(d)/'bad-index')
                idx=Path(d)/'bad-index' if case in ('torn_record','missing_stop') else root.parent/'index'
                r=verify_run(root,idx,Path(d)/'v');self.assertFalse(r['fixture_complete'])
    def test_capacity_exhaustion_is_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.setup_fixture(d)
            for name,value in [('decoded_bytes',4096),('work_db_bytes',65536),('partitions',1),('ledger_bytes',64),('records',1)]:
                r=verify_run(root,root.parent/'index',Path(d)/name,budget={name:value,'partition_bytes':8192,'record_bytes':8192})
                self.assertFalse(r['fixture_complete']);self.assertTrue(r['issue_counts'])
    def test_report_uses_complete_run_and_keeps_actual_gates_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.setup_fixture(d);r=generate(root,root.parent/'index',Path(d)/'report')
            self.assertTrue(r['fixture_complete'],r['gaps']);self.assertFalse(r['complete_evidence']);self.assertFalse(r['cost_verified'])
            self.assertEqual(r['production_approval'],'NOT_AUTHORIZED')
            self.assertEqual(len(r['matrix']),13);self.assertEqual(len({x['requirement'] for x in r['matrix']}),13)
            self.assertEqual(next(x['status'] for x in r['matrix'] if x['requirement']=='fee_applicability'),'BLOCKED')

class FollowupEdges(unittest.TestCase):
    def test_package_keeps_scope_journal_and_partition_ledgers(self):
        from .transfer import package,restore
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);root=fixture(d/'case');report=generate(root,root.parent/'index',d/'report',verification_limits=dict(partition_bytes=8192,record_bytes=8192))
            p=package(root,root.parent/'index',d/'store',quota=8*1024**2,identity=json.loads((root/'identity.json').read_bytes()),report=d/'report/quality.json')
            restored=d/'reader';restore(p['manifest'],restored,expected_sha256=p['sha256'])
            index_run(restored,d/'reader-index');r=verify_run(restored,d/'reader-index',d/'reader-verification',budget=dict(partition_bytes=8192,record_bytes=8192))
            self.assertTrue(r['fixture_complete'],r)
            self.assertEqual(file_sha(root/'detached/main.sqlite3'),file_sha(restored/'detached/main.sqlite3'))
            self.assertTrue((restored/'verification/partition_results.jsonl').is_file())
            with self.assertRaises(OSError):package(root,root.parent/'index',d/'small',quota=50,identity={},report=d/'report/quality.json')
    def test_compact_repeat_dependency_crosses_partitions(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);root=d/'run';root.mkdir();a=Archive(root/'source',evidence_class='FIXTURE',source_binding='repeat:main');a.start()
            p=dict(asset='BTC',value=100000,source_ts=100.,receipt_ts=100.1,original_receipt_ts=100.1,available_at=100.1,feed='fixture',epoch='e',basis='ORIGINAL',accepted_by_owner=True)
            a.source(p);a.source(dict(p,receipt_ts=100.2,original_receipt_ts=100.2,available_at=100.2));a.write('STOP',dict(clean=True));a.close();index_run(root,d/'index')
            r=verify_run(root,d/'index',d/'v',budget=dict(partition_bytes=1200,record_bytes=1200))
            self.assertEqual(r['counts']['SOURCE_REPEAT'],1);self.assertNotIn('RECORD_VERIFICATION',r['issue_counts']);self.assertGreater(r['metrics']['cross_partition_dependencies'],0)
            self.assertFalse(r['fixture_complete']) # No declared complete scope/native journals.
    def test_unreadable_segment_and_combined_journal_capacity(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);root=fixture(d/'case')
            with patch('ops.recording_workflow.whole_run.lines',side_effect=PermissionError('fixture unreadable')):
                r=verify_run(root,root.parent/'index',d/'unreadable')
            self.assertFalse(r['fixture_complete']);self.assertIn('UNREADABLE_OR_CORRUPT_SEGMENT',r['issue_counts'])
            r=verify_run(root,root.parent/'index',d/'journal-quota',budget=dict(journal_bytes=1))
            self.assertFalse(r['fixture_complete']);self.assertIn('CAPACITY_EXHAUSTED',r['issue_counts'])
    def test_exact_ambiguity_and_quote_gap_are_rejected(self):
        for case in ('duplicate_source','conflicting_source','late_quote','quote_sequence_gap','metadata_duplicate','final_id'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as d:
                d=Path(d);root=fixture(d/'case')
                def change(rs):
                    for i,r in enumerate(rs):
                        p=r['payload']
                        if case in ('duplicate_source','conflicting_source') and r['kind']=='SOURCE' and p['asset']=='BRTI' and p['source_ts']==BASE+895-.2:
                            c=deepcopy(r)
                            if case=='conflicting_source':
                                c['payload']['value']+=1;c['payload'].pop('observation_id');c['payload']['observation_id']=sha(canonical(c['payload']))
                            rs.insert(i+1,c);break
                        if case=='late_quote' and r['kind']=='QUOTE_ACCEPT':p['accepted_at']=BASE+2000;break
                        if case=='quote_sequence_gap' and r['kind']=='QUOTE_ACCEPT':rs.pop(i);break
                        if case=='metadata_duplicate' and r['kind']=='HTTP_RESPONSE' and p['official_fields']['ticker']=='FIXTURE-A':rs.insert(i+1,deepcopy(r));break
                        if case=='final_id' and r['kind']=='NATIVE_RECORD':
                            n=json.loads(p['raw'])
                            if n.get('final'):
                                n['final']['publication_id']='0'*64;p['raw']=canonical(n).decode();p['sha256']=sha(p['raw'].encode());break
                mutate(root,change);index_run(root,d/'idx');r=verify_run(root,d/'idx',d/'v')
                self.assertFalse(r['fixture_complete'],case)
                details=(d/'v/issues.jsonl').read_text()
                expected={'duplicate_source':'DUPLICATE_SOURCE_IDENTITY','conflicting_source':'CONFLICTING_SOURCE_PUBLICATION','late_quote':'MISSING_OR_AMBIGUOUS_PROOF_RECEIPT','quote_sequence_gap':'UNRESOLVED_STREAM_OR_RECEIVE','metadata_duplicate':'MISSING_OR_AMBIGUOUS_EXACT_METADATA','final_id':'FINAL_PUBLICATION_ID'}[case]
                self.assertIn(expected,details)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fixture');p.add_argument('--large',action='store_true');a=p.parse_args()
    if a.fixture:
        with patch('socket.socket.connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
            print(fixture(a.fixture,large=a.large))
    else:unittest.main(argv=[sys.argv[0]])
