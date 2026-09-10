import unittest

import scalp_v6_data_quality_segmenter_v1 as dq

T = "KXBTC15M-26SEP092045-45"


class DataQualitySegmenterTests(unittest.TestCase):
    def test_cumulative_reject_snapshots_are_not_summed(self):
        lines = [
            f"LEAD_V6 MIDCONTRACT | {T} | V5 n=0 | V6 n=0 | rejects price=2 degraded=42 base=16 high=1",
            f"LEAD_V6 MIDCONTRACT | {T} | V5 n=0 | V6 n=0 | rejects price=3 degraded=77 base=21 high=4",
            f"LEAD_V6 CONTRACT_SUMMARY | {T} | V5 n=1 | V6 n=1 | rejects price=3 degraded=80 base=25 high=4",
        ]
        c = dq.parse_lines(lines)[T]
        self.assertEqual(c.reject_price, 3)
        self.assertEqual(c.reject_degraded, 80)
        self.assertEqual(c.reject_base, 25)
        self.assertEqual(c.reject_high, 4)
        self.assertTrue(c.contract_summary_seen)

    def test_missing_brti_is_separated_for_v5_and_flagged_for_v6(self):
        lines = [
            f"LEAD_V6 CANDIDATE | V5_BASELINE | {T} | UP | zone V5_RULES | ask 0.120 | brti5 +5.00 | brti15 N/A | left 666s",
            f"LEAD_V6 CANDIDATE | V6_QUALIFIED | {T} | UP | zone PREFERRED_7_30C | ask 0.120 | brti5 +5.00 | brti15 N/A | left 664s",
        ]
        c = dq.parse_lines(lines)[T]
        self.assertEqual(c.v5_candidate_brti_missing, 1)
        self.assertEqual(c.v6_missing_brti_integrity_violations, 1)
        self.assertIn("V6_MISSING_BRTI_INTEGRITY", c.audit_labels(None, None))

    def test_display_boundary_case_is_review_only(self):
        line = (
            f"LEAD_V6 RESULT | V6_QUALIFIED | {T} | UP | zone PREFERRED_7_30C | "
            "style NO_EXPANSION | entry 0.200 | max_exec_gain +0.100 | adverse -0.010 | hit10 False | hit20 False"
        )
        c = dq.parse_lines([line])[T]
        self.assertEqual(c.v6_results, 1)
        self.assertEqual(c.score_boundary_review_items, 1)
        self.assertIn("SCORE_BOUNDARY_REVIEW", c.audit_labels(None, None))

    def test_heartbeat_brti_rate_and_gap_are_raw_metrics(self):
        lines = [
            f"LEAD_V6 HEARTBEAT | {T} | 13.49m | BTC 78233.14 | BRTI N/A | UP 0.320 | DOWN 0.690 | pending 0",
            f"LEAD_V6 HEARTBEAT | {T} | 12.99m | BTC 78221.01 | BRTI 78216.25 | UP 0.250 | DOWN 0.760 | pending 0",
            f"LEAD_V6 HEARTBEAT | {T} | 11.99m | BTC 78198.63 | BRTI N/A | UP 0.180 | DOWN 0.830 | pending 0",
        ]
        c = dq.parse_lines(lines)[T]
        self.assertEqual(c.heartbeat_count, 3)
        self.assertEqual(c.brti_na_heartbeats, 2)
        self.assertAlmostEqual(c.brti_na_rate_pct, 66.666666, places=4)
        self.assertAlmostEqual(c.max_heartbeat_gap_s, 60.0, places=4)
        self.assertEqual(c.audit_labels(None, None), [])
        self.assertIn("BRTI_NA_RATE_OVER_AUDIT_LIMIT", c.audit_labels(50.0, None))
        self.assertIn("HEARTBEAT_GAP_OVER_AUDIT_LIMIT", c.audit_labels(None, 45.0))

    def test_contracts_stay_separate(self):
        t2 = "KXBTC15M-26SEP092100-00"
        lines = [
            f"LEAD_V6 HEARTBEAT | {T} | 10.00m | BTC 1 | BRTI N/A | UP 0.1 | DOWN 0.9 | pending 0",
            f"LEAD_V6 HEARTBEAT | {t2} | 10.00m | BTC 1 | BRTI 2 | UP 0.1 | DOWN 0.9 | pending 0",
        ]
        parsed = dq.parse_lines(lines)
        self.assertEqual(set(parsed), {T, t2})
        self.assertEqual(parsed[T].brti_na_heartbeats, 1)
        self.assertEqual(parsed[t2].brti_na_heartbeats, 0)


if __name__ == "__main__":
    unittest.main()
