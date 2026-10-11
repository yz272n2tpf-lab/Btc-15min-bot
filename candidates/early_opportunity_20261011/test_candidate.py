"""Synthetic mechanism tests. Passing does NOT validate the fixture forecasts."""
from copy import deepcopy
import unittest

from test_btc15_supported_early import value_frame as legacy_value_frame
from btc15_v2_product.directional import protected_frame
from .qualification import EvidenceRegistry, digest, qualify_opportunity, settlement_context
from .lifecycle import Candidate


def value_frame(*args, **kwargs):
    # Older unit fixtures used two independent spreads whose complements sum to
    # .99. Candidate tests use a single reciprocal binary order book instead.
    f=legacy_value_frame(*args,**kwargs)
    if f['fair']['side']=='UP':
        f['down_bid']=1-f['up_ask'];f['down_ask']=1-f['up_bid']
    else:
        f['up_bid']=1-f['down_ask'];f['up_ask']=1-f['down_bid']
    f['quote']['quotes']=[f[k] for k in ('up_bid','up_ask','down_bid','down_ask')]
    return f


def profile(horizon=240):
    return dict(evidence_class='SYNTHETIC_FIXTURE',purpose='EARLY_DIRECTIONAL_OPPORTUNITY',
        validated=True,not_for_scalp=True,validation_report_sha256='f'*64,
        validation_completed_ts=1.,horizon_seconds=horizon,manual_execution_budget_seconds=10.,
        execution_reserve_dollars=.02,horizon_evidence_sha256='h'*64,
        execution_evidence_sha256='e'*64,uncertainty_method='TEST_ONLY_NOT_EMPIRICAL')


def registry(p=None):
    return EvidenceRegistry([p or profile()],permit_test_fixtures=True)


def prediction(f,p=None,lower=.73):
    p=p or profile()
    return dict(profile_sha256=digest(p),frame_sha256=digest(f),contract=f['contract'],
        target=f['target'],side=f['fair']['side'],feature_cutoff=f['feature_cutoff'],
        available_ts=f['captured_ts']-.02,valid_until=min(f['captured_ts']+1,f['official_close']),
        horizon_seconds=p['horizon_seconds'],mean_future_bid=max(.78,lower),lower_bound_mean_future_bid=lower,
        basis='HELDOUT_SAME_SIDE_BID_AT_VALIDATED_HORIZON',model_fair_used_as_future_bid=False,
        directional_support=True,regime_in_validation_support=True,
        uncertainty_method=p['uncertainty_method'],settlement_conditioned=True,
        settlement_path_supported=True,settlement_evidence_hash=settlement_context(f)['evidence_hash'])


def samples(f,average=79980.,count=30):
    close=f['official_close']
    f['settlement_evidence']=dict(contract=f['contract'],target=f['target'],official_close=close,
        asof=f['feature_cutoff'],owner_epoch=f['brti']['delivery']['owner_epoch'],
        samples=[dict(second=int(close-60+i),value=average,received_ts=close-60+i+.02) for i in range(count)])
    return f


class Admission(unittest.TestCase):
    def test_without_validated_opportunity_model_value_cannot_issue_buy(self):
        for side in ('UP','DOWN'):
            f=value_frame(side=side)
            q=qualify_opportunity(f,f['captured_ts']+.001)
            self.assertFalse(q['ready']);self.assertIn('VALIDATED_OPPORTUNITY_EVIDENCE_REQUIRED',q['reasons'])
            out=Candidate().process(f,f['captured_ts']+.001)
            self.assertIsNone(out['origin']);self.assertNotEqual(out['event'],'BUY')
            self.assertIsNotNone(out['final'])

    def test_four_through_seven_minute_and_other_supported_horizons_both_sides(self):
        for side in ('UP','DOWN'):
            for horizon in (150,180,240,300,360,420):
                for offset in (10,60,300):
                    f=value_frame(offset=offset,side=side);p=profile(horizon)
                    q=qualify_opportunity(f,f['captured_ts']+.001,prediction(f,p),registry(p))
                    self.assertTrue(q['ready'],q)
                    self.assertGreater(q['economics']['conservative_expected_net'],0)
                    self.assertFalse(q['actionable']);self.assertFalse(q['live_profitability_validated'])

    def test_horizon_fits_evidence_not_one_fixed_entry_window(self):
        f=value_frame(offset=700);short=profile(150);long=profile(240)
        self.assertTrue(qualify_opportunity(f,f['captured_ts']+.001,prediction(f,short),registry(short))['ready'])
        self.assertFalse(qualify_opportunity(f,f['captured_ts']+.001,prediction(f,long),registry(long))['ready'])

    def test_last_second_and_29_second_multiminute_entries_rejected(self):
        for side in ('UP','DOWN'):
            for left in (29.1,15.,5.,1.1):
                f=samples(value_frame(offset=900-left,side=side,ask=.05),count=min(59,int(60-left)))
                p=profile(150)
                q=qualify_opportunity(f,f['captured_ts']+.001,prediction(f,p),registry(p))
                self.assertFalse(q['ready']);self.assertIn('OPPORTUNITY_HORIZON_DOES_NOT_FIT_CONTRACT',q['reasons'])
                e=Candidate(registry(p));out=e.process(f,f['captured_ts']+.001,prediction(f,p))
                self.assertNotEqual(out['event'],'BUY');self.assertIsNone(out['origin'])

    def test_untrusted_fixture_future_forecast_and_frame_tampering_block(self):
        f=value_frame();p=profile();pred=prediction(f,p)
        self.assertFalse(qualify_opportunity(f,f['captured_ts'],pred,EvidenceRegistry([p]))['ready'])
        for key,value in [('available_ts',f['captured_ts']+1),('frame_sha256','wrong'),
                          ('side','DOWN'),('model_fair_used_as_future_bid',True),
                          ('regime_in_validation_support',False),('settlement_evidence_hash','wrong')]:
            altered=deepcopy(pred);altered[key]=value
            self.assertFalse(qualify_opportunity(f,f['captured_ts'],altered,registry(p))['ready'],key)
        future=profile();future['validation_completed_ts']=f['official_open']+1
        self.assertFalse(qualify_opportunity(f,f['captured_ts'],prediction(f,future),registry(future))['ready'])

    def test_bid_forecast_costs_and_reserve_not_model_fair(self):
        f=value_frame(p=.99)
        self.assertFalse(qualify_opportunity(f,f['captured_ts'],prediction(f,lower=.55),registry())['ready'])
        good=qualify_opportunity(f,f['captured_ts'],prediction(f),registry())
        self.assertAlmostEqual(good['economics']['conservative_expected_net'],.14)
        self.assertIsNone(good['economics']['realized_profit'])

    def test_source_quote_and_feature_failures_still_reject(self):
        for change in ('stale','foreign','mapping','fees','momentum','volatility'):
            f=value_frame()
            if change=='stale':f['quote']['exchange_ts_ms']-=10000
            if change=='foreign':f['quote']['ticker']='OTHER'
            if change=='mapping':f['down_bid']-=.05;f['quote']['quotes'][2]-=.05
            if change=='fees':f.pop('fee_schedule')
            if change=='momentum':f['model_features']['values']['move1']=-1
            if change=='volatility':f['model_features']['values']['vol5']=-1
            self.assertFalse(qualify_opportunity(f,f['captured_ts'],prediction(f),registry())['ready'],change)

    def test_partial_average_requires_exact_causal_seconds(self):
        f=samples(value_frame(offset=870.9));s=settlement_context(f)
        self.assertEqual(s['known_count'],30);self.assertEqual(s['raw_unknown_mean_hurdle'],'80020.0')
        self.assertEqual(s['missing_elapsed_seconds'],[int(f['official_close']-30)])
        for change in ('duplicate','future','foreign','received_future','wrong_owner'):
            g=deepcopy(f);e=g['settlement_evidence']
            if change=='duplicate':e['samples'].append(e['samples'][0])
            if change=='future':e['samples'][0]['second']=int(f['official_close'])
            if change=='foreign':e['contract']='OTHER'
            if change=='received_future':e['samples'][0]['received_ts']=f['captured_ts']+1
            if change=='wrong_owner':e['owner_epoch']='OTHER'
            with self.assertRaises(ValueError,msg=change):settlement_context(g)


class Lifecycle(unittest.TestCase):
    def start(self,side='UP',offset=300):
        e=Candidate(registry());f=value_frame(side=side,offset=offset)
        out=e.process(f,f['captured_ts']+.001,prediction(f));self.assertEqual(out['event'],'BUY',out)
        return e,out

    def step(self,e,seq,**kwargs):
        f=value_frame(sequence=seq,offset=300+5*(seq-1),**kwargs)
        return e.process(f,f['captured_ts']+.001,prediction(f))

    def test_buy_hold_watch_recover_exit_and_opposite_reentry(self):
        for side in ('UP','DOWN'):
            opposite='DOWN' if side=='UP' else 'UP'
            e,first=self.start(side);origin=first['origin']['origin_id']
            self.assertEqual(self.step(e,2,side=side)['guidance'],'HOLD')
            watch=self.step(e,3,side=side,p=.80,ask=.52);self.assertEqual(watch['guidance'],'WATCH')
            self.assertIsNone(watch['terminal'])
            # No repeated warning alert while support remains below the anchor.
            lingering=self.step(e,4,side=side,p=.81);self.assertEqual(lingering['guidance'],'WATCH');self.assertIsNone(lingering['event'])
            self.assertEqual(self.step(e,5,side=side,p=.83)['guidance'],'HOLD')
            exit_out=self.step(e,6,side=opposite,p=.6)
            self.assertEqual(exit_out['guidance'],'EXIT');self.assertEqual(exit_out['event'],'EXIT')
            terminal=deepcopy(exit_out['terminal']);self.assertEqual(terminal['origin_id'],origin)
            self.assertIsNone(terminal['realized_profit'])
            self.step(e,7,side=opposite,ask=.99,p=.995)
            saved=e.checkpoint();restored=Candidate(registry());restored.restore(saved)
            new=self.step(restored,8,side=opposite)
            self.assertEqual(new['event'],'BUY',new);self.assertNotEqual(new['origin']['origin_id'],origin)
            self.assertEqual(new['history'][0]['terminal'],terminal)
            repeated=self.step(restored,9,side=opposite)
            self.assertNotEqual(repeated['event'],'BUY');self.assertEqual(repeated['origin'],new['origin'])

    def test_missing_forecast_is_not_a_new_setup_or_exit(self):
        e,_=self.start();self.step(e,2,side='DOWN',p=.6)
        f=value_frame(sequence=3,offset=310)
        no_forecast=e.process(f,f['captured_ts']+.001)
        self.assertEqual(no_forecast['guidance'],'EXIT');self.assertFalse(e.reentry_reset)
        self.assertNotEqual(self.step(e,4)['event'],'BUY')

    def test_missing_fees_or_features_do_not_rearm_unchanged_setup(self):
        for field in ('fee_schedule','model_features'):
            e,_=self.start();self.step(e,2,side='DOWN',p=.6)
            f=value_frame(sequence=3,offset=310);f.pop(field)
            e.process(f,f['captured_ts']+.001)
            self.assertFalse(e.reentry_reset,field)
            self.assertNotEqual(self.step(e,4)['event'],'BUY')

    def test_probability_noise_alone_cannot_exit_or_duplicate_buy(self):
        e,_=self.start()
        for seq,p in enumerate((.8299,.8301,.8298,.8302),2):
            out=self.step(e,seq,p=p)
            self.assertNotIn(out['event'],('BUY','EXIT','WATCH'));self.assertIsNone(out['terminal'])

    def test_average_can_warn_while_spot_brti_and_model_still_support_side(self):
        e,origin=self.start(offset=620)
        f=samples(value_frame(sequence=2,offset=870.9),average=79900,count=30)
        out=e.process(f,f['captured_ts']+.001)
        self.assertEqual(out['guidance'],'WATCH');self.assertIsNone(out['terminal'])
        self.assertIn('ACCUMULATED_SETTLEMENT_CHALLENGES_THESIS',out['management']['candidate_warning_reasons'])
        self.assertGreater(f['brti']['value'],f['target'])
        self.assertEqual(out['origin'],origin['origin'])

    def test_unavailable_kind_with_residual_values_never_issues(self):
        f=value_frame();f['kind']='UNAVAILABLE'
        out=Candidate(registry()).process(f,f['captured_ts']+.001,prediction(f))
        self.assertEqual(out['guidance'],'UNAVAILABLE');self.assertIsNone(out['origin'])

    def test_management_rejects_wrong_mapping_and_quote_rollback(self):
        e,_=self.start();self.step(e,2);before=e.checkpoint()
        for mode in ('mapping','rollback','conflict'):
            f=value_frame(sequence=3,offset=310,side='DOWN',p=.6)
            if mode=='mapping':f['up_bid']-=.05;f['quote']['quotes'][0]-=.05
            if mode=='rollback':f['quote']['seq']=1
            if mode=='conflict':f['quote']['seq']=2
            out=e.process(f,f['captured_ts']+.001)
            self.assertEqual(out['guidance'],'UNAVAILABLE',out);self.assertEqual(e.checkpoint(),before)
            self.assertIsNone(out['terminal']);self.assertIsNotNone(out['final'])

    def test_outage_rollover_order_and_old_target_never_create_trade(self):
        e,entry=self.start();before=e.checkpoint();f=value_frame(sequence=2,offset=305)
        f['brti']['ready']=False;out=e.process(f,f['captured_ts']+.001)
        self.assertEqual(out['guidance'],'UNAVAILABLE');self.assertEqual(e.checkpoint(),before)
        f=value_frame(sequence=1,offset=300);out=e.process(f,f['captured_ts']+.001,prediction(f))
        self.assertEqual(out['guidance'],'UNAVAILABLE');self.assertEqual(e.checkpoint(),before)
        f=value_frame(sequence=2,offset=305);f['target']+=1
        out=e.process(f,f['captured_ts']+.001);self.assertEqual(out['guidance'],'UNAVAILABLE')
        f=value_frame(sequence=3,offset=1210);f['official_open']+=900;f['official_close']+=900
        f['contract']='KXBTC15M-26OCT031630-30';f['quote'].update(ticker=f['contract'],close_ms=int(f['official_close']*1000))
        out=e.process(f,f['captured_ts']+.001)
        self.assertIsNone(out['origin']);self.assertEqual(out['history'][0]['origin'],entry['origin'])

    def test_final_gates_unchanged_and_safety_always_offline(self):
        for gap in (10,20,30,40,49,50,75,80):
            for p in (.89,.90,.95):
                f=value_frame(offset=540,p=p);f['btc_price']=f['target']+gap
                f['model_features']['values']['current_coinbase_close']=f['btc_price']
                out=Candidate().process(f,f['captured_ts']+.001)
                self.assertEqual(out['final'],protected_frame(f,f['captured_ts']+.001)[0]['final'])
                self.assertFalse(out['orders']);self.assertTrue(out['signal_only']);self.assertFalse(out['actionable'])


if __name__=='__main__':unittest.main()
