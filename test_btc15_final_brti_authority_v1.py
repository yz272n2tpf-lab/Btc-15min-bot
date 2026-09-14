#!/usr/bin/env python3
import unittest

from btc15_final_brti_authority_v1 import evaluate_final_brti_authority


class FinalBrtiAuthorityTests(unittest.TestCase):
    def test_fresh_up_agreement_is_ready(self):
        x = evaluate_final_brti_authority(
            value=78025, age_sec=1.2, target=78000, fair_side="UP"
        )
        self.assertTrue(x.ready)
        self.assertTrue(x.agrees_with_fair)
        self.assertEqual(x.side, "UP")
        self.assertAlmostEqual(x.gap, 25)

    def test_fresh_down_agreement_is_ready(self):
        x = evaluate_final_brti_authority(
            value=77975, age_sec=4.9, target=78000, fair_side="DOWN"
        )
        self.assertTrue(x.ready)
        self.assertTrue(x.agrees_with_fair)
        self.assertEqual(x.side, "DOWN")

    def test_exact_five_seconds_remains_fresh(self):
        x = evaluate_final_brti_authority(
            value=78020, age_sec=5.0, target=78000, fair_side="UP"
        )
        self.assertTrue(x.ready)

    def test_older_than_five_seconds_fails_closed(self):
        x = evaluate_final_brti_authority(
            value=78020, age_sec=5.001, target=78000, fair_side="UP"
        )
        self.assertFalse(x.ready)
        self.assertFalse(x.agrees_with_fair)

    def test_exact_eleven_dollar_gap_is_wait(self):
        x = evaluate_final_brti_authority(
            value=78011, age_sec=1, target=78000, fair_side="UP"
        )
        self.assertFalse(x.ready)

    def test_gap_over_eleven_is_ready(self):
        x = evaluate_final_brti_authority(
            value=78011.01, age_sec=1, target=78000, fair_side="UP"
        )
        self.assertTrue(x.ready)

    def test_fair_disagreement_blocks_final_authority(self):
        x = evaluate_final_brti_authority(
            value=78025, age_sec=1, target=78000, fair_side="DOWN"
        )
        self.assertTrue(x.ready)
        self.assertFalse(x.agrees_with_fair)

    def test_missing_data_fails_closed(self):
        x = evaluate_final_brti_authority(
            value=None, age_sec=None, target=78000, fair_side="UP"
        )
        self.assertFalse(x.ready)
        self.assertFalse(x.agrees_with_fair)
        self.assertIsNone(x.side)


if __name__ == "__main__":
    unittest.main()
