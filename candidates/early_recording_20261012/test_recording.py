"""Synthetic mechanical tests only. No network, model fitting or market evaluation."""
import ast
import base64
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock,patch

from btc15_brti_delivery_v1 import Delivery
from btc15_information_journal_v1 import CompressedJournal,information_lines
from btc15_quote_proof_offpath_v1 import OffPathProofWriter,Witness
from btc15_v2_product.bootstrap import PreparedProvider
import btc15_kalshi_quote_provenance_v1 as quotes
from .archive import Archive,read_archive,reconstruct,canonical,sha,BUDGET,source_events
from .seams import Observer,available_sources
from .replay import quote_chain,proof_receipts
from .ledger import protocol,fee_evidence,associate,source_association

ROOT=Path(__file__).resolve().parents[2]
BOT=ROOT/'bot_two_output_build_v4_13_profit_protection_shadow.py'


def validate(proof,witness):
    quotes.replay(proof,witness.source_time,witness.ticker,witness.close_ms,witness.consumed_ms)
    return proof['identity']


@contextmanager
def capture(**kwargs):
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'evidence'
        archive=Archive(path,evidence_class='FIXTURE',source_binding='synthetic-mechanical-fixture')
        writer=OffPathProofWriter(Path(d)/'proof',validate,quotes.MAX_BYTES,
            queue_size=64,archive=archive,**kwargs)
        observer=Observer(writer,btc_feed='fixture:coinbase:BTC-USD',btc_epoch='btc-process',
                          brti_feed='fixture:BRTI',clock=lambda:1002.)
        try:yield path,archive,writer,observer
        finally:writer.close()


def rows(path):return read_archive(path)['records']


def event_pair(ticker='M',seq=1):
    return [dict(type='orderbook_snapshot',sid=7,seq=seq,msg=dict(market_ticker=ticker,market_id='id',
                yes_dollars_fp=[['0.40','12.50']],no_dollars_fp=[['0.59','9.25']])),
            dict(type='orderbook_delta',sid=7,seq=seq+1,msg=dict(market_ticker=ticker,market_id='id',
                side='yes',price_dollars='0.40',delta_fp='2.25',ts_ms=1000000))]


class Storage(unittest.TestCase):
    def test_exact_source_roundtrip_and_rollover_120_seconds(self):
        with capture() as (path,a,w,o):
            delivery=Delivery();o.bind_delivery(delivery)
            for t in range(780,911):
                o.source('BTC',80000+t/100,t,t+.1,'btc-process')
                delivery.accept(80001+t/100,t,t+.2,'brti-owner')
                if t%10==0:w.queue.join()
            w.queue.join();self.assertTrue(w.close())
            rs=rows(path)
            for asset in ('BTC','BRTI'):
                data=available_sources(rs,910.5,asset=asset)
                self.assertEqual(len(data),131)
                self.assertEqual((data[0]['source_ts'],data[-1]['source_ts']),(780,910))
                self.assertFalse(any('contract' in x for x in data))
                self.assertEqual(len(available_sources(rs,900.,asset=asset)),120)
            self.assertEqual(available_sources(rs,780.1,asset='BTC')[0]['value'],80007.8)
            self.assertTrue(all(r['evidence_class']=='FIXTURE' for r in rs))

    def test_brtI_duplicate_keeps_first_receipt_later_update_not_backdated(self):
        with capture() as (path,a,w,o):
            d=Delivery();o.bind_delivery(d)
            d.accept(80000,100,101,'owner');d.accept(80000,100,104,'owner')
            d.accept(80001,102,104,'owner');w.queue.join();w.close()
            actual=available_sources(rows(path),103,asset='BRTI')
            self.assertEqual(len(actual),1);self.assertEqual(actual[0]['receipt_ts'],101)
            self.assertEqual(d.select(103,104)['value'],80000)
            repeats=[r['payload'] for r in source_events(rows(path)) if r['kind']=='SOURCE_REPEAT']
            self.assertEqual(len(repeats),1)
            self.assertEqual((repeats[0]['receipt_ts'],repeats[0]['original_receipt_ts']),(104,101))

    def test_recovery_never_becomes_original_receipt(self):
        with capture() as (path,a,w,o):
            d=Delivery();o.bind_delivery(d);d.accept(80000,100,101,'owner')
            d.remember([(90.,79999.)],104);d.remember([(90.,79999.)],105)
            w.queue.join();w.close();rs=rows(path)
            all_points=available_sources(rs,104,asset='BRTI',include_recovered=True)
            p=next(p for p in all_points if p['basis']=='RECOVERED')
            self.assertEqual(p['receipt_ts'],104);self.assertIsNone(p['original_receipt_ts'])
            self.assertFalse(available_sources(rs,103,asset='BRTI',include_recovered=True)[0]['basis']=='RECOVERED')
            self.assertEqual(len(available_sources(rs,105,asset='BRTI')),1)

    def test_conflict_failure_epoch_gap_are_visible_without_owner_change(self):
        with capture() as (path,a,w,o):
            d=Delivery();o.bind_delivery(d);d.accept(80000,100,101,'one')
            with self.assertRaises(ValueError):d.accept(80001,100,102,'one')
            self.assertEqual(d.select(102,102)['value'],80000)
            d.fail(103);d.accept(80005,120,121,'one');d.accept(80006,121,122,'two')
            w.queue.join();w.close();rs=rows(path)
            text=json.dumps([r['payload'] for r in rs if r['kind']=='SOURCE_GAP'])
            for reason in ('CONFLICT','PRIMARY_UNAVAILABLE','SOURCE_GAP_OVER_15S','SOURCE_START_OR_EPOCH_CHANGE'):
                self.assertIn(reason,text)

    def test_invalid_chronology_is_gap_not_native_point(self):
        with capture() as (path,a,w,o):
            o.source('BTC',1,103,102,'e');o.source('BTC',float('nan'),100,101,'e')
            w.queue.join();w.close()
            self.assertFalse(available_sources(rows(path),110,asset='BTC'))
            self.assertEqual(sum(r['kind']=='SOURCE_GAP' for r in rows(path)),2)

    def test_exact_information_reconstruction_uses_vector_deltas(self):
        with capture() as (path,a,w,o):
            inputs=[]
            for i in range(3):
                value=dict(schema='BTC15_INFORMATION_INPUT_V1',anchor=dict(decision=100+i,
                    ticks=[[j,j+.1,80000+j] for j in range(i,120+i)],completed=[[1,2,3,4,5,6,7]]),
                    cut=101+i,brti=dict(source=100,received=100.1,epoch='b'),
                    proof=dict(events=event_pair(),epoch='q'))
                raw=canonical(value);inputs.append(raw)
                o.emit('INFORMATION_INPUT',raw=raw,frame_id=str(i),published=True)
                w.queue.join()
            w.close();rs=rows(path)
            self.assertEqual([x['raw'] for x in reconstruct(rs)],inputs)
            vectors=[r['payload'] for r in rs if r['kind']=='VECTOR' and r['payload']['name']=='btc_ticks']
            self.assertEqual([len(x['append']) for x in vectors],[120,1,1])
            self.assertEqual([x['drop'] for x in vectors],[0,1,1])

    def test_segment_disk_budgets_and_no_pruning(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';j=CompressedJournal(p,segment_bytes=250,max_total_bytes=700,max_record_bytes=300)
            raw=canonical(dict(a='a'*100))+b'\n'
            for _ in range(12):j.append(raw)
            files=list(j.directory.glob('*.gz'));before={f:f.read_bytes() for f in files}
            self.assertTrue(len(files)>1);self.assertTrue(all(f.stat().st_size<=250 for f in files))
            with self.assertRaises(OSError):
                for _ in range(20):j.append(raw)
            self.assertTrue(all(f.exists() and f.read_bytes().startswith(v) for f,v in before.items()))
            self.assertLessEqual(sum(f.stat().st_size for f in j.directory.glob('*.gz')),700)

    def test_short_write_roundtrip_and_zero_write_fail_closed(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            j=CompressedJournal(Path(d)/'a');original=os.write
            with patch('btc15_information_journal_v1.os.write',side_effect=lambda fd,b:original(fd,b[:3])):
                j.append(b'{"fixture":1}\n')
            self.assertEqual(list(information_lines(Path(d)/'a')),[b'{"fixture":1}\n'])
            with patch('btc15_information_journal_v1.os.write',return_value=0),self.assertRaises(OSError):j.append(b'x\n')
            self.assertTrue(j.failed)
            with self.assertRaises(OSError):j.append(b'x\n')

    def test_queue_overflow_idle_flush_and_byte_cap(self):
        with capture(queue_bytes=1500) as (path,a,w,o):
            gate=threading.Event();entered=threading.Event();original=a.observe
            def held(*args):entered.set();gate.wait(2);return original(*args)
            a.observe=held
            o.emit('SOURCE_GAP',reason='fixture');self.assertTrue(entered.wait(1))
            accepted=[o.emit('SOURCE_GAP',reason='fixture') for _ in range(30)]
            self.assertIn(False,accepted);self.assertLessEqual(w.peak_queued_bytes,1500)
            gate.set();w.queue.join();w.close()
            self.assertTrue(any(r['kind']=='EVIDENCE_GAP' for r in rows(path)))
            self.assertGreater(w.status()['losses'].get('QUEUE_BYTES',0),0)

    def test_queue_capacity_overflow(self):
        with capture() as (path,a,w,o):
            gate=threading.Event();entered=threading.Event();original=a.observe
            def held(*args):entered.set();gate.wait(2);return original(*args)
            a.observe=held;o.emit('SOURCE_GAP',reason='fixture');self.assertTrue(entered.wait(1))
            results=[o.emit('SOURCE_GAP',reason='fixture') for _ in range(100)]
            self.assertIn(False,results);gate.set();w.queue.join();w.close()
            self.assertGreater(w.status()['losses'].get('QUEUE_OVERFLOW',0),0)

    def test_concurrent_gap_counters_and_idle_durable_report(self):
        with capture() as (path,a,w,o):
            def dropped():
                for _ in range(100):w.gap('QUEUE_OVERFLOW')
            threads=[threading.Thread(target=dropped) for _ in range(4)]
            for t in threads:t.start()
            for t in threads:t.join()
            w.close();self.assertEqual(w.status()['losses']['QUEUE_OVERFLOW'],400)
            self.assertEqual(sum(r['payload']['reasons'].get('QUEUE_OVERFLOW',0) for r in rows(path) if r['kind']=='EVIDENCE_GAP'),400)

    def test_disk_full_worker_failure_cannot_throw_into_owner(self):
        with capture() as (path,a,w,o):
            w.queue.join();a.journal.append=Mock(side_effect=OSError('synthetic ENOSPC'))
            d=Delivery();o.bind_delivery(d)
            d.accept(80000,100,101,'owner');w.queue.join()
            self.assertEqual(d.select(101,101)['value'],80000)
            self.assertTrue(w.status()['archive_failed'])
            d.accept(80001,101,102,'owner');self.assertEqual(d.select(102,102)['value'],80001)
            w.queue.join();w.close()
            self.assertFalse(any(r['kind']=='STOP' for r in rows(path)))

    def test_corruption_restart_deterministic_and_old_bytes_untouched(self):
        with capture() as (path,a,w,o):
            o.source('BTC',80000,100,101,'old');w.queue.join();w.close()
            f=next(Path(str(path)+'.segments').glob('*.gz'));f.write_bytes(f.read_bytes()+b'torn')
            before=sha(f.read_bytes())
            second=Archive(path,evidence_class='FIXTURE',source_binding='same-fixture')
            w2=OffPathProofWriter(path.parent/'p2',validate,quotes.MAX_BYTES,archive=second)
            self.assertTrue(w2.close());r1=read_archive(path);r2=read_archive(path)
            self.assertEqual(r1,r2);self.assertEqual(sha(f.read_bytes()),before)
            self.assertTrue(any(g['reason']=='CORRUPT_SEGMENT' for g in r1['gaps']))
            self.assertFalse(r1['continuous_across_sessions'])
            self.assertTrue(all(r['session']==second.session for r in r1['records']))

    def test_exclusive_archive_and_protected_root(self):
        with self.assertRaises(ValueError):Archive('/data/forbidden',evidence_class='FIXTURE',source_binding='x')
        with tempfile.TemporaryDirectory() as d:
            a=Archive(Path(d)/'a',evidence_class='FIXTURE',source_binding='x');a.start()
            b=Archive(Path(d)/'a',evidence_class='FIXTURE',source_binding='x')
            try:
                with self.assertRaises(BlockingIOError):b.start()
            finally:a.close();b.close()

    def test_submit_has_no_serialization_or_io_and_rejects_mutable_payloads(self):
        with capture() as (path,a,w,o):
            # Hold the existing worker so patched serialization only covers submit.
            gate=threading.Event();entered=threading.Event();original=a.observe
            def held(*args):entered.set();gate.wait(2);return original(*args)
            a.observe=held;o.emit('SOURCE_GAP',reason='x');self.assertTrue(entered.wait(1))
            with patch('json.dumps',side_effect=AssertionError('path serialization')):
                self.assertTrue(o.emit('SOURCE_GAP',reason='x'))
                self.assertFalse(o.emit('SOURCE_GAP',data={'mutable':True}))
            gate.set();w.queue.join()


class QuoteMechanics(unittest.TestCase):
    def _provider(self):
        p=PreparedProvider.__new__(PreparedProvider)
        p.lock=threading.Lock();p.ticker='M';p.close_ms=1800000;p.book=None;p.events=[];p.epoch=None
        return p

    def test_same_socket_decoder_outputs_and_subscription_commands(self):
        outputs=[]
        with capture() as (path,a,w,o):
            for enabled in (False,True):
                p=self._provider();events=event_pair()
                ws=Mock();ws.recv.side_effect=[json.dumps(e) for e in events]+[EOFError('fixture disconnect')]
                if enabled:o.bind_provider(p)
                with patch.object(quotes.time,'time',return_value=1001.),patch.object(quotes.uuid,'uuid4',return_value='e'),patch.object(quotes.rollover_diag,'emit'):
                    with self.assertRaises(EOFError):p.session(ws,'M')
                outputs.append((deepcopy(p.book.levels),p.book.seq,p.book.ts_ms,p.accepted_ts,
                                p.presentation_quote,ws.send.call_args_list,ws.recv.call_args_list))
            w.queue.join();w.close();self.assertEqual(outputs[0],outputs[1])
            chain=quote_chain(rows(path));self.assertEqual(len(chain['states']),2)
            self.assertEqual(chain['states'][-1]['top']['up_bid_quantity'],'14.75')
            self.assertEqual(chain['states'][-1]['top']['up_ask_quantity'],'9.25')
            self.assertEqual(chain['states'][-1]['received_at'],1001.)
            self.assertFalse(chain['fill_evidence'])

    def test_exact_proof_hash_and_native_witness_with_receipt_association(self):
        with capture() as (path,a,w,o):
            events=event_pair()
            for e in events:
                raw=json.dumps(e);o.quote_receive(raw,'M','e',1001.,1);o.quote_accept(raw,'M','e',1001.,1001.1)
            witness=Witness('M','decision-1002','e',1002000,'id',7,2,1000000,1800000)
            self.assertTrue(w.submit(witness,events));w.queue.join();w.close()
            rec=reconstruct(rows(path));self.assertEqual(len(rec),1)
            expected=dict(source_time=witness.source_time,ticker='M',epoch='e',consumed_ms=1002000,
                          identity=witness.identity,events=events)
            self.assertEqual(rec[0]['raw'],json.dumps(expected,separators=(',',':'),allow_nan=False).encode())
            self.assertEqual(sha(rec[0]['raw']),rec[0]['proof_sha256'])
            self.assertTrue(proof_receipts(rec[0],rows(path))['timing_verified'])

    def test_missing_update_gap_disconnect_reconnect(self):
        with capture() as (path,a,w,o):
            for epoch,events in [('e1',[event_pair()[0],dict(event_pair()[1],seq=3)]),('e2',event_pair())]:
                o.emit('STREAM_START',ticker='M',epoch=epoch)
                for e in events:
                    raw=json.dumps(e);o.quote_receive(raw,'M',epoch,1001.,1);o.quote_accept(raw,'M',epoch,1001.,1001.1)
                o.emit('STREAM_END',ticker='M',epoch=epoch,reason='fixture_disconnect')
            w.queue.join();w.close();out=quote_chain(rows(path))
            self.assertTrue(any(g['reason']=='QUOTE_RECONSTRUCTION_GAP' for g in out['gaps']))
            self.assertEqual(out['states'][-1]['epoch'],'e2');self.assertEqual(out['states'][-1]['seq'],2)

    def test_accept_without_receipt_is_not_upgraded_consumer_time(self):
        with capture() as (path,a,w,o):
            for e in event_pair():o.quote_accept(json.dumps(e),'M','e',1001.,1002.)
            w.queue.join();w.close();result=quote_chain(rows(path))
            self.assertFalse(result['states']);self.assertEqual(len(result['gaps']),2)

    def test_receive_after_accept_is_rejected(self):
        with capture() as (path,a,w,o):
            raw=json.dumps(event_pair()[0]);o.quote_receive(raw,'M','e',1002,1);o.quote_accept(raw,'M','e',1002,1001)
            w.queue.join();w.close();self.assertFalse(quote_chain(rows(path))['states'])


class Provenance(unittest.TestCase):
    def test_real_information_publisher_capture_equivalence_and_reconstruction(self):
        from btc15_information_v1 import InformationPublisher,FairAssessment
        from completion_audit.isolated_decision_v2 import FrozenRuntime
        from test_btc15_isolated_decision_v2 import completed
        from test_btc15_information_v1 import Rig
        initial=FrozenRuntime(completed());rig=Rig(initial,offset=300)
        from btc15_information_service_v1 import DurablePublisher
        raw=rig.export.capture()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'archive';a=Archive(path,evidence_class='FIXTURE',source_binding='fixture')
            p=DurablePublisher(FairAssessment(),journal_path=Path(d)/'plain')
            q=DurablePublisher(FairAssessment(),journal_path=Path(d)/'observed',evidence_archive=a)
            self.assertEqual(p.offer(raw,rig.export.health,lambda:rig.at),q.offer(raw,rig.export.health,lambda:rig.at))
            self.assertEqual(p.latest,q.latest);self.assertEqual(p.frames,q.frames)
            self.assertEqual((Path(d)/'plain').read_bytes(),(Path(d)/'observed').read_bytes())
            q.close_evidence()
            self.assertEqual(reconstruct(rows(path))[0]['raw'],raw)
    def test_original_native_source_join_rejects_later_brti(self):
        with capture() as (path,a,w,o):
            o.source('BTC',80000,100,101,'btc-process')
            o.source('BRTI',80001,101,102,'owner');o.source('BRTI',80002,102,104,'owner')
            w.queue.join();w.close()
            f=dict(contract='M',feature_cutoff=103,btc_price=80000,btc_source=100,btc_received=101,
                brti=dict(value=80001,cf_ts=101,delivery=dict(observed_ts=102,owner_epoch='owner')))
            self.assertTrue(all(x['ref'] for x in source_association(f,rows(path))['sources'].values()))
            f['brti']=dict(value=80002,cf_ts=102,delivery=dict(observed_ts=104,owner_epoch='owner'))
            self.assertIsNone(source_association(f,rows(path))['sources']['BRTI']['ref'])

    def test_mutated_depth_cannot_match_original_receive_even_with_same_identity(self):
        with capture() as (path,a,w,o):
            events=event_pair()
            for e in events:
                raw=json.dumps(e);o.quote_receive(raw,'M','e',1001.,1);o.quote_accept(raw,'M','e',1001.,1001.1)
            mutated=deepcopy(events);mutated[0]['msg']['yes_dollars_fp'][0][1]='999'
            witness=Witness('M','decision','e',1002000,'id',7,2,1000000,1800000)
            w.submit(witness,mutated);w.queue.join();w.close()
            proof=reconstruct(rows(path))[0]
            self.assertFalse(proof_receipts(proof,rows(path))['timing_verified'])

    def test_information_publisher_false_and_exception_keep_input_failure_record(self):
        from btc15_information_service_v1 import DurablePublisher
        raw=canonical(dict(anchor=dict(decision=100,ticks=[],completed=[]),proof=dict(events=[]),cut=101))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'archive';a=Archive(path,evidence_class='FIXTURE',source_binding='fixture')
            p=DurablePublisher(Mock(),journal_path=Path(d)/'out',evidence_archive=a)
            with patch('btc15_information_service_v1.InformationPublisher.offer',return_value=False):
                self.assertFalse(p.offer(raw,lambda:None,lambda:101))
            with patch('btc15_information_service_v1.InformationPublisher.offer',side_effect=RuntimeError('fixture')):
                with self.assertRaises(RuntimeError):p.offer(raw,lambda:None,lambda:101)
            p.close_evidence()
            self.assertEqual([x['raw'] for x in reconstruct(rows(path))],[raw,raw])
            self.assertEqual(sum(r['kind']=='INFORMATION_FAILURE' for r in rows(path)),2)

    def test_metadata_raw_receipt_fee_unknowns_and_endpoint_whitelist(self):
        with capture() as (path,a,w,o):
            raw=b'{"series":{"ticker":"KXBTC15M","fee_type":"quadratic","fee_multiplier":1}}'
            o.http('/trade-api/v2/series/KXBTC15M',raw)
            o.http('/trade-api/v2/portfolio/positions',b'private-not-allowed')
            w.queue.join();w.close();rs=rows(path)
            http=[r['payload'] for r in rs if r['kind']=='HTTP_RESPONSE'];self.assertEqual(len(http),1)
            self.assertEqual(http[0]['raw_sha256'],sha(raw));self.assertIsNone(http[0]['applicable_scope'])
            blob=next(r['payload'] for r in rs if r['kind']=='HTTP_BYTES')
            self.assertEqual(base64.b64decode(blob['raw_base64']),raw)
            fee=fee_evidence(raw,http[0]['endpoint'],http[0]['received_at'])
            self.assertFalse(fee['applicability_verified']);self.assertIn('rounding',fee['missing'])

    def test_http_seam_uses_original_get_and_decoded_return(self):
        tree=ast.parse(BOT.read_text());fn=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='kalshi_get'][-1]
        response=Mock();response.json.return_value={'market':{'ticker':'M'}};response.content=b'{"market":{"ticker":"M"}}'
        request=Mock();request.get.return_value=response
        ns=dict(datetime=datetime,timezone=timezone,requests=request,KALSHI_BASE_URL='fixture.invalid',
                kalshi_headers=lambda *args:{},rollover_diag=Mock())
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(BOT),'exec'),ns)
        with capture() as (path,a,w,o):
            before=ns['kalshi_get']('/trade-api/v2/markets/M');calls=request.get.call_args_list[:]
            request.reset_mock();o.bind_http(ns)
            after=ns['kalshi_get']('/trade-api/v2/markets/M');self.assertEqual(before,after)
            self.assertEqual(request.get.call_args_list,calls);w.queue.join();w.close()
            self.assertEqual(sum(r['kind']=='HTTP_RESPONSE' for r in rows(path)),1)

    def test_lifecycle_keeps_cancellations_expiries_and_exact_final_origin(self):
        ref=dict(snapshot_sha256='a'*64,journal_id='native',sequence=2,record_sha256='b'*64)
        base=dict(contract='M',opened=0,closed=900,target=80000,side='UP',origin_id='original',origin_at=100,
                  setup_id='setup',ticket_id='ticket',at=102,provenance='SYNTHETIC_FIXTURE',evidence_class='FIXTURE')
        events=[dict(base,kind=k,event_id=k) for k in ('SETUP','CONFIRMATION','TICKET','CANCELLATION','EXPIRY')]
        native=[dict(base,kind='FINAL',source_ts=200,received_ts=201,ref=ref,provenance='VERIFIED_DETACHED_NATIVE'),
                dict(base,kind='EXIT',origin_id='later-origin',source_ts=202,received_ts=203,ref=ref,provenance='VERIFIED_DETACHED_NATIVE')]
        result=associate(events,native);self.assertEqual(len(result),5)
        self.assertTrue(all(len(x['native'])==1 and x['native'][0]['kind']=='FINAL' for x in result))
        wrong=[dict(native[0],contract='NEXT'),dict(native[0],source_ts=901,received_ts=902)]
        self.assertTrue(all(not x['native'] for x in associate(events,wrong)))
        self.assertFalse(protocol(size=1,reaction_seconds=10,reserve_cents=1,evidence_id='declared-fixture')['fill_evidence'])

    def test_archive_byte_corruption_and_fixture_identity_cannot_pass(self):
        with capture() as (path,a,w,o):
            o.source('BTC',80000,100,101,'epoch');w.queue.join();w.close()
            import gzip
            f=next(Path(str(path)+'.segments').glob('*.gz'));raw=gzip.decompress(f.read_bytes())
            f.write_bytes(gzip.compress(raw.replace(b'80000',b'80001')))
            got=read_archive(path);self.assertFalse(got['records']);self.assertTrue(got['gaps'])


class Equivalence(unittest.TestCase):
    def test_actual_btc_getter_same_request_return_and_failure(self):
        tree=ast.parse(BOT.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='get_btc_spot')
        class Clock(datetime):
            @classmethod
            def now(cls,tz):return datetime.fromtimestamp(101,tz)
        response=Mock();response.json.return_value=dict(time=datetime.fromtimestamp(100,timezone.utc).isoformat(),price='80000')
        requests=Mock();requests.get.return_value=response
        ns=dict(requests=requests,COINBASE_TICKER='fixture:coinbase',datetime=Clock,timezone=timezone,
                parse_dt=datetime.fromisoformat)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(BOT),'exec'),ns)
        with capture() as (path,a,w,o):
            before=ns['get_btc_spot']();calls=requests.get.call_args_list[:];requests.reset_mock()
            o.bind_btc(ns);self.assertEqual(ns['get_btc_spot'](),before)
            self.assertEqual(requests.get.call_args_list,calls)
            requests.get.side_effect=TimeoutError('synthetic');
            with self.assertRaises(TimeoutError):ns['get_btc_spot']()
            w.queue.join();w.close()
            source=available_sources(rows(path),102,asset='BTC')
            self.assertEqual(len(source),1);self.assertEqual(source[0]['receipt_ts'],101)
            self.assertTrue(any(r['kind']=='SOURCE_GAP' and r['payload'].get('reason')=='OWNER_FETCH_FAILED' for r in rows(path)))

    def test_native_early_final_management_scalp_and_research_transitions(self):
        from btc15_v2_product.directional import Directional
        from btc15_scalp_journal_v1 import Scalp
        from test_btc15_supported_early import value_frame
        from test_btc15_scalp_journal_v1 import state,ENTRY
        from candidates.early_rebuild_20261012.engine import Engine
        from candidates.early_rebuild_20261012.test_engine import fixture as research_fixture
        from completion_audit.isolated_decision_v2 import stable
        with capture() as (path,a,w,o):
            for cls,frames in [(Directional,[value_frame(),value_frame(2,ask=.7),value_frame(3,ask=.7,p=.8),
                    value_frame(4,ask=.68,p=.78,momentum=-10),value_frame(5,ask=.55,p=.6,side='DOWN')]),
                (Scalp,[state(ENTRY-1,seq=1),state(seq=2),state(ENTRY+1,.72,3),state(ENTRY+3,.68,4)])]:
                engines=[cls(),cls()]
                for e in engines:e.restore({})
                for f in frames:
                    before=deepcopy(f)
                    o.emit('SOURCE_GAP',reason='SYNTHETIC_OUTPUT_EQUIVALENCE_FIXTURE')
                    # Existing strategy receives the identical detached fixture;
                    # no archive result is an input to these protected reducers.
                    x=engines[0].process(deepcopy(f),f['captured_ts']+.001)
                    y=engines[1].process(deepcopy(f),f['captured_ts']+.001)
                    self.assertEqual(stable(x),stable(y));self.assertEqual(f,before)
                w.queue.join()
            engines=[Engine(),Engine()]
            for t in range(0,81,5):
                f=research_fixture(t);o.source('BTC',100000+t,t,t+.1,'fixture')
                self.assertEqual(engines[0].process(deepcopy(f)),engines[1].process(deepcopy(f)))
            w.queue.join()

    def test_full_frozen_loop_capture_enabled_disabled_exact(self):
        from completion_audit.isolated_decision_v2 import FrozenRuntime,stable
        from test_btc15_isolated_decision_v2 import completed,fixture,OPEN
        with capture() as (path,a,w,o):
            original=FrozenRuntime(completed());observed=FrozenRuntime(completed())
            o.bind_btc_tick(observed.ns);o.bind_delivery(observed.ns['_brti_delivery'])
            for elapsed in (120,125,130,600,605,895,900,905):
                f=fixture(elapsed,ticker='KXBTC15M-19DEC311930-30') if elapsed>=900 else fixture(elapsed)
                expected=original.step(deepcopy(f));actual=observed.step(deepcopy(f))
                self.assertEqual(stable(actual),stable(expected))
                self.assertEqual(stable(observed.snapshot()),stable(original.snapshot()))
                w.queue.join()
            self.assertTrue(w.close())
            self.assertGreater(sum(r['kind']=='SOURCE' for r in rows(path)),0)

    def test_strategy_sources_byte_identical_to_verified_baseline(self):
        import subprocess
        paths=['bot_two_output_build_v4_13_profit_protection_shadow.py','btc15_brti_delivery_v1.py',
          'btc15_kalshi_quote_provenance_v1.py','btc15_v2_product/bootstrap.py',
          'btc15_v2_product/directional.py','btc15_v2_product/early_entry.py',
          'btc15_v2_product/early_management.py','btc15_scalp_journal_v1.py',
          'candidates/early_rebuild_20261012/engine.py','candidates/early_rebuild_20261012/continuation.py']
        for p in paths:
            expected=subprocess.check_output(['git','show','3fd0e8a8b49e4db564e3185acb051e75d60e8e06:'+p],cwd=ROOT)
            self.assertEqual((ROOT/p).read_bytes(),expected,p)


if __name__=='__main__':unittest.main()
