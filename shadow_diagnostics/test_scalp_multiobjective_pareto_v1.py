#!/usr/bin/env python3
import unittest

import scalp_multiobjective_pareto_v1 as p


class ParetoFrontierTests(unittest.TestCase):
    def row(self, name, hit, cov, cheap, ask, mins, n=20):
        return {
            "name": name,
            "n": n,
            "plus10_rate": hit,
            "true_contract_coverage": cov,
            "affordable_true_contract_coverage_le50": cheap,
            "avg_entry_ask_c": ask,
            "avg_minutes_left": mins,
        }

    def test_dominated_row_is_removed(self):
        a = self.row("A", .90, .92, .75, 38, 7.0)
        b = self.row("B", .85, .90, .70, 42, 6.0)
        out = p.pareto_frontier([a, b])
        self.assertEqual([r["name"] for r in out], ["A"])

    def test_real_tradeoff_rows_are_both_kept(self):
        accuracy = self.row("ACCURACY", .96, .82, .60, 34, 5.5)
        coverage = self.row("COVERAGE", .91, .96, .84, 40, 8.0)
        names = {r["name"] for r in p.pareto_frontier([accuracy, coverage])}
        self.assertEqual(names, {"ACCURACY", "COVERAGE"})

    def test_lower_ask_and_earlier_can_prevent_domination(self):
        late = self.row("LATE", .94, .92, .74, 48, 4.0)
        early = self.row("EARLY", .93, .92, .74, 31, 9.0)
        names = {r["name"] for r in p.pareto_frontier([late, early])}
        self.assertEqual(names, {"LATE", "EARLY"})

    def test_invalid_and_tiny_rows_are_excluded(self):
        good = self.row("GOOD", .90, .90, .70, 35, 7.0, n=20)
        tiny = self.row("TINY", 1.0, 1.0, 1.0, 10, 12.0, n=2)
        bad = {**self.row("BAD", .99, .99, .99, 10, 12.0), "avg_entry_ask_c": None}
        out = p.pareto_frontier([good, tiny, bad], min_n=8)
        self.assertEqual([r["name"] for r in out], ["GOOD"])


if __name__ == "__main__":
    unittest.main()
