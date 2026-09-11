import unittest

from unified_scalp_heartbeat_path_audit_v1 import audit_lines


def candidate(ticker="T1", side="UP", entry=.20, left=180):
    return (
        f"LEAD_V7 CANDIDATE | lane MOMENTUM_EXPANSION | {ticker} | {side} | zone Z "
        f"| ask {entry:.3f} | btc5 +1 | btc15 +1 | btc30 +1 | accel +1 | brti5 +1 "
        f"| brti15 +1 | ask5 +0 | ask15 +0 | left {left}s"
    )


def heartbeat(ticker="T1", leftm=2.5, up=.18, down=.82):
    return (
        f"LEAD_V7 HEARTBEAT | {ticker} | {leftm:.2f}m | BTC 1 | BRTI 1 "
        f"| UP {up:.3f} | DOWN {down:.3f} | pending 1"
    )


def result(ticker="T1", side="UP", entry=.20, t10="60.0", lane="MOMENTUM_EXPANSION", adv=-.05):
    return (
        f"LEAD_V7 RESULT | lane {lane} | {ticker} | {side} | zone Z | style EXPANSION "
        f"| entry {entry:.3f} | max_gain +0.150 | adverse {adv:+.3f} "
        f"| to+5c 20.0 | to+10c {t10} | to+20c None | reprice+5c 20.0"
    )


class UnifiedHeartbeatPathAuditTests(unittest.TestCase):
    def test_success_pre_target_adverse(self):
        report = audit_lines([candidate(left=180), heartbeat(leftm=2.5, up=.17), heartbeat(leftm=2.0, up=.31), result(t10="60.0")])
        self.assertEqual(report["classifications"]["SUCCESS_PRETARGET_ADVERSE_OBSERVED"], 1)
        self.assertAlmostEqual(report["matched"][0]["worst_sampled_pre_target_delta"], -.03)

    def test_post_target_dip_not_counted(self):
        report = audit_lines([candidate(left=180), heartbeat(leftm=2.6, up=.22), heartbeat(leftm=1.5, up=.10), result(t10="30.0")])
        self.assertEqual(report["classifications"]["SUCCESS_NO_PRETARGET_ADVERSE_OBSERVED"], 1)
        self.assertAlmostEqual(report["matched"][0]["worst_sampled_pre_target_delta"], .02)

    def test_failure_uses_180s_window(self):
        report = audit_lines([candidate(left=220), heartbeat(leftm=3.0, up=.12), result(t10="None")])
        self.assertEqual(report["classifications"]["FAILED_WITH_SAMPLED_ADVERSE"], 1)

    def test_down_side_uses_down_price(self):
        report = audit_lines([candidate(side="DOWN", entry=.40, left=180), heartbeat(leftm=2.5, up=.70, down=.31), result(side="DOWN", entry=.40, t10="90.0")])
        self.assertEqual(report["classifications"]["SUCCESS_PRETARGET_ADVERSE_OBSERVED"], 1)
        self.assertAlmostEqual(report["matched"][0]["worst_sampled_pre_target_delta"], -.09)

    def test_legacy_reversal_audit_only(self):
        report = audit_lines([result(lane="ULTRA_CHEAP_REVERSAL", entry=.05)])
        self.assertEqual(report["legacy_reversal_research_only"], 1)
        self.assertEqual(report["matched_results"], 0)
        self.assertEqual(report["decision"]["separate_ultra_cheap_graduation_path"], "REJECT")

    def test_unmatched_result_fails_closed(self):
        report = audit_lines([result()])
        self.assertEqual(report["unmatched_results"], 1)
        self.assertEqual(report["classifications"]["UNMATCHED_RESULT"], 1)

    def test_unknown_lane_flagged(self):
        report = audit_lines([result(lane="OTHER")])
        self.assertEqual(report["unknown_lane_records"], 1)

    def test_price_zone_diagnostic_only(self):
        report = audit_lines([candidate(entry=.04, left=180), heartbeat(leftm=2.5, up=.03), result(entry=.04, t10="None")])
        self.assertIn("3_7C", report["zones"])
        self.assertEqual(report["decision"]["adverse_trap_tightening"], "MORE_DATA")


if __name__ == "__main__":
    unittest.main()
