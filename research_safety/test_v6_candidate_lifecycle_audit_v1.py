import json
import unittest

from v6_candidate_lifecycle_audit_v1 import audit_records, normalize_records

C_V5 = (
    "LEAD_V6 CANDIDATE | V5_BASELINE | KXBTC15M-TEST | DOWN | zone V5_RULES | "
    "ask 0.300 | btc5 +1 | btc15 +2 | btc30 +3 | accel +4 | brti5 +5 | "
    "brti15 +6 | ask5 +0.000 | ask15 +0.000 | left 600s"
)
C_V6 = (
    "LEAD_V6 CANDIDATE | V6_QUALIFIED | KXBTC15M-TEST | DOWN | zone PREFERRED_7_30C | "
    "ask 0.30 | btc5 +1 | btc15 +2 | btc30 +3 | accel +4 | brti5 +5 | "
    "brti15 +6 | ask5 +0.000 | ask15 +0.000 | left 600s"
)
R_V5 = (
    "LEAD_V6 RESULT | V5_BASELINE | KXBTC15M-TEST | DOWN | zone V5_RULES | "
    "style EXPANSION | entry 0.300 | max_exec_gain +0.200 | adverse -0.020 | "
    "hit10 True | hit20 True | to_exec+5c 30 | to_exec+10c 40 | "
    "to_exec+20c 50 | kalshi_reprice+5c 30"
)
R_V6 = (
    "LEAD_V6 RESULT | V6_QUALIFIED | KXBTC15M-TEST | DOWN | zone PREFERRED_7_30C | "
    "style EXPANSION | entry 0.300 | max_exec_gain +0.200 | adverse -0.020 | "
    "hit10 True | hit20 True | to_exec+5c 30 | to_exec+10c 40 | "
    "to_exec+20c 50 | kalshi_reprice+5c 30"
)
HB2 = "LEAD_V6 HEARTBEAT | KXBTC15M-TEST | 9.99m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 2"
HB0 = "LEAD_V6 HEARTBEAT | KXBTC15M-TEST | 8.99m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 0"


class CandidateLifecycleAuditTests(unittest.TestCase):
    def test_happy_path_pairs_and_pending(self):
        payload = {"deploy": [
            {"timestamp": "2026-09-10T12:00:00Z", "message": C_V5},
            {"timestamp": "2026-09-10T12:00:01Z", "message": C_V6},
            {"timestamp": "2026-09-10T12:00:02Z", "message": HB2},
            {"timestamp": "2026-09-10T12:00:31Z", "message": R_V5},
            {"timestamp": "2026-09-10T12:00:41Z", "message": R_V6},
            {"timestamp": "2026-09-10T12:00:42Z", "message": HB0},
        ]}
        result = audit_records(normalize_records(json.dumps(payload)))
        self.assertTrue(result["ok"])
        self.assertEqual(result["paired_results"], 2)
        self.assertEqual(result["resolution_samples"], 2)
        self.assertAlmostEqual(result["avg_resolution_seconds"], 35.5)
        self.assertEqual(result["max_resolution_seconds"], 40.0)

    def test_orphan_result_is_flagged(self):
        result = audit_records(normalize_records(R_V5))
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["orphan_results"]), 1)

    def test_pending_mismatch_is_flagged(self):
        result = audit_records(normalize_records("\n".join([C_V5, HB0])))
        self.assertFalse(result["ok"])
        self.assertEqual(result["pending_mismatches"][0]["reconstructed_pending"], 1)

    def test_v6_candidate_requires_prior_matching_v5_candidate(self):
        result = audit_records(normalize_records(C_V6))
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["v6_without_v5_candidate"]), 1)

    def test_unresolved_at_window_end_is_reported_but_not_fatal(self):
        result = audit_records(normalize_records(C_V5))
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["unresolved_candidates"]), 1)

    def test_fifo_pairing_handles_repeated_same_key(self):
        text = "\n".join([C_V5, C_V5, R_V5, R_V5, HB0])
        result = audit_records(normalize_records(text))
        self.assertTrue(result["ok"])
        self.assertEqual(result["paired_results"], 2)
        self.assertEqual(len(result["unresolved_candidates"]), 0)


if __name__ == "__main__":
    unittest.main()
