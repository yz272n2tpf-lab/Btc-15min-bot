import unittest
from structural_lead_lag import prepare
from structural_path_alignment import native_paths
from structural_value_head import cheap_rows, calls


class StructuralSourceTests(unittest.TestCase):
    def vr(self):
        return dict(t=103.,ticker='A',target=100.,side='UP',features_ready=True,brti_fresh=True,
                    btc_age=1.,receipt_left=5.,btc15=5.,ask15=.01,ask=.35,bid=.34)

    def main(self,**kw):
        return dict(dict(t=102.,ticker='A',target=100.,brti_source_t=100.,sigma=10.,
                         signed_gap=5.,brti_gap=3.),**kw)

    def test_causal_join_rejects_fresh_receipt_of_stale_brti(self):
        rs,bad=prepare([self.vr()],[self.main(brti_source_t=97.)])
        self.assertEqual(rs,[]);self.assertEqual(bad['asof_brti_now_stale'],1)

    def test_join_never_uses_future_row_and_target_mismatch_is_fatal(self):
        self.assertEqual(prepare([self.vr()],[self.main(t=104.)])[0],[])
        with self.assertRaises(ValueError):prepare([self.vr()],[self.main(target=101.)])

    def record(self):
        q=dict(ticker='A',transport='timestamped_contiguous_ws',source_ts_ms=99000,
               validated_at_ms=100000,up_bid=.34,up_ask=.35,down_bid=.65,down_ask=.66)
        p=dict(schema='V81_TIMESTAMPED_INPUTS_V1',orders=False,signal_only=True,ticker='A',
               open_ts=0,close_ts=900,target=100.,quote=q,btc_source_utc='1970-01-01T00:01:39Z',
               brti=dict(source_ts_ms=99000,status='PRIMARY_OK',clean_for_qualification=True))
        return dict(receipt_epoch=100.,state=dict(contract='A',generated_utc='1970-01-01T00:01:39Z',input_provenance=p))

    def test_native_path_requires_fresh_publication_and_source(self):
        for mutate in ('publication','brti','quote','future_btc'):
            r=self.record();p=r['state']['input_provenance']
            if mutate=='publication':r['state']['generated_utc']='1970-01-01T00:01:35Z'
            if mutate=='brti':p['brti']['source_ts_ms']=94000
            if mutate=='quote':p['quote']['source_ts_ms']=93000
            if mutate=='future_btc':p['btc_source_utc']='1970-01-01T00:01:41Z'
            self.assertFalse(native_paths([r])[0])

    def test_native_path_deduplicates_same_validated_frame(self):
        tape,_=native_paths([self.record(),self.record()])
        self.assertEqual(len(tape['A']),1);self.assertEqual(tape['A'][0]['target'],100.)

    def test_native_path_rejects_cross_contract_or_non_signal_only(self):
        for key,value in [('ticker','B'),('orders',True)]:
            r=self.record();r['state']['input_provenance'][key]=value
            self.assertFalse(native_paths([r])[0])

    def cheap(self,**kw):
        return dict(dict(ticker='A',p_existing=.8,q=.7,receipt_left=8.,z=1.,basis=2.,m15=3.,m30=4.,m60=5.,
                         up_bid=.7,up_ask=.71,down_bid=.29,down_ask=.30),**kw)

    def test_cheap_head_keeps_probability_and_motion_on_candidate_side(self):
        r=cheap_rows([self.cheap()])[0]
        self.assertEqual(r['side'],'DOWN');self.assertAlmostEqual(r['p_held'],.2)
        self.assertEqual(r['z'],-1.);self.assertEqual(r['m15'],-3.)

    def test_cheap_head_does_not_expand_time_or_price_domain(self):
        self.assertEqual(cheap_rows([self.cheap(receipt_left=11.)]),[])
        self.assertEqual(cheap_rows([self.cheap(down_ask=.2)]),[])

    def test_value_control_keeps_first_call_not_future_cheapest_quote(self):
        rows=[dict(ticker='A',t=100.,ask=.4,p_held=.8),dict(ticker='A',t=110.,ask=.3,p_held=.9)]
        self.assertEqual(calls(dict(name='existing_control'),rows)[0]['t'],100.)


if __name__=='__main__':unittest.main()
