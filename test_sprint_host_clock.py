"""Protect against mistaking PHC-relative estimates for true UTC bounds."""
import unittest
from decimal import Decimal
from sprint_evidence.host_clock_diagnostics import summarize_tracking


HOSTED_TRACKING = "50484330,PHC0,1,1790709843.140441296,-0.000005108,0.000004585,0.000007324,10.496,0.075,0.696,0.000000001,0.000012658,8.0,Normal\n"


class HostedClockInterpretationTests(unittest.TestCase):
    def test_actual_hosted_values_have_conditional_arithmetic_not_utc_certificate(self):
        result = summarize_tracking(HOSTED_TRACKING)
        self.assertEqual(result["state"], "OBSERVED")
        self.assertEqual(result["reference_name"], "PHC0")
        self.assertEqual(Decimal(result["conditional_system_reference_error_us"]), Decimal("17.7665"))
        self.assertIsNone(result["absolute_utc_error_us"])
        self.assertIsNone(result["justified_worst_case_rate_ppm"])
        self.assertFalse(result["is_certificate"])

    def test_rms_or_skew_cannot_be_promoted_to_a_bound(self):
        text = HOSTED_TRACKING.replace("0.696", "0.000000001")
        result = summarize_tracking(text)
        self.assertIsNone(result["justified_worst_case_rate_ppm"])

    def test_malformed_nonfinite_negative_uncertainty_fail_closed(self):
        for text in ("", "garbage", HOSTED_TRACKING + HOSTED_TRACKING,
                     HOSTED_TRACKING.replace("0.696", "NaN"),
                     HOSTED_TRACKING.replace("0.000012658", "-0.000012658")):
            result = summarize_tracking(text)
            self.assertEqual(result["state"], "UNAVAILABLE")
            self.assertFalse(result["is_certificate"])


if __name__ == "__main__":
    unittest.main()
