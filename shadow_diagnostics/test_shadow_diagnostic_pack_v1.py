import sys
import unittest
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kalshi_shadow_diagnostic_pack_v1 as diag


def fixture():
    rows = []
    truth = {"C_UP": "UP", "C_DOWN": "DOWN", "C_ASKBLOCK": "UP"}
    base = pd.Timestamp("2026-09-10T00:00:00Z")
    specs = {
        "C_UP": ("UP", 0.82, 0.40, 50.0, 1.2),
        "C_DOWN": ("DOWN", 0.82, 0.40, 50.0, 1.2),
        # Everything passes Tier-1 except ask.  The blocker audit should catch it.
        "C_ASKBLOCK": ("UP", 0.82, 0.52, 50.0, 1.2),
    }
    for ci, (contract, (preferred, fair, ask, gap, ratio)) in enumerate(specs.items()):
        for step, ml in enumerate([8.0, 7.5]):
            ts = base + pd.Timedelta(minutes=15 * ci, seconds=30 * step)
            signed_gap = gap if preferred == "UP" else -gap
            for side in ["UP", "DOWN"]:
                same = side == preferred
                side_fair = fair if same else 1.0 - fair
                side_ask = ask if same else 1.0 - ask + 0.01
                rows.append(
                    {
                        "timestamp_utc": ts.isoformat(),
                        "contract": contract,
                        "side": side,
                        "minutes_left": ml,
                        "btc_gap": signed_gap,
                        "abs_btc_gap": abs(signed_gap),
                        "side_ask": side_ask,
                        "opposite_ask": (1.0 - ask + 0.01) if same else ask,
                        "side_fair": side_fair,
                        "side_edge": side_fair - side_ask,
                        "preferred_fair_side": preferred,
                        "preferred_fair": fair,
                        "preferred_edge": fair - ask,
                        "current_target_side": preferred,
                        "dist_over_range5": ratio,
                        "brti_agrees_side": same,
                        "btc_move_5s_side": 1.0 if same else -1.0,
                        "btc_move_15s_side": 1.0 if same else -1.0,
                        "btc_move_30s_side": 1.0 if same else -1.0,
                    }
                )
    return pd.DataFrame(rows), truth


class ShadowDiagnosticTests(unittest.TestCase):
    def test_side_normalization(self):
        self.assertEqual(diag.norm_side("yes"), "UP")
        self.assertEqual(diag.norm_side("0"), "DOWN")
        self.assertEqual(diag.norm_side("higher"), "UP")

    def test_preferred_snapshot_collapse_and_price(self):
        raw, truth = fixture()
        pref = diag.prepare_preferred_frame(raw, truth)
        self.assertEqual(len(pref), 6)
        up = pref[pref["contract"] == "C_UP"].iloc[0]
        self.assertEqual(up["preferred_side"], "UP")
        self.assertAlmostEqual(up["ask_c"], 40.0)
        self.assertTrue(bool(up["correct"]))

    def test_locked_tier1_rule_is_replayed_exactly(self):
        raw, truth = fixture()
        pref = diag.prepare_preferred_frame(raw, truth)
        score = diag.baseline_scorecard(pref, len(truth))
        tier1 = score[score["lane"] == "LOCKED_TIER1_EARLY"].iloc[0]
        # C_UP and C_DOWN pass.  C_ASKBLOCK is rejected only because ask > 45c.
        self.assertEqual(int(tier1["calls"]), 2)
        self.assertAlmostEqual(float(tier1["accuracy"]), 1.0)

    def test_blocker_ledger_identifies_ask_gate(self):
        raw, truth = fixture()
        pref = diag.prepare_preferred_frame(raw, truth)
        ledger, summary = diag.early_blocker_audit(pref, truth)
        blocked = ledger[ledger["contract"] == "C_ASKBLOCK"].iloc[0]
        self.assertFalse(bool(blocked["qualified"]))
        self.assertEqual(blocked["failed_gates"], "ask_le_45c")
        ask_row = summary[summary["gate"] == "ask_le_45c"].iloc[0]
        self.assertEqual(int(ask_row["one_gate_removed_rescue_contracts"]), 1)
        self.assertAlmostEqual(float(ask_row["rescue_accuracy"]), 1.0)


if __name__ == "__main__":
    unittest.main()
