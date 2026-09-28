#!/usr/bin/env python3
import unittest

import scalp_kalshi_lag_fingerprint_v1 as k


class KalshiLagFingerprintTests(unittest.TestCase):
    def test_percentile_midrank(self):
        vals = [1.0, 2.0, 2.0, 4.0]
        self.assertAlmostEqual(k.percentile(2.0, vals), 0.50)

    def test_stronger_impulse_and_muted_response_scores_higher(self):
        dev = [
            {"momentum_floor15": 5, "btc_move30_side": 15, "acceleration": 0, "ask_move15": .01, "ask_move5": .01, "spread": .02},
            {"momentum_floor15": 10, "btc_move30_side": 25, "acceleration": 2, "ask_move15": .03, "ask_move5": .02, "spread": .03},
            {"momentum_floor15": 20, "btc_move30_side": 40, "acceleration": 5, "ask_move15": .06, "ask_move5": .04, "spread": .04},
        ]
        scales = k.build_scales(dev)
        strong_lag = {
            "momentum_floor15": 20, "btc_move30_side": 40, "acceleration": 5,
            "ask_move15": .005, "ask_move5": .005, "spread": .02,
            "btc_brti_agree15": 1, "btc_against_side": 0, "brti_against_side": 0,
            "dual_reversal_evidence": 0,
        }
        priced = {
            **strong_lag,
            "ask_move15": .07, "ask_move5": .05,
        }
        a = k.lag_fingerprint(strong_lag, scales)
        b = k.lag_fingerprint(priced, scales)
        self.assertGreater(a["lag_index"], b["lag_index"])
        self.assertGreater(a["lag_gap"], b["lag_gap"])

    def test_reversal_evidence_penalizes_lag_index(self):
        dev = [
            {"momentum_floor15": 5, "btc_move30_side": 15, "acceleration": 0, "ask_move15": .01, "ask_move5": .01, "spread": .02},
            {"momentum_floor15": 20, "btc_move30_side": 40, "acceleration": 5, "ask_move15": .06, "ask_move5": .04, "spread": .04},
        ]
        scales = k.build_scales(dev)
        base = {
            "momentum_floor15": 20, "btc_move30_side": 40, "acceleration": 5,
            "ask_move15": .01, "ask_move5": .01, "spread": .02,
            "btc_brti_agree15": 1, "btc_against_side": 0, "brti_against_side": 0,
            "dual_reversal_evidence": 0,
        }
        safe = k.lag_fingerprint(base, scales)["lag_index"]
        risky = k.lag_fingerprint({**base, "dual_reversal_evidence": 1}, scales)["lag_index"]
        self.assertGreater(safe, risky)

    def test_missing_units_fail_gracefully(self):
        scales = k.build_scales([])
        out = k.lag_fingerprint({}, scales)
        self.assertIsNone(out["lag_index"])


if __name__ == "__main__":
    unittest.main()
