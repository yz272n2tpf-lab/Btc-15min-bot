#!/usr/bin/env python3
import unittest

import BTC15_SCALP_CANDIDATE_FEATURE_INVENTORY_V1 as m


class CandidateFeatureInventoryTests(unittest.TestCase):
    def rows(self):
        out = []
        for i in range(12):
            out.append({
                "record_type": "CANDIDATE",
                "contract": f"C{i//2}",
                "candidate_id": f"x{i}",
                "timestamp_utc": f"2026-09-15T00:{i:02d}:00Z",
                "side": "UP" if i % 2 == 0 else "DOWN",
                "entry_ask": str(.30 + i * .01),
                "seconds_left": str(800 - i * 10),
                "btc30": str(15 + i),
                "btc10": str(5 + i * .5),
                "volume_z": str(-1 + i * .2),
                "current_bid": str(.28 + i * .01),
                "signal_time_ms": str(100 + i),
            })
        return out

    def test_inventory_excludes_price_time_identity_and_already_tested_btc30(self):
        s = m.inventory_candidate_rows(self.rows())
        self.assertIn("btc30", s["numeric_fields"])
        self.assertIn("btc30", s["already_tested_fields"])
        self.assertIn("btc10", s["next_nonprice_numeric_fields"])
        self.assertIn("volume_z", s["next_nonprice_numeric_fields"])
        self.assertNotIn("entry_ask", s["next_nonprice_numeric_fields"])
        self.assertNotIn("seconds_left", s["next_nonprice_numeric_fields"])
        self.assertNotIn("current_bid", s["next_nonprice_numeric_fields"])
        self.assertNotIn("signal_time_ms", s["next_nonprice_numeric_fields"])
        self.assertNotIn("candidate_id", s["next_nonprice_numeric_fields"])

    def test_sparse_or_non_numeric_fields_do_not_become_numeric_candidates(self):
        rows = self.rows()
        for i, r in enumerate(rows):
            r["sparse_feature"] = "1" if i < 3 else ""
            r["label"] = "bullish" if i % 2 == 0 else "bearish"
        s = m.inventory_candidate_rows(rows)
        self.assertNotIn("sparse_feature", s["numeric_fields"])
        self.assertNotIn("label", s["numeric_fields"])

    def test_inventory_never_selects_or_promotes(self):
        s = m.inventory_candidate_rows(self.rows())
        self.assertFalse(s["orders"])
        self.assertTrue(s["manual_execution_only"])
        self.assertFalse(s["entry_price_filter_applied"])
        self.assertFalse(s["fixed_time_window_applied"])
        self.assertFalse(s["feature_selected"])
        self.assertFalse(s["auto_promote_allowed"])


if __name__ == "__main__":
    unittest.main()
