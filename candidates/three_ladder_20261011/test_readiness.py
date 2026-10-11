from copy import deepcopy
from pathlib import Path
import json,unittest,subprocess,sys,os
import numpy as np
from .isolation import verify_component,deployment_plan
from .profile_study import paths,features,future,fit,predict
from candidates.early_opportunity_20261011.lifecycle import Candidate
from candidates.early_opportunity_20261011.test_candidate import value_frame,registry,prediction
from candidates.early_opportunity_20261011.qualification import EvidenceRegistry

ROOT=Path(__file__).resolve().parents[2]

def observations():
    return [dict(contract='C',time=float(t),target=100.,btc=101+t/1000,brti=102.,side='UP',p=.8,left=900-t,
                 up_bid=.3+t/10000,up_ask=.31+t/10000,down_bid=.69-t/10000,down_ask=.7-t/10000,healthy=True) for t in range(0,601,5)]

class ProfileStudy(unittest.TestCase):
    def test_future_max_cannot_become_exit(self):
        rows=observations();rows[20]['up_bid']=.98;rows[20]['up_ask']=.99
        self.assertEqual(future(rows,0,240)['bid'],rows[48]['up_bid'])
    def test_unseen_future_cannot_change_features(self):
        rows=observations();first=features(rows,20,240);rows[30]['btc']=999
        np.testing.assert_array_equal(first,features(rows,20,240))
    def test_quote_gap_and_outage_censor_path(self):
        rows=observations();rows[20]['healthy']=False;self.assertIsNone(future(rows,0,240))
        rows=observations();del rows[10:15];self.assertIsNone(future(rows,0,240))
    def test_late_runway_is_rejected_without_global_cutoff(self):
        rows=observations();rows[20]['left']=29.1;self.assertIsNone(features(rows,20,240))
        rows[20]['left']=700;self.assertIsNotNone(features(rows,20,420))
    def test_duplicate_identity_conflict_excluded(self):
        rows=observations();data,c=paths(rows+rows);self.assertEqual(len(data['C']),len(rows));self.assertEqual(c,0)
        bad=deepcopy(rows[0]);bad['up_bid']+=.01;data,c=paths(rows+[bad]);self.assertEqual(c,1);self.assertEqual(len(data['C']),len(rows)-1)
    def test_later_expiry_does_not_rewrite_original_source_health(self):
        r=observations()[0];old=deepcopy(r);old['healthy']=False
        data,c=paths([r,old]);self.assertTrue(data['C'][0]['healthy']);self.assertEqual(c,0)
        data,c=paths([old,r]);self.assertFalse(data['C'][0]['healthy'])
    def test_disabled_research_profile_cannot_gain_native_authority(self):
        p=json.loads((ROOT/'audit/three_ladder_readiness_20261011/research_profile_DISABLED.json').read_text())
        self.assertFalse(p['enabled']);self.assertFalse(p['validated']);self.assertEqual(len(EvidenceRegistry().profiles),0)
        self.assertFalse(set(p['development_contracts'])&set(p['calibration_contracts']))
        f=value_frame();o=Candidate().process(f,f['captured_ts']);self.assertNotEqual(o['event'],'BUY')

class Isolation(unittest.TestCase):
    def test_early_checkout_cannot_pass_as_independent_scalp(self):
        with self.assertRaisesRegex(ValueError,'COMPONENT_REVISION_MISMATCH:scalp'):verify_component('scalp',ROOT)
    def test_each_unchanged_directional_owner_passes(self):
        for c in ('early','final','cockpit'):self.assertEqual(verify_component(c,ROOT)['status'],'PASS')
    def test_exact_independent_scalp_root_passes(self):
        p=ROOT.parent/'scalp-source'
        if not p.exists():self.skipTest('Supply separate checkout at pinned independent SCALP revision')
        self.assertEqual(verify_component('scalp',p)['status'],'PASS')
    def test_no_generic_promotion_or_production_permission(self):
        for c in ('early','scalp','final','cockpit'):self.assertFalse(deployment_plan(c)['deploy'])
        with self.assertRaises(ValueError):deployment_plan('all')
    def test_final_qualifies_independently_of_missing_early_profile(self):
        f=value_frame(offset=600,p=.95,ask=.5)
        result=Candidate().process(f,f['captured_ts'])
        self.assertTrue(result['final']['ready']);self.assertNotEqual(result['event'],'BUY')
        self.assertFalse(result['orders']);self.assertTrue(result['signal_only'])
    def test_early_lifecycle_has_its_own_origin_namespace(self):
        f=value_frame();c=Candidate(registry());r=c.process(f,f['captured_ts'],prediction(f))
        self.assertEqual(r['event'],'BUY');self.assertEqual(r['warning_owner'],'EARLY')
        self.assertEqual(r['final_role'],'INDEPENDENT_SETTLEMENT_EVIDENCE');self.assertNotIn('scalp',r)
    def test_simultaneous_three_ladders_use_separate_process_and_origins(self):
        scalp=ROOT.parent/'scalp-source'
        if not scalp.exists():self.skipTest('Independent SCALP checkout required')
        verify_component('scalp',scalp)
        # Synthetic fixture authority ONLY; separate interpreter prevents Python
        # from resolving independent SCALP imports to the EARLY checkout.
        code='''
import json
from test_btc15_scalp_entry_restore import frame
from btc15_v2_product.scalp import Scalp
from btc15_v2_product.scalp_economics import ENTRY_POLICY
from test_btc15_scalp_journal_v1 import OPEN
e=Scalp();e.restore({});a,_,v=e.process(frame(at=OPEN+480),OPEN+480.001)
origin=v['origin'];_,_,p=e.process(frame(at=OPEN+481,ask=.71,seq=2),OPEN+481.001)
_,_,x=e.process(frame(at=OPEN+482,ask=.62,seq=3),OPEN+482.001)
print(json.dumps(dict(policy=ENTRY_POLICY,event=a['event'],origin=origin,protect=p['guidance'],exit=x['guidance'],terminal=x['terminal'])))
'''
        s=json.loads(subprocess.check_output([sys.executable,'-B','-c',code],cwd=scalp,env={**os.environ,'PYTHONPATH':str(scalp)},text=True).splitlines()[-1])
        f=value_frame(offset=480,p=.95);c=Candidate(registry());r=c.process(f,f['captured_ts']+.001,prediction(f))
        self.assertEqual(s['policy'],'SCALP_MOMENTUM_COST_ROOM_V3');self.assertEqual(s['event'],'SCALP_SIGNAL')
        self.assertEqual(r['event'],'BUY');self.assertTrue(r['final']['ready'])
        self.assertEqual(r['origin']['contract'],s['origin']['contract']);self.assertEqual(r['origin']['signal_ts'],s['origin']['signal_ts'])
        self.assertNotEqual(r['origin']['origin_id'],s['origin']['origin_id'])
        self.assertEqual(s['protect'],'PROTECT');self.assertEqual(s['exit'],'EXIT')
        self.assertEqual(s['terminal']['origin']['origin_id'],s['origin']['origin_id']);self.assertIsNone(r['terminal'])
        self.assertEqual(c.origin['origin_id'],r['origin']['origin_id']);self.assertIsNone(c.terminal)

if __name__=='__main__':unittest.main()
