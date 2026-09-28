#!/usr/bin/env python3
import unittest

import scalp_rescue_feasibility_v1 as r


class RescueFeasibilityTests(unittest.TestCase):
    def test_reason_level_hindsight_is_separated(self):
        ledger = [
            {"reason":"BTC30_BELOW_BASELINE_15","complete_candidate_paths":1,"hindsight_any_plus5":True,"hindsight_any_plus10":True,"hindsight_any_plus20":False,"hindsight_early_plus10":True,"hindsight_affordable_plus10":True,"hindsight_early_affordable_plus10":True,"hindsight_nonbaseline_plus10":True,"best_hindsight_peak_c":14.0},
            {"reason":"BTC30_BELOW_BASELINE_15","complete_candidate_paths":1,"hindsight_any_plus5":False,"hindsight_any_plus10":False,"hindsight_any_plus20":False,"hindsight_early_plus10":False,"hindsight_affordable_plus10":False,"hindsight_early_affordable_plus10":False,"hindsight_nonbaseline_plus10":False,"best_hindsight_peak_c":4.0},
            {"reason":"NO_CANDIDATE_ROWS","complete_candidate_paths":0,"hindsight_any_plus5":False,"hindsight_any_plus10":False,"hindsight_any_plus20":False,"hindsight_early_plus10":False,"hindsight_affordable_plus10":False,"hindsight_early_affordable_plus10":False,"hindsight_nonbaseline_plus10":False,"best_hindsight_peak_c":None},
        ]
        out = r.summarize(ledger)
        weak = out["by_reason"]["BTC30_BELOW_BASELINE_15"]
        self.assertEqual(weak["contracts"], 2)
        self.assertEqual(weak["with_hindsight_plus10"], 1)
        self.assertEqual(weak["with_hindsight_early_affordable_plus10"], 1)
        self.assertEqual(weak["hindsight_plus10_share"], 0.5)
        self.assertTrue(out["forward_freeze_required"])
        self.assertFalse(out["orders"])
        self.assertFalse(out["automatic_promotion"])

    def test_empty_ledger_is_safe(self):
        out = r.summarize([])
        self.assertEqual(out["contracts"], 0)
        self.assertEqual(out["by_reason"], {})
        self.assertTrue(out["hindsight_labels_are_development_only"])


if __name__ == "__main__":
    unittest.main()
