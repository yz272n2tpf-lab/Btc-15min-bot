"""Check identity accounting and uncertainty labels in offline decision ledgers."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import nextgen_v2_decision_ledger as ledger
from test_nextgen_v2_review import MANIFEST, bundle, record, rehash

FAMILY = 'candidate_verify_v2'


def case(cid, left, right, family=FAMILY):
    return {'contract': 'C', 'candidate_id': cid, 'opportunity_index': 1,
            'lanes': {'EXPERIMENT': ledger.decision_fact(left, family),
                      'CONTROL': ledger.decision_fact(right, family)}}


class DecisionFacts(unittest.TestCase):
    def test_absent_entry_has_no_invented_reason_price_or_profit(self):
        result = ledger.decision_fact(None, FAMILY)
        self.assertEqual(result['action_state'], 'NO_ENTRY_RECORDED')
        self.assertEqual(result['reason_availability'], 'NOT_EXPORTED')
        self.assertIsNone(result['exported_reason'])
        self.assertIsNone(result['entry_ask_c'])
        self.assertEqual(result['outcomes']['1'], {'state': 'NO_RECORD', 'net_c_per_contract': None})

    def test_entered_and_unscored_is_not_absent_or_zero_profit(self):
        row = record('A', protected=False); row['one_lot_taker_taker_net_c'] = 10
        result = ledger.decision_fact(row, FAMILY)
        self.assertTrue(result['action_observed'])
        self.assertEqual(result['outcomes']['1']['state'], 'NO_OBSERVED_PROTECTED_EXIT')
        self.assertIsNone(result['outcomes']['1']['net_c_per_contract'])

    def test_exported_reason_and_zero_delay_preserved(self):
        row = record('A'); row.update(decision_reason='IMMEDIATE_STRONG', entry_elapsed_sec=0, actual_delay_sec=99)
        result = ledger.decision_fact(row, FAMILY)
        self.assertEqual(result['exported_reason'], 'IMMEDIATE_STRONG')
        self.assertEqual(result['reason_availability'], 'EXPORTED')
        self.assertEqual(result['entry_delay_sec'], 0)
        self.assertEqual(result['entry_ask_c'], 50)

    def test_fixed_control_delay_fallback_and_missing_reason(self):
        row = record('A'); row['actual_delay_sec'] = 5.2
        result = ledger.decision_fact(row, FAMILY)
        self.assertEqual(result['entry_delay_sec'], 5.2)
        self.assertEqual(result['reason_availability'], 'NOT_EXPORTED')

    def test_positive_zero_negative_and_missing_fee_are_distinct(self):
        for net, state in ((2, 'POSITIVE'), (0, 'ZERO'), (-2, 'NEGATIVE'), (1e-16, 'ZERO')):
            self.assertEqual(ledger.outcome(record('A', net1=net), FAMILY, 1)['state'], 'OBSERVED_' + state + '_NET_EXIT')
        row = record('A'); row['one_lot_taker_taker_net_c'] = None
        self.assertEqual(ledger.outcome(row, FAMILY, 1)['state'], 'PROTECTED_EXIT_WITHOUT_FEE_NET')

    def test_warning_absence_is_not_trade_absence(self):
        row = record('A', net1=5); row.update(warning=False, exit=True, exit_time_sec=30)
        result = ledger.decision_fact(row, ledger.review.WATCH)
        self.assertTrue(result['record_present'])
        self.assertFalse(result['action_observed'])
        self.assertEqual(result['action_state'], 'NO_WARNING_RECORDED')
        self.assertEqual(result['outcomes']['1']['net_c_per_contract'], 5)
        self.assertIsNone(result['entry_ask_c'])

    def test_warning_proxy_and_unresolved_are_separate(self):
        row = record('A'); row.update(warning=True, exit=False, warning_time_sec=2, unresolved_warning=True,
                                      recovered_new_high_after_warning=False)
        result = ledger.decision_fact(row, ledger.review.WATCH)
        self.assertTrue(result['unresolved_warning'])
        self.assertFalse(result['new_high_after_warning_proxy'])
        self.assertIsNone(result['warning_lead_sec'])
        self.assertIsNone(result['outcomes']['1']['net_c_per_contract'])


class LedgerAccounting(unittest.TestCase):
    def test_all_four_action_classes_partition_the_anchor(self):
        rows = [case('A', record('A'), record('A')), case('B', record('B'), None),
                case('C', None, record('C', net1=10)), case('D', None, None)]
        result = ledger.comparison(rows, FAMILY, 'EXPERIMENT', 'CONTROL')
        self.assertEqual(result['action_class_counts'], {'BOTH': 1, 'EXPERIMENT_ONLY': 1, 'CONTROL_ONLY': 1, 'NEITHER': 1})
        self.assertEqual(result['experiment_actions'], 2)
        self.assertEqual(result['control_actions'], 2)
        self.assertEqual(result['anchor_contracts'], 1)
        self.assertEqual(result['control_only_outcome_counts_one_lot'], {'OBSERVED_POSITIVE_NET_EXIT': 1})

    def test_omitted_negative_and_unknown_outcomes_are_not_combined(self):
        rows = [case('A', None, record('A', net1=-3)), case('B', None, record('B', protected=False))]
        result = ledger.comparison(rows, FAMILY, 'EXPERIMENT', 'CONTROL')
        self.assertEqual(result['control_only_contracts'], 1)
        self.assertEqual(result['control_only_outcome_counts_one_lot'], {'OBSERVED_NEGATIVE_NET_EXIT': 1, 'NO_OBSERVED_PROTECTED_EXIT': 1})
        self.assertTrue(all(row['both_protected_net_delta_c']['1'] is None for row in result['records']))

    def test_paired_price_and_net_deltas_only_when_observed(self):
        rows = [case('A', record('A', ask=.4, net1=7), record('A', ask=.5, net1=5)),
                case('B', record('B', protected=False), record('B'))]
        result = ledger.comparison(rows, FAMILY, 'EXPERIMENT', 'CONTROL')
        self.assertEqual(result['records'][0]['entry_price_improvement_c'], 10)
        self.assertEqual(result['records'][0]['both_protected_net_delta_c']['1'], 2)
        self.assertIsNone(result['records'][1]['both_protected_net_delta_c']['1'])

    def test_watch_classification_and_lead_do_not_claim_trade_loss(self):
        control = record('A'); control.update(warning=True, exit=True, lead=10)
        shadow = record('A'); shadow.update(warning=False, exit=True, lead=None)
        result = ledger.comparison([case('A', shadow, control, ledger.review.WATCH)], ledger.review.WATCH, 'EXPERIMENT', 'CONTROL')
        self.assertEqual(result['action_kind'], 'WARNING')
        self.assertEqual(result['control_only_warning_with_observed_exit'], 1)
        self.assertIsNone(result['control_only_outcome_counts_one_lot'])
        self.assertEqual(result['records'][0]['both_protected_net_delta_c']['1'], 0)
        self.assertIsNone(result['records'][0]['paired_warning_lead_improvement_sec'])

    def test_complete_bundle_preserves_denominator_and_all_comparisons(self):
        source = bundle(); before = copy.deepcopy(source)
        result = ledger.build_ledger(source, MANIFEST)
        self.assertTrue(result['valid_snapshot'])
        self.assertEqual(result['serial_signals'], 2)
        self.assertEqual(result['future_full_contracts'], 3)
        self.assertEqual(result['full_contracts_without_serial_opportunities'], 2)
        self.assertEqual(result['family_anchor_counts']['scalp2_economics_v2'], 1)
        self.assertEqual(len(result['comparisons']), 28)
        self.assertEqual(len(result['family_rows']), 7)
        self.assertFalse(result['quiet_contract_identifiers_available'])
        self.assertFalse(result['winner_selected'])
        self.assertFalse(result['skip_reasons_inferred'])
        self.assertEqual(source, before)

    def test_source_row_order_does_not_change_opportunity_matching(self):
        first = bundle(); second = copy.deepcopy(first)
        for family in second['audit']['audit_records'].values():
            for rows in family.values():
                rows.reverse()
        rehash(second)
        a, b = ledger.build_ledger(first, MANIFEST), ledger.build_ledger(second, MANIFEST)
        self.assertEqual(a['family_rows'], b['family_rows'])
        self.assertEqual(a['comparisons'], b['comparisons'])

    def test_malformed_tampered_and_unsafe_evidence_fail_closed(self):
        tampered = bundle(); tampered['audit']['orders'] = True
        drift = bundle(); drift['state']['code_sha256'] = 'changed'; rehash(drift)
        for source in (None, {}, {'state': []}, tampered, drift):
            result = ledger.build_ledger(source, MANIFEST)
            self.assertEqual(result['status'], 'BLOCKED_INVALID_SNAPSHOT')
            self.assertEqual(result['family_rows'], [])
            self.assertEqual(result['comparisons'], [])

    def test_markdown_caps_detail_only_and_escapes_data(self):
        result = ledger.build_ledger(bundle(), MANIFEST)
        result['family_rows'] *= 10
        before = copy.deepcopy(result)
        text = ledger.markdown(result, MANIFEST)
        total = sum(len(MANIFEST['families'][r['family']]['experiments']) for r in result['family_rows'])
        self.assertIn(f'Detail rows shown: 40 of {total}', text)
        self.assertEqual(result, before)
        self.assertIn('NOT_EXPORTED', text)
        self.assertEqual(ledger.cell('<script>|`\n'), '&lt;script&gt;&#124;&#96; ')

    def test_offline_cli_is_reproducible_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'bundle.json'; source.write_text(json.dumps(bundle()))
            with patch.object(ledger.review, 'http_reader', side_effect=AssertionError('network forbidden')), redirect_stdout(io.StringIO()):
                self.assertEqual(ledger.main([str(source), '--output', str(root / 'one')]), 0)
                saved = (root / 'one/ledger.json').read_bytes()
                self.assertEqual(ledger.main([str(source), '--output', str(root / 'one')]), 2)
                self.assertEqual(saved, (root / 'one/ledger.json').read_bytes())
                self.assertEqual(ledger.main([str(source), '--output', str(root / 'two')]), 0)
                self.assertEqual(saved, (root / 'two/ledger.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
