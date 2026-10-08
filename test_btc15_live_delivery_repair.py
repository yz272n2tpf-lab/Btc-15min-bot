"""Integrated delivery regressions; synthetic sources, no live/order access."""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch

from btc15_v2_product.bootstrap import Pool, Preparation, PreparedProvider
from btc15_v2_product.delivery import finish
from btc15_v2_product.admin import LOCAL
from btc15_v2_product.directional import Directional
from btc15_v2_product.journal import ProcessorEnvelope
from btc15_brti_delivery_v1 import Delivery
from test_btc15_v2_product_r1 import market, book_for, InertProvider, OPEN
from test_btc15_integrated_finish import frame


class EndRun(BaseException):
    pass


class DeliveryRepair(unittest.TestCase):
    def setUp(self):
        self.at=OPEN+870
        self.pool=Pool(InertProvider,lambda:self.at)
        self.pool.select(market(),80000)
        self.owner=self.pool.current
        self.owner.proof_writer=SimpleNamespace(submit=lambda *_:True)
        self.addCleanup(lambda:setattr(LOCAL,'attempt',None))

    def test_current_stream_survives_repeated_preparation_through_official_close(self):
        next_market=market(OPEN+900)
        old=self.owner
        for second in range(870,900):
            self.at=OPEN+second
            book=book_for(old,self.at)
            self.pool.prepare(next_market)
            self.assertIs(self.pool.current,old)
            self.assertIs(old.book,book)
            with patch('btc15_v2_product.bootstrap.time.time',return_value=self.at):
                values=self.pool.consume(old.ticker,datetime.fromtimestamp(self.at,timezone.utc).isoformat(),old.close_ms)
            self.assertEqual(values,(.34,.35,.65,.66))
            self.assertEqual(self.pool.last_product_quote['ticker'],market()['ticker'])
        with self.assertRaisesRegex(ValueError,'NO_PREOPEN'):
            self.pool.select(next_market,80001)
        self.at=OPEN+900
        self.pool.select(next_market,80001)
        self.assertIsNot(self.pool.current,old)
        self.assertIsNone(self.pool.consume(old.ticker,'old',old.close_ms))
        fresh=self.pool.current
        fresh.proof_writer=old.proof_writer
        book_for(fresh,self.at-.1)
        with patch('btc15_v2_product.bootstrap.time.time',return_value=self.at):
            self.assertIsNone(self.pool.consume(fresh.ticker,'before-open',fresh.close_ms))
        book_for(fresh,self.at+.2)
        with patch('btc15_v2_product.bootstrap.time.time',return_value=self.at+.2):
            self.assertIsNotNone(self.pool.consume(fresh.ticker,'after-open',fresh.close_ms))

    def test_real_connection_runner_does_not_connect_unopened_or_reset_current(self):
        current_book=book_for(self.owner,self.at)
        future=self.pool.prepare(market(OPEN+900))
        connections=[]
        class Connection:
            def __enter__(inner):
                connections.append(self.at)
                self.assertIs(self.pool.current,self.owner)
                self.assertIs(self.owner.book,current_book)
                return inner
            def __exit__(inner,*args):return False
        def session(ws,ticker):
            self.assertEqual(ticker,market(OPEN+900)['ticker'])
            raise EndRun()
        future.session=session
        def sleep(seconds):self.at+=seconds
        with patch('btc15_v2_product.bootstrap.time.time',side_effect=lambda:self.at), \
             patch('btc15_v2_product.bootstrap.time.sleep',side_effect=sleep), \
             patch('websockets.sync.client.connect',return_value=Connection()), \
             patch('btc15_kalshi_parity_shadow_v1.auth_headers',return_value={}):
            with self.assertRaises(EndRun):future.run()
        self.assertEqual(len(connections),1)
        self.assertGreaterEqual(connections[0],OPEN+900)
        self.assertIs(self.owner.book,current_book)

    def test_connection_failures_back_off_per_owner_without_accepting_bad_book(self):
        self.at=OPEN+905
        self.pool.select(market(OPEN+900),80000)
        p=self.pool.current
        attempts=[]
        def connect(*a,**kw):
            attempts.append(self.at)
            if len(attempts)==5:raise EndRun()
            raise ValueError('cross-market or missing identity')
        def sleep(seconds):self.at+=seconds
        with patch('btc15_v2_product.bootstrap.time.time',side_effect=lambda:self.at), \
             patch('btc15_v2_product.bootstrap.time.monotonic',side_effect=lambda:self.at), \
             patch('btc15_v2_product.bootstrap.time.sleep',side_effect=sleep), \
             patch('websockets.sync.client.connect',side_effect=connect), \
             patch('btc15_kalshi_parity_shadow_v1.auth_headers',return_value={}):
            with self.assertRaises(EndRun):p.run()
        gaps=[b-a for a,b in zip(attempts,attempts[1:])]
        for actual,minimum in zip(gaps,[1,2,4,8]):self.assertGreaterEqual(actual,minimum-.001)
        self.assertIsNone(p.book)
        self.assertIsNone(p.last_product_quote)

    def test_active_metadata_refresh_uses_exact_identity_and_never_next_list(self):
        calls=[]
        def get(path,params=None):
            calls.append(path)
            return {'market':market()}
        prep=Preparation(get,lambda m:m['floor_strike'],self.pool,lambda:self.at)
        selected=prep.select(lambda:self.fail('active contract must not rediscover from list'))
        self.assertEqual(selected['ticker'],self.owner.ticker)
        self.assertEqual(calls,['/trade-api/v2/markets/'+self.owner.ticker])
        prep.get=lambda *a,**k:{'market':market(OPEN+900)}
        with self.assertRaisesRegex(ValueError,'FIXED_OFFICIAL_IDENTITY_CHANGED'):
            prep.select(lambda:None)
        self.assertIs(self.pool.current,self.owner)

    def test_quote_wait_reports_fresh_brti_separately_and_complete_frame_recovers(self):
        at=self.at
        delivery=Delivery()
        delivery.accept(80020,at-1,at-.2,'upstream')
        source=datetime.fromtimestamp(at-1,timezone.utc)
        received=datetime.fromtimestamp(at-.2,timezone.utc)
        ns={'_brti_delivery':delivery,'_btc_spot_provenance':dict(source_utc=source,observed_utc=received)}
        offered=[]
        LOCAL.attempt=dict(outcome='QUOTE_WAIT')
        with patch('btc15_v2_product.delivery.time.time',return_value=at):
            finish(ns,self.pool,SimpleNamespace(offer=offered.append))
        self.assertEqual(offered[0]['reason'],'QUOTE_SOURCE_UNAVAILABLE')
        self.assertEqual(offered[0]['delivery']['brti'],'CURRENT')
        self.assertEqual(offered[0]['delivery']['brti_source_ts'],at-1)
        engine=Directional();engine.restore({})
        envelope=ProcessorEnvelope(engine,'main')
        _,_,view=envelope.process((offered[0],None),at)
        self.assertEqual(view['status'],'UNAVAILABLE')
        self.assertNotIn('expires_at',view)
        self.assertEqual(view['delivery']['brti'],'CURRENT')
        fresh=frame(offset=305,sequence=1)
        _,_,recovered=envelope.process((fresh,None),fresh['captured_ts'])
        self.assertIn(recovered['status'],('AVAILABLE','PASS'))
        self.assertLessEqual(recovered['expires_at'],fresh['brti']['cf_ts']+5)
        for stage,reason in [('get_active_market','OFFICIAL_MARKET_UNAVAILABLE'),('get_btc_spot','BTC_SOURCE_UNAVAILABLE')]:
            LOCAL.attempt=dict(outcome='NATIVE_EXCEPTION',failed_stage=stage)
            with patch('btc15_v2_product.delivery.time.time',return_value=at):finish(ns,self.pool,SimpleNamespace(offer=offered.append))
            self.assertEqual(offered[-1]['reason'],reason)


if __name__=='__main__':unittest.main()
