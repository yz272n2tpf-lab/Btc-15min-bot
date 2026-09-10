import unittest

from v6_result_integrity_audit_v1 import audit_lines


def result_line(
    grade="V6_QUALIFIED",
    ticker="KXBTC15M-TEST",
    side="UP",
    style="NO_EXPANSION",
    entry="0.200",
    gain="+0.070",
    adverse="-0.020",
    hit10="False",
    hit20="False",
    t5="47.0",
    t10="None",
    t20="None",
    ask5="47.0",
):
    return (
        f"LEAD_V6 RESULT | {grade} | {ticker} | {side} | zone PREFERRED_7_30C | "
        f"style {style} | entry {entry} | max_exec_gain {gain} | adverse {adverse} | "
        f"hit10 {hit10} | hit20 {hit20} | to_exec+5c {t5} | to_exec+10c {t10} | "
        f"to_exec+20c {t20} | kalshi_reprice+5c {ask5}"
    )


class ResultIntegrityAuditTests(unittest.TestCase):
    def test_clean_result_passes(self):
        r = audit_lines([result_line()])
        self.assertTrue(r["ok"])
        self.assertEqual(r["by_grade"]["V6_QUALIFIED"]["hit5"], 1)

    def test_exact_printed_5c_boundary_is_ambiguous_not_false_failure(self):
        r = audit_lines([result_line(gain="+0.050", t5="None", ask5="31.0")])
        self.assertTrue(r["ok"])
        self.assertEqual(r["boundary_ambiguous_count"], 1)
        self.assertEqual(r["by_grade"]["V6_QUALIFIED"]["hit5"], 0)

    def test_exact_printed_10c_boundary_is_ambiguous_not_reclassified(self):
        r = audit_lines([result_line(gain="+0.100", t5="20.0", t10="None", hit10="False")])
        self.assertTrue(r["ok"])
        checks = [x["check"] for x in r["boundary_ambiguous"]]
        self.assertIn("t10", checks)
        self.assertEqual(r["by_grade"]["V6_QUALIFIED"]["hit10"], 0)

    def test_definite_threshold_contradiction_fails_closed(self):
        r = audit_lines([result_line(gain="+0.060", t5="None")])
        self.assertFalse(r["ok"])
        self.assertGreaterEqual(r["contradiction_count"], 1)

    def test_duplicate_result_fails_closed(self):
        line = result_line()
        r = audit_lines([line, line])
        self.assertFalse(r["ok"])
        self.assertEqual(r["duplicate_count"], 1)

    def test_style_and_boolean_consistency_are_checked(self):
        bad_style = result_line(
            style="BURST", gain="+0.120", t5="10.0", t10="40.0", hit10="True"
        )
        bad_bool = result_line(
            style="EXPANSION", gain="+0.120", t5="10.0", t10="40.0", hit10="False"
        )
        r1 = audit_lines([bad_style])
        r2 = audit_lines([bad_bool])
        self.assertFalse(r1["ok"])
        self.assertEqual(r1["style_mismatch_count"], 1)
        self.assertFalse(r2["ok"])
        self.assertGreaterEqual(r2["contradiction_count"], 1)


if __name__ == "__main__":
    unittest.main()
