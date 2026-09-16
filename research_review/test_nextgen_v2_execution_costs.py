"""Offline tests of fixed-exit extra-cost arithmetic and safety boundaries."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import nextgen_v2_execution_costs as costs
from test_nextgen_v2_review import MANIFEST, bundle, record, rehash

FAMILY = 'candidate_verify_v2'


class CostArithmetic(unittest.TestCase):
    def test_extra_cost_applies_once_on_each_side(self):
        row = record('A', net1=16)
        self.assertEqual(costs.stressed_net(row, FAMILY, 1, 1, 2), 13)
        self.assertEqual(costs.stressed_net(row, FAMILY, 1, 0, 0), 16)

    def test_ten_lot_is_per_contract_not_multiplied_by_ten(self):
        row = record('A', net1=16)
        self.assertEqual(costs.stressed_net(row, FAMILY, 10, 1, 1), 15)

    def test_unprotected_is_missing_even_if_a_net_value_is_present(self):
        row = record('A', protected=False)
        row['one_lot_taker_taker_net_c'] = 100
        self.assertIsNone(costs.stressed_net(row, FAMILY, 1, 0, 0))

    def test_missing_fee_net_is_not_zero(self):
        row = record('A'); row['one_lot_taker_taker_net_c'] = None
        result = costs.lane_summary([row], FAMILY, 1, 1)
        self.assertEqual(result['protected_exits_missing_fee_net'], 1)
        self.assertIsNone(result['scenarios'][0]['conditional_mean_net_c_per_contract'])

    def test_watch_uses_frozen_exit_not_warning(self):
        row = record('A', net1=5); row.update(exit=True, warning=False)
        self.assertEqual(costs.stressed_net(row, costs.review.WATCH, 1, 1, 1), 3)
        row.update(exit=False, warning=True)
        self.assertIsNone(costs.stressed_net(row, costs.review.WATCH, 1, 1, 1))

    def test_counts_preserve_all_entries_and_unique_contracts(self):
        rows = [record('A', net1=5), record('B', net1=-3), record('C', contract='D', protected=False)]
        result = costs.lane_summary(rows, FAMILY, 1, 4)
        self.assertEqual(result['entries'], 3)
        self.assertEqual(result['entry_contracts'], 2)
        self.assertEqual(result['entry_contract_coverage'], .5)
        self.assertEqual(result['scored_exit_contracts'], 1)
        self.assertEqual(result['without_observed_protected_exit'], 1)
        self.assertEqual(result['scenarios'][0]['conditional_mean_net_c_per_contract'], 1)
        self.assertEqual(result['scenarios'][1]['conditional_mean_net_c_per_contract'], -1)

    def test_zero_and_empty_sample_are_not_wins(self):
        values = costs.statistics_for([2 - 2, 4e-16, -4e-16, -1, 1])
        self.assertEqual(values['zero_observed_exits'], 3)
        self.assertEqual(values['positive_observed_exits'], 1)
        self.assertEqual(values['negative_observed_exits'], 1)
        empty = costs.lane_summary([], FAMILY, 1, 0)
        self.assertIsNone(empty['conditional_mean_break_even_extra_round_trip_c'])
        self.assertIsNone(empty['scenarios'][0]['positive_fraction_of_scored_exits'])

    def test_break_even_never_implies_positive_buffer_for_losing_mean(self):
        result = costs.lane_summary([record('A', net1=-3)], FAMILY, 1, 1)
        self.assertEqual(result['conditional_mean_break_even_extra_round_trip_c'], 0)
        self.assertFalse(result['baseline_conditional_mean_positive'])

    def test_invalid_costs_and_unsupported_lots_rejected(self):
        for value in (-1, float('nan'), float('inf'), True, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                costs.stressed_net(record('A'), FAMILY, 1, value, 0)
        with self.assertRaises(ValueError):
            costs.stressed_net(record('A'), FAMILY, 100, 0, 0)

    def test_equal_cost_cancels_in_paired_delta_without_hiding_omissions(self):
        controls = [record('A', net1=10), record('B', protected=False), record('C', net1=-5)]
        shadows = [record('B', net1=12), record('A', net1=13), record('D', net1=3)]
        result = costs.paired_summary(shadows, controls, FAMILY, 1)
        self.assertEqual(result['matched_entries'], 2)
        self.assertEqual(result['both_scored_exits'], 1)
        self.assertEqual(result['matched_entries_excluded_for_missing_exit_or_fee_net'], 1)
        self.assertEqual(result['control_only_entries'], 1)
        self.assertEqual(result['shadow_only_entries'], 1)
        self.assertTrue(all(s['conditional_paired_net_delta_c'] == 3 for s in result['scenarios']))


class CostReportSafety(unittest.TestCase):
    def test_all_lanes_controls_and_lot_scenarios_are_present(self):
        source = bundle(); before = copy.deepcopy(source)
        result = costs.build_report(source, MANIFEST)
        self.assertTrue(result['valid_snapshot'])
        self.assertEqual(len(result['lane_results']), 24)
        self.assertEqual(len(result['paired_comparisons']), 28)
        for lane in result['lane_results']:
            self.assertEqual([r['lot_scenario'] for r in lane['lots']], [1, 10])
            self.assertTrue(all(len(r['scenarios']) == 4 for r in lane['lots']))
        self.assertEqual(source, before)
        self.assertFalse(result['winner_selected'])
        self.assertTrue(result['assumptions']['no_fill_or_latency_simulation'])
        self.assertTrue(any('manual-fill guarantee' in item for item in result['limitations']))
        self.assertIn('not a fill simulator', costs.__doc__.lower())
        json.dumps(result, allow_nan=False)

    def test_malformed_drift_and_unsafe_snapshot_fail_closed(self):
        cases = [None, {}, {'state': []}]
        changed = bundle(); changed['state']['code_sha256'] = 'bad'; rehash(changed); cases.append(changed)
        unsafe = bundle(); unsafe['audit']['orders'] = True; rehash(unsafe); cases.append(unsafe)
        for source in cases:
            with self.subTest(source_type=type(source).__name__):
                result = costs.build_report(source, MANIFEST)
                self.assertFalse(result['valid_snapshot'])
                self.assertEqual(result['lane_results'], [])
                self.assertEqual(result['paired_comparisons'], [])
                self.assertIn('No economics report', costs.markdown(result))

    def test_tampered_record_rejected_before_arithmetic(self):
        source = bundle()
        source['audit']['audit_records'][FAMILY]['V1_IMMEDIATE'][0]['entry_ask'] = .01
        self.assertFalse(costs.build_report(source, MANIFEST)['valid_snapshot'])

    def test_rendering_keeps_missing_values_and_conditional_scope_explicit(self):
        result = costs.build_report(bundle(), MANIFEST)
        md = costs.markdown(result)
        self.assertIn('conditional mean cents per contract', md)
        self.assertIn('No exit / missing fee net', md)
        self.assertIn('not zero profit', md)
        self.assertIn('not deployed', md)

    def test_offline_cli_reproducible_no_network_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'bundle.json'; source.write_text(json.dumps(bundle()))
            with patch.object(costs.review, 'http_reader', side_effect=AssertionError('network forbidden')), redirect_stdout(io.StringIO()):
                self.assertEqual(costs.main([str(source), '--output', str(root / 'one')]), 0)
                first = (root / 'one/stress.json').read_bytes()
                self.assertEqual(costs.main([str(source), '--output', str(root / 'one')]), 2)
                self.assertEqual((root / 'one/stress.json').read_bytes(), first)
                self.assertEqual(costs.main([str(source), '--output', str(root / 'two')]), 0)
                self.assertEqual((root / 'two/stress.json').read_bytes(), first)


if __name__ == '__main__':
    unittest.main()
