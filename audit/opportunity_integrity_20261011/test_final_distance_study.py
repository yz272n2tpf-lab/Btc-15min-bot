"""Synthetic accounting/gate tests, not historical performance results."""
import unittest
from copy import deepcopy
from candidates.early_opportunity_20261011.test_candidate import value_frame
from .final_distance_study import acceptance,evaluate,VARIANTS


class Comparison(unittest.TestCase):
    def frame(self,gap=30,p=.95,left=300,side='UP',sequence=1):
        f=value_frame(offset=900-left,side=side,p=p,sequence=sequence)
        f['btc_price']=f['target']+gap*(1 if side=='UP' else -1)
        f['model_features']['values']['current_coinbase_close']=f['btc_price']
        return f

    def row(self,f):
        return dict(frame=f,decision_ts=f['captured_ts']+.001,role='UNTOUCHED_EVALUATION',
            provenance_reviewed=True,selected_calls_only=False,volatility_regime_from_frozen_development_bins='TEST_BIN')

    def label(self,f,result='UP'):
        return {f['contract']:dict(status='finalized',result=result,target=f['target'],
            official_close=f['official_close'],source_receipt_sha256='TEST_ONLY')}

    def test_requested_distance_grid_both_sides_and_90_gate(self):
        for side in ('UP','DOWN'):
            for gap in (9,10,19,20,29,30,39,40,49,50):
                f=self.frame(gap=gap,side=side)
                for v in VARIANTS[:6]:
                    expected=gap>=50 if v=='CURRENT_75_50' else True if v=='NO_FIXED_DISTANCE' else gap>=int(v.split('_')[1])
                    self.assertEqual(acceptance(f,f['captured_ts'],v),expected,(side,gap,v))
                f=self.frame(gap=gap,p=.89,side=side)
                self.assertFalse(acceptance(f,f['captured_ts'],'NO_FIXED_DISTANCE'))

    def test_six_to_eight_minute_75_gate_retained_in_late_variants(self):
        f=self.frame(gap=60,left=400)
        self.assertFalse(acceptance(f,f['captured_ts'],'LATE_10'))
        self.assertTrue(acceptance(f,f['captured_ts'],'NO_FIXED_DISTANCE'))

    def test_missing_settlement_model_never_uses_eventual_average(self):
        f=self.frame();f['brti']['final60_avg']=f['target']+100
        for v in VARIANTS[-2:]:self.assertIsNone(acceptance(f,f['captured_ts'],v))

    def test_first_lock_contract_unit_not_poll_count_and_earlier_timing(self):
        a=self.frame(gap=30,left=300);b=self.frame(gap=60,left=290,sequence=2)
        r=evaluate([self.row(a),self.row(b),self.row(b)],self.label(a))
        self.assertEqual(r['comparison']['CURRENT_75_50']['n'],1)
        self.assertEqual(r['comparison']['LATE_30']['n'],1)
        self.assertEqual(r['comparison']['LATE_30']['additional_contract_locks'],0)
        self.assertAlmostEqual(r['comparison']['LATE_30']['mean_earlier_seconds_on_common_contracts'],10)
        self.assertEqual(r['rejected']['DUPLICATE_OR_CONFLICTING_FRAME'],1)

    def test_additional_wrong_lock_false_rate_and_uncertainty(self):
        f=self.frame(gap=30);r=evaluate([self.row(f)],self.label(f,'DOWN'))
        self.assertEqual(r['comparison']['CURRENT_75_50']['n'],0)
        self.assertIsNone(r['comparison']['CURRENT_75_50']['accuracy'])
        v=r['comparison']['LATE_30'];self.assertEqual(v['additional_contract_locks'],1)
        self.assertEqual(v['incorrect'],1);self.assertEqual(v['false_lock_rate'],1.)
        self.assertIsNotNone(v['false_lock_wilson95']);self.assertEqual(v['groups']['side']['UP']['n'],1)

    def test_bad_provenance_causality_selected_calls_and_conflicts_excluded(self):
        f=self.frame();good=self.row(f)
        for key,value in [('role','TRAIN'),('provenance_reviewed',False),('selected_calls_only',True)]:
            r=deepcopy(good);r[key]=value
            self.assertEqual(evaluate([r],self.label(f))['accepted_native_frames'],0)
        future=deepcopy(good);future['frame']['brti']['cf_ts']=f['captured_ts']+1
        self.assertEqual(evaluate([future],self.label(f))['accepted_native_frames'],0)
        other=deepcopy(good);other['frame']['btc_price']+=1
        self.assertEqual(evaluate([good,other],self.label(f))['accepted_native_frames'],0)


if __name__=='__main__':unittest.main()
