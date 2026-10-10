"""Focused native entry/management checks; no shadow or performance claims."""
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile
import unittest

from btc15_v2_product.directional import Directional,CANDIDATE
from btc15_v2_product.early_entry import ARTIFACT,WEIGHTS,POLICY,FeeCache
from btc15_v2_product.early_management import install_features
from btc15_ladder_journal_v1 import Journal,packed
from test_btc15_ladder_completion_v1 import frame


def value_frame(sequence=1,ask=.53,p=.83,side='UP',offset=None,momentum=None):
    f=frame(sequence=sequence,offset=540+(sequence-1)*5 if offset is None else offset,
            ask=ask,p=p,side=side)
    f.update(candidate=CANDIDATE,artifact=ARTIFACT,weights=WEIGHTS,
        fee_schedule=dict(series='KXBTC15M',fee_type='quadratic',multiplier=1.,
                          observed_ts=f['captured_ts']-2,source='/trade-api/v2/series/KXBTC15M'))
    f['btc_price']+=(sequence-1)*2*(1 if side=='UP' else -1)
    f['brti']['value']=f['btc_price']
    sign=1 if side=='UP' else -1
    f['model_features']=dict(target=f['target'],official_open=f['official_open'],feature_cutoff=f['feature_cutoff'],
        values=dict(move1=sign*10 if momentum is None else momentum,move5=sign*30,
                    range5=100,vol5=.0003,current_coinbase_close=f['btc_price']))
    return f


def step(e,f):return e.process(f,f['captured_ts']+.001)


class SupportedEarly(unittest.TestCase):
    def engine(self):
        e=Directional();e.restore({});return e

    def pair(self,**kwargs):
        e=self.engine();a=step(e,value_frame(**kwargs));b=step(e,value_frame(sequence=2,**kwargs))
        return e,a,b

    def test_53_at_83_first_frame_both_sides_real_immutable_origins(self):
        for side in ('UP','DOWN'):
            e=self.engine();r,s,v=step(e,value_frame(side=side))
            self.assertEqual(r['event'],'BUY');self.assertEqual(v['early']['guidance'],'ENTER')
            self.assertFalse(v['final']['ready']);self.assertEqual(v['origin']['entry_policy'],POLICY)
            self.assertEqual(v['origin']['original_ask'],.53);self.assertEqual(v['origin']['side'],side)
            self.assertEqual(v['early_opportunity']['status'],'QUALIFIED')
            self.assertEqual(v['final']['helper']['origin_id'],v['origin']['origin_id'])
            self.assertTrue(v['origin']['qualification']['ready']);self.assertIsNone(v['origin']['manual_fill'])
            self.assertFalse(v['orders']);self.assertLess(len(packed(r)),65536)
            self.assertGreater(v['origin']['qualification']['economics']['round_trip_stress_value_margin'],0)
            with tempfile.TemporaryDirectory() as tmp:
                j=Journal(Path(tmp)/'main.sqlite3','main');j.commit(r,s);saved=j.get('state');j.close()
                restored=self.engine();restored.restore(saved)
                _,_,held=step(restored,value_frame(sequence=2,ask=.70,side=side))
                self.assertEqual(held['origin'],v['origin']);self.assertEqual(held['early']['guidance'],'HOLD')

    def test_no_universal_price_probability_window_or_count_gate(self):
        for ask,p in ((.46,.7),(.5,.75),(.53,.83),(.61,.8),(.70,.85),(.80,.9),(.95,.99)):
            r,_,v=step(self.engine(),value_frame(ask=ask,p=p))
            self.assertEqual(r['event'],'BUY',(ask,p))
        for offset in (10,60,300,540,790,895):
            r,_,v=step(self.engine(),value_frame(offset=offset))
            self.assertEqual(r['event'],'BUY',offset)
        _,_,v=step(self.engine(),value_frame(ask=.99,p=.995))
        self.assertIsNone(v['origin']);self.assertFalse(v['early']['qualification']['conditions']['positive_round_trip_value'])

    def test_positive_ev_alone_cannot_create_call(self):
        mutations={
            'unknown_model':lambda f:f.update(artifact='other'),
            'wrong_target_side':lambda f:f.update(btc_price=f['target']-80),
            'neutral_brti':lambda f:f['brti'].update(value=f['target']),
            'momentum_against':lambda f:f['model_features']['values'].update(move1=-1),
            'trend_against':lambda f:f['model_features']['values'].update(move5=-1),
            'features_missing':lambda f:f.pop('model_features'),
            'features_future':lambda f:f['model_features'].update(feature_cutoff=f['captured_ts']+1),
            'features_foreign_target':lambda f:f['model_features'].update(target=f['target']+1),
            'volatility_invalid':lambda f:f['model_features']['values'].update(vol5=-1),
            'fees_missing':lambda f:f.pop('fee_schedule'),
            'fees_expired':lambda f:f['fee_schedule'].update(observed_ts=f['captured_ts']-121),
            'fees_future':lambda f:f['fee_schedule'].update(observed_ts=f['captured_ts']+1),
            'fees_unsupported':lambda f:f['fee_schedule'].update(fee_type='flat'),
            'high_fee':lambda f:f['fee_schedule'].update(multiplier=30),
        }
        for name,mutate in mutations.items():
            with self.subTest(name=name):
                f=value_frame();mutate(f);r,_,v=step(self.engine(),f)
                self.assertIsNone(v['origin']);self.assertNotEqual(r.get('event'),'BUY')

    def test_all_management_states_without_final_lock(self):
        e=self.engine();_,_,entry=step(e,value_frame())
        _,_,held=step(e,value_frame(2,ask=.7));self.assertEqual(held['early']['guidance'],'HOLD')
        _,_,watch=step(e,value_frame(3,ask=.7,p=.8));self.assertEqual(watch['early']['guidance'],'WATCH')
        _,_,protect=step(e,value_frame(4,ask=.68,p=.78,momentum=-10))
        self.assertEqual(protect['early']['guidance'],'PROTECT');self.assertFalse(protect['final']['ready'])
        r,s,exited=step(e,value_frame(5,ask=.55,p=.6,side='DOWN'))
        self.assertEqual(exited['early']['guidance'],'EXIT');self.assertFalse(exited['final']['ready'])
        self.assertEqual(r['event'],'EXIT');self.assertEqual(exited['origin'],entry['origin'])
        t=exited['terminal'];self.assertEqual(t['reason'],'DIRECTIONAL_THESIS_INVALIDATED')
        self.assertAlmostEqual(t['executable_exit_bid'],.44);self.assertLess(t['economics']['net_liquidation_scenario'],0)
        self.assertIsNone(t['realized_profit']);self.assertIsNone(t['manual_fill']);self.assertFalse(t['closure_confirmed'])
        self.assertLess(len(packed(r)),65536)
        restored=self.engine();restored.restore(s)
        r,_,recovery=step(restored,value_frame(6,ask=.75))
        self.assertEqual(recovery['early']['guidance'],'EXIT');self.assertEqual(recovery['terminal'],t)
        self.assertIsNone(r['event']);self.assertEqual(recovery['origin'],entry['origin'])
        damaged=deepcopy(s);damaged['terminal']['origin_id']='WRONG'
        with self.assertRaisesRegex(ValueError,'TERMINAL_CONFLICT'):self.engine().restore(damaged)

    def test_favorable_sale_economics_do_not_force_directional_exit(self):
        e=self.engine();step(e,value_frame())
        _,_,v=step(e,value_frame(2,ask=.80,p=.75,momentum=-10))
        self.assertEqual(v['early']['guidance'],'WATCH')
        self.assertFalse(v['final']['ready'])
        self.assertIsNone(v['terminal'])
        self.assertGreater(v['management']['economics']['net_liquidation_scenario'],0)
        self.assertEqual(v['management']['reason'],
            'FAVORABLE_LIQUIDATION_ECONOMICS_DIRECTIONAL_THESIS_NOT_INVALIDATED')

    def test_no_exit_from_clock_outage_missing_features_or_repeated_quote(self):
        for mode in ('clock','brti','book','features','repeated','zero_bid'):
            e=self.engine();_,_,entry=step(e,value_frame());f=value_frame(2,side='DOWN',p=.6)
            if mode=='clock':f=value_frame(2,offset=898)
            if mode=='brti':f['brti']['ready']=False
            if mode=='book':f['quote']['ticker']='OTHER'
            if mode=='features':f.pop('model_features')
            if mode=='repeated':f['quote']['exchange_ts_ms']=entry['origin']['entry_provenance']['quote']['exchange_ts_ms']
            if mode=='zero_bid':f['up_bid']=0;f['quote']['quotes'][0]=0
            r,_,v=step(e,f)
            self.assertNotEqual(v.get('early',{}).get('guidance'),'EXIT',mode)
            self.assertIsNone(e.terminal,mode);self.assertNotEqual(r.get('event'),'EXIT',mode)
            self.assertEqual(v['origin'],entry['origin'])

    def test_exit_releases_at_contract_rollover_without_fabricated_fill(self):
        e=self.engine();step(e,value_frame());step(e,value_frame(2,side='DOWN',p=.6))
        f=value_frame(3,p=.6,ask=.9,offset=1205)
        f.update(official_open=f['official_open']+900,official_close=f['official_close']+900,contract='KXBTC15M-26OCT031630-30')
        f['quote'].update(ticker=f['contract'],close_ms=int(f['official_close']*1000))
        r,_,v=step(e,f);self.assertIsNone(v['origin']);self.assertIsNone(v['terminal']);self.assertIsNone(r['event'])

    def test_historical_origins_remain_independent_and_compatible(self):
        f=frame(ask=.35,p=.8);f['candidate']=CANDIDATE
        r,s,v=step(self.engine(),f);self.assertEqual(r['event'],'BUY');self.assertFalse(v['final']['ready'])
        self.assertEqual(v['origin']['entry_policy'],'HISTORICAL_TIER1')
        s.pop('terminal');e=self.engine();e.restore(s)
        _,_,v=step(e,value_frame(2));self.assertEqual(v['origin']['original_ask'],.35)

    def test_feature_capture_returns_unchanged_original_and_exact_causal_binding(self):
        returned={'move1':1};start=datetime(2026,10,3,20,tzinfo=timezone.utc)
        ns={'_fair_build_snapshot':lambda *a,**kw:returned};install_features(ns)
        self.assertIs(ns['_fair_build_snapshot'](None,start,80000,_cut=start),returned)
        self.assertEqual(ns['_early_model_features']['feature_cutoff'],start.timestamp())
        returned['move1']=2;self.assertEqual(ns['_early_model_features']['values']['move1'],1)

    def test_deployment_handoff_copies_only_live_origin_not_old_publication(self):
        from btc15_v2_product.early_origin_transfer import transfer,PREDECESSOR,BUILD
        from btc15_v2_product import REVISION
        import sqlite3
        e=self.engine();f=value_frame();_,saved,v=step(e,f)
        with tempfile.TemporaryDirectory() as tmp:
            prior=Path(tmp)/PREDECESSOR/'main.sqlite3';prior.parent.mkdir()
            with sqlite3.connect(prior) as db:
                db.execute('CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT)')
                db.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY,sha256 TEXT,body BLOB)')
                db.executemany('INSERT INTO meta VALUES (?,?)',dict(product_revision=REVISION,
                    deployment=PREDECESSOR,build=BUILD,lane='main',state=json.dumps(saved)).items())
            before=prior.read_bytes()
            for name,at,active in (('new',f['captured_ts']+1,True),('later',f['official_close'],False)):
                dest=Path(tmp)/name/'main.sqlite3';dest.parent.mkdir()
                j=Journal(dest,'main');transfer(j,dest,at)
                self.assertEqual(j.get('origin_transfer')['active_origin_imported'],active)
                self.assertFalse(j.get('origin_transfer')['publication_imported'])
                if active:
                    self.assertEqual(j.get('state')['origin'],v['origin'])
                    transfer(j,dest,at+1)
                    restored=self.engine();restored.restore(j.get('state'))
                    _,_,view=step(restored,value_frame(2,ask=.7))
                    self.assertEqual(view['early']['guidance'],'HOLD')
                else:
                    self.assertIsNone(j.get('state')['origin'])
                    self.assertEqual(j.get('state')['signal_history'][-1]['origin_id'],v['origin']['origin_id'])
                j.close()
            self.assertEqual(prior.read_bytes(),before)

    def test_second_buy_after_exit_with_restart_and_distinct_origin(self):
        e=self.engine()
        first,_,entry=step(e,value_frame())
        self.assertEqual(first['event'],'BUY')
        exited,_,exit_view=step(e,value_frame(2,side='DOWN',p=.6))
        self.assertEqual(exited['event'],'EXIT')
        first_origin=entry['origin']['origin_id']
        first_terminal=deepcopy(exit_view['terminal'])
        # A post-EXIT frame that is not entry-qualified must not erase history.
        unready=value_frame(3,ask=.99,p=.995)
        rejected,saved,view=step(e,unready)
        self.assertNotEqual(rejected['event'],'BUY')
        self.assertEqual(view['terminal'],first_terminal)
        self.assertEqual(view['origin']['origin_id'],first_origin)
        restored=self.engine();restored.restore(saved)
        # Only fresh qualified evidence can create another origin.
        second,checkpoint,new_view=step(restored,value_frame(4))
        self.assertEqual(second['event'],'BUY')
        self.assertNotEqual(new_view['origin']['origin_id'],first_origin)
        self.assertIsNone(new_view['terminal'])
        self.assertIn(first_origin,[x['origin_id'] for x in checkpoint['signal_history']])
        previous=next(x for x in checkpoint['signal_history'] if x['origin_id']==first_origin)
        self.assertEqual(previous['terminal']['state'],'EXIT')
        self.assertFalse(previous['terminal']['manual_exit_confirmed'])
        duplicate,_,dup_view=step(restored,value_frame(5))
        self.assertNotEqual(duplicate['event'],'BUY')
        self.assertEqual(dup_view['origin']['origin_id'],new_view['origin']['origin_id'])

    def test_fee_cache_is_bounded_and_missing_fees_fail_closed(self):
        at=[10];calls=[]
        def get(path):
            calls.append(path);return {'series':{'ticker':'KXBTC15M','fee_type':'quadratic','fee_multiplier':1}}
        c=FeeCache(get,lambda:at[0]);c.refresh();c.refresh();self.assertEqual(len(calls),1)
        at[0]=70;c.get=lambda _: {'series':{}};c.refresh();self.assertIsNone(c.value)

if __name__=='__main__':unittest.main()

