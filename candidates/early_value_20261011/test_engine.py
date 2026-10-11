"""Focused mechanics; none of these fixtures establish historical profitability."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json,unittest
from candidates.early_condition_20261011.test_engine import row
from candidates.early_opportunity_20261011.test_candidate import value_frame,samples
from candidates.early_condition_20261011.study import score_episode
from btc15_v2_product.directional import protected_frame
from .engine import Engine,Rules
from .qualification import features,screen,economics
from .native import NativeCandidate
from .study import replay


def enter(side='UP',**kw):
    e=Engine(proposal_mode=True,**kw)
    for t in range(0,151,5):e.process(row(t,side))
    assert e.origin
    return e


def reverse(e,side='UP'):
    for t in range(155,271,5):
        e.process(row(t,side,delta=95-2*(t-150),bid=max(.05,.35-.002*(t-150))))
    assert e.terminal
    return e


def supported():
    cell=dict(supported=True,gross_gain_lower=.20,min_left=190,max_left=900,min_ask=.01,max_ask=.58)
    return {'support':{s:dict(cell,exception=deepcopy(cell)) for s in ('UP','DOWN')}}


class ValueLifecycle(unittest.TestCase):
    def test_buy_hold_watch_exit_up_down(self):
        for side in ('UP','DOWN'):
            e=reverse(enter(side),side);events=[z['event'] for z in e.events]
            self.assertEqual(events[0],'BUY');self.assertIn('WATCH',events);self.assertIn('EXIT',events)
            self.assertLess(events.index('WATCH'),events.index('EXIT'))
            self.assertLess(e.terminal['net_quote_scenario'],0)

    def test_early_protection_does_not_wait_for_long_trend_reversal(self):
        e=enter()
        for t in range(155,201,5):e.process(row(t,delta=95-.3*(t-150),bid=.35-.001*(t-150)))
        self.assertEqual(e.guidance,'WATCH')
        x=features(e.history,e.last,'UP',e.rules)
        self.assertGreater(x['move_long'],0)

    def test_watch_recovery_hold(self):
        e=enter()
        for t in range(155,206,5):e.process(row(t,delta=95,bid=.35-.0005*(t-150)))
        self.assertEqual(e.guidance,'WATCH');self.assertIsNone(e.terminal)
        for t in range(210,281,5):e.process(row(t,delta=95+t-205,bid=.35+.001*(t-205)))
        self.assertEqual(e.guidance,'HOLD');self.assertIsNone(e.terminal)

    def test_no_holding_timer(self):
        e=enter()
        for t in range(155,751,5):e.process(row(t))
        self.assertIsNone(e.terminal);self.assertEqual(e.guidance,'HOLD')
        self.assertGreater(e.last['time']-e.origin['time'],420)

    def test_confidence_noise_invalidates_entry_not_holder_exit(self):
        e=enter();e.process(row(155,p=.51))
        self.assertFalse(e.manual_entry(155)['research_entry_valid'])
        for t in range(160,201,5):e.process(row(t))
        self.assertIsNone(e.terminal);self.assertEqual(e.guidance,'HOLD')
        self.assertEqual(e.ticket['status'],'INVALIDATED')

    def test_same_side_fresh_reentry(self):
        e=reverse(enter());first=e.origin['id']
        for t in range(275,561,5):e.process(row(t,delta=-145+1.7*(t-270),bid=.10+.001*(t-270)))
        buys=[z for z in e.events if z['event']=='BUY']
        self.assertEqual(len(buys),2);self.assertNotEqual(first,e.origin['id'])

    def test_both_reversal_directions(self):
        for side in ('UP','DOWN'):
            e=reverse(enter(side),side);opposite='DOWN' if side=='UP' else 'UP'
            for t in range(275,491,5):e.process(row(t,opposite,delta=145+.5*(t-270),bid=.25+.0004*(t-270)))
            self.assertEqual([z['side'] for z in e.events if z['event']=='BUY'],[side,opposite])

    def test_duplicate_and_unchanged_setup_suppressed(self):
        e=enter();r=deepcopy(e.last)
        for _ in range(5):self.assertIsNone(e.process(r)['event'])
        for t in range(155,301,5):e.process(row(t))
        self.assertEqual(sum(z['event']=='BUY' for z in e.events),1)

    def test_outage_not_new_setup_or_sale(self):
        e=reverse(enter());e.reset_seen=False;r=row(275);r['healthy']=False;e.process(r)
        self.assertFalse(e.reset_seen)
        e=enter();r=row(155);r['healthy']=False;out=e.process(r)
        self.assertEqual(out['guidance'],'WATCH');self.assertIsNone(out['executable_exit_bid'])
        self.assertEqual(out['entry_guidance'],'WAIT');self.assertIsNone(e.terminal)

    def test_source_expiry_without_new_publication(self):
        e=enter();out=e.manual_entry(161)
        self.assertFalse(out['research_entry_valid']);self.assertIn('BUY_QUOTE_EXPIRED',out['ticket']['invalidation_reasons'])
        self.assertIsNone(e.terminal)

    def test_manual_quote_refresh_then_above_ceiling_invalidates(self):
        e=enter();out=e.process(row(155,bid=.40))
        self.assertAlmostEqual(out['ticket']['current_ask'],.41)
        out=e.process(row(160,bid=.59))
        self.assertEqual(out['entry_guidance'],'WAIT')
        self.assertIn('VALUE_PRICE',out['ticket']['invalidation_reasons'])
        self.assertIsNone(e.terminal)

    def test_fee_or_profile_loss_invalidates_ticket(self):
        e=Engine(profile=supported())
        for t in range(0,151,5):e.process(row(t))
        self.assertIsNotNone(e.origin)
        e.profile['support']['UP']['supported']=False
        out=e.process(row(155))
        self.assertFalse(out['research_entry_valid']);self.assertIsNone(e.terminal)

    def test_rollover_does_not_transfer_ticket(self):
        e=enter();out=e.process(row(900,contract='B',close=1800))
        self.assertIsNone(e.origin);self.assertFalse(out['research_entry_valid'])
        self.assertEqual(e.closed[-1]['censor'],'ROLLOVER_WITHOUT_EXIT')
        self.assertIn('OLDER_CONTRACT',e.process(row(905,contract='A',close=1800))['reasons'])

    def test_delayed_malformed_identity_and_expired(self):
        for change in ('delay','numeric','target','expiry'):
            e=enter();r=row(155)
            if change=='delay':r['received']+=20
            if change=='numeric':r['btc']=None
            if change=='target':r['target']+=1
            if change=='expiry':r['left']=0
            out=e.process(r);self.assertFalse(out['research_entry_valid'],change);self.assertIsNone(e.terminal)

    def test_settlement_contradiction_requires_correct_binding(self):
        for contract in ('A','OTHER'):
            e=enter()
            for t in range(155,841,5):e.process(row(t))
            for t in range(845,896,5):
                r=row(t,delta=440,bid=.75-.0005*(t-840))
                r['settlement']=dict(verified_causal=True,contract=contract,asof=float(t),hurdle=100500.)
                e.process(r)
            if contract=='A':self.assertEqual(e.terminal['reason'],'SETTLEMENT_BREAKDOWN')
            else:self.assertIsNone(e.terminal)

    def test_29_second_and_other_late_entries_blocked(self):
        for left in (29.1,1.1,120,189,190):
            e=Engine(proposal_mode=True)
            for t in range(0,151,5):e.process(row(t,close=40+left))
            self.assertIsNone(e.origin,left)

    def test_no_25_cent_floor(self):
        for side in ('UP','DOWN'):
            e=Engine(proposal_mode=True)
            for t in range(0,151,5):e.process(row(t,side,bid=.10+.0001*t))
            self.assertIsNotNone(e.origin);self.assertLess(e.origin['ask'],.25)

    def test_cheap_weak_direction_rejected(self):
        e=Engine(proposal_mode=True)
        for t in range(0,151,5):e.process(row(t,p=.60,bid=.10))
        self.assertIsNone(e.origin)

    def test_price_ceiling_and_exception_evidence(self):
        for ask,p,expected in ((.55,.85,True),(.58,.85,False),(.58,.95,True),(.59,.99,False)):
            e=Engine(proposal_mode=True)
            for t in range(0,151,5):e.process(row(t,p=p,bid=ask-.01))
            self.assertEqual(e.origin is not None,expected,(ask,p))
        r=row(150,bid=.57,p=.95);profile=supported()
        self.assertTrue(economics(r,'UP',profile,Rules())['ready'])
        profile['support']['UP']['exception']['gross_gain_lower']=.10
        self.assertFalse(economics(r,'UP',profile,Rules())['ready'])

    def test_fees_spread_and_absent_economics(self):
        r=row(150);p=supported();p['support']['UP']['gross_gain_lower']=.06
        self.assertFalse(economics(r,'UP',p,Rules())['ready'])
        e=Engine()
        for t in range(0,151,5):e.process(row(t))
        self.assertIsNone(e.origin)

    def test_later_better_prices_do_not_change_prefix(self):
        rows=[row(t) for t in range(0,301,5)];a=Engine(proposal_mode=True);b=Engine(proposal_mode=True)
        out=[a.process(r) for r in rows[:40]]
        self.assertEqual(out,[b.process(r) for r in rows][:40])

    def test_delayed_entry_cancel_is_not_a_fill(self):
        rows=[row(t) for t in range(0,151,5)]
        rows[9]=row(45,p=.51)
        result=replay({'A':rows},'unified_value')
        self.assertEqual(len(result['episodes']),1)
        e=result['episodes'][0];self.assertEqual(e['censor'],'MANUAL_BUY_INVALIDATED')
        self.assertIsNone(e['scenario'])

    def test_no_best_future_price_for_exit(self):
        e=reverse(enter());episode=e.closed[0];rows=[row(t) for t in range(0,901,5)]
        for r in rows:
            if r['time']>=episode['exit']['available']+30:r.update(up_bid=.99,up_ask=1.,down_bid=0.,down_ask=.01)
        self.assertLess(score_episode(episode,rows)['scenario']['exit_bid'],.99)

    def test_signal_only_all_paths(self):
        e=reverse(enter())
        for out in e.events:
            self.assertFalse(out['actionable']);self.assertFalse(out['production_enabled'])
            self.assertTrue(out['signal_only']);self.assertFalse(out['orders'])
            self.assertIsNone(out['manual_fill']);self.assertIsNone(out['realized_profit'])


class NativeRegression(unittest.TestCase):
    def test_bad_native_evidence_and_final_independence(self):
        for change in ('quote','fee','features','future','settlement'):
            f=value_frame(offset=200)
            if change=='quote':f['quote']['ticker']='OTHER'
            if change=='fee':f.pop('fee_schedule')
            if change=='features':f['model_features']['values']['current_coinbase_close']+=1
            if change=='future':f['btc_received']=f['feature_cutoff']+1
            if change=='settlement':f=samples(value_frame(offset=870.9));f['settlement_evidence']['samples'][0]['received_ts']=f['captured_ts']+1
            before=deepcopy(f);out=NativeCandidate().process(f,f['captured_ts'])
            self.assertIn('reason',out);self.assertFalse(out['actionable']);self.assertEqual(f,before)
        f=value_frame(offset=200);final=protected_frame(f,f['captured_ts'])[0]['final']
        NativeCandidate().process(f,f['captured_ts'])
        self.assertEqual(protected_frame(f,f['captured_ts'])[0]['final'],final)

    def test_single_authentic_native_frame_no_invented_history(self):
        raw=json.loads(Path('audit/existing_evidence_20261011/early_native_replay_frame.json').read_text())
        f=raw.get('frame',raw)
        if 'kind' not in f:f=raw.get('entry_provenance',raw)
        result=NativeCandidate().process(f,f.get('captured_ts',0))
        self.assertIsNone(result['event']);self.assertFalse(result['actionable'])


if __name__=='__main__':unittest.main()
