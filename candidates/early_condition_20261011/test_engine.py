"""Mechanism/regression tests ONLY; historical performance is in study results."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from .engine import Engine, Rules, economics, screen, features, digest
from .native import NativeCandidate
from .study import replay, stats, score_episode
from candidates.early_opportunity_20261011.test_candidate import value_frame, samples
from btc15_v2_product.directional import protected_frame


def row(t,side='UP',delta=None,bid=None,contract='A',close=900,p=.85):
    delta=20+.5*t if delta is None else delta
    bid=min(.75,.20+.001*t) if bid is None else bid
    sign=1 if side=='UP' else -1
    r=dict(time=float(t),received=float(t),left=close-t,target=100000.,btc=100000+sign*delta,brti=100000+sign*(delta-2),
        side=side,p=p,healthy=True,contract=contract,publication_id=str((contract,t)),source_epoch='test',evidence_class='SYNTHETIC_FIXTURE')
    ask=bid+.01
    r.update({side.lower()+'_bid':bid,side.lower()+'_ask':ask,('down'if side=='UP'else'up')+'_bid':1-ask,('down'if side=='UP'else'up')+'_ask':1-bid})
    return r


def enter(side='UP'):
    e=Engine(proposal_mode=True)
    for t in range(0,151,5):e.process(row(t,side))
    assert e.origin
    return e


def reverse(e,side='UP'):
    for t in range(155,271,5):
        e.process(row(t,side,delta=95-2*(t-150),bid=max(.05,.35-.002*(t-150))))
    assert e.terminal
    return e


class Lifecycle(unittest.TestCase):
    def test_buy_hold_watch_exit_both_sides(self):
        for side in ('UP','DOWN'):
            e=reverse(enter(side),side)
            events=[x['event']for x in e.events]
            self.assertEqual(events[0],'BUY');self.assertIn('WATCH',events);self.assertIn('EXIT',events)
            self.assertLess(events.index('WATCH'),events.index('EXIT'))
            self.assertEqual(e.closed[0]['origin']['side'],side)
            self.assertLess(e.terminal['net_quote_scenario'],0)
            self.assertIsNone(e.terminal['realized_profit'])

    def test_no_fixed_holding_time_exit(self):
        e=enter()
        for t in range(155,751,5):e.process(row(t))
        self.assertIsNone(e.terminal)
        self.assertEqual(e.guidance,'HOLD')
        self.assertGreater(e.last['time']-e.origin['time'],420)

    def test_one_noise_update_and_confidence_alone_do_not_exit(self):
        e=enter()
        f=row(155,p=.50,delta=80,bid=.33);e.process(f)
        for t in range(160,251,5):e.process(row(t,p=.51))
        self.assertIsNone(e.terminal);self.assertEqual(e.guidance,'HOLD')

    def test_watch_recovers_hold(self):
        e=enter()
        # Flat prices lose momentum and the quote weakens, but both structural
        # boundaries remain intact; warning can recover without terminal latch.
        for t in range(155,206,5):e.process(row(t,delta=95,bid=.35-.0005*(t-150)))
        self.assertEqual(e.guidance,'WATCH');self.assertIsNone(e.terminal)
        for t in range(210,281,5):e.process(row(t,delta=95+(t-205),bid=.35+.001*(t-205)))
        self.assertEqual(e.guidance,'HOLD');self.assertIsNone(e.terminal)
        self.assertIn('HOLD',[r['event']for r in e.events])

    def test_distinct_same_side_reentry(self):
        e=reverse(enter());first=e.origin['id']
        for t in range(275,561,5):e.process(row(t,delta=-145+1.7*(t-270),bid=.10+.001*(t-270)))
        buys=[x for x in e.events if x['event']=='BUY']
        self.assertEqual(len(buys),2);self.assertNotEqual(first,e.origin['id'])

    def test_up_down_and_down_up_reentry(self):
        for side in ('UP','DOWN'):
            e=reverse(enter(side),side);opposite='DOWN'if side=='UP'else'UP'
            for t in range(275,561,5):e.process(row(t,opposite,delta=145+(t-270)*.5,bid=.30+.001*(t-270)))
            buys=[x for x in e.events if x['event']=='BUY']
            self.assertEqual([x['side']for x in buys],[side,opposite])

    def test_unchanged_setup_and_duplicates_suppressed(self):
        e=enter();original=e.origin['id'];last=deepcopy(e.last)
        for _ in range(10):self.assertIsNone(e.process(last)['event'])
        for t in range(155,400,5):e.process(row(t))
        self.assertEqual(sum(x['event']=='BUY'for x in e.events),1);self.assertEqual(e.origin['id'],original)

    def test_outage_cannot_reset_or_invent_fill(self):
        e=reverse(enter());e.reset_seen=False
        x=row(275);x['healthy']=False;e.process(x)
        self.assertFalse(e.reset_seen);self.assertEqual(len(e.closed),1)
        e2=enter();x=row(155);x['healthy']=False;r=e2.process(x)
        self.assertEqual(r['guidance'],'WATCH');self.assertIsNone(r['executable_exit_bid']);self.assertIsNone(e2.terminal)

    def test_rollover_and_old_contract_and_expiry(self):
        e=enter();e.process(row(900,contract='B',close=1800))
        self.assertIsNone(e.origin);self.assertEqual(e.closed[-1]['censor'],'ROLLOVER_WITHOUT_EXIT')
        x=row(905,contract='A',close=1800)
        self.assertIn('OLDER_CONTRACT',e.process(x)['reasons'])
        x=row(1800,contract='B',close=1800)
        self.assertIn('DELAYED_OR_EXPIRED',e.process(x)['reasons'])

    def test_settlement_path_requires_causal_binding(self):
        for identity in ('A','OTHER'):
            e=enter()
            for t in range(155,841,5):e.process(row(t))
            for t in range(845,896,5):
                x=row(t,delta=440,bid=.75-.0005*(t-840))
                x['settlement']=dict(verified_causal=True,contract=identity,asof=float(t),hurdle=100500.)
                e.process(x)
            if identity=='A':
                self.assertIsNotNone(e.terminal);self.assertEqual(e.terminal['reason'],'SETTLEMENT_BREAKDOWN')
            else:self.assertIsNone(e.terminal)

    def test_late_entry_rejected_29_seconds_and_other_late_prices(self):
        for left in (29.1,15,5,1.1,189):
            e=Engine(proposal_mode=True)
            for t in range(0,151,5):e.process(row(t,close=130+left))
            self.assertIsNone(e.origin)

    def test_economic_profile_blocks_all_unsupported_proposals(self):
        for side in ('UP','DOWN'):
            e=Engine()
            for t in range(0,200,5):e.process(row(t,side,p=.99))
            self.assertIsNone(e.origin)

    def test_fee_reserve_and_supported_price_range(self):
        r=row(150);c=dict(supported=True,gross_gain_lower=.05,min_left=200,max_left=800,min_ask=.1,max_ask=.8)
        p={'cells':{'UP_LOW':c}}
        self.assertFalse(economics(r,'UP',p,Rules())['ready'])
        c['gross_gain_lower']=.10
        self.assertTrue(economics(r,'UP',p,Rules())['ready'])
        c['min_left']=800
        self.assertFalse(economics(r,'UP',p,Rules())['ready'])

    def test_delayed_missing_history_and_target_conflict(self):
        e=enter();x=row(155);x['received']=180
        self.assertEqual(e.process(x)['guidance'],'WATCH')
        self.assertIsNone(e.terminal)
        e=enter();x=row(155);x['target']+=1
        self.assertIn('CONTRACT_IDENTITY_CONFLICT',e.process(x)['reasons'])

    def test_prefix_causality(self):
        rows=[row(t)for t in range(0,301,5)]
        a=Engine(proposal_mode=True);b=Engine(proposal_mode=True)
        out=[a.process(r)for r in rows[:40]]
        future=[b.process(r)for r in rows]
        self.assertEqual(out,future[:40])

    def test_replay_does_not_substitute_future_best_bid(self):
        e=reverse(enter());seq=[row(t)for t in range(0,901,5)]
        episode=e.closed[0];exit_time=episode['exit']['available'];entry_time=episode['origin']['decision_available']
        for r in seq:
            if r['time']>=exit_time+30:r.update(up_bid=.99,up_ask=1.,down_bid=0,down_ask=.01)
        scored=score_episode(episode,seq,10)
        self.assertLess(scored['scenario']['exit_bid'],.99)
        self.assertGreaterEqual(scored['scenario']['exit_at'],exit_time+10)

    def test_observed_quote_is_never_confirmed_fill(self):
        e=reverse(enter())
        for event in e.events:
            self.assertFalse(event['actionable']);self.assertFalse(event['production_enabled'])
            self.assertTrue(event['signal_only']);self.assertFalse(event['orders']);self.assertIsNone(event['manual_fill'])


class Native(unittest.TestCase):
    def test_actual_recovered_frame_no_invented_history(self):
        p=Path('audit/existing_evidence_20261011/early_native_replay_frame.json')
        raw=json.loads(p.read_text())
        # Saved artifact includes original raw native evidence under frame.
        f=raw.get('frame',raw)
        if 'kind'not in f:f=raw.get('entry_provenance',raw)
        n=NativeCandidate();result=n.process(f,f.get('captured_ts',0))
        self.assertIsNone(result['event']);self.assertFalse(result['actionable'])

    def test_native_provenance_errors(self):
        for change in ('quote','fee','features','future','settlement'):
            f=value_frame(offset=200)
            if change=='quote':f['quote']['ticker']='OTHER'
            if change=='fee':f.pop('fee_schedule')
            if change=='features':f['model_features']['values']['current_coinbase_close']+=1
            if change=='future':f['btc_received']=f['feature_cutoff']+1
            if change=='settlement':f=samples(value_frame(offset=870.9));f['settlement_evidence']['samples'][0]['received_ts']=f['captured_ts']+1
            out=NativeCandidate().process(f,f['captured_ts'])
            self.assertIn('reason',out,change);self.assertIsNone(out['event'])

    def test_final_and_scalp_ownership(self):
        f=value_frame(offset=200);before=deepcopy(f);final=protected_frame(f,f['captured_ts'])[0]['final']
        NativeCandidate().process(f,f['captured_ts'])
        self.assertEqual(f,before);self.assertEqual(protected_frame(f,f['captured_ts'])[0]['final'],final)
        text=Path('candidates/early_condition_20261011/engine.py').read_text()
        self.assertNotIn('import scalp',text);self.assertNotIn('protected_frame(',text)


if __name__=='__main__':unittest.main()
