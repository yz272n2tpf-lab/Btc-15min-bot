import ast
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
import zlib

import btc15_ladder_product_v1 as product
from btc15_ladder_journal_v1 import Journal,Worker,view


OPEN=datetime(2026,10,3,20,tzinfo=timezone.utc).timestamp()


def frame(offset=300,sequence=1,p=.80,ask=.35,side='UP'):
    at=OPEN+offset
    up=p if side=='UP' else 1-p
    prices=[ask-.01,ask,1-ask-.01,1-ask] if side=='UP' else [1-ask-.01,1-ask,ask-.01,ask]
    gap=80 if side=='UP' else -80
    return dict(kind='NATIVE_DECISION',candidate=product.CANDIDATE,native_epoch='epoch',native_sequence=sequence,
        captured_ts=at,feature_cutoff=at-.05,contract='KXBTC15M-26OCT031615-15',official_open=OPEN,
        official_close=OPEN+900,target=80000.,btc_price=80000.+gap,btc_source=at-.2,btc_received=at-.1,
        fair=dict(side=side,fair=p,ask=ask,edge=p-ask,up_fair=up,down_fair=1-up,
                  dist_over_range5=2.),
        brti=dict(value=80000.+gap,cf_ts=at-1,ready=True,
                  delivery=dict(owner_epoch='b',observed_ts=at-.5)),
        quote=dict(ticker='KXBTC15M-26OCT031615-15',source_time=product.iso(at-.05),close_ms=int((OPEN+900)*1000),
            epoch='q',consumed_ms=int((at-.02)*1000),exchange_ts_ms=int((at-.1)*1000),sid=1,seq=sequence,
            market_id='market',quotes=prices),
        up_bid=prices[0],up_ask=prices[1],down_bid=prices[2],down_ask=prices[3],artifact='artifact',weights='weights')


class DirectionalTests(unittest.TestCase):
    def setUp(self):
        self.engine=product.Directional();self.engine.restore({})

    def step(self,**kw):
        f=frame(**kw);return self.engine.process(f,f['captured_ts']+.01)

    def test_early_does_not_need_ready_final(self):
        record,state,out=self.step()
        self.assertEqual(record['event'],'BUY');self.assertFalse(out['final']['ready'])
        self.assertEqual(out['origin']['original_ask'],.35)

    def test_restored_origin_confirm_then_protect(self):
        _,state,buy=self.step()
        engine=product.Directional();engine.restore(state)
        f=frame(offset=425,sequence=2,p=.95,ask=.72)
        record,state,out=engine.process(f,f['captured_ts']+.01)
        self.assertEqual(record['event'],'HOLD');self.assertEqual(out['warning'],'CONFIRMED')
        self.assertEqual(out['final']['early_origin_id'],buy['origin']['origin_id'])
        f=frame(offset=430,sequence=3,p=.65,ask=.72,side='DOWN')
        _,_,out=engine.process(f,f['captured_ts']+.01)
        self.assertEqual(out['warning'],'PROTECT');self.assertEqual(out['origin'],buy['origin'])
        self.assertIsNone(out['exit_guidance'])

    def test_protect_stays_latched(self):
        self.step();self.step(offset=425,sequence=2,p=.95,ask=.75)
        self.step(offset=430,sequence=3,p=.6,ask=.75,side='DOWN')
        _,_,out=self.step(offset=435,sequence=4,p=.95,ask=.75)
        self.assertEqual(out['early']['guidance'],'PROTECT')

    def test_pass_has_no_fake_origin(self):
        r,_,out=self.step(p=.6,ask=.49)
        self.assertEqual(out['status'],'PASS');self.assertIsNone(out['origin']);self.assertIsNone(r['event'])

    def test_two_minute_entry_is_actual_gate(self):
        _,_,out=self.step(offset=770)
        self.assertEqual(out['early']['guidance'],'BUY')

    def test_down_original_ask(self):
        _,_,out=self.step(side='DOWN')
        self.assertEqual(out['origin']['side'],'DOWN');self.assertEqual(out['origin']['original_ask'],.35)

    def test_duplicate_not_second_buy(self):
        self.step();r,_,out=self.step()
        self.assertEqual(out['status'],'UNAVAILABLE');self.assertNotIn('event',r)

    def test_failed_sources_cannot_create_origin(self):
        cases=[('future_btc',lambda f:f.update(btc_received=f['captured_ts']+1)),
            ('stale_brti',lambda f:f['brti'].update(cf_ts=f['captured_ts']-5.01)),
            ('future_brti',lambda f:f['brti'].update(cf_ts=f['captured_ts']+1)),
            ('stale_quote',lambda f:f['quote'].update(exchange_ts_ms=int((f['captured_ts']-6.1)*1000))),
            ('wrong_contract',lambda f:f['quote'].update(ticker='OTHER')),
            ('quote_mismatch',lambda f:f.update(up_ask=.33)),
            ('wrong_window',lambda f:f.update(official_open=OPEN+1)),
            ('model_missing',lambda f:f.update(fair=None))]
        for name,mutation in cases:
            with self.subTest(name=name):
                f=frame();mutation(f);r,_,out=self.engine.process(f,f['captured_ts']+.01)
                self.assertEqual(out['status'],'UNAVAILABLE');self.assertIsNone(out['origin'])

    def test_outage_keeps_origin_without_false_warning(self):
        _,_,buy=self.step();f=frame(offset=305,sequence=2);f['brti']['ready']=False
        r,_,out=self.engine.process(f,f['captured_ts']+.01)
        self.assertEqual(out['status'],'UNAVAILABLE');self.assertEqual(out['origin'],buy['origin'])
        self.assertNotIn('event',r)

    def test_rollover_not_exit_or_reentry(self):
        self.step();f=frame(offset=1205,sequence=2,p=.6,ask=.6)
        f.update(official_open=OPEN+900,official_close=OPEN+1800,contract='KXBTC15M-26OCT031630-30')
        f['quote'].update(ticker=f['contract'],close_ms=int(f['official_close']*1000))
        r,_,out=self.engine.process(f,f['captured_ts']+.01)
        self.assertEqual(out['status'],'PASS');self.assertIsNone(out['origin'])

    def test_phase_and_flip_probability(self):
        for offset,phase in [(590,'NORMAL'),(605,'5M_CAUTION'),(725,'3M_GUARD')]:
            e=product.Directional();e.restore({});f=frame(offset=offset)
            _,_,out=e.process(f,f['captured_ts']+.01)
            self.assertEqual(out['phase'],phase);self.assertAlmostEqual(out['flip_risk_pct'],20)

    def test_final_stays_early(self):
        _,_,out=self.step(offset=421,p=.95,ask=.9)
        self.assertTrue(out['final']['ready']);self.assertIsNone(out['origin'])


class JournalTests(unittest.TestCase):
    def test_durable_roundtrip_restart_and_expiry(self):
        with tempfile.TemporaryDirectory() as d:
            e=product.Directional();e.restore({});f=frame();r,state,out=e.process(f,f['captured_ts']+.01)
            j=Journal(Path(d)/'test.sqlite3','main');self.assertEqual(j.commit(r,state),1);j.close()
            j=Journal(Path(d)/'test.sqlite3','main');self.assertEqual(j.get('state')['origin']['original_ask'],.35)
            row=j.db.execute('SELECT sha256,body FROM events').fetchone()
            raw=zlib.decompress(row[1]);self.assertEqual(hashlib.sha256(raw).hexdigest(),row[0]);j.close()
            from btc15_ladder_journal_v1 import atomic_json
            atomic_json(Path(d)/'main.json',out)
            self.assertEqual(view(d,'main',f['captured_ts']+.1)['status'],'AVAILABLE')
            self.assertEqual(view(d,'main',f['captured_ts']+6)['status'],'UNAVAILABLE')

    def test_worker_no_missing_record(self):
        with tempfile.TemporaryDirectory() as d:
            now=OPEN+301
            w=Worker(d,'main',product.Directional(),clock=lambda:now)
            self.assertTrue(w.offer(frame()))
            w.queue.join()
            self.assertIsNone(w.failed);self.assertEqual(w.written,1)
            self.assertEqual(view(d,'main',now)['journal']['sequence'],1)
            w.queue.put(None);w.thread.join(2)


class IntegrationTests(unittest.TestCase):
    def test_frozen_source_identity(self):
        raw=Path('bot_two_output_build_v4_13_profit_protection_shadow.py').read_bytes()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
                         'f547ab4238592910ed76fee61870cd18714d09f0')

    def test_native_quote_witness_not_later_book(self):
        src=Path('btc15_kalshi_quote_provenance_v1.py').read_text()
        self.assertIn('self.last_product_quote = dict',src)
        src=Path('btc15_ladder_product_v1.py').read_text()
        self.assertNotIn('provider.book',src);self.assertNotIn('requests.',src)

    def test_generated_runtime_compiles(self):
        import btc15_information_install_v1 as installer
        with tempfile.TemporaryDirectory() as d:
            installer.assemble(Path(d))
            server=(Path(d)/'BTC15_DASHBOARD_LIVE_SERVER_V1.py').read_text()
            self.assertIn('serve_ladders(self)',server)
            self.assertIn('/ladders/panel.js',(Path(d)/'BTC_Kalshi_App_Live_v13.html').read_text())


if __name__=='__main__':unittest.main()
