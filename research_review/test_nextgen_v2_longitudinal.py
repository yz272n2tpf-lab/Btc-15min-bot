"""Regression tests for cumulative V2 checkpoint review."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import nextgen_v2_longitudinal as series
from test_nextgen_v2_review import MANIFEST, bundle, rehash


def later(previous, contracts=4, signals=2, captured='2026-09-17T00:31:00+00:00'):
    result = copy.deepcopy(previous)
    result['captured_utc'] = captured
    result['state']['future_full_contracts'] = contracts
    result['state']['serial_signals'] = signals
    result['state']['last_poll_utc'] = captured
    result['state']['source_latest_utc'] = captured
    result['state']['source_sha256'] = 'b'*64
    result['audit']['source_sha256'] = 'b'*64
    result['state']['evidence_readiness']['sample_ready'] = contracts >= 100 and signals >= 100
    result['state']['status'] = 'READY_FOR_MANUAL_V2_COMPARISON' if contracts >= 100 and signals >= 100 else 'COLLECTING_NEXTGEN_V2'
    return rehash(result)


class LongitudinalValidation(unittest.TestCase):
    def test_valid_cumulative_series_uses_latest_totals_without_summing(self):
        first = bundle(); second = later(first)
        result = series.build_series([first, second], MANIFEST)
        self.assertTrue(result['valid_series'])
        self.assertEqual(result['checkpoint_count'], 2)
        self.assertEqual(result['latest_future_full_contracts'], 4)
        self.assertEqual(result['latest_serial_signals'], 2)
        self.assertEqual(result['remaining_full_contracts'], 96)
        self.assertTrue(result['cumulative_snapshots_are_not_summed'])
        self.assertFalse(result['winner_selected'])

    def test_reversed_inputs_duplicate_capture_and_regression_fail_closed(self):
        first = bundle(); second = later(first)
        self.assertFalse(series.build_series([second, first], MANIFEST)['valid_series'])
        duplicate = later(first, captured=first['captured_utc'])
        self.assertFalse(series.build_series([first, duplicate], MANIFEST)['valid_series'])
        regressed = later(first, contracts=1, signals=1)
        self.assertFalse(series.build_series([first, regressed], MANIFEST)['valid_series'])

    def test_window_drift_and_changed_history_fail_closed(self):
        first = bundle(); second = later(first)
        second['state']['window_id'] = 'wrong'; rehash(second)
        self.assertFalse(series.build_series([first, second], MANIFEST)['valid_series'])
        second = later(first)
        row = second['audit']['audit_records']['candidate_verify_v2']['V1_IMMEDIATE'][0]
        row['entry_ask'] += .01; rehash(second)
        errors = series.build_series([first, second], MANIFEST)['integrity_errors']
        self.assertTrue(any('changed' in error for error in errors))

    def test_missing_historical_opportunity_fails_closed(self):
        first = bundle(); second = later(first, signals=1)
        family = 'candidate_verify_v2'
        for lane in second['audit']['audit_records'][family].values():
            lane.pop()
        for lane in second['state'][family].values():
            lane['signals'] = len(second['audit']['audit_records'][family][next(iter(second['audit']['audit_records'][family]))])
        rehash(second)
        errors = series.validate_series([first, second], MANIFEST)
        self.assertTrue(any('lost' in error or 'regressed' in error for error in errors))

    def test_invalid_series_emits_no_latest_comparisons(self):
        result = series.build_series([], MANIFEST)
        self.assertEqual(result['status'], 'BLOCKED_INVALID_SERIES')
        self.assertNotIn('latest_comparisons', result)

    def test_cli_never_overwrites_scorecard(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root/'bundle.json'; source.write_text(json.dumps(bundle()))
            output = root/'scorecard'
            self.assertEqual(series.main([str(source), '--output', str(output)]), 0)
            original = (output/'scorecard.json').read_bytes()
            self.assertEqual(series.main([str(source), '--output', str(output)]), 2)
            self.assertEqual((output/'scorecard.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
