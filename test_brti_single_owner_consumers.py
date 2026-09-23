"""Migration guard: the existing scalp primary/verifier must never run in shared mode."""
import os
import unittest
from unittest.mock import Mock, patch
from brti_resilience_shadow_v2 import BrtiResilienceGuard, qualification_value, _self_test

class SharedGuard(unittest.TestCase):
    def test_success_and_failure_never_call_upstream_or_retry(self):
        primary=Mock(side_effect=AssertionError('upstream forbidden'))
        verifier=Mock(side_effect=AssertionError('upstream verifier forbidden'))
        guard=BrtiResilienceGuard()
        with patch.dict(os.environ,BTC15_USE_SHARED_BRTI='1'), patch(
            'btc15_brti_shared_consumer_v1.read_shared_brti',return_value=dict(
                value=100000.,source_ts_ms=1780000000000,age_seconds=1.)) as read:
            sample=guard.fetch(primary,verifier)
            self.assertEqual(qualification_value(sample),100000.)
            self.assertEqual(sample.source_ts_ms,1780000000000)
            read.side_effect=RuntimeError('source stale')
            bad=guard.fetch(primary,verifier)
            self.assertIsNone(qualification_value(bad))
            self.assertEqual(read.call_count,2)
            self.assertEqual(bad.attempts,1)
        primary.assert_not_called();verifier.assert_not_called()

    def test_existing_off_mode_guard_regressions_unchanged(self):
        with patch.dict(os.environ,BTC15_USE_SHARED_BRTI='0'):
            _self_test()

if __name__=='__main__':unittest.main()
