#!/usr/bin/env python3
from __future__ import annotations

import unittest

import btc15_scalp_ladder_research_service_v1 as svc


class ResearchServiceTests(unittest.TestCase):
    def test_sha_is_stable(self):
        self.assertEqual(
            svc.sha256_bytes(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )

    def test_selection_is_never_actionable(self):
        opps = []
        # 12 strong validation secondary rows.
        for i in range(12):
            opps.append({
                "split": "VALIDATION",
                "opportunity_index": 2,
                "t5_sec": "10",
                "t10_sec": "20",
                "peak_gain": "0.15",
                "adverse_gain": "-0.03",
            })
        # Report-only data can be terrible; it must not affect validation selection.
        for i in range(12):
            opps.append({
                "split": "REPORT_ONLY",
                "opportunity_index": 2,
                "t5_sec": "",
                "t10_sec": "",
                "peak_gain": "0.00",
                "adverse_gain": "-0.20",
            })

        sel = svc.build_selection(opps, [])
        self.assertTrue(sel["opportunities"]["secondary"]["validation_viable"])
        self.assertFalse(sel["opportunities"]["secondary"]["actionable_now"])
        self.assertTrue(sel["opportunities"]["secondary"]["report_only_confirmation_only"])
        self.assertFalse(sel["report_only_used_for_selection"])
        self.assertFalse(sel["protected_primary_changed"])

    def test_failed_cut_requires_validation_and_forward(self):
        failed = []
        for i in range(12):
            failed.append({
                "split": "VALIDATION",
                "adverse_trigger_cents": "5",
                "min_elapsed_sec": "20",
                "would_recover_to_plus5": "false",
                "gain_at_trigger": "-0.05",
                "best_gain_after_trigger": "0.02",
            })
        sel = svc.build_selection([], failed)
        f = sel["failed_primary"]
        self.assertIsNotNone(f["validation_selected_cell"])
        self.assertTrue(f["requires_freeze_before_forward"])
        self.assertTrue(f["requires_20_new_forward"])
        self.assertFalse(f["actionable_now"])


if __name__ == "__main__":
    unittest.main()
