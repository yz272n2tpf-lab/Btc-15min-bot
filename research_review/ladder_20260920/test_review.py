"""Offline regression and characterization tests; no efficacy certification."""
import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "shadow_diagnostics"))
import review
import scalp_pullback_entry_forward_v1 as lane
import scalp_opportunity_quality_frontier_v1 as q


def op(ask=.60, paths=()):
    return {"contract": "C", "candidate_id": "C|UP|1", "opportunity_index": 1,
            "entry_ask": ask, "seconds_left": 600,
            "_candidate": {"timestamp_utc": "2026-09-20T12:00:00Z"},
            "_paths": [dict(elapsed_sec=e, current_ask=a, current_bid=b) for e, a, b in paths]}


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads((HERE / "archived_workflow_evidence.json").read_text())

    def test_two_exact_hash_runs_agree_and_missing_stays_missing(self):
        result = review.scorecard(self.evidence)
        self.assertFalse(result["raw_tape_reproduced"])
        self.assertIsNone(result["winner_id_retention"]["observed"])
        self.assertEqual(result["lanes"][review.CANDIDATE]["reported_count_numerators"]["plus10"], 213)
        self.assertFalse(result["holdout"]["eligible_boundary_certified"])

    def test_same_counts_different_source_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            review.parse_comparison(self.evidence["later_changed_source"])

    def test_noninteger_count_cannot_be_invented(self):
        with self.assertRaises(ValueError):
            review.count_from_rate(.5, 3)


class FrozenLaneTests(unittest.TestCase):
    def test_first_ask_is_used_and_30_second_boundary_is_inclusive(self):
        x = op(paths=[(29, .51, .50), (30, .49, .48), (31, .40, .39)])
        d = lane.first_pullback_entry(x, .50, 30.)
        self.assertEqual((d["entry_elapsed_sec"], d["entry_ask"]), (30, .49))

    def test_no_value_by_deadline_leaves_original_move_intact(self):
        x = op(paths=[(30, .51, .50), (30.001, .49, .48)])
        before = copy.deepcopy(x)
        self.assertIsNone(lane.first_pullback_entry(x, .50, 30.))
        self.assertEqual(x, before)

    def test_future_outcomes_do_not_change_decision(self):
        x = op(paths=[(5, .49, .48)])
        before = lane.first_pullback_entry(x, .50, 30.)
        x.update(peak_gain=.99, adverse_gain=-.99, protected_exit_gain=.88, plus10=1)
        x["_paths"].append(dict(elapsed_sec=31, current_ask=.01, current_bid=0))
        self.assertEqual(lane.first_pullback_entry(x, .50, 30.), before)

    def test_no_preentry_bid_scores_the_entry(self):
        x = op(paths=[(1, .90, .89), (10, .49, .48), (20, .54, .53)])
        r = lane.replay_from_pullback(x, .50, 30.)
        self.assertEqual(r["plus5"], 0)
        self.assertFalse(r["protected_exit_observed"])

    def test_first_observed_four_cent_giveback_and_postexit_peak_are_distinct(self):
        x = op(.40, [(1, .46, .45), (2, .50, .49), (3, .47, .46), (4, .45, .44), (5, .71, .70)])
        r = lane.replay_from_pullback(x, .50, 30.)
        self.assertEqual(r["protected_exit_elapsed_sec"], 4)
        self.assertAlmostEqual(r["protected_exit_gain"], .04)
        self.assertEqual(r["plus20"], 1)  # after EXIT; must not be called captured profit

    def test_missing_paths_are_not_zero_profit(self):
        r = lane.replay_from_pullback(op(.40), .50, 30.)
        self.assertFalse(r["movement_scoreable"])
        self.assertIsNone(r["plus5"])
        self.assertIsNone(r["one_lot_taker_taker_net_c"])

    def test_price_neutral_qualification_and_minimum_time_both_sides(self):
        for side in ("UP", "DOWN"):
            for ask in (.10, .80):
                c = dict(side=side, entry_ask=ask, seconds_left=120, btc30=15)
                self.assertTrue(q.baseline_qualified(c))
                self.assertFalse(q.baseline_qualified({**c, "seconds_left": 119.999}))


class HistoricalLimitCharacterization(unittest.TestCase):
    """Passing means the limitation was reproduced, not that it is acceptable."""
    def rows(self, first_gain):
        rows = []
        for i, minute in enumerate((0, 2)):
            cid = f"C|UP|{i}"
            rows += [dict(record_type="CANDIDATE", contract="C", candidate_id=cid,
                          timestamp_utc=f"2026-09-20T12:0{minute}:00Z", entry_ask=.40,
                          seconds_left=600-minute*60, btc30=20, side="UP"),
                     dict(record_type="PATH", candidate_id=cid, elapsed_sec=1,
                          exec_gain=first_gain if i == 0 else .20),
                     dict(record_type="RESULT", candidate_id=cid,
                          timestamp_utc=f"2026-09-20T12:0{minute}:30Z")]
        return rows

    def test_legacy_builder_does_not_reset_after_unarmed_result(self):
        self.assertEqual(len(q.build_serial_opportunities(self.rows(.02))), 1)
        # Established ENDED_UNARMED policy would permit the later qualified candidate.

    def test_armed_without_exit_remains_blocking(self):
        self.assertEqual(len(q.build_serial_opportunities(self.rows(.08))), 1)

    def test_legacy_lane_assumes_quote_validity_and_clamps_negative_elapsed(self):
        x = op(paths=[(-1, -.10, -.20)])
        d = lane.first_pullback_entry(x, .50, 30.)
        self.assertEqual((d["entry_elapsed_sec"], d["entry_ask"]), (0, -.10))
        # This proves an input-validation assumption, not occurrence in the missing tape.


if __name__ == "__main__":
    unittest.main()
