import unittest
from v7_brti_reliability_audit_v1 import audit

LOG = """
LEAD_V7 HEARTBEAT | A | 9.0m | BTC 1 | BRTI 1.1 | UP 0.5 | DOWN 0.5 | pending 0
LEAD_V7 HEARTBEAT | A | 8.5m | BTC 1 | BRTI N/A | UP 0.5 | DOWN 0.5 | pending 0
LEAD_V7 HEARTBEAT | A | 8.0m | BTC 1 | BRTI N/A | UP 0.5 | DOWN 0.5 | pending 0
LEAD_V7 MIDCONTRACT | A | MOM n=0 | REV n=0 | BRTI BRTI_RESILIENCE | samples=10 | primary_ok=7 (70.0%) | retry_recovered=2 | missing=0 | errors=3 | verifier_ok=0 | verifier_disagree=0 | diag_cache=4
LEAD_V7 REJECTS | {'MOM_BRTI_DEGRADED': 5, 'REV_BRTI_DEGRADED': 2}
LEAD_V7 HEARTBEAT | B | 9.0m | BTC 1 | BRTI 1.2 | UP 0.5 | DOWN 0.5 | pending 0
LEAD_V7 MIDCONTRACT | B | MOM n=0 | REV n=0 | BRTI BRTI_RESILIENCE | samples=20 | primary_ok=16 (80.0%) | retry_recovered=5 | missing=0 | errors=4 | verifier_ok=0 | verifier_disagree=0 | diag_cache=8
LEAD_V7 REJECTS | {'MOM_BRTI_DEGRADED': 1}
LEAD_V7 CONTRACT_SUMMARY | B | MOM n=0 | REV n=0 | BRTI BRTI_RESILIENCE | samples=20 | primary_ok=16 (80.0%) | retry_recovered=5 | missing=0 | errors=4 | verifier_ok=0 | verifier_disagree=0 | diag_cache=8
"""

class BrtiAuditTests(unittest.TestCase):
    def test_contract_streak_and_availability(self):
        r = audit(LOG)
        self.assertEqual(r["contracts"]["A"]["heartbeat_samples"], 3)
        self.assertEqual(r["contracts"]["A"]["na_count"], 2)
        self.assertEqual(r["contracts"]["A"]["max_consecutive_na"], 2)
        self.assertEqual(r["contracts"]["A"]["availability_transitions"], 1)

    def test_duplicate_resilience_snapshot_is_deduped(self):
        self.assertEqual(audit(LOG)["resilience_snapshot_count"], 2)

    def test_failure_classifies_reporting_divergence(self):
        classes = audit(LOG)["failure_classes"]
        self.assertIn("PRIMARY_ERRORS_PRESENT", classes)
        self.assertIn("RETRY_RECOVERY_ACTIVE", classes)
        self.assertIn("HEARTBEAT_VS_CUMULATIVE_MISSING_DIVERGENCE", classes)
        self.assertIn("VERIFIER_ACTIVITY_UNOBSERVED", classes)

    def test_reject_suppression_is_lane_specific(self):
        q = audit(LOG)["qualification_suppression_observed"]
        self.assertEqual(q["A"]["momentum_brti_degraded_rejects_observed"], 5)
        self.assertEqual(q["A"]["reversal_brti_degraded_rejects_observed"], 2)
        self.assertEqual(q["B"]["reversal_brti_degraded_rejects_observed"], 0)

    def test_no_snapshot_is_explicit(self):
        r = audit("LEAD_V7 HEARTBEAT | X | 1.0m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 0")
        self.assertIn("NO_RESILIENCE_SNAPSHOT", r["failure_classes"])
        self.assertIsNone(r["latest_resilience"])

    def test_research_only_contract(self):
        r = audit(LOG)
        self.assertTrue(r["research_only"])
        self.assertFalse(r["production_mutation"])

if __name__ == "__main__":
    unittest.main()
