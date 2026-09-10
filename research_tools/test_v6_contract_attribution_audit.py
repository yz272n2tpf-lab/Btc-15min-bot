import unittest
from v6_contract_attribution_audit import audit_lines


class ContractAttributionAuditTests(unittest.TestCase):
    def test_matching_summary_passes(self):
        lines = [
            "LEAD_V6 RESULT | V6_QUALIFIED | A | UP | zone PREFERRED_7_30C | hit10 True",
            "LEAD_V6 CONTRACT_SUMMARY | A | V5 n=1 hit5=100.0% | V6 n=1 hit5=100.0% | rejects price=0",
        ]
        result = audit_lines(lines)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["v6_results_reconstructed"], 1)

    def test_late_result_after_summary_is_flagged(self):
        lines = [
            "LEAD_V6 RESULT | V6_QUALIFIED | A | UP | zone PREFERRED_7_30C | hit10 True",
            "LEAD_V6 CONTRACT_SUMMARY | A | V5 n=1 | V6 n=1 hit5=100.0% | rejects price=0",
            "LEAD_V6 RESULT | V6_QUALIFIED | A | UP | zone PREFERRED_7_30C | hit10 True | entry 0.14",
        ]
        result = audit_lines(lines)
        self.assertEqual(result["status"], "FLAG")
        self.assertEqual(result["mismatches"][0]["kind"], "SUMMARY_UNDERCOUNT")
        self.assertEqual(len(result["late_results_after_own_summary"]), 1)

    def test_cross_contract_leak_pattern_is_visible(self):
        lines = [
            "LEAD_V6 RESULT | V6_QUALIFIED | A | UP | zone X | hit10 True",
            "LEAD_V6 RESULT | V6_QUALIFIED | A | UP | zone X | hit10 True | entry 0.2",
            "LEAD_V6 RESULT | V6_QUALIFIED | A | UP | zone X | hit10 False",
            "LEAD_V6 CONTRACT_SUMMARY | A | V5 n=3 | V6 n=3 hit5=100.0% | rejects price=0",
            "LEAD_V6 RESULT | V6_QUALIFIED | A | UP | zone X | hit10 True | entry 0.14",
            "LEAD_V6 RESULT | V6_QUALIFIED | B | DOWN | zone X | hit10 True",
            "LEAD_V6 CONTRACT_SUMMARY | B | V5 n=1 | V6 n=2 hit5=100.0% | rejects price=0",
        ]
        result = audit_lines(lines)
        by_ticker = {x["ticker"]: x for x in result["mismatches"]}
        self.assertEqual(by_ticker["A"]["kind"], "SUMMARY_UNDERCOUNT")
        self.assertEqual(by_ticker["A"]["actual_results"], 4)
        self.assertEqual(by_ticker["B"]["kind"], "SUMMARY_EXCESS")
        self.assertEqual(by_ticker["B"]["actual_results"], 1)

    def test_duplicate_export_line_is_deduped(self):
        line = "LEAD_V6 RESULT | V6_QUALIFIED | A | UP | zone X | hit10 True"
        result = audit_lines([line, line, "LEAD_V6 CONTRACT_SUMMARY | A | V5 n=1 | V6 n=1 | rejects price=0"])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["v6_results_reconstructed"], 1)

    def test_zero_summary_is_parsed(self):
        result = audit_lines(["LEAD_V6 CONTRACT_SUMMARY | A | V5 n=0 | V6 n=0 | rejects price=0"])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["summaries_seen"], 1)


if __name__ == "__main__":
    unittest.main()
