"""Test the audit itself, including deliberate in-memory mechanism defects."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import nextgen_v2_causal_audit as audit

MANIFEST = json.loads(audit.MANIFEST.read_text())


class SyntheticAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = audit.load_core()
        cls.reference = audit.run_audit(MANIFEST, cls.core, count=5)

    def test_reference_passes_all_groups_without_efficacy_claim(self):
        result = self.reference
        self.assertEqual(result['status'], 'MECHANISM_TESTS_PASS')
        self.assertEqual(result['failure_count'], 0)
        self.assertEqual(len(result['groups']), 17)
        self.assertGreater(result['checks'], 800)
        self.assertFalse(result['orders'])
        self.assertFalse(result['winner_selected'])
        self.assertFalse(result['market_efficacy_established'])
        self.assertFalse(result['live_raw_tape_audited'])
        self.assertFalse(result['certification_passed'])
        self.assertEqual(result['code_sha256'], MANIFEST['code_sha256'])

    def test_deterministic_rerun(self):
        self.assertEqual(audit.run_audit(MANIFEST, self.core, count=5), self.reference)

    def test_changed_source_is_rejected_before_core_import(self):
        with patch.object(audit, 'fingerprint', return_value='changed'), patch.object(audit, 'load_core') as load:
            result = audit.run_audit(MANIFEST)
        self.assertEqual(result['status'], 'BLOCKED_CODE_DRIFT')
        self.assertEqual(result['checks'], 0)
        load.assert_not_called()

    def test_mid_run_source_change_is_reported(self):
        with patch.object(audit, 'fingerprint', side_effect=[MANIFEST['code_sha256'], 'changed']):
            result = audit.run_audit(MANIFEST, self.core, count=1)
        self.assertEqual(result['status'], 'MECHANISM_TESTS_FAIL')
        self.assertEqual(result['groups']['source_integrity']['failures'], 1)

    def test_outcome_leaking_decision_is_detected(self):
        original = self.core.dynamic_verify_decision
        def leaked(op):
            result = original(op)
            if result is not None and op.get('plus10') == 1:
                result = {**result, 'entry_ask': result['entry_ask'] + .001}
            return result
        with patch.object(self.core, 'dynamic_verify_decision', side_effect=leaked):
            result = audit.run_audit(MANIFEST, self.core, count=5)
        self.assertEqual(result['status'], 'MECHANISM_TESTS_FAIL')
        self.assertGreater(result['groups']['decision_outcome_independence']['failures'], 0)

    def test_future_path_leaking_decision_is_detected(self):
        original = self.core.dynamic_verify_decision
        def leaked(op):
            result = original(op)
            if result is not None and op['_paths']:
                result = {**result, 'entry_ask': result['entry_ask'] + op['_paths'][-1]['current_bid'] / 100}
            return result
        with patch.object(self.core, 'dynamic_verify_decision', side_effect=leaked):
            result = audit.run_audit(MANIFEST, self.core, count=5)
        self.assertGreater(result['groups']['decision_prefix']['failures'], 0)
        self.assertGreater(result['groups']['decision_future_suffix']['failures'], 0)

    def test_changed_watch_exit_detected_by_independent_oracle(self):
        original = self.core.watch_measure
        def changed(op, mode):
            result = original(op, mode)
            if result['exit_time_sec'] is not None:
                result['exit_time_sec'] += 1
            return result
        with patch.object(self.core, 'watch_measure', side_effect=changed):
            result = audit.run_audit(MANIFEST, self.core, count=5)
        self.assertGreater(result['groups']['watch_exit_oracle']['failures'], 0)

    def test_reference_oracle_does_not_call_frozen_helper(self):
        op = audit.make_op(points=[(2, .53), (4, .49)])
        with patch.object(self.core, 'watch_measure', side_effect=AssertionError('oracle must be independent')):
            elapsed, gain = audit.reference_exit(op)
        self.assertEqual(elapsed, 4)
        self.assertAlmostEqual(gain, .04)

    def test_input_mutation_is_detected(self):
        original = self.core.dynamic_verify_decision
        def mutation(op):
            result = original(op)
            op['unexpected_mutation'] = True
            return result
        with patch.object(self.core, 'dynamic_verify_decision', side_effect=mutation):
            result = audit.run_audit(MANIFEST, self.core, count=1)
        self.assertEqual(result['groups']['input_immutability']['failures'], 1)

    def test_failure_examples_are_bounded_but_counts_are_not(self):
        checks = audit.Checks()
        for index in range(100):
            checks.compare('deliberate', str(index), 1, 2)
        self.assertEqual(len(checks.failures), 50)
        self.assertEqual(checks.groups['deliberate']['failures'], 100)

    def test_report_discloses_live_evidence_limit(self):
        md = audit.markdown(self.reference)
        self.assertIn('No live raw tape audited', md)
        self.assertIn('delayed/backdated', md)
        self.assertIn('Undeployed offline', md)
        self.assertIn('candidate feature causality', md)

    def test_cli_preserves_earlier_audit_and_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(audit, 'run_audit', return_value=copy.deepcopy(self.reference)), redirect_stdout(io.StringIO()):
                self.assertEqual(audit.main(['--output', str(root / 'one')]), 0)
                saved = (root / 'one/audit.json').read_bytes()
                self.assertEqual(audit.main(['--output', str(root / 'one')]), 2)
                self.assertEqual(saved, (root / 'one/audit.json').read_bytes())
                self.assertEqual(audit.main(['--output', str(root / 'two')]), 0)
                self.assertEqual(saved, (root / 'two/audit.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
