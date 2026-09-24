"""Engineering acceptance probes; passing tests can establish rejection.

Synthetic paths only. No closed validation or holdout observations are loaded.
"""
from collections import deque
from copy import deepcopy
import math
import unittest

from btc15_brti_delivery_v1 import Delivery
from btc15_kalshi_quote_provenance_v1 import replay
from completion_audit.cadence_projection_probe_v1 import (
    AnchorHistory, actual_parity_counterexample, frozen_functions, gate_inputs, profit_counterexample,
    persistence_phase_counterexample, profit_namespace, proof_counterexample, quote_proof, raw_ladders,
    source_availability,
)


class IsolatedClockTests(unittest.TestCase):
    def test_unchanged_state_never_accumulates_micro_persistence(self):
        h = AnchorHistory()
        for at in range(0, 31, 5):
            h.commit(at, 'A')
            committed = deepcopy(h.__dict__)
            for micro in (at+.01, at+.5, at+1, at+2, at+3, at+4):
                state = h.project(micro, 'A')
                self.assertLessEqual(state['early'], 7)
                self.assertLessEqual(state['unified']['UP'], 7)
                self.assertEqual(h.__dict__, committed)
        self.assertEqual(h.project(30, 'A')['early'], 7)

    def test_exact_legacy_counts_with_jitter_and_skipped_quote_cycles(self):
        h = AnchorHistory()
        ns = frozen_functions({'_unified_candidate_persistence'}, _unified_hist=deque())
        for at in (0., 5.17, 10.02, 25.2, 30.19, 35.23, 55.1):
            h.commit(at, 'A', candidate=at != 10.02)
            ns['_unified_hist'] = deepcopy(h.unified)
            for cut in (at, at+.001, at+1.1, at+4.5):
                for side in ('UP', 'DOWN'):
                    self.assertEqual(h.project(cut, 'A')['unified'][side],
                                     ns['_unified_candidate_persistence']('A', side, cut))

    def test_rollover_retains_btc_but_not_cross_contract_raw_or_counts(self):
        h = AnchorHistory()
        h.commit(895, 'A'); h.commit(900, 'B', candidate=False)
        self.assertEqual([x['contract'] for x in h.raw], ['B'])
        self.assertEqual(len(h.btc), 2)
        self.assertEqual(h.project(901, 'B'), dict(early=0, unified=dict(UP=0, DOWN=0)))

    def test_persistence_window_is_timestamp_based_not_number_of_projections(self):
        h = AnchorHistory(); h.commit(0, 'A')
        self.assertEqual(h.project(30, 'A')['early'], 1)
        self.assertEqual(h.project(30.000001, 'A')['early'], 0)
        for i in range(1000): h.project(30+i/1000, 'A')
        self.assertEqual(len(h.early), 1)

    def test_duplicate_anchor_and_future_anchor_rejected(self):
        h = AnchorHistory(); h.commit(5, 'A')
        for cut in (4, 5):
            with self.assertRaises(ValueError): h.commit(cut, 'A')
        with self.assertRaises(ValueError): h.project(4.9, 'A')

    def test_extra_extreme_does_not_leak_into_next_legacy_feature(self):
        h = AnchorHistory()
        for at in range(0, 31, 5): h.commit(at, 'A', ask=.60)
        ns = frozen_functions({'rows_since', 'low_high'}, history=deepcopy(h.raw))
        ns['history'].append(dict(ts=31, contract='A', up_ask=.10))
        self.assertEqual(ns['low_high']('up_ask', 31, 30), (.10, .60))
        h.commit(35, 'A', ask=.60)
        ns['history'] = deepcopy(h.raw)
        self.assertEqual(ns['low_high']('up_ask', 35, 30), (.60, .60))


class RawGateTests(unittest.TestCase):
    def test_repeated_identical_inputs_preserve_all_three_raw_states(self):
        expected = raw_ladders(**gate_inputs())
        self.assertEqual(expected, dict(EARLY=True, FINAL=True, CORE_SCALP=True))
        for unused in range(20): self.assertEqual(raw_ladders(**gate_inputs()), expected)

    def test_new_causal_quote_changes_early_and_core_not_final(self):
        a = raw_ladders(**gate_inputs())
        b = raw_ladders(**gate_inputs(pref_ask=.80, pref_edge=.16))
        self.assertEqual([k for k in a if a[k] != b[k]], ['EARLY', 'CORE_SCALP'])

    def test_new_brti_disagreement_changes_only_final_raw_gate(self):
        a = raw_ladders(**gate_inputs())
        b = raw_ladders(**gate_inputs(brti_side='DOWN', brti_gap=-80.))
        self.assertEqual([k for k in a if a[k] != b[k]], ['FINAL'])

    def test_time_gate_boundary_is_not_duplicate_persistence(self):
        a = raw_ladders(**gate_inputs(minutes_left=8.000001))
        b = raw_ladders(**gate_inputs(minutes_left=8.))
        self.assertFalse(a['FINAL']); self.assertTrue(b['FINAL'])
        self.assertEqual(a['EARLY'], b['EARLY'])

    def test_final_six_minute_gap_boundary_preserved(self):
        self.assertFalse(raw_ladders(**gate_inputs(minutes_left=6.000001, abs_gap=60))['FINAL'])
        self.assertTrue(raw_ladders(**gate_inputs(minutes_left=6., abs_gap=60))['FINAL'])

    def test_brti_exact_five_second_boundary(self):
        self.assertTrue(raw_ladders(**gate_inputs(brti_age=5.))['FINAL'])
        self.assertFalse(raw_ladders(**gate_inputs(brti_age=5.000001))['FINAL'])

    def test_nan_inputs_fail_closed(self):
        self.assertFalse(any(raw_ladders(**gate_inputs(pref_fair=math.nan)).values()))


class CausalAvailabilityTests(unittest.TestCase):
    def test_candidate_source_projection_is_causal_at_every_qualified_instant(self):
        for kwargs in (dict(), dict(delay=2.4), dict(delay=4.4), dict(jitter=.2),
                       dict(outage=(40, 48)), dict(quote_wait=(40, 48))):
            for cadence in (5, 1):
                result = source_availability(cadence, duration=90, **kwargs)
                for source, received, decision, checked in result['causal_checks']:
                    self.assertLessEqual(source, received)
                    self.assertLessEqual(received, decision)
                    self.assertLessEqual(decision, checked)
                    self.assertLessEqual(checked-source, 5)

    def test_no_inference_of_future_main_receipt(self):
        d = Delivery(); d.accept(100001, 10, 11.8, 'epoch')
        self.assertIsNone(d.select(11.7999, 12))
        self.assertTrue(d.select(11.8, 11.8)['ready'])

    def test_transport_error_blocks_until_recovered_causal_receipt(self):
        d = Delivery(); d.accept(100001, 10, 11, 'epoch'); d.fail(11.5)
        self.assertFalse(d.select(11.6, 11.6)['ready'])
        d.accept(100002, 12, 13, 'epoch')
        self.assertFalse(d.select(11.6, 13)['ready'])
        self.assertTrue(d.select(13, 13)['ready'])

    def test_owner_restart_cannot_relabel_an_earlier_decision(self):
        d = Delivery(); d.accept(100001, 10, 11, 'epoch1')
        d.accept(100002, 12, 13, 'epoch2')
        self.assertIsNone(d.select(11, 13))

    def test_source_only_bound_improves_but_does_not_claim_complete_availability(self):
        old = source_availability(5, duration=90)
        fast = source_availability(1, duration=90)
        self.assertGreater(fast['percent'], old['percent'])
        self.assertEqual(fast['percent'], 100.)

    def test_large_receipt_age_still_expires_at_one_second_cadence(self):
        self.assertLess(source_availability(1, delay=4.4, duration=90)['percent'], 100)


class CompletePathRejectionTests(unittest.TestCase):
    def test_preappend_phase_differs_even_without_any_extra_committed_hit(self):
        result = persistence_phase_counterexample()
        self.assertEqual(result['legacy_emitted_at_5'], 1)
        self.assertEqual(result['isolated_projection_at_6'], 2)
        self.assertEqual(result['appended_micro_rows'], 0)
        self.assertFalse(result['new_market_information'])

    def test_actual_parity_audit_rejects_faster_intervening_frame(self):
        old = actual_parity_counterexample(5)
        fast = actual_parity_counterexample(1)
        self.assertEqual(old['overall_status'], 'PASS')
        self.assertEqual(fast['overall_status'], 'WAIT')
        for name in ('clock_delta_sec', 'target_delta', 'quote_max_delta',
                     'brti_time_delta_sec', 'brti_value_delta'):
            self.assertEqual(old[name], 0.)
            self.assertEqual(fast[name], 0.)
        self.assertEqual(old['source_timestamp_utc'], fast['source_timestamp_utc'])
        self.assertTrue(fast['brti_match'])
        self.assertFalse(fast['quote_scorable'])

    def test_unchanged_book_cannot_preserve_exit_semantics_if_extra_calls_commit(self):
        for side in ('UP', 'DOWN'):
            result = profit_counterexample(side)
            self.assertEqual(len(result['5']), 1)
            self.assertEqual(len(result['1']), 1)
            self.assertEqual(result['5'][0]['exit_reason'], 'TARGET_20')
            self.assertEqual(result['1'][0]['exit_reason'], 'TARGET_20')
            self.assertEqual(result['5'][0]['exit_seconds'], 15.)
            self.assertEqual(result['1'][0]['exit_seconds'], 11.)
            self.assertEqual(result['5'][0]['exit_bid'], result['1'][0]['exit_bid'])

    def test_discarded_projection_cannot_keep_a_new_entry_connected(self):
        committed = profit_namespace()
        projection = profit_namespace()
        projection['_start_profit_shadow'](dict(signal_id='micro-only', contract='A', side='UP',
            entry_ts=1., signal_timestamp_utc='engineering', entry_ask=.30))
        self.assertEqual(len(projection['_profit_shadow_pending']), 1)
        self.assertEqual(len(committed['_profit_shadow_pending']), 0)
        # Next projection starts from the unchanged committed anchor. There is
        # nothing to protect, despite the prior projection's emitted entry.
        next_projection = profit_namespace()
        next_projection['_update_profit_shadow'](dict(contract='A', up_bid=.60), 2., None)
        self.assertEqual(next_projection['rows'], [])

    def test_scheduling_protection_only_on_legacy_clock_preserves_that_subsystem(self):
        env = profit_namespace()
        env['_start_profit_shadow'](dict(signal_id='engineering', contract='A', side='UP',
            entry_ts=-10., signal_timestamp_utc='engineering', entry_ask=.30))
        for at in range(6):
            if at % 5 == 0:
                env['_update_profit_shadow'](dict(contract='A', up_bid=.51), at, None)
        self.assertEqual(env['rows'][0]['exit_seconds'], 15.)
        # This proves the narrow workaround, not new micro-entry lifecycle
        # equivalence or independent parity delivery for faster full frames.

    def test_faster_proof_overwrite_turns_identical_prices_into_parity_wait(self):
        result = proof_counterexample()
        self.assertEqual(result['old'], 'PASS')
        self.assertEqual(result['faster'], 'WAIT')
        self.assertIn('exact collector frame', result['reason'])

    def test_exact_snapshot_passes_without_overwriting_identity(self):
        p = quote_proof(300000, 299000)
        self.assertEqual(replay(p, p['source_time'], 'A', 900000, 301000)[0], (.39, .41, .59, .61))

    def test_future_timestamped_book_rejected(self):
        p = quote_proof(300000, 300001)
        with self.assertRaises(ValueError): replay(p, p['source_time'], 'A', 900000, 300000)

    def test_quote_interruption_recovery_does_not_reuse_old_proof(self):
        p = quote_proof(300000, 299000)
        with self.assertRaises(ValueError): replay(p, p['source_time'], 'A', 900000, 306001)
        recovered = quote_proof(307000, 306900, seq=20)
        replay(recovered, recovered['source_time'], 'A', 900000, 307100)
        with self.assertRaises(ValueError): replay(recovered, p['source_time'], 'A', 900000, 307100)

    def test_rollover_and_official_close_fail_closed(self):
        p = quote_proof(899000, 898900)
        for ticker, closed, now in [('B', 1800000, 899100), ('A', 900000, 900000)]:
            with self.assertRaises(ValueError): replay(p, p['source_time'], ticker, closed, now)

    def test_fast_quote_update_then_reversion_can_change_stop_first_path(self):
        def environment():
            return frozen_functions({'_update_true_scalp_pending'},
                _true_scalp_pending=[dict(contract='A', side='UP', entry_ask=.40, entry_ts=0,
                    max_future_bid=.39, min_future_bid=.39, stop_ts=None,
                    hits={.10: None, .15: None, .20: None})],
                TRUE_SCALP_STOP=.10, TRUE_SCALP_TARGETS=[.10, .15, .20],
                TRUE_SCALP_HORIZON_SECONDS=180, _finalize_true_scalp=lambda *a: None)
        old = environment(); fast = environment()
        for at, bid in [(1, .25), (2, .55), (5, .55)]:
            snap = dict(contract='A', up_bid=bid, seconds_left=600-at)
            fast['_update_true_scalp_pending'](snap, at)
            if at == 5: old['_update_true_scalp_pending'](snap, at)
        self.assertIsNone(old['_true_scalp_pending'][0]['stop_ts'])
        self.assertEqual(fast['_true_scalp_pending'][0]['stop_ts'], 1)
        self.assertEqual(old['_true_scalp_pending'][0]['hits'][.10], 5)
        self.assertIsNone(fast['_true_scalp_pending'][0]['hits'][.10])
        # This difference IS new causal price information, unlike the unchanged
        # book arm/exit counterexample; it must be reported separately.


if __name__ == '__main__':
    unittest.main()
