"""Synthetic timestamped complete-loop engineering. No evaluation cohorts."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest
import numpy as np
import pandas as pd
from completion_audit.cadence_projection_probe_v1 import quote_proof, profit_namespace
from completion_audit.isolated_decision_v2 import (
    ARTIFACT_SHA, WEIGHTS_SHA, FUNCTION_NAMES, FrozenRuntime,
    ImmutableFrames, PhaseProjection, PhaseLatchProjection, stable, derive_companion_profit,
)

OPEN = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
TICKER = 'KXBTC15M-19DEC311915-15'


def fixture(offset, *, ask=.41, btc=100080., source_offset=None,
            quote_wait=False, brti_delay=2.4, brti_value=100080., ticker=TICKER):
    at = OPEN+offset
    source = at-.1 if source_offset is None else OPEN+source_offset
    opened = OPEN if ticker == TICKER else OPEN+900
    proof = quote_proof(round(at*1000), round((at-.2)*1000), ticker)
    proof['events'][0]['msg']['yes_dollars_fp'] = [[str(round(ask-.02, 4)), '10']]
    proof['events'][0]['msg']['no_dollars_fp'] = [[str(round(1-ask, 4)), '10']]
    proof['events'][1]['msg']['price_dollars'] = str(round(ask-.02, 4))
    return dict(decision=at, market=dict(
        ticker=ticker, open_time=datetime.fromtimestamp(opened, timezone.utc).isoformat(),
        close_time=datetime.fromtimestamp(opened+900, timezone.utc).isoformat(),
        floor_strike=100000., yes_bid_dollars=ask-.02, yes_ask_dollars=ask,
        no_bid_dollars=1-ask, no_ask_dollars=1-(ask-.02)),
        btc=btc, btc_source=datetime.fromtimestamp(source, timezone.utc),
        btc_received=datetime.fromtimestamp(source+.05, timezone.utc),
        proof=proof, quote_wait=quote_wait,
        brti_receipts=[(brti_value, at-brti_delay, at-.01, 'owner')])


def completed():
    index = pd.date_range('2019-12-31T23:50Z','2020-01-01T00:05Z',freq='min')
    prices = [100000+5*i+(-1)**i*2 for i in range(len(index))]
    return pd.DataFrame(dict(Open=prices, High=np.array(prices)+2,
                             Low=np.array(prices)-2, Close=prices, Volume=1.,
                             source_utc=index), index=index)


def frame(offset=300):
    inp = fixture(offset)
    at = inp['decision']
    return dict(decision=at, opened=OPEN, closed=OPEN+900, ticker=TICKER,
                brti=dict(ready=True, source=at-2.4, received=at-.01, epoch='owner'),
                btc=dict(source=at-.1, received=at-.05, value=inp['btc']),
                proof=inp['proof'], quotes=[.39,.41,.59,.61],
                rows=[dict(contract=TICKER, side=side, decision=at) for side in ('UP','DOWN')],
                model=dict(artifact=ARTIFACT_SHA, weights=WEIGHTS_SHA))


def validate(store, captured, checked, health=None):
    # Explicit synthetic current-owner health; this is never supplied by the
    # production-facing component itself.
    if health is None:
        health=dict(ready=True,epoch='owner',observed=checked)
    return store.validate(captured,checked,health)


class FullLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial = FrozenRuntime(completed())

    def test_fitted_model_executes_and_original_phase_really_is_exercised(self):
        runtime = self.initial.fork()
        out = runtime.step(fixture(300))
        self.assertFalse(any('WARNING' in m for m in out['messages']), out['messages'])
        self.assertEqual(len(out['inputs']), 1)
        self.assertEqual(out['inputs'][0]['weights_sha256'], WEIGHTS_SHA)
        rows = [row for path,row in out['records'] if path == 'UNIFIED_SUBMINUTE_LOG']
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['side_fair'] is not None for row in rows))
        self.assertEqual(rows[0]['candidate_persistence_30s'], 0)
        self.assertEqual(runtime.ns['iteration'], 1)

    def test_every_function_global_namespace_is_private(self):
        a = self.initial.fork(); b = a.fork()
        for name in FUNCTION_NAMES:
            self.assertIs(b.ns[name].__globals__, b.ns)
            self.assertIsNot(b.ns[name].__globals__, a.ns)
        self.assertIsNot(a.ns['_fair_rf'], b.ns['_fair_rf'])
        self.assertIsNot(a.ns['_brti_delivery'], b.ns['_brti_delivery'])
        self.assertIsNot(a.ns['_brti_lock'], b.ns['_brti_lock'])
        b.ns['later_temporary']={'value':1}
        b.restore(a.snapshot())
        self.assertNotIn('later_temporary',b.ns)

    def test_legacy_outputs_and_all_snapshot_state_match_with_extras(self):
        oracle = self.initial.fork(); candidate = PhaseProjection(self.initial.fork())
        cuts = (300.,305.17,310.02,315.2,330.19,335.23,340.1)
        for i,cut in enumerate(cuts):
            inp = fixture(cut, ask=(.41,.60,.32,.52)[i%4], btc=100080+(-1)**i*11,
                          quote_wait=i==3)
            expected = oracle.step(inp)
            actual = candidate.legacy(inp)
            self.assertEqual(stable(actual), stable(expected))
            self.assertEqual(stable(oracle.snapshot()), stable(candidate.runtime.snapshot()))
            frozen = stable(candidate.runtime.snapshot())
            for j in (1,2,3):
                micro = fixture(cut+j/5, ask=.21 if j==2 else .75, btc=100000+j*9)
                candidate.extra(micro)
                self.assertEqual(stable(candidate.runtime.snapshot()), frozen)

    def test_quote_wait_retains_btc_without_advancing_strategy_and_recovers(self):
        r = self.initial.fork(); r.step(fixture(300))
        before = deepcopy(r.ns['history']); hits = deepcopy(r.ns['_unified_hist'])
        r.step(fixture(305, quote_wait=True))
        self.assertEqual(r.ns['history'], before)
        self.assertEqual(r.ns['_unified_hist'], hits)
        self.assertEqual(len(r.ns['_ec_btc_ticks']), 2)
        result = r.step(fixture(310))
        self.assertFalse(any('WARNING' in m for m in result['messages']))
        self.assertEqual(r.ns['iteration'], 2)

    def test_rollover_only_commits_on_legacy_and_preserves_btc_closeouts(self):
        r = PhaseProjection(self.initial.fork()); r.legacy(fixture(895))
        snapshot = stable(r.runtime.snapshot())
        with self.assertRaises(ValueError):
            r.extra(fixture(901,ticker='KXBTC15M-19DEC311930-15'))
        self.assertEqual(stable(r.runtime.snapshot()), snapshot)
        r.legacy(fixture(901,ticker='KXBTC15M-19DEC311930-15'))
        self.assertEqual({row['contract'] for row in r.runtime.ns['history']}, {'KXBTC15M-19DEC311930-15'})
        self.assertEqual(len(r.runtime.ns['_ec_btc_ticks']), 2)
        self.assertIn(TICKER, r.runtime.ns['_brti_pending_contracts'])

    def test_repeated_identical_source_inputs_cannot_become_extra_decisions(self):
        r = PhaseProjection(self.initial.fork()); original=fixture(300); r.legacy(original)
        for cut in (300.1,300.2,301.,302.):
            duplicate = deepcopy(original); duplicate['decision']=OPEN+cut
            duplicate['proof']['source_time']=datetime.fromtimestamp(OPEN+cut,timezone.utc).isoformat()
            self.assertIsNone(r.extra(duplicate))

    def test_new_brti_between_legacy_is_causal_and_not_borrowed_back(self):
        r = PhaseProjection(self.initial.fork()); old=r.legacy(fixture(300,brti_value=100080))
        extra=r.extra(fixture(301,brti_value=99990))[0]
        oldrows=[v for k,v in old['records'] if k=='UNIFIED_SUBMINUTE_LOG']
        newrows=[v for k,v in extra['records'] if k=='UNIFIED_SUBMINUTE_LOG']
        self.assertEqual(oldrows[0]['brti_side'], 'UP')
        self.assertEqual(newrows[0]['brti_side'], 'DOWN')
        self.assertEqual(r.runtime.ns['_brti_delivery'].states[-1]['value'], 100080)

    def test_simple_phase_replacement_loses_actual_legacy_rolling_extreme(self):
        r=PhaseProjection(self.initial.fork())
        r.legacy(fixture(295,ask=.61))
        r.legacy(fixture(300,ask=.21))
        output=r.extra(fixture(301,ask=.61))[0]
        snap=next(v for k,v in output['records'] if k=='SNAPSHOT_LOG')
        self.assertEqual(snap['up_low_60s'], .61)
        self.assertEqual(min(v['up_ask'] for v in r.runtime.ns['history']), .21)

    def test_projection_only_entry_is_orphaned_on_next_projection(self):
        r=PhaseProjection(self.initial.fork()); r.legacy(fixture(300,ask=.51))
        first=r.extra(fixture(301,ask=.31))[1]
        second=r.extra(fixture(302,ask=.51))[1]
        born=[e for e in first['pending'] if e['entry_ts']==OPEN+301]
        self.assertEqual(len(born),1)
        self.assertFalse(any(e['event_id']==born[0]['event_id'] for e in second['pending']))

    def test_companion_birth_conflicts_with_original_global_repeat_gate(self):
        r=PhaseProjection(self.initial.fork()); r.legacy(fixture(300,ask=.51))
        extra=r.extra(fixture(301,ask=.31))[1]
        new=next(e for e in extra['pending'] if e['entry_ts']==OPEN+301)
        r.legacy(fixture(305,ask=.31))
        original=next(e for e in r.runtime.ns['pending'] if e['entry_ts']==OPEN+305)
        self.assertLess(original['entry_ts']-new['entry_ts'],r.runtime.ns['EVENT_SAMPLE_SPACING_SECONDS'])

    def test_committing_companion_birth_changes_next_legacy_state(self):
        oracle=self.initial.fork(); candidate=self.initial.fork()
        for runtime in (oracle,candidate): runtime.step(fixture(300,ask=.51))
        candidate.step(fixture(301,ask=.31))
        oracle.step(fixture(305,ask=.31));candidate.step(fixture(305,ask=.31))
        key=(TICKER,'UP')
        self.assertEqual(oracle.ns['last_event_created'][key],OPEN+305)
        self.assertEqual(candidate.ns['last_event_created'][key],OPEN+301)
        self.assertNotEqual(stable(oracle.snapshot()),stable(candidate.snapshot()))


    def test_phase_latches_preserve_extrema_btc_history_and_emitted_counts(self):
        r=PhaseLatchProjection(self.initial.fork())
        r.legacy(fixture(290,ask=.41))
        r.legacy(fixture(295,ask=.41))
        emitted=r.legacy(fixture(300,ask=.21))
        expected={path:[row['candidate_persistence_30s'] for p,row in emitted['records'] if p==path]
                  for path in ('EARLY_CONF_LOG','UNIFIED_SUBMINUTE_LOG')}
        frozen=stable(r.runtime.snapshot())
        for cut in (301,302,303,304):
            out,private=r.extra(fixture(cut,ask=.41))
            snap=next(row for path,row in out['records'] if path=='SNAPSHOT_LOG')
            self.assertEqual(snap['up_low_60s'],.21)
            for path,counts in expected.items():
                self.assertEqual([v['candidate_persistence_30s'] for k,v in out['records'] if k==path],counts)
            self.assertEqual(len(private['_ec_btc_ticks']),4)
            self.assertEqual(len(private['_early_hist']),3)
            self.assertEqual(len(private['_unified_hist']),6)
            self.assertEqual(stable(r.runtime.snapshot()),frozen)

    def test_latch_window_expires_by_time_without_adding_hits(self):
        r=PhaseLatchProjection(self.initial.fork())
        r.legacy(fixture(270,ask=.41))
        r.legacy(fixture(300,ask=.41))
        out=r.extra(fixture(300.001,ask=.41))[0]
        rows=[v for k,v in out['records'] if k=='UNIFIED_SUBMINUTE_LOG']
        self.assertEqual(rows[0]['candidate_persistence_30s'],0)
        self.assertEqual(len(r.runtime.ns['_unified_hist']),4)

    def test_latched_projection_still_advances_armed_exit_on_unchanged_book(self):
        r=PhaseLatchProjection(self.initial.fork())
        r.runtime.ns['_start_profit_shadow'](dict(signal_id='native',contract=TICKER,
            side='UP',entry_ts=OPEN+290,signal_timestamp_utc='synthetic',entry_ask=.30))
        r.legacy(fixture(300,ask=.53))
        self.assertTrue(r.runtime.ns['_profit_shadow_pending'][0]['armed'])
        # Only a genuinely newer BRTI observation; quotes/BTC unchanged.
        inp=fixture(301,ask=.53)
        original=r.anchor
        inp['btc_source']=original['btc_source'];inp['btc_received']=original['btc_received']
        inp['proof']=deepcopy(original['proof'])
        inp['proof']['source_time']=datetime.fromtimestamp(OPEN+301,timezone.utc).isoformat()
        out=r.extra(inp)[0]
        exits=[v for k,v in out['records'] if k=='PROFIT_SHADOW_LOG']
        self.assertEqual(exits[0]['exit_reason'],'TARGET_20')
        self.assertEqual(exits[0]['exit_seconds'],11.)
        self.assertEqual(len(r.runtime.ns['_profit_shadow_pending']),1)
        native=r.legacy(fixture(305,ask=.53))
        exits=[v for k,v in native['records'] if k=='PROFIT_SHADOW_LOG']
        self.assertEqual(exits[0]['exit_seconds'],15.)

    def test_true_scalp_companion_conflicts_with_120_second_cooldown(self):
        class CertainFixture:
            def predict_proba(self,frame):return np.array([[.01,.99]])
        for side in ('UP','DOWN'):
            r=PhaseLatchProjection(self.initial.fork())
            r.runtime.ns['_true_scalp_model']=CertainFixture()
            r.runtime.ns['_true_scalp_medians']={}
            r.runtime.ns['_true_scalp_ready']=True
            r.legacy(fixture(300,ask=.51))
            ask=.31 if side=='UP' else .71
            micro=r.extra(fixture(301,ask=ask))[1]
            birth=next(e for e in micro['_true_scalp_pending'] if e['side']==side)
            r.legacy(fixture(305,ask=ask))
            original=next(e for e in r.runtime.ns['_true_scalp_pending'] if e['side']==side)
            self.assertEqual(original['entry_ts']-birth['entry_ts'],4.)
            self.assertLess(4.,r.runtime.ns['TRUE_SCALP_COOLDOWN_SECONDS'])
            self.assertEqual(r.runtime.ns['_profit_shadow_pending'][0]['entry_ts'],OPEN+305)


    def test_phase_latch_next_legacy_decision_and_state_equal_oracle(self):
        oracle=self.initial.fork();candidate=PhaseLatchProjection(self.initial.fork())
        for cut in (300,305,310):
            inp=fixture(cut,ask=.41,btc=100080+cut%7)
            expected=oracle.step(inp);actual=candidate.legacy(inp)
            self.assertEqual(stable(actual),stable(expected))
            self.assertEqual(stable(candidate.runtime.snapshot()),stable(oracle.snapshot()))
            candidate.extra(fixture(cut+.1,ask=.11,btc=99950))
            candidate.extra(fixture(cut+.2,ask=.81,btc=100200))

    def test_partial_candle_and_source_caches_do_not_leak_micro_extremes(self):
        r=PhaseLatchProjection(self.initial.fork());r.legacy(fixture(301))
        before=stable(r.runtime.snapshot())
        out,state=r.extra(fixture(302,btc=150000,brti_value=150000))
        self.assertEqual(len(out['inputs']),1)
        self.assertEqual(out['inputs'][0]['features']['current_coinbase_close'],150000)
        self.assertEqual(stable(r.runtime.snapshot()),before)
        self.assertEqual(r.runtime.ns['_brti_delivery'].states[-1]['value'],100080)
        out=r.legacy(fixture(305,btc=100080))
        self.assertLess(out['inputs'][0]['features']['range5'],100)


class ImmutableFrameTests(unittest.TestCase):
    def test_unknown_current_health_is_not_qualified(self):
        s=ImmutableFrames();s.publish(frame())
        with self.assertRaises(ValueError):s.validate(s.capture(),OPEN+300)

    def test_slow_reader_keeps_exact_proof_while_newer_frame_publishes(self):
        store=ImmutableFrames();old=store.publish(frame(300));captured=store.capture(old)
        store.publish(frame(301));store.publish(frame(302))
        validated=validate(store,captured,OPEN+302)
        self.assertEqual(validated['decision'],OPEN+300)
        self.assertEqual(validated['proof']['source_time'],datetime.fromtimestamp(OPEN+300,timezone.utc).isoformat())

    def test_retained_bytes_survive_eviction_missing_id_never_borrows_latest(self):
        store=ImmutableFrames(limit=1);old=store.publish(frame());captured=store.capture(old)
        store.publish(frame(301))
        with self.assertRaises(KeyError):store.capture(old)
        self.assertEqual(validate(store,captured,OPEN+302)['decision'],OPEN+300)

    def test_age_boundary_and_stale_future_receipts(self):
        store=ImmutableFrames();store.publish(frame());captured=store.capture()
        validate(store,captured,OPEN+302.6)
        with self.assertRaises(ValueError):validate(store,captured,OPEN+302.601)
        for changes in ({'source':OPEN+301}, {'received':OPEN+300.001}, {'ready':False}, {'epoch':''}):
            f=frame();f['brti'].update(changes);store.publish(f)
            with self.assertRaises(ValueError):validate(store,store.capture(),OPEN+300)

    def test_missing_partial_mismatched_frames_fail_closed(self):
        variants=[]
        a=frame();a['rows']=a['rows'][:1];variants.append(a)
        a=frame();a['rows'][1]['decision']+=1;variants.append(a)
        a=frame();a['quotes'][0]=.40;variants.append(a)
        a=frame();a['model']['weights']='0'*64;variants.append(a)
        a=frame();a['rows'][0]['contract']='WRONG';variants.append(a)
        for a in variants:
            s=ImmutableFrames();s.publish(a)
            with self.assertRaises(ValueError):validate(s,s.capture(),OPEN+300)

    def test_future_quote_and_rollover_are_rejected(self):
        s=ImmutableFrames();f=frame();f['proof']['consumed_ms']+=1;s.publish(f)
        with self.assertRaises(ValueError):validate(s,s.capture(),OPEN+300)
        s.publish(frame(899))
        with self.assertRaises(ValueError):validate(s,s.capture(),OPEN+900)

    def test_publication_does_not_alias_input_and_hash_detects_change(self):
        s=ImmutableFrames();f=frame();identity=s.publish(f);f['brti']['source']+=100
        validate(s,s.capture(identity),OPEN+300)
        captured=s.capture(identity)
        with self.assertRaises(ValueError):validate(s,(identity,captured[1]+b' '),OPEN+300)


    def test_current_health_failure_recovery_and_owner_restart(self):
        s=ImmutableFrames();s.publish(frame());capture=s.capture()
        good=dict(ready=True,epoch='owner',observed=OPEN+301)
        validate(s,capture,OPEN+301,good)
        for change in ({'ready':False},{'epoch':'restarted'},{'observed':OPEN+302}):
            with self.assertRaises(ValueError):
                validate(s,capture,OPEN+301,dict(good,**change))
        validate(s,capture,OPEN+302,dict(good,observed=OPEN+302))
        with self.assertRaises(ValueError):validate(s,capture,OPEN+303,good)


class LifecycleAlternativesTests(unittest.TestCase):
    def test_append_only_origin_replayed_on_legacy_ticks_retains_protection(self):
        origin=dict(signal_id='MICRO',contract='A',side='UP',entry_ts=1.,
                    signal_timestamp_utc='synthetic',entry_ask=.30)
        tape=[(5.,.51),(10.,.51)]
        def derive(cut):
            env=profit_namespace();env['_start_profit_shadow'](deepcopy(origin))
            for when,bid in tape:
                if when<=cut:
                    env['_update_profit_shadow'](dict(contract='A',up_bid=bid),when,dict(ready=True,side='UP'))
            return deepcopy((env['_profit_shadow_pending'],env['rows']))
        self.assertFalse(derive(4)[0][0]['armed'])
        self.assertTrue(derive(5)[0][0]['armed'])
        for when in (5.01,6,7,8,9.99):self.assertEqual(derive(when),derive(5))
        self.assertEqual(derive(10)[1][0]['exit_reason'],'TARGET_20')
        self.assertEqual(derive(10)[1][0]['exit_seconds'],9.)

    def test_new_price_stop_recovery_needs_policy_choice_not_isolation(self):
        origin=dict(signal_id='MICRO',contract='A',side='DOWN',entry_ts=1.,
                    signal_timestamp_utc='synthetic',entry_ask=.30)
        def run(tape):
            e=profit_namespace();e['_start_profit_shadow'](origin)
            for at,bid in tape:e['_update_profit_shadow'](dict(contract='A',down_bid=bid),at,dict(ready=True,side='DOWN'))
            return e['rows']
        legacy=run([(5,.45),(10,.51)])
        faster=run([(5,.45),(6,.35),(10,.51)])
        self.assertEqual(legacy[0]['exit_reason'],'TARGET_20')
        self.assertEqual(faster[0]['exit_reason'],'TRAIL_PROTECT')
        self.assertNotEqual(legacy,faster)


    def test_companion_replay_is_query_count_independent_both_sides(self):
        for side in ('UP','DOWN'):
            origin=dict(signal_id='micro',contract='A',side=side,entry_ts=1.,
                        signal_timestamp_utc='synthetic',entry_ask=.30)
            tape=[dict(decision=t,snap=dict(contract='A',up_bid=bid,down_bid=bid),
                       brti=dict(ready=True,side=side)) for t,bid in ((5,.45),(10,.51))]
            original=deepcopy((origin,tape))
            at_arm=derive_companion_profit(origin,tape,5)
            for t in (5.001,6,7,8,9.99,5.1,6.4):
                self.assertEqual(derive_companion_profit(origin,tape,t),at_arm)
            self.assertEqual(derive_companion_profit(origin,tape,10)['exits'][0]['exit_reason'],'TARGET_20')
            self.assertEqual((origin,tape),original)

    def test_companion_replay_rollover_and_duplicate_legacy_timestamps(self):
        origin=dict(signal_id='micro',contract='A',side='UP',entry_ts=1.,
                    signal_timestamp_utc='synthetic',entry_ask=.30)
        tape=[dict(decision=5.,snap=dict(contract='B',up_bid=.60),brti=dict(ready=True,side='UP'))]
        self.assertEqual(derive_companion_profit(origin,tape,5),dict(pending=[],exits=[]))
        with self.assertRaises(ValueError):derive_companion_profit(origin,tape+deepcopy(tape),5)
        with self.assertRaises(ValueError):derive_companion_profit(origin,tape,.99)

    def test_brti_protection_and_trail_priority_remain_frozen(self):
        origin=dict(signal_id='micro',contract='A',side='UP',entry_ts=1.,
                    signal_timestamp_utc='synthetic',entry_ask=.30)
        def replay(bid):
            tape=[dict(decision=5,snap=dict(contract='A',up_bid=.45),brti=dict(ready=True,side='UP')),
                  dict(decision=10,snap=dict(contract='A',up_bid=bid),brti=dict(ready=True,side='DOWN'))]
            return derive_companion_profit(origin,tape,10)['exits'][0]['exit_reason']
        self.assertEqual(replay(.44),'BRTI_PROTECT')
        self.assertEqual(replay(.40),'TRAIL_PROTECT')


if __name__=='__main__':unittest.main()
