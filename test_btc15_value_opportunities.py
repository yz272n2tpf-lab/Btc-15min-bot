"""Focused regressions for the live native value and coverage repair."""
from copy import deepcopy
import unittest
from btc15_v2_product.directional import Directional,protected_frame
from btc15_v2_product.opportunities import economics,evaluate
from test_btc15_ladder_completion_v1 import frame
from test_btc15_integrated_finish import scalp_frame
from btc15_v2_product.scalp import Scalp

class ValueAnalysis(unittest.TestCase):
    def view(self,**kw):
        f=frame(**kw);e=Directional();e.restore({})
        r,_,v=e.process(f,f['captured_ts']+.001)
        self.assertIn(v['status'],('PASS','AVAILABLE'))
        self.assertFalse(v['orders']);self.assertTrue(v['signal_only'])
        return r,v

    def test_53_cent_positive_value_is_evaluated_without_new_authority(self):
        r,v=self.view(ask=.53,p=.8,offset=540)
        o=v['early_opportunity'];self.assertEqual(o['status'],'WATCH')
        self.assertIsNone(o['price_ceiling']);self.assertIsNone(o['target_ask'])
        self.assertAlmostEqual(o['economics']['net_model_ev_scenario'],.25)
        self.assertAlmostEqual(o['economics']['win_profit_scenario'],.45)
        self.assertAlmostEqual(o['economics']['loss_scenario'],.55)
        self.assertGreater(o['economics']['stress_net_model_ev_scenario'],0)
        self.assertFalse(o['origin_authority']);self.assertIsNone(v['origin'])
        self.assertIsNone(r.get('event'))
        self.assertIn('unvalidated',o['reason'])
        self.assertTrue(any('verified frozen model' in x for x in o['improvements']))

    def test_no_45_50_or_replacement_ceiling(self):
        for ask in (.450001,.5,.53,.55,.6,.7,.8,.9,.95):
            _,v=self.view(ask=ask,p=.99)
            self.assertEqual(v['early_opportunity']['status'],'WATCH',ask)
            self.assertEqual(len(v['opportunity_analysis']['candidates']),2)

    def test_cheap_weak_and_expensive_negative_economics_are_not_qualified(self):
        for ask,p in ((.3,.55),(.99,.995),(.8,.8)):
            _,v=self.view(ask=ask,p=p)
            self.assertEqual(v['early_opportunity']['status'],'PASS')
            self.assertIsNone(v['origin'])
        self.assertLess(economics(.995,.98,.99)['net_model_ev_scenario'],0)

    def test_entire_window_evaluated_independently_of_final_and_tier(self):
        for offset in (1,60,299,300,540,780,899):
            _,v=self.view(ask=.53,p=.8,offset=offset)
            self.assertEqual(v['early_opportunity']['status'],'WATCH')
            self.assertFalse(v['final']['ready'])
            self.assertEqual(v['opportunity_analysis']['seconds_left'],900-offset)

    def test_historical_tier_and_final_are_preserved(self):
        _,v=self.view(ask=.35,p=.8)
        self.assertIsNotNone(v['origin']);self.assertEqual(v['early_opportunity']['status'],'QUALIFIED')
        self.assertFalse(v['final']['ready'])
        _,v=self.view(ask=.95,p=.95,offset=540)
        self.assertTrue(v['final']['ready']);self.assertEqual(v['early_opportunity']['status'],'PASS')

    def test_both_sides_costs_and_no_fill_inference(self):
        f=frame(ask=.53,p=.8,side='DOWN');raw,_=protected_frame(f,f['captured_ts'])
        o,a=evaluate(raw,f)
        self.assertEqual(o['side'],'DOWN')
        for c in a['candidates']:
            self.assertIsNone(c['economics']['expected_profit'])
            self.assertFalse(c['economics']['fill_guaranteed'])
        for ask in (0,-.1,1.1,float('nan')):
            self.assertFalse(economics(.8,0,ask)['valid_book'])
        self.assertTrue(economics(.8,.99,1)['valid_book'])

    def test_pullback_and_momentum_use_only_same_contract_causal_prior(self):
        e=Directional();e.restore({});f=frame(ask=.6,p=.8)
        e.process(f,f['captured_ts']+.001)
        f=frame(offset=305,sequence=2,ask=.53,p=.82);f['btc_price']+=2
        _,_,v=e.process(f,f['captured_ts']+.001)
        c=v['opportunity_analysis']['candidates'][0]
        self.assertTrue(c['pullback_observed']);self.assertEqual(c['btc_move_since_previous_native'],2)
        self.assertEqual(c['secondary_state'],'WATCH');self.assertIsNone(v['origin'])
        raw,_=protected_frame(f,f['captured_ts']);prior=deepcopy(e.prior_final);prior['contract']='FOREIGN'
        _,a=evaluate(raw,f,prior)
        self.assertFalse(a['candidates'][0]['pullback_observed'])

    def test_stale_or_wrong_contract_never_gets_value_authority(self):
        for mutate in (lambda f:f['quote'].update(ticker='OTHER'),lambda f:f['brti'].update(cf_ts=f['captured_ts']-6)):
            f=frame(ask=.53);mutate(f);e=Directional();e.restore({})
            _,_,v=e.process(f,f['captured_ts']+.001)
            self.assertEqual(v['status'],'UNAVAILABLE');self.assertNotIn('opportunity_analysis',v)

    def test_scalp_reports_both_sides_without_using_final(self):
        e=Scalp();e.restore({});f=scalp_frame()
        r,_,v=e.process(f,f['captured_ts']+.001)
        self.assertEqual(r['event'],'SCALP_SIGNAL')
        self.assertEqual([x['side'] for x in v['opportunity_coverage']],['UP','DOWN'])
        self.assertEqual(v['opportunity_coverage'][0]['status'],'QUALIFIED')
        self.assertIsNone(v['opportunity_coverage'][0]['expected_profit'])

if __name__=='__main__':unittest.main()
