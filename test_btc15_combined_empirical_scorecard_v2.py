#!/usr/bin/env python3
import unittest

import btc15_combined_empirical_scorecard_v2 as m
import BTC15_DASHBOARD_STATE_SOURCE_AUDIT_V1 as source_audit


def scalp(cid, idx, *, peak, entry=.35, terminal="EXIT", exit_gain=.08, actionable_exit=True, seconds=600):
    return {
        "candidate_id": cid,
        "opportunity_index": idx,
        "terminal_state": terminal,
        "completed": True,
        "side": "UP" if idx % 2 else "DOWN",
        "entry_price": entry,
        "peak_exec_gain": peak,
        "exit_gain": exit_gain if terminal == "EXIT" else None,
        "actionable_exit": actionable_exit,
        "entry_seconds_left": seconds,
    }


class CombinedEmpiricalScorecardV2Tests(unittest.TestCase):
    def test_two_serial_scalps_same_contract_count_union_once(self):
        s = m.score_records([{
            "contract": "C1",
            "scalps": [
                scalp("a", 1, peak=.14),
                scalp("b", 2, peak=.22),
            ],
        }])
        self.assertEqual(s["contracts"], 1)
        self.assertEqual(s["scalp_contracts"], 1)
        self.assertEqual(s["union_actionable_contracts"], 1)
        self.assertEqual(s["scalp"]["opportunities"], 2)
        self.assertEqual(s["scalp"]["multi_scalp_contracts"], 1)
        self.assertEqual(s["scalp"]["max_scalps_in_one_contract"], 2)

    def test_early_three_scalps_final_still_one_union_contract(self):
        s = m.score_records([{
            "contract": "C2",
            "official_side": "UP",
            "early": {"state": "QUALIFIED", "side": "UP", "ask": .32, "fair": .80, "seconds_left": 420},
            "final": {"state": "LOCK", "side": "UP", "ask": .94, "fair": .95, "seconds_left": 300},
            "scalps": [
                scalp("a", 1, peak=.06),
                scalp("b", 2, peak=.12),
                scalp("c", 3, peak=.25),
            ],
        }])
        self.assertEqual(s["union_actionable_contracts"], 1)
        self.assertEqual(s["path_pattern_counts"]["EARLY+SCALP+FINAL"], 1)
        self.assertEqual(s["scalp"]["opportunities"], 3)
        self.assertEqual(s["early"]["accuracy"], 1.0)
        self.assertEqual(s["final"]["accuracy"], 1.0)

    def test_expensive_correct_final_does_not_become_good_entry(self):
        s = m.score_records([{
            "contract": "C3",
            "official_side": "DOWN",
            "final": {"state": "LOCK", "side": "DOWN", "ask": .94, "fair": .96, "seconds_left": 300},
        }])
        self.assertEqual(s["final"]["accuracy"], 1.0)
        self.assertEqual(s["final"]["ask_le_50c_n"], 0)
        self.assertEqual(s["final"]["avg_ask"], .94)
        self.assertTrue(s["final_accuracy_is_not_entry_quality"])

    def test_ended_unarmed_counts_opportunity_but_not_actionable_exit(self):
        ended = scalp(
            "u1", 1, peak=.03, entry=.41, terminal="ENDED_UNARMED",
            exit_gain=None, actionable_exit=False,
        )
        s = m.score_records([{"contract": "C4", "scalps": [ended]}])
        self.assertEqual(s["scalp_contracts"], 1)
        self.assertEqual(s["scalp"]["opportunities"], 1)
        self.assertEqual(s["scalp"]["ended_unarmed_n"], 1)
        self.assertEqual(s["scalp"]["protected_exit_n"], 0)
        self.assertTrue(s["scalp"]["ended_unarmed_non_actionable_exit_invariant"])

    def test_watch_is_not_actionable(self):
        s = m.score_records([{
            "contract": "C5",
            "final": {"state": "WATCH", "side": "UP", "fair": .89, "seconds_left": 500},
        }])
        self.assertEqual(s["final_contracts"], 0)
        self.assertEqual(s["union_actionable_contracts"], 0)
        self.assertEqual(s["path_pattern_counts"]["NONE"], 1)

    def test_duplicate_current_and_terminal_candidate_is_deduped(self):
        terminal = scalp("dup", 1, peak=.13, entry=.37)
        current = {
            "candidate_id": "dup",
            "opportunity_index": 1,
            "state": "PROTECT",
            "side": "UP",
            "entry_price": .37,
            "peak_exec_gain": .10,
            "entry_seconds_left": 600,
        }
        s = m.score_records([{"contract": "C6", "scalps": [current, terminal]}])
        self.assertEqual(s["scalp"]["opportunities"], 1)
        self.assertEqual(s["scalp"]["completed_opportunities"], 1)
        self.assertEqual(s["union_actionable_contracts"], 1)

    def test_scalp_move_thresholds_preserve_serial_opportunity_denominator(self):
        s = m.score_records([{
            "contract": "C7",
            "scalps": [
                scalp("a", 1, peak=.04),
                scalp("b", 2, peak=.10),
                scalp("c", 3, peak=.21),
            ],
        }])
        self.assertEqual(s["scalp"]["completed_with_peak"], 3)
        self.assertEqual(s["scalp"]["plus_5c_n"], 2)
        self.assertEqual(s["scalp"]["plus_10c_n"], 2)
        self.assertEqual(s["scalp"]["plus_20c_n"], 1)
        self.assertAlmostEqual(s["scalp"]["plus_10c_rate"], 2/3)

    def test_duplicate_contract_record_fails_closed(self):
        with self.assertRaises(ValueError):
            m.score_records([
                {"contract": "C8"},
                {"contract": "C8"},
            ])

    def test_safety_envelope(self):
        s = m.score_records([{"contract": "C9"}])
        self.assertFalse(s["orders"])
        self.assertTrue(s["manual_execution_only"])
        self.assertFalse(s["numeric_flip_risk_validated"])
        self.assertFalse(s["module_thresholds_changed"])
        self.assertFalse(s["production_behavior_changed"])
        self.assertTrue(s["union_counts_each_contract_once"])
        self.assertTrue(s["serial_scalps_preserved_separately"])

    def test_packed_dashboard_state_contract_discovery_source_is_auditable(self):
        src = source_audit.decoded_source()
        self.assertIn("NO ACTIVE KXBTC15M CONTRACT", src)
        self.assertIn("KXBTC15M", src)
        source_audit.print_audit()


if __name__ == "__main__":
    unittest.main()
