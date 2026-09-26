"""Adversarial 2020 timestamp fixtures. No validation-cohort or predictive scoring."""
import ast
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import threading
import time
from types import SimpleNamespace
import unittest
from urllib.request import urlopen

from btc15_kalshi_quote_provenance_v1 import Book
from btc15_information_v1 import (
    ACTION, INFO, FIELDS, FIELD_CLASSES, AUTHORITATIVE_FIELDS, AUTHORITY_CLASSES,
    FairAssessment, InformationPublisher, Unavailable, identity, iso, pack, unpack, validate,
)
from btc15_information_native_v1 import NativeExport, instrument, server_for as native_server
from btc15_information_service_v1 import LocalIngress, response, server_for as info_server, step
from completion_audit.isolated_decision_v2 import FrozenRuntime, stable
from test_btc15_isolated_decision_v2 import completed, fixture, OPEN, TICKER


def provider(inp, sequence=None, epoch='quote-owner'):
    proof = deepcopy(inp['proof'])
    if sequence is not None:
        proof['events'][0]['seq'] = sequence-1
        proof['events'][1]['seq'] = sequence
    book = Book(inp['market']['ticker'])
    for event in proof['events']:
        book.apply(event)
    return SimpleNamespace(lock=threading.Lock(), ticker=inp['market']['ticker'], book=book,
                           events=proof['events'], epoch=epoch)


class Rig:
    def __init__(self, initial, offset=300., ask=.41, brti_delay=2.4):
        self.runtime = initial.fork()
        self.at = OPEN+offset
        inp = fixture(offset, ask=ask, brti_delay=brti_delay)
        self.provider = provider(inp, int(offset*100))
        self.export = NativeExport(clock=lambda:self.at, epoch='native-owner',
                                   provider_reader=lambda:self.provider)
        self.runtime.ns['_btc15_information_offer'] = self.export.offer
        loop = next(n for n in instrument(self.runtime.tree).body
                    if isinstance(n,ast.While) and isinstance(n.test,ast.Name) and n.test.id=='running')
        self.runtime.loop = compile(ast.Module(body=[loop], type_ignores=[]), '<instrumented>', 'exec')
        self.output = self.runtime.step(inp)
        if self.export.anchor is None:
            raise AssertionError(self.export.last_offer_error)

    def tick(self, offset, **kwargs):
        self.at = OPEN+offset
        inp = fixture(offset, **kwargs)
        self.provider = provider(inp, int(offset*100))
        self.output = self.runtime.step(inp)
        return inp, self.output

    def sources(self, offset, ask=.41, brti_value=100080, brti_delay=2.4, epoch='owner'):
        self.at = OPEN+offset
        inp = fixture(offset, ask=ask, brti_value=brti_value, brti_delay=brti_delay)
        self.provider = provider(inp, int(offset*100))
        self.runtime.ns['_brti_delivery'].accept(brti_value, self.at-brti_delay, self.at-.01, epoch)
        return inp

    def publish(self, publisher):
        return step(publisher,self.export,lambda:self.at)

    def read(self, publisher, offset=None, frame_id=None):
        if offset is not None:
            self.at=OPEN+offset
        path='/information' if frame_id is None else '/information/frame/'+frame_id
        return unpack(response(publisher,self.export,path,lambda:self.at)[1])


class InformationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial = FrozenRuntime(completed())
        cls.fair = FairAssessment()

    def make(self, **kwargs):
        return Rig(self.initial, **kwargs), InformationPublisher(self.fair)

    def test_native_feature_and_probability_exact_at_same_cut(self):
        rig, pub = self.make()
        self.assertTrue(rig.publish(pub))
        out = rig.read(pub)
        self.assertEqual(out['probability_up'], rig.runtime.ns['_ec_live']['up_fair'])
        self.assertEqual(out['range5'], rig.runtime.ns['_ec_live']['range5'])
        self.assertEqual(out['probability_up_change_since_native'], 0.)
        self.assertEqual(out['status'], 'AVAILABLE')

    def test_protection_status_is_informational_clock_derived_only(self):
        rig,pub=self.make();rig.publish(pub)
        out=rig.read(pub)
        self.assertAlmostEqual(out['flip_risk_pct'],100*out['model_flip_probability'])
        self.assertEqual(out['protection_phase'],'NORMAL')
        self.assertIs(out['five_minute_caution'],False)
        self.assertIs(out['three_minute_guard'],False)
        rig.at=OPEN+721
        rig.runtime.ns['_brti_delivery'].accept(100080,rig.at-2.4,rig.at-.01,'owner')
        rig.provider=provider(fixture(721),72100)
        self.assertTrue(rig.publish(pub))
        out=rig.read(pub)
        self.assertEqual(out['protection_phase'],'3M_GUARD')
        self.assertIs(out['three_minute_guard'],True)
        self.assertFalse(set(out)&set(AUTHORITATIVE_FIELDS))

    def test_protection_watch_cannot_be_position_or_exit_authority(self):
        rig,pub=self.make();rig.publish(pub);out=rig.read(pub)
        self.assertEqual(out['protection_watch'],'NORMAL')
        for forbidden in ('position_status','hold','protect','exit','action','armed'):
            self.assertNotIn(forbidden,out)
        self.assertFalse(set(out)&set(AUTHORITATIVE_FIELDS))

    def test_closed_output_schema_classifies_every_field_and_has_no_action(self):
        rig,pub=self.make();rig.publish(pub)
        for out in (rig.read(pub), pub.read({},OPEN+306)):
            self.assertEqual(set(out),set(FIELDS))
            self.assertEqual(set(out),set(FIELD_CLASSES))
            self.assertEqual(set(FIELD_CLASSES.values()),{INFO})
            self.assertFalse(set(out)&set(AUTHORITATIVE_FIELDS))
            self.assertEqual(out['authority'],INFO)
            self.assertIs(out['orders'],False)
        self.assertEqual(set(AUTHORITY_CLASSES.values()),{ACTION})

    def test_instrumentation_only_adds_one_read_observer_expression(self):
        original=self.initial.tree; altered=instrument(original)
        loop=next(n for n in altered.body if isinstance(n,ast.While) and isinstance(n.test,ast.Name) and n.test.id=='running')
        block=next(n for n in loop.body if isinstance(n,ast.Try))
        observer=block.body.pop()
        self.assertEqual(ast.unparse(observer),'_btc15_information_offer(globals())')
        self.assertEqual(ast.dump(altered,include_attributes=False),ast.dump(original,include_attributes=False))

    def test_all_native_outputs_and_166_plus_state_bindings_equal_with_fast_reads(self):
        oracle=self.initial.fork();rig,pub=self.make()
        expected=oracle.step(fixture(300))
        self.assertEqual(stable(rig.output),stable(expected))
        self.assertEqual(stable(rig.runtime.snapshot()),stable(oracle.snapshot()))
        for cut in (305.17,310.02,315.2,330.19,335.23):
            # The real source owner continues independently of either decision clock.
            for t in (cut-1.,cut-.5):
                inp=rig.sources(t,ask=.11 if t==cut-1 else .81,brti_value=99950)
                receipt=inp['brti_receipts'][0]
                oracle.ns['_brti_delivery'].accept(*receipt)
                before=stable(rig.runtime.snapshot())
                rig.publish(pub);rig.read(pub);rig.read(pub)
                self.assertEqual(stable(rig.runtime.snapshot()),before)
            inp,actual=rig.tick(cut,ask=.35 if cut<315 else .75,quote_wait=cut==315.2)
            expected=oracle.step(inp)
            self.assertEqual(stable(actual),stable(expected))
            self.assertEqual(stable(rig.runtime.snapshot()),stable(oracle.snapshot()))

    def test_many_repeated_queries_do_not_evaluate_or_renew_any_clock(self):
        rig,pub=self.make();rig.publish(pub)
        first=rig.read(pub);before=stable(rig.runtime.snapshot())
        for i in range(20):
            rig.at=OPEN+300+i*.03
            self.assertFalse(rig.publish(pub))
            out=rig.read(pub)
            for field in ('frame_id','evaluated_ts','published_ts','expires_at'):
                self.assertEqual(out[field],first[field])
        self.assertEqual(len(pub.frames),1)
        self.assertEqual(stable(rig.runtime.snapshot()),before)

    def test_only_new_brti_updates_information_not_native_state(self):
        rig,pub=self.make();rig.publish(pub)
        rig.at=OPEN+301
        rig.runtime.ns['_brti_delivery'].accept(99950,rig.at-2.4,rig.at-.01,'owner')
        before=stable(rig.runtime.snapshot())
        self.assertTrue(rig.publish(pub));out=rig.read(pub)
        self.assertEqual(out['brti_side'],'DOWN')
        self.assertEqual(out['btc_source_ts'],OPEN+299.9)
        self.assertEqual(stable(rig.runtime.snapshot()),before)

    def test_fast_quotes_change_information_without_entries_or_candles(self):
        rig,pub=self.make();base=unpack(rig.export.anchor[0])
        for t,ask in ((300.1,.11),(300.2,.91),(300.3,.31)):
            rig.sources(t,ask=ask)
            before=stable(rig.runtime.snapshot())
            self.assertTrue(rig.publish(pub))
            out=rig.read(pub);self.assertAlmostEqual(out['up_ask'],ask)
            self.assertEqual(unpack(rig.export.anchor[0])['ticks'],base['ticks'])
            self.assertEqual(stable(rig.runtime.snapshot()),before)

    def test_partial_candle_extremes_only_change_on_native_tick(self):
        rig,pub=self.make(offset=301)
        rig.publish(pub);original=rig.read(pub)['range5']
        rig.sources(302,brti_value=150000)
        rig.publish(pub);self.assertEqual(rig.read(pub)['range5'],original)
        rig.tick(305,btc=150000)
        rig.publish(pub);self.assertGreater(rig.read(pub)['range5'],original)

    def test_persistence_boundary_extras_never_add_or_prune_native_hits(self):
        rig,pub=self.make(offset=270)
        rig.tick(300)
        original=stable((rig.runtime.ns['_early_hist'],rig.runtime.ns['_unified_hist']))
        for t in (300.001,300.01,300.1,301):
            rig.sources(t);rig.publish(pub)
            self.assertEqual(stable((rig.runtime.ns['_early_hist'],rig.runtime.ns['_unified_hist'])),original)

    def test_armed_target_counterexample_preserves_actual_later_exit_both_sides(self):
        for side,ask in (('UP',.53),('DOWN',.49)):
            rig,pub=self.make(offset=295,ask=ask)
            rig.runtime.ns['_start_profit_shadow'](dict(signal_id='native',contract=TICKER,side=side,
                entry_ts=OPEN+290,signal_timestamp_utc='synthetic',entry_ask=.30))
            rig.tick(300,ask=ask)
            self.assertTrue(rig.runtime.ns['_profit_shadow_pending'][0]['armed'])
            before=stable(rig.runtime.snapshot())
            for t in (301,302,303,304):
                rig.at=OPEN+t  # Identical prices and genuinely newer agreeing BRTI.
                rig.runtime.ns['_brti_delivery'].accept(100080 if side=='UP' else 99920,OPEN+t-2.4,OPEN+t-.01,'owner')
                source_state=stable(rig.runtime.snapshot())
                rig.publish(pub);rig.read(pub)
                self.assertEqual(stable(rig.runtime.snapshot()),source_state)
                self.assertEqual(len(rig.runtime.ns['_profit_shadow_pending']),1)
            _,out=rig.tick(305,ask=ask,brti_value=100080 if side=='UP' else 99920)
            exits=[v for k,v in out['records'] if k=='PROFIT_SHADOW_LOG']
            self.assertEqual(exits[0]['exit_reason'],'TARGET_20')
            self.assertEqual(exits[0]['exit_seconds'],15.)

    def test_cooldowns_events_and_protection_functions_not_called_on_fast_path(self):
        rig,pub=self.make()
        def forbidden(*args,**kwargs):raise AssertionError('Action function called')
        for name in ('log_early_conf_shadow','log_unified_subminute','_update_profit_shadow',
                     '_start_profit_shadow','_maybe_true_scalp_signal','update_pending','maybe_create_event'):
            rig.runtime.ns[name]=forbidden
        before=stable(rig.runtime.snapshot())
        for t in (301,301.5,302):
            rig.at=OPEN+t
            self.assertTrue(rig.publish(pub) if t==301 else not rig.publish(pub))
            rig.read(pub)
        self.assertEqual(stable(rig.runtime.snapshot()),before)

    def test_brti_exact_five_second_deadline_then_wait_has_no_values(self):
        rig,pub=self.make();rig.publish(pub)
        self.assertEqual(rig.read(pub,302.6)['status'],'AVAILABLE')
        # Health can be unavailable after expiry; API must redact all dependent values.
        status,raw=response(pub,rig.export,'/information',lambda:OPEN+302.6001)
        out=unpack(raw)
        self.assertEqual(status,200);self.assertEqual(out['status'],'WAIT')
        for name in ('probability_up','up_ask','brti_value','frame_id','target'):
            self.assertIsNone(out[name])

    def test_stale_future_receipt_and_source_rejected_at_capture(self):
        rig,pub=self.make();raw=unpack(rig.export.capture())
        for field,value in (('source',OPEN+301),('received',OPEN+301),('source',OPEN+294.999)):
            changed=deepcopy(raw);changed['brti'][field]=value
            self.assertFalse(pub.offer(pack(changed),rig.export.health,lambda:rig.at))
            self.assertIsNone(pub.latest)

    def test_inference_latency_rechecked_after_evaluation(self):
        rig,pub=self.make();raw=rig.export.capture();health=rig.export.health()
        class Slow:
            def evaluate(_,f,q):
                result=self.fair.evaluate(f,q);rig.at+=2.601;return result
        pub.evaluator=Slow()
        self.assertFalse(pub.offer(raw,lambda:dict(health,observed=rig.at),lambda:rig.at))
        self.assertIsNone(pub.latest)

    def test_health_lease_expiry_and_owner_restart_invalidate_retained_frame(self):
        rig,pub=self.make();rig.publish(pub);health=rig.export.health()
        self.assertEqual(pub.read(health,OPEN+301.001)['status'],'WAIT')
        for field,value in (('native_epoch','new-native'),('brti_epoch','new-brti'),
                            ('quote_epoch','new-quote'),('anchor_id','missing'),('ready',False),('observed',OPEN+303)):
            out=pub.read(dict(health,**{field:value}),OPEN+301.001)
            self.assertEqual(out['status'],'WAIT')

    def test_owner_restart_during_inference_fails_and_new_source_recovers(self):
        rig,pub=self.make();raw=rig.export.capture()
        calls=[]
        def health():
            h=rig.export.health();calls.append(1)
            if len(calls)>1:h['brti_epoch']='restarted'
            return h
        self.assertFalse(pub.offer(raw,health,lambda:rig.at))
        rig.sources(301,epoch='restarted')
        self.assertTrue(rig.publish(pub));self.assertEqual(rig.read(pub)['status'],'AVAILABLE')

    def test_quote_interruption_recovery_does_not_resurrect_a_duplicate(self):
        rig,pub=self.make();rig.publish(pub)
        rig.provider.book.valid=False
        step(pub,rig.export,lambda:rig.at)
        self.assertIsNone(pub.latest)
        rig.provider.book.valid=True
        self.assertFalse(rig.publish(pub))
        self.assertEqual(rig.read(pub)['status'],'WAIT')
        rig.sources(301)
        self.assertTrue(rig.publish(pub));self.assertEqual(rig.read(pub)['status'],'AVAILABLE')

    def test_native_export_failure_does_not_change_original_state(self):
        rig,pub=self.make();before=stable(rig.runtime.snapshot())
        broken=dict(rig.runtime.ns);broken['_fair_ready']=False
        rig.export.offer(broken)
        self.assertIsNone(rig.export.anchor)
        self.assertEqual(stable(rig.runtime.snapshot()),before)

    def test_rollover_waits_for_native_anchor_and_cannot_relabel_old_frame(self):
        import pandas as pd
        initial=self.initial.fork()
        index=pd.date_range('2019-12-31T23:50Z','2020-01-01T00:16Z',freq='min')
        initial.ns['_fair_btc']=pd.DataFrame(dict(Open=100080.,High=100090.,Low=100070.,
            Close=100080.,Volume=1.,source_utc=index),index=index)
        rig=Rig(initial,offset=895);pub=InformationPublisher(self.fair);rig.publish(pub)
        old=pub.latest
        rig.at=OPEN+900
        self.assertEqual(pub.read({},rig.at,old)['status'],'WAIT')
        next_ticker='KXBTC15M-19DEC311930-15'
        rig.provider=provider(fixture(901,ticker=next_ticker),90100)
        with self.assertRaises(Unavailable):rig.export.capture()
        rig.tick(901,ticker=next_ticker)
        self.assertTrue(rig.publish(pub))
        self.assertEqual(rig.read(pub)['ticker'],next_ticker)
        self.assertEqual(pub.read({},rig.at,old)['status'],'WAIT')

    def test_same_quote_identity_with_changed_prices_is_not_novel(self):
        rig,pub=self.make();self.assertTrue(rig.publish(pub))
        rig.provider=provider(fixture(300,ask=.31),30000)
        self.assertFalse(rig.publish(pub))
        self.assertEqual(pub.reason,'QUOTE_CLOCK_RENEWAL_OR_CONFLICT')

    def test_sequence_only_acknowledgement_does_not_publish_new_information(self):
        rig,pub=self.make();rig.publish(pub);old=pub.latest
        event=dict(type='ok',sid=rig.provider.book.sid,seq=rig.provider.book.seq+1,
                   msg=dict(market_tickers=[TICKER]))
        rig.provider.book.apply(event);rig.provider.events.append(event)
        rig.at=OPEN+300.5
        self.assertFalse(rig.publish(pub))
        self.assertEqual(pub.latest,old)

    def test_fractional_native_cuts_match_frozen_probability_exactly(self):
        rig,pub=self.make()
        for cut in (305.17,310.02,315.2):
            rig.tick(cut,btc=100100.)
            self.assertTrue(rig.publish(pub))
            self.assertEqual(rig.read(pub)['probability_up'],rig.runtime.ns['_ec_live']['up_fair'])

    def test_same_contract_target_cannot_change_even_after_brti_owner_restart(self):
        rig,pub=self.make();rig.publish(pub)
        rig.sources(301,epoch='restart')
        a=unpack(rig.export.anchor[0]);a['target']+=1
        rig.export.anchor=(pack(a),rig.export.anchor[1])
        self.assertFalse(rig.publish(pub))
        self.assertEqual(pub.reason,'FIXED_MARKET_CHANGED')

    def test_information_reads_leave_owner_objects_and_original_sinks_untouched(self):
        rig,pub=self.make()
        owner=lambda:stable((rig.provider.ticker,rig.provider.epoch,rig.provider.events,
            vars(rig.provider.book),rig.runtime.ns['_brti_delivery'].states,
            rig.runtime.ns['_brti_delivery'].statuses,rig.runtime.ns['_brti_delivery'].seen,
            rig.runtime.ns['_brti_delivery'].epoch,rig.runtime.records,rig.runtime.inputs,
            rig.runtime.messages,rig.runtime.diag,rig.runtime.saves))
        before=owner()
        for _ in range(10):rig.publish(pub);rig.read(pub)
        self.assertEqual(owner(),before)

    def test_native_true_scalp_cooldown_state_equivalent_with_extra_information(self):
        import numpy as np
        @dataclass(frozen=True)
        class Certain:
            fixture_identity: str = 'SYNTHETIC_99_PERCENT_NOT_A_TRAINED_MODEL'
            def predict_proba(self,frame):return np.array([[.01,.99]])
        initial=self.initial.fork()
        initial.ns.update(_true_scalp_model=Certain(),_true_scalp_medians={},_true_scalp_ready=True)
        oracle=initial.fork();rig=Rig(initial,ask=.31);pub=InformationPublisher(self.fair)
        expected=oracle.step(fixture(300,ask=.31))
        self.assertEqual(stable(expected),stable(rig.output))
        self.assertTrue(rig.runtime.ns['_true_scalp_pending'])
        for t in (301,302):
            rig.sources(t,ask=.71)
            oracle.ns['_brti_delivery'].accept(*fixture(t,ask=.71)['brti_receipts'][0])
            before=stable(rig.runtime.snapshot())
            rig.publish(pub);rig.read(pub)
            self.assertEqual(stable(rig.runtime.snapshot()),before)
        inp,out=rig.tick(305,ask=.31)
        expected=oracle.step(inp)
        self.assertEqual(stable(expected),stable(out))
        self.assertEqual(stable(rig.runtime.snapshot()),stable(oracle.snapshot()))

    def test_unavailable_feature_support_never_carries_previous_probability(self):
        rig,pub=self.make();rig.publish(pub)
        rig.sources(301)
        a=unpack(rig.export.anchor[0]);a['completed']=a['completed'][-1:]
        rig.export.anchor=(pack(a),rig.export.anchor[1])
        self.assertFalse(rig.publish(pub))
        self.assertEqual(rig.read(pub)['status'],'WAIT')
        self.assertIsNone(rig.read(pub)['probability_up'])

    def test_quote_owner_restart_during_evaluation_fails_closed(self):
        rig,pub=self.make()
        class Restart:
            def evaluate(_,f,q):
                result=self.fair.evaluate(f,q)
                rig.provider.epoch='restarted'
                return result
        pub.evaluator=Restart()
        self.assertFalse(rig.publish(pub))
        self.assertEqual(rig.read(pub)['status'],'WAIT')

    def test_exact_boundary_btc_quote_and_market_expiry(self):
        rig,pub=self.make();f=unpack(rig.export.capture());h=rig.export.health()
        for field,value in (('quote_received',OPEN+300.01),('cut',OPEN+299.99)):
            bad=deepcopy(f);bad[field]=value
            self.assertFalse(pub.offer(pack(bad),lambda:h,lambda:rig.at))
        bad=deepcopy(f);bad['proof']['consumed_ms']+=1
        self.assertFalse(pub.offer(pack(bad),lambda:h,lambda:rig.at))
        for seconds in (310,900):
            with self.assertRaises(Unavailable):
                validate(pack(f),dict(h,observed=OPEN+seconds),OPEN+seconds)

    def test_regression_conflict_and_clock_renewal_fail_closed(self):
        rig,pub=self.make();rig.publish(pub)
        original=unpack(rig.export.capture())
        for mutate in (lambda f:f['brti'].update(value=99999),
                       lambda f:f['brti'].update(source=OPEN+297.5)):
            changed=deepcopy(original);mutate(changed)
            self.assertFalse(pub.offer(pack(changed),rig.export.health,lambda:rig.at))
            self.assertIsNone(pub.latest)

    def test_immutable_retention_exact_identity_no_latest_fallback(self):
        rig,pub=self.make();pub.retention=1;rig.publish(pub)
        first=pub.latest;saved=pub.frames[first]
        rig.sources(301);rig.publish(pub)
        self.assertEqual(rig.read(pub,frame_id=first)['status'],'WAIT')
        # A slow reader's captured bytes retain exact original source/proof.
        validate(saved[0],rig.export.health(),rig.at)
        self.assertEqual(unpack(saved[1])['evaluated_ts'],OPEN+300)

    def test_missing_or_corrupt_anchor_proof_model_and_schema_fail_closed(self):
        rig,pub=self.make();f=unpack(rig.export.capture())
        mutations=(lambda f:f['anchor'].update(weights='0'*64),
                   lambda f:f.update(anchor_id='0'*64),
                   lambda f:f['proof'].update(ticker='WRONG'),
                   lambda f:f['anchor']['ticks'].append([OPEN+301,OPEN+301,100080]),
                   lambda f:f.update(entry_price=.31))
        for mutation in mutations:
            bad=deepcopy(f);mutation(bad)
            self.assertFalse(pub.offer(pack(bad),rig.export.health,lambda:rig.at))
        with self.assertRaises(Unavailable):unpack(b'{"x":1,"x":2}')
        with self.assertRaises(Unavailable):unpack(b'{"x":NaN}')

    def test_busy_owner_fails_closed_without_mutation_or_waiting(self):
        rig,pub=self.make();before=stable(rig.runtime.snapshot())
        for lock in (rig.provider.lock,rig.runtime.ns['_brti_delivery'].lock):
            # RLock must be held on another thread to simulate contention.
            acquired=threading.Event();release=threading.Event()
            def hold():
                with lock:acquired.set();release.wait(2)
            thread=threading.Thread(target=hold);thread.start();acquired.wait(1)
            start=time.monotonic()
            with self.assertRaises(Unavailable):rig.export.capture()
            self.assertLess(time.monotonic()-start,.5)
            release.set();thread.join(1)
        self.assertEqual(stable(rig.runtime.snapshot()),before)

    def test_real_loopback_handoff_http_read_wait_and_unknown_identity(self):
        rig,pub=self.make();native=native_server(rig.export)
        t=threading.Thread(target=native.serve_forever,daemon=True);t.start()
        ingress=LocalIngress(native.server_port);service=info_server(pub,ingress,clock=lambda:rig.at)
        t2=threading.Thread(target=service.serve_forever,daemon=True);t2.start()
        try:
            self.assertTrue(step(pub,ingress,lambda:rig.at))
            with urlopen(f'http://127.0.0.1:{service.server_port}/information') as reply:
                self.assertIn('no-store',reply.headers['Cache-Control'])
                out=unpack(reply.read());self.assertEqual(out['status'],'AVAILABLE')
            self.assertEqual(out['authority'],INFO)
            _,raw=response(pub,ingress,'/information/frame/'+'0'*64,lambda:rig.at)
            self.assertEqual(unpack(raw)['status'],'WAIT')
            self.assertEqual(response(pub,ingress,'/state',lambda:rig.at)[0],404)
            rig.at=OPEN+303
            _,raw=response(pub,ingress,'/information',lambda:rig.at)
            self.assertEqual(unpack(raw)['status'],'WAIT')
        finally:
            service.shutdown();native.shutdown();service.server_close();native.server_close()
            t.join(1);t2.join(1)

    def test_wall_clock_regression_waits_without_republishing(self):
        rig,pub=self.make();rig.publish(pub);rig.read(pub)
        out=pub.read(rig.export.health(),OPEN+299)
        self.assertEqual(out['reason'],'CLOCK_REGRESSION')
        self.assertIsNone(out['probability_up'])

    def test_separate_inference_process_uses_only_read_only_loopback_ingress(self):
        import os
        import subprocess
        import sys
        rig,_=self.make();native=native_server(rig.export)
        thread=threading.Thread(target=native.serve_forever,daemon=True);thread.start()
        before=stable(rig.runtime.snapshot())
        script='''
import json,os,sys
from btc15_information_v1 import InformationPublisher,unpack
from btc15_information_service_v1 import LocalIngress,step,response
ingress=LocalIngress(int(sys.argv[1]));at=float(sys.argv[2])
publisher=InformationPublisher()
assert step(publisher,ingress,lambda:at)
code,body=response(publisher,ingress,'/information',lambda:at)
value=unpack(body)
print(json.dumps(dict(pid=os.getpid(),status=value['status'],probability_up=value['probability_up'])))
'''
        try:
            result=json.loads(subprocess.check_output([sys.executable,'-B','-c',script,
                str(native.server_port),str(rig.at)],text=True,timeout=30))
            self.assertNotEqual(result['pid'],os.getpid())
            self.assertEqual(result['status'],'AVAILABLE')
            self.assertEqual(result['probability_up'],rig.runtime.ns['_ec_live']['up_fair'])
            self.assertEqual(stable(rig.runtime.snapshot()),before)
        finally:
            native.shutdown();native.server_close();thread.join(1)


if __name__ == '__main__':
    unittest.main()
