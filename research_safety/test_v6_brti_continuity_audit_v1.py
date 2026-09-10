import unittest

import v6_brti_continuity_audit_v1 as audit

T = "KXBTC15M-26SEP100515-15"


class BrtiContinuityAuditTests(unittest.TestCase):
    def test_na_streak_and_recovery_count(self):
        lines = [
            f"LEAD_V6 HEARTBEAT | {T} | 11.49m | BTC 1 | BRTI N/A | UP 0.7 | DOWN 0.3 | pending 0",
            f"LEAD_V6 HEARTBEAT | {T} | 10.99m | BTC 1 | BRTI 2 | UP 0.7 | DOWN 0.3 | pending 0",
            f"LEAD_V6 HEARTBEAT | {T} | 10.49m | BTC 1 | BRTI N/A | UP 0.7 | DOWN 0.3 | pending 0",
            f"LEAD_V6 HEARTBEAT | {T} | 9.99m | BTC 1 | BRTI N/A | UP 0.7 | DOWN 0.3 | pending 0",
            f"LEAD_V6 HEARTBEAT | {T} | 9.49m | BTC 1 | BRTI N/A | UP 0.7 | DOWN 0.3 | pending 0",
            f"LEAD_V6 HEARTBEAT | {T} | 9.00m | BTC 1 | BRTI N/A | UP 0.7 | DOWN 0.3 | pending 0",
            f"LEAD_V6 HEARTBEAT | {T} | 8.00m | BTC 1 | BRTI 2 | UP 0.7 | DOWN 0.3 | pending 0",
        ]
        c = audit.parse_lines(lines)[T]
        self.assertEqual(c.heartbeat_count, 7)
        self.assertEqual(c.brti_na_heartbeats, 5)
        self.assertEqual(c.brti_available_heartbeats, 2)
        self.assertEqual(c.longest_brti_na_streak, 4)
        self.assertEqual(c.brti_recoveries, 2)

    def test_v6_candidate_with_present_brti_is_clean(self):
        line = (
            f"LEAD_V6 CANDIDATE | V6_QUALIFIED | {T} | DOWN | zone PREFERRED_7_30C | "
            "ask 0.120 | btc5 +20.17 | brti5 +14.88 | brti15 +13.57 | left 321s"
        )
        c = audit.parse_lines([line])[T]
        self.assertEqual(c.v6_candidates, 1)
        self.assertEqual(c.v6_missing_brti_integrity_violations, 0)

    def test_v6_candidate_missing_brti_is_integrity_violation(self):
        line = (
            f"LEAD_V6 CANDIDATE | V6_QUALIFIED | {T} | DOWN | zone PREFERRED_7_30C | "
            "ask 0.120 | brti5 +14.88 | brti15 N/A | left 321s"
        )
        c = audit.parse_lines([line])[T]
        self.assertEqual(c.v6_missing_brti_integrity_violations, 1)

    def test_v5_missing_brti_is_counted_separately(self):
        line = (
            f"LEAD_V6 CANDIDATE | V5_BASELINE | {T} | DOWN | zone V5_RULES | "
            "ask 0.150 | brti5 +20.24 | brti15 N/A | left 545s"
        )
        c = audit.parse_lines([line])[T]
        self.assertEqual(c.v5_candidates, 1)
        self.assertEqual(c.v5_candidates_missing_brti, 1)
        self.assertEqual(c.v6_missing_brti_integrity_violations, 0)

    def test_cumulative_degraded_rejects_take_max_not_sum(self):
        lines = [
            f"LEAD_V6 MIDCONTRACT | {T} | V5 n=0 | V6 n=0 | rejects price=0 degraded=9 base=15 high=0",
            f"LEAD_V6 MIDCONTRACT | {T} | V5 n=1 | V6 n=0 | rejects price=0 degraded=52 base=79 high=0",
            f"LEAD_V6 CONTRACT_SUMMARY | {T} | V5 n=1 | V6 n=1 | rejects price=0 degraded=60 base=90 high=0",
        ]
        c = audit.parse_lines(lines)[T]
        self.assertEqual(c.reject_degraded, 60)
        self.assertTrue(c.contract_summary_seen)

    def test_contracts_are_isolated(self):
        t2 = "KXBTC15M-26SEP100530-30"
        lines = [
            f"LEAD_V6 HEARTBEAT | {T} | 10.0m | BTC 1 | BRTI N/A | UP 0.5 | DOWN 0.5 | pending 0",
            f"LEAD_V6 HEARTBEAT | {t2} | 10.0m | BTC 1 | BRTI 2 | UP 0.5 | DOWN 0.5 | pending 0",
        ]
        parsed = audit.parse_lines(lines)
        self.assertEqual(parsed[T].brti_na_heartbeats, 1)
        self.assertEqual(parsed[t2].brti_na_heartbeats, 0)


if __name__ == "__main__":
    unittest.main()
