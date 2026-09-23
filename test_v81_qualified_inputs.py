"""Actual decoder, source adapter and publisher regressions; no credentials/network."""
import ast
import copy
from collections import defaultdict, deque
from datetime import datetime, timezone
import os
from pathlib import Path
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

import btc15_v81_qualified_inputs_v1 as inputs
from btc15_kalshi_quote_provenance_v1 import Book

NOW = datetime(2026,9,23,21,22,43,719000,tzinfo=timezone.utc).timestamp()
OPEN = datetime(2026,9,23,21,15,tzinfo=timezone.utc).timestamp()
CLOSE = OPEN + 900
TICKER = 'KXBTC15M-26SEP231730-30'


def iso(ts):return datetime.fromtimestamp(ts,timezone.utc).isoformat()


def market():
    return dict(ticker=TICKER,open_time=iso(OPEN),close_time=iso(CLOSE),floor_strike=84362.95,
                yes_bid_dollars='.60',yes_ask_dollars='.61',no_bid_dollars='.39',no_ask_dollars='.40')


def quote(now=NOW):
    return dict(ticker=TICKER,epoch='ws-1',market_id='official-market',sid=1,sequence=90,
                source_ts_ms=int((now-.2)*1000),validated_at_ms=int(now*1000),
                transport='timestamped_contiguous_ws',up_bid=.43,up_ask=.44,down_bid=.56,down_ask=.57)


def brti(now=NOW):
    return dict(value=84345.17,source_ts_ms=int((now-2)*1000),owner_epoch='owner-v2',sequence=10,
                status='PRIMARY_OK',clean_for_qualification=True)


def make_row(now=NOW):
    q=quote(now);b=brti(now)
    p=dict(schema=inputs.SCHEMA,ticker=TICKER,open_ts=OPEN,close_ts=CLOSE,target=84362.95,
           quote=q,brti=b,signal_only=True,orders=False)
    return dict(ts=now,ticker=TICKER,left=CLOSE-now,target=84362.95,btc=84349.09,brti=b['value'],
                input_provenance=p,**{k:q[k]for k in ('up_bid','up_ask','down_bid','down_ask')})


def publisher_scope(clock):
    tree=ast.parse(Path('v81_30_45_live_feed.py').read_text())
    names={'publish_signal','publish_wait','_primary_reason'}
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    scope=dict(STATE={},STATE_LOCK=threading.Lock(),require_qualified=inputs.require_qualified,
               InputUnavailable=inputs.InputUnavailable,
               time=types.SimpleNamespace(time=lambda:clock[0],strftime=time.strftime,gmtime=time.gmtime))
    exec(compile(ast.Module(body=functions,type_ignores=[]),'<actual publisher>','exec'),scope)
    return scope


class Adapter(unittest.TestCase):
    def setUp(self):
        self.clock=[NOW];self.m=market();self.q=quote();self.b=brti()
        self.provider=Mock();self.provider.frame.side_effect=lambda *args:copy.deepcopy(self.q)
        response=Mock();response.json.return_value={'price':'84349.09','time':iso(NOW-.6)}
        self.get=Mock(return_value=response);self.read=Mock(side_effect=lambda:copy.deepcopy(self.b))
        self.adapter=inputs.QualifiedInputs(lambda:copy.deepcopy(self.m),lambda m:m['floor_strike'],
            self.get,'https://btc.invalid',provider=self.provider,brti_read=self.read,clock=lambda:self.clock[0])
        self.env=patch.dict(os.environ,BTC15_USE_SHARED_BRTI='1');self.env.start();self.addCleanup(self.env.stop)

    def test_captured_40c_rest_entry_is_replaced_by_57c_ws_ask(self):
        row=self.adapter.snapshot()
        self.assertEqual(row['down_ask'],.57)
        self.assertEqual(row['input_provenance']['quote']['source_ts_ms'],self.q['source_ts_ms'])
        self.assertEqual(row['input_provenance']['brti']['source_ts_ms'],self.b['source_ts_ms'])
        tree=ast.parse(Path('v81_30_45_live_feed.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='quality_30_45')
        scope={'_fresh':lambda f:True,'evidence_route':lambda f:('CORE',1.3)}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<actual frozen gate>','exec'),scope)
        strong={'v4':True,'structure_ok':True}
        self.assertEqual(scope['quality_30_45'](dict(row,down_ask=.4),'DOWN',strong),(True,'CORE'))
        self.assertEqual(scope['quality_30_45'](row,'DOWN',strong),(False,None))

    def test_rest_quotes_missing_does_not_remove_valid_ws_opportunity(self):
        for k in tuple(self.m):
            if k.endswith('_dollars'):del self.m[k]
        self.q.update(up_bid=.34,up_ask=.35,down_bid=.65,down_ask=.66)
        self.assertEqual(self.adapter.snapshot()['up_ask'],.35)

    def test_no_ws_fails_closed_without_rest_or_brti_fallback(self):
        self.provider.frame.return_value=None;self.provider.frame.side_effect=None
        with self.assertRaisesRegex(inputs.InputUnavailable,'TIMESTAMPED_QUOTES'):self.adapter.snapshot()
        self.read.assert_not_called();self.get.assert_not_called()

    def test_shared_owner_required(self):
        with patch.dict(os.environ,BTC15_USE_SHARED_BRTI='0'):
            with self.assertRaisesRegex(inputs.InputUnavailable,'SHARED_BRTI_REQUIRED'):self.adapter.snapshot()
        self.read.assert_not_called()

    def test_refresh_quotes_after_network_wait(self):
        updated=quote();updated.update(down_ask=.61,down_bid=.60,up_bid=.39,up_ask=.40)
        self.provider.frame.side_effect=[quote(),updated]
        self.assertEqual(self.adapter.snapshot()['down_ask'],.61)

    def test_network_wait_cannot_turn_old_brti_into_fresh(self):
        def late():self.clock[0]+=4;return self.b
        self.read.side_effect=late
        with self.assertRaisesRegex(inputs.InputUnavailable,'BRTI_SOURCE'):self.adapter.snapshot()

    def test_fixed_target_or_clock_drift_rejected(self):
        self.adapter.snapshot();self.m['floor_strike']+=.01
        with self.assertRaisesRegex(inputs.InputUnavailable,'FIXED_TARGET'):self.adapter.snapshot()

    def test_cross_close_and_invalid_official_window_rejected(self):
        for changes in ({'open_time':iso(OPEN+1)},{'close_time':iso(CLOSE+900)},{'ticker':'KXOTHER'}):
            with self.subTest(changes=changes):
                self.m=market();self.m.update(changes)
                with self.assertRaises(inputs.InputUnavailable):self.adapter.snapshot()
        self.m=market();self.clock[0]=CLOSE
        with self.assertRaises(inputs.InputUnavailable):self.adapter.snapshot()


class SourceAge(unittest.TestCase):
    def test_brti_boundary_future_missing_not_receipt_time(self):
        for age,ok in [(5,True),(5.001,False),(-.001,False)]:
            row=make_row();row['input_provenance']['brti']['source_ts_ms']=int(NOW*1000-age*1000)
            if ok:inputs.require_qualified(row,NOW)
            else:
                with self.assertRaises(inputs.InputUnavailable):inputs.require_qualified(row,NOW)
        row=make_row();del row['input_provenance']['brti']['source_ts_ms']
        with self.assertRaises(inputs.InputUnavailable):inputs.require_qualified(row,NOW)

    def test_quote_age_and_source_ticker(self):
        for changes in ({'source_ts_ms':int(NOW*1000)-6001},{'source_ts_ms':int(NOW*1000)+1},
                        {'ticker':'OLD'},{'transport':'REST'},{'epoch':None}):
            row=make_row();row['input_provenance']['quote'].update(changes)
            with self.subTest(changes=changes),self.assertRaises(inputs.InputUnavailable):inputs.require_qualified(row,NOW)

    def test_row_prices_must_match_exact_provenance(self):
        row=make_row();row['down_ask']=.40
        with self.assertRaisesRegex(inputs.InputUnavailable,'QUOTE_VALUE_MISMATCH'):inputs.require_qualified(row,NOW)

    def test_current_publication_cannot_renew_expired_sources(self):
        row=make_row();clock=[NOW];scope=publisher_scope(clock)
        scope['publish_signal'](row,'UP','CORE',.44,.43,NOW)
        state=scope['STATE'];old=copy.deepcopy(state)
        self.assertTrue(inputs.publication_view(state,NOW+.1)['active'])
        result=inputs.publication_view(state,NOW+3.01)
        self.assertFalse(result['active']);self.assertEqual(result['status'],'WAIT')
        self.assertEqual(state,old)
        self.assertEqual(result['generated_utc'],old['generated_utc'])
        self.assertEqual(result['last_signal_event'],old['last_signal_event'])

    def test_stale_publication_and_horizon_fail_closed(self):
        clock=[NOW];scope=publisher_scope(clock);row=make_row()
        scope['publish_signal'](row,'UP','CORE',.44,.43,NOW)
        state=copy.deepcopy(scope['STATE']);state['generated_utc']=iso(NOW-3.501)
        self.assertFalse(inputs.publication_view(state,NOW)['active'])
        state=copy.deepcopy(scope['STATE']);state['last_signal_event']['signal_ts']=NOW-180.001
        self.assertFalse(inputs.publication_view(state,NOW)['active'])


class DecoderAndRecovery(unittest.TestCase):
    def provider(self):
        p=inputs.QuoteProvider.__new__(inputs.QuoteProvider)
        p.lock=threading.Lock();p.ticker=TICKER;p.close_ms=int(CLOSE*1000);p.events=[];p.epoch='ws-1'
        p.book=Book(TICKER)
        p.book.apply(dict(type='orderbook_snapshot',sid=1,seq=1,msg=dict(market_ticker=TICKER,
            market_id='official-market',yes_dollars_fp=[['.43','10']],no_dollars_fp=[['.56','10']])))
        return p

    def delta(self,seq=2,now=NOW):
        return dict(type='orderbook_delta',sid=1,seq=seq,msg=dict(market_ticker=TICKER,
            market_id='official-market',side='yes',price_dollars='.43',delta_fp='1',ts_ms=int((now-.2)*1000)))

    def test_snapshot_only_gap_and_reconnect(self):
        p=self.provider()
        with patch('btc15_v81_qualified_inputs_v1.time.time',return_value=NOW):
            self.assertIsNone(p.frame(TICKER,int(CLOSE*1000)))
            p.book.apply(self.delta());self.assertEqual(p.frame(TICKER,int(CLOSE*1000))['down_ask'],.57)
            with self.assertRaises(ValueError):p.book.apply(self.delta(seq=4))
            self.assertIsNone(p.frame(TICKER,int(CLOSE*1000)))
            p=self.provider();p.epoch='ws-2';p.book.apply(self.delta())
            self.assertEqual(p.frame(TICKER,int(CLOSE*1000))['epoch'],'ws-2')

    def test_rollover_resets_without_ticker_leakage(self):
        p=self.provider();p.book.apply(self.delta())
        self.assertIsNone(p.frame('KXBTC15M-NEXT',int((CLOSE+900)*1000)))
        self.assertIsNone(p.book);self.assertEqual(p.ticker,'KXBTC15M-NEXT')

    def test_empty_book_cannot_be_replaced_by_rest(self):
        p=self.provider();p.book.apply(self.delta());p.book.levels['yes'].clear()
        with patch('btc15_v81_qualified_inputs_v1.time.time',return_value=NOW):
            self.assertIsNone(p.frame(TICKER,int(CLOSE*1000)))

    def test_duplicate_does_not_renew_quote_timestamp(self):
        p=self.provider();event=self.delta();p.book.apply(event);self.assertFalse(p.book.apply(event))
        with patch('btc15_v81_qualified_inputs_v1.time.time',return_value=NOW+6):
            self.assertIsNone(p.frame(TICKER,int(CLOSE*1000)))

    def test_actual_loop_failure_clears_confirmation_publishes_wait(self):
        tree=ast.parse(Path('v81_30_45_live_feed.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='loop')
        class EndIteration(BaseException):pass
        clock=[NOW];scope=publisher_scope(clock);wait=Mock()
        scope.update(active={'ticker':TICKER},confirm=defaultdict(deque,{'old':deque([NOW])}),
            snap=Mock(side_effect=inputs.InputUnavailable('TIMESTAMPED_QUOTES_UNAVAILABLE')),
            _qualified_inputs=types.SimpleNamespace(last_ticker=TICKER),POLL=1.,publish_wait=wait)
        scope['time'].sleep=Mock(side_effect=EndIteration)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<actual loop>','exec'),scope)
        with self.assertRaises(EndIteration):scope['loop']()
        self.assertFalse(scope['confirm'])
        wait.assert_called_once_with(TICKER,reason='TIMESTAMPED_QUOTES_UNAVAILABLE')
        self.assertEqual(scope['active'],{'ticker':TICKER})


if __name__=='__main__':unittest.main()
