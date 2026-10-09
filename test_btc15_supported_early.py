"""Native entry/lifecycle regressions, not a performance or shadow test."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from btc15_v2_product.directional import Directional,CANDIDATE
from btc15_v2_product.early_entry import ARTIFACT,WEIGHTS,POLICY,FeeCache
from btc15_ladder_journal_v1 import Journal,packed
from test_btc15_ladder_completion_v1 import frame


def value_frame(sequence=1,ask=.53,p=.95,side='UP',offset=None):
    f=frame(sequence=sequence,offset=540+(sequence-1)*5 if offset is None else offset,
            ask=ask,p=p,side=side)
    f.update(candidate=CANDIDATE,artifact=ARTIFACT,weights=WEIGHTS,
        fee_schedule=dict(series='KXBTC15M',fee_type='quadratic',multiplier=1.,
                          observed_ts=f['captured_ts']-2,source='/trade-api/v2/series/KXBTC15M'))
    f['btc_price']+=(sequence-1)*2*(1 if side=='UP' else -1)
    f['brti']['value']=f['btc_price']
    return f


def step(e,f):
    return e.process(f,f['captured_ts']+.001)


class SupportedEarly(unittest.TestCase):
    def engine(self):
        e=Directional();e.restore({});return e

    def pair(self,**kwargs):
        e=self.engine();a=step(e,value_frame(**kwargs));b=step(e,value_frame(sequence=2,**kwargs))
        return e,a,b

    def test_53_both_sides_create_real_immutable_origins(self):
        for side in ('UP','DOWN'):
            e,first,(r,s,v)=self.pair(side=side)
            self.assertIsNone(first[2]['origin']);self.assertEqual(first[2]['early_opportunity']['status'],'WATCH')
            self.assertEqual(r['event'],'BUY');self.assertEqual(v['early']['guidance'],'ENTER')
            self.assertEqual(v['origin']['entry_policy'],POLICY)
            self.assertEqual(v['origin']['original_ask'],.53);self.assertEqual(v['origin']['side'],side)
            self.assertEqual(v['early_opportunity']['status'],'QUALIFIED')
            self.assertTrue(v['early_opportunity']['origin_authority'])
            self.assertEqual(v['final']['helper']['origin_id'],v['origin']['origin_id'])
            self.assertTrue(v['origin']['qualification']['ready'])
            self.assertIsNone(v['origin']['manual_fill']);self.assertFalse(v['orders'])
            self.assertLess(len(packed(r)),65536)
            self.assertAlmostEqual(v['origin']['qualification']['economics']['stress_net_model_ev_scenario'],.39)
            with tempfile.TemporaryDirectory() as tmp:
                j=Journal(Path(tmp)/'main.sqlite3','main');j.commit(r,s);saved=j.get('state');j.close()
                restored=self.engine();restored.restore(saved)
                _,_,held=step(restored,value_frame(sequence=3,ask=.70,side=side))
                self.assertEqual(held['origin'],v['origin']);self.assertEqual(held['early']['guidance'],'HOLD')

    def test_price_decision_depends_on_economics_not_50_or_other_cap(self):
        for ask in (.46,.50,.53,.61,.70,.80,.87):
            _,_,(r,_,v)=self.pair(ask=ask,p=.99)
            self.assertEqual(r['event'],'BUY',ask);self.assertEqual(v['origin']['original_ask'],ask)
        _,_,(r,_,v)=self.pair(ask=.92,p=.99)
        self.assertIsNone(v['origin']);self.assertFalse(v['early']['qualification']['conditions']['stress_edge_reserve'])
        self.assertIsNone(r['event'])

    def test_insufficient_support_cannot_create_call(self):
        mutations={
            'unknown_model':lambda f:f.update(artifact='other'),
            'weak_probability':lambda f:f['fair'].update(fair=.89,up_fair=.89,down_fair=.11,edge=.89-.53),
            'wrong_target_side':lambda f:f.update(btc_price=f['target']-80),
            'neutral_brti':lambda f:f['brti'].update(value=f['target']+11),
            'volatility':lambda f:f['fair'].update(dist_over_range5=.99),
            'fees_missing':lambda f:f.pop('fee_schedule'),
            'fees_expired':lambda f:f['fee_schedule'].update(observed_ts=f['captured_ts']-121),
            'fees_future':lambda f:f['fee_schedule'].update(observed_ts=f['captured_ts']+1),
            'fees_unsupported':lambda f:f['fee_schedule'].update(fee_type='flat'),
            'high_fee':lambda f:f['fee_schedule'].update(multiplier=30),
        }
        for name,mutate in mutations.items():
            with self.subTest(name=name):
                e=self.engine()
                for n in (1,2):
                    f=value_frame(n);mutate(f);r,_,v=step(e,f)
                    self.assertIsNone(v['origin']);self.assertNotEqual(r.get('event'),'BUY')

    def test_confirmation_requires_advancing_independent_sources(self):
        for key in ('book','btc','brti','epoch','momentum','brti_reversal','probability'):
            e=self.engine();a=value_frame();step(e,a);b=value_frame(2)
            if key=='book':b['quote'].update(seq=a['quote']['seq'])
            if key=='btc':b['btc_source']=a['btc_source']
            if key=='brti':b['brti']['cf_ts']=a['brti']['cf_ts']
            if key=='epoch':b['quote']['epoch']='new'
            if key=='momentum':b['btc_price']=a['btc_price']-1
            if key=='brti_reversal':b['brti']['value']=a['brti']['value']-1
            if key=='probability':b['fair'].update(fair=.94,up_fair=.94,down_fair=.06,edge=.94-.53)
            r,_,v=step(e,b);self.assertIsNone(v['origin'],key);self.assertNotEqual(r.get('event'),'BUY',key)

    def test_outage_restart_and_gap_do_not_accumulate_confirmation(self):
        for mode in ('outage','restart','gap'):
            e=self.engine();_,s,_=step(e,value_frame())
            if mode=='outage':e.process(dict(kind='UNAVAILABLE',reason='SOURCE_EXPIRED'),0)
            if mode=='restart':e=self.engine();e.restore(s)
            b=value_frame(2,offset=560 if mode=='gap' else None)
            _,_,v=step(e,b);self.assertIsNone(v['origin'],mode)

    def test_management_and_protection_remain_latched_without_new_exit(self):
        e,_,(_,saved,buy)=self.pair()
        _,_,held=step(e,value_frame(3,ask=.70));self.assertEqual(held['early']['guidance'],'HOLD')
        _,_,protect=step(e,value_frame(4,ask=.70,p=.8))
        self.assertEqual(protect['early']['guidance'],'PROTECT')
        _,_,recovery=step(e,value_frame(5,ask=.70))
        self.assertEqual(recovery['early']['guidance'],'PROTECT')
        self.assertEqual(recovery['origin'],buy['origin']);self.assertIsNone(recovery['exit_guidance'])
        self.assertFalse(recovery['final']['helper']['exit_authority'])

    def test_historical_origin_still_independent_of_final(self):
        e=self.engine();f=frame(ask=.35,p=.8)
        r,_,v=step(e,f);self.assertEqual(r['event'],'BUY');self.assertFalse(v['final']['ready'])
        self.assertEqual(v['origin']['entry_policy'],'HISTORICAL_TIER1')

    def test_fee_cache_is_bounded_and_missing_fees_fail_closed(self):
        at=[10];calls=[]
        def get(path):
            calls.append(path);return {'series':{'ticker':'KXBTC15M','fee_type':'quadratic','fee_multiplier':1}}
        c=FeeCache(get,lambda:at[0]);c.refresh();c.refresh();self.assertEqual(len(calls),1)
        self.assertEqual(c.value['observed_ts'],10)
        at[0]=70;c.get=lambda _: {'series':{}};c.refresh();self.assertIsNone(c.value)

if __name__=='__main__':unittest.main()
