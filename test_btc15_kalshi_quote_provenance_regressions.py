#!/usr/bin/env python3
"""Offline exchange-message and actual parity integration tests. NO ORDERS."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
import btc15_kalshi_quote_provenance_v1 as q
from test_btc15_parity_measurement_regressions import ParityMeasurements

TICKER = 'KXBTC15M-26SEP201315-15'
NOW = 1790000000500
CLOSE = NOW + 500000


def snapshot(ticker=TICKER):
    return dict(type='orderbook_snapshot', sid=2, seq=2, msg=dict(
        market_ticker=ticker, market_id='uuid-1',
        yes_dollars_fp=[['0.49', '20.00']], no_dollars_fp=[['0.50', '25.00']]))


def delta(seq=3, ts_ms=NOW-200, **kwargs):
    msg = dict(market_ticker=TICKER, market_id='uuid-1', side='yes',
               price_dollars='0.4900', delta_fp='1.00', ts_ms=ts_ms,
               ts=datetime.fromtimestamp(ts_ms/1000, timezone.utc).isoformat())
    msg.update(kwargs)
    return dict(type='orderbook_delta', sid=2, seq=seq, msg=msg)


def ready():
    book=q.Book(TICKER)
    book.apply(snapshot()); book.apply(delta())
    return book


def proof():
    return dict(source_time='collector', ticker=TICKER, epoch='connection-1',
                consumed_ms=NOW, identity=['uuid-1',2,3,NOW-200],
                events=[snapshot(),delta()])


class Quotes(unittest.TestCase):
    def test_missing_snapshot_field_reports_exact_safe_path(self):
        for field in ('market_ticker',):
            event=snapshot();del event['msg'][field]
            with self.assertRaises(q.MissingQuoteField) as caught:
                q.Book(TICKER).apply(event)
            self.assertEqual(caught.exception.field,field)
            self.assertIn('Book.apply->Book._apply/orderbook_snapshot',str(caught.exception))

    def test_missing_field_diagnostics_never_echo_unknown_values(self):
        exc=q.MissingQuoteField('secret-value', 'secret-payload')
        self.assertNotIn('secret',str(exc))
        self.assertIn('UNKNOWN_FIELD',str(exc))

    def test_exact_timestamp_sequence_replay(self):
        values, identity=q.replay(proof(),'collector',TICKER,CLOSE,NOW)
        self.assertEqual(values,(.49,.50,.50,.51))
        self.assertIn('seq=3',identity)
        self.assertIn('ts_ms='+str(NOW-200),identity)

    def test_same_millisecond_distinct_sequence(self):
        book=ready(); book.apply(delta(seq=4,price_dollars='.51'))
        self.assertEqual(book.seq,4)
        self.assertEqual(book.ts_ms,NOW-200)
        with self.assertRaises(ValueError):book.quotes(NOW,CLOSE) # crossed

    def test_duplicate_does_not_apply_twice_or_refresh(self):
        book=ready(); quantity=book.levels['yes'].copy()
        self.assertFalse(book.apply(delta()))
        self.assertEqual(book.levels['yes'],quantity)
        with self.assertRaises(ValueError):book.quotes(NOW+6000,CLOSE)

    def test_conflicting_duplicate_invalidates(self):
        book=ready()
        with self.assertRaises(ValueError):book.apply(delta(delta_fp='2'))
        with self.assertRaises(ValueError):book.quotes(NOW,CLOSE)

    def test_gap_requires_new_snapshot(self):
        book=ready()
        with self.assertRaises(ValueError):book.apply(delta(seq=5))
        with self.assertRaises(ValueError):book.apply(delta(seq=4))
        with self.assertRaises(ValueError):book.apply(snapshot())
        self.assertEqual(ready().quotes(NOW,CLOSE),(.49,.5,.5,.51))

    def test_out_of_order_invalidates(self):
        book=ready()
        with self.assertRaises(ValueError):book.apply(delta(seq=1))

    def test_reconnect_cannot_start_with_delta(self):
        with self.assertRaises(ValueError):q.Book(TICKER).apply(delta())

    def test_untimestamped_snapshot_not_fresh(self):
        book=q.Book(TICKER); book.apply(snapshot())
        with self.assertRaises(ValueError):book.quotes(NOW,CLOSE)

    def test_stale_and_future(self):
        for ts in (NOW-6001,NOW+1):
            book=q.Book(TICKER);book.apply(snapshot());book.apply(delta(ts_ms=ts))
            with self.assertRaises(ValueError):book.quotes(NOW,CLOSE)

    def test_timestamp_mismatch_regression_and_missing(self):
        bad=[delta(seq=4,ts_ms=NOW-300),delta(seq=4,ts='2000-01-01T00:00:00Z')]
        missing=delta(seq=4);del missing['msg']['ts_ms'];bad.append(missing)
        for event in bad:
            with self.assertRaises((ValueError,KeyError)):ready().apply(event)

    def test_cross_contract_and_market_id_rejected(self):
        for extra in ({'market_ticker':'NEXT'},{'market_id':'OTHER'}):
            with self.assertRaises(ValueError):ready().apply(delta(seq=4,**extra))

    def test_subscription_identity_rejected(self):
        event=delta(seq=4);event['sid']=3
        with self.assertRaises(ValueError):ready().apply(event)

    def test_exact_contract_window(self):
        book=ready()
        for close in (NOW, NOW+900000):
            with self.assertRaises(ValueError):book.quotes(NOW,close)

    def test_missing_or_crossed_side(self):
        for change in ({'delta_fp':'-21'},{'price_dollars':'.6'}):
            book=ready();book.apply(delta(seq=4,**change))
            with self.assertRaises(ValueError):book.quotes(NOW,CLOSE)

    def test_bad_levels_fail_closed(self):
        for extra in ({'price_dollars':'NaN'},{'delta_fp':'-999'},{'side':'bad'}):
            with self.assertRaises(ValueError):ready().apply(delta(seq=4,**extra))

    def test_proof_exact_frame_contract_and_identity(self):
        for key,value in [('source_time','wrong'),('ticker','NEXT'),('identity',['uuid-1',2,4,NOW-200]),('epoch','')]:
            p=proof();p[key]=value
            with self.assertRaises(ValueError):q.replay(p,'collector',TICKER,CLOSE,NOW)

    def test_missing_stale_and_incomplete_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'proof'
            with patch.object(q,'proof_path',return_value=path):
                with self.assertRaises(FileNotFoundError):q.validate('collector',TICKER,CLOSE,NOW)
                path.write_text('{')
                with self.assertRaises(ValueError):q.validate('collector',TICKER,CLOSE,NOW)
        with self.assertRaises(ValueError):q.replay(proof(),'collector',TICKER,CLOSE,NOW+6001)

    def test_rollover_clears_provider_before_use(self):
        provider=object.__new__(q.Provider)
        provider.lock=threading.Lock();provider.ticker=TICKER;provider.book=ready();provider.events=[]
        self.assertIsNone(provider.consume('NEXT','collector',CLOSE+900000))
        self.assertIsNone(provider.book)
        self.assertIsNone(provider.consume('NEXT','collector',CLOSE+900000))

    def test_atomic_consumption_and_replay(self):
        provider=object.__new__(q.Provider)
        provider.lock=threading.Lock();provider.ticker=TICKER;provider.book=ready()
        provider.events=[snapshot(),delta()];provider.epoch='connection-1'
        with tempfile.TemporaryDirectory() as directory,patch.object(q.time,'time',return_value=NOW/1000),patch.object(q,'proof_path',return_value=Path(directory)/'proof'):
            self.assertEqual(provider.consume(TICKER,'collector',CLOSE),(.49,.5,.5,.51))
            self.assertEqual(q.validate('collector',TICKER,CLOSE,NOW)[0],(.49,.5,.5,.51))

    def test_opt_in_default_off_and_both_data_roots_supported(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertFalse(q.enabled())
        with patch.dict(os.environ,{q.FLAG:'1'},clear=True):
            self.assertTrue(q.enabled())
        with patch.dict(os.environ,{q.FLAG:'1','BTC15_ISOLATED_CANARY_LOCAL_DATA':'1'},clear=True):
            self.assertTrue(q.enabled())

    def test_read_only_wire_and_unchanged_brti_loop_order(self):
        self.assertEqual(q.subscription(TICKER),{'id':1,'cmd':'subscribe','params':{'channels':['orderbook_delta'],'market_tickers':[TICKER]}})
        source=Path(q.__file__).read_text()
        self.assertEqual(source.count('ws.send('),2)
        self.assertEqual(q.snapshot_request(TICKER,2,3),{'id':3,'cmd':'update_subscription','params':{'sid':2,'market_tickers':[TICKER],'action':'get_snapshot'}})
        self.assertNotIn('/portfolio/',source)
        main=Path('bot_two_output_build_v4_13_profit_protection_shadow.py').read_text()
        self.assertLess(main.index('_retry_brti_closeouts(datetime.now(timezone.utc))'),main.index('quotes = consume_ws_quotes('))
        self.assertLess(main.index('_track_brti_contract(ticker, target, close_dt, btc)'),main.index('quotes = consume_ws_quotes('))


class QuoteParity(unittest.TestCase):
    def setUp(self):
        self.fixture=ParityMeasurements();self.fixture.setUp()
        self.env=patch.dict(os.environ,{q.FLAG:'1','BTC15_ISOLATED_CANARY_LOCAL_DATA':'1'})
        self.env.start();self.addCleanup(self.env.stop)

    def test_verified_exact_state_can_pass(self):
        with patch.object(q,'validate',return_value=((.49,.5,.5,.51),'seq=3,ts_ms=123')):
            record=self.fixture.audit()
        self.assertEqual(record['overall_status'],'PASS')
        self.assertTrue(record['quote_match'])
        self.assertIn('QUOTES_WS_STATE_MATCH',record['notes'])

    def test_same_identity_different_value_fails_without_tolerance_widening(self):
        with patch.object(q,'validate',return_value=((.4901,.5,.5,.51),'seq=3')):
            record=self.fixture.audit()
        self.assertEqual(record['overall_status'],'FAIL')
        self.assertIn('QUOTES_WS_VALUE_MISMATCH',record['notes'])

    def test_missing_or_stale_proof_never_passes(self):
        with patch.object(q,'validate',side_effect=ValueError('unavailable')):
            record=self.fixture.audit()
        self.assertEqual(record['overall_status'],'WAIT')
        self.assertFalse(record['quote_scorable'])

    def test_verified_quotes_cannot_hide_brti_failure(self):
        with patch.object(q,'validate',return_value=((.49,.5,.5,.51),'seq=3')):
            record=self.fixture.audit(ticks=[(self.fixture.pub,100010.)])
        self.assertEqual(record['overall_status'],'FAIL')


class Retention(unittest.TestCase):
    def evidence(self):
        e=q.Evidence(TICKER);e.accept(snapshot());e.accept(delta())
        return e

    def request(self,e):
        e.size=q.MAX_BYTES//4
        return e.refresh(10)

    def reply(self,e):
        event=snapshot();event.update(id=e.pending,seq=e.book.seq+1)
        return event

    def test_omitted_empty_sides_are_not_keyerrors_or_quotes(self):
        for side in ('yes','no'):
            event=snapshot();del event['msg'][side+'_dollars_fp']
            book=q.Book(TICKER);book.apply(event);book.apply(delta(side=side,delta_fp='0'))
            with self.assertRaises(ValueError):book.quotes(NOW,CLOSE)
            self.assertTrue(book.valid)

    def test_empty_side_recovers_only_from_real_contiguous_update(self):
        event=snapshot();del event['msg']['no_dollars_fp']
        book=q.Book(TICKER);book.apply(event)
        with self.assertRaises(ValueError):book.quotes(NOW,CLOSE)
        book.apply(delta(side='no',price_dollars='.50',delta_fp='2'))
        self.assertEqual(book.quotes(NOW,CLOSE),(.49,.50,.50,.51))

    def test_missing_deprecated_ts_uses_real_ts_ms(self):
        event=delta();del event['msg']['ts']
        book=q.Book(TICKER);book.apply(snapshot());book.apply(event)
        self.assertEqual(book.ts_ms,NOW-200)

    def test_missing_required_timestamp_diagnostic_and_invalidation(self):
        e=self.evidence();event=delta(seq=4);del event['msg']['ts_ms']
        with self.assertRaises(q.MissingQuoteField) as caught:e.accept(event)
        self.assertEqual(caught.exception.field,'ts_ms')
        self.assertFalse(e.book.valid)
        self.assertFalse(e.events)

    def test_retention_requests_snapshot_without_discarding_current_evidence(self):
        e=self.evidence();events=e.events.copy();command=self.request(e)
        self.assertEqual(command['params']['action'],'get_snapshot')
        self.assertEqual(e.events,events)
        self.assertEqual(e.book.quotes(NOW,CLOSE),(.49,.50,.50,.51))
        self.assertIsNone(e.refresh(11))

    def test_rebase_starts_at_actual_exchange_snapshot_and_waits_for_timestamp(self):
        e=self.evidence();self.request(e);reply=self.reply(e)
        self.assertTrue(e.accept(reply));self.assertEqual(e.events,[reply])
        with self.assertRaises(ValueError):e.book.quotes(NOW,CLOSE)
        e.accept(delta(seq=5))
        p=proof();p['events']=e.events;p['identity'][2]=5
        self.assertEqual(q.replay(p,'collector',TICKER,CLOSE,NOW)[0],(.49,.50,.50,.51))

    def test_gap_cannot_be_hidden_by_rebase(self):
        e=self.evidence();self.request(e);reply=self.reply(e);reply['seq']+=1
        with self.assertRaises(ValueError):e.accept(reply)
        with self.assertRaises(ValueError):e.book.quotes(NOW,CLOSE)

    def test_rebase_rejects_cross_market_sid_and_wrong_command(self):
        for key in ('market','sid','id'):
            e=self.evidence();self.request(e);reply=self.reply(e)
            if key=='market':reply['msg']['market_ticker']='NEXT'
            else:reply[key]+=1
            with self.assertRaises(ValueError):e.accept(reply)
            self.assertFalse(e.book.valid)

    def test_duplicate_snapshot_does_not_reset_retention_or_refresh(self):
        e=q.Evidence(TICKER);event=snapshot();e.accept(event);before=e.size
        self.assertFalse(e.accept(event));self.assertEqual(e.size,before)
        self.assertEqual(len(e.events),1)

    def test_duplicate_delta_preserves_timestamp_and_size(self):
        e=self.evidence();before=e.size;e.accept(delta())
        self.assertEqual(e.size,before);self.assertEqual(e.book.ts_ms,NOW-200)

    def test_overflow_waits_for_snapshot_without_inventing_replay_base(self):
        e=self.evidence();self.request(e);e.size=q.MAX_BYTES
        e.accept(delta(seq=4));self.assertTrue(e.overflow);self.assertEqual(e.events,[])
        reply=self.reply(e);e.accept(reply)
        self.assertFalse(e.overflow);self.assertEqual(e.events,[reply])
        self.assertIsNone(e.book.ts_ms)

    def test_unresponsive_snapshot_request_fails_closed(self):
        e=self.evidence();self.request(e)
        with self.assertRaises(ValueError):e.refresh(21)
        self.assertFalse(e.book.valid)

    def test_sequenced_acknowledgement_counts_but_never_freshens(self):
        e=self.evidence();command=self.request(e)
        e.accept(dict(type='ok',id=command['id'],sid=2,seq=4,msg={'market_tickers':[TICKER]}))
        self.assertEqual(e.book.seq,4);self.assertEqual(e.book.ts_ms,NOW-200)
        e.accept(self.reply(e));e.accept(delta(seq=6))
        p=proof();p['events']=e.events;p['identity'][2]=6
        self.assertEqual(q.replay(p,'collector',TICKER,CLOSE,NOW)[0],(.49,.50,.50,.51))

    def test_reconnect_recovery_does_not_reuse_old_book(self):
        old=self.evidence();self.request(old)
        fresh=q.Evidence(TICKER)
        with self.assertRaises(ValueError):fresh.accept(delta(seq=4))
        fresh=q.Evidence(TICKER);fresh.accept(snapshot());fresh.accept(delta())
        self.assertEqual(fresh.book.seq,3);self.assertIsNone(fresh.pending)

    def test_near_close_empty_book_and_exact_rollover(self):
        e=self.evidence();e.accept(delta(seq=4,delta_fp='-21'))
        with self.assertRaises(ValueError):e.book.quotes(NOW,CLOSE)
        e.accept(delta(seq=5,delta_fp='1'))
        with self.assertRaises(ValueError):e.book.quotes(CLOSE,CLOSE)
        with self.assertRaises(ValueError):e.accept(delta(seq=6,market_ticker='NEXT'))

    def test_actual_session_many_rebases_no_reconnect_or_order_commands(self):
        provider=object.__new__(q.Provider)
        provider.lock=threading.Lock();provider.ticker=TICKER;provider.close_ms=CLOSE
        provider.book=None;provider.events=[];provider.epoch=None
        class Wire:
            def __init__(self):self.sent=[];self.seq=1;self.pending=None;self.steps=0;self.done=False
            def send(self,raw):
                command=json.loads(raw);self.sent.append(command)
                if command['cmd']=='update_subscription':self.pending=command['id']
            def recv(self,timeout):
                self.seq+=1;self.steps+=1
                if self.seq==2 or self.pending is not None:
                    event=snapshot();event['seq']=self.seq
                    if self.pending is not None:event['id']=self.pending;self.pending=None
                else:
                    event=delta(seq=self.seq);event['msg']['fixture_padding']='x'*1500
                if self.steps==80:provider.ticker='NEXT'
                return json.dumps(event)
        wire=Wire()
        import contextlib,io
        out=io.StringIO()
        with patch.object(q,'MAX_BYTES',16384),patch.object(q.time,'time',return_value=NOW/1000),contextlib.redirect_stdout(out):
            provider.session(wire,TICKER)
        self.assertEqual(out.getvalue().count('WS CONNECT'),1)
        self.assertGreater(out.getvalue().count('EVIDENCE REBASE'),10)
        self.assertEqual(sum(c['cmd']=='subscribe' for c in wire.sent),1)
        for command in wire.sent[1:]:
            self.assertEqual(command['params']['action'],'get_snapshot')
            self.assertEqual(command['params']['market_tickers'],[TICKER])
        self.assertLess(len(json.dumps(provider.events)),16384)



if __name__=='__main__':
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (Quotes,QuoteParity,Retention))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
