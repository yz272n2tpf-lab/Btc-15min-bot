#!/usr/bin/env python3
import copy
import unittest

from btc15_dashboard_presentation_session_v1 import DashboardPresentationSession


def combined(contract="C1", seconds=600.0, *, final_state="WATCH", final_side=None, final_fair=None):
    return {
        "contract": contract,
        "canonical_seconds_left": seconds,
        "up_bid": .44,
        "up_ask": .45,
        "down_bid": .55,
        "down_ask": .56,
        "early": {"state": "PASS", "side": None, "ask": None, "fair": None, "edge": None},
        "final": {"state": final_state, "side": final_side, "fair": final_fair},
    }


def scalp_ui(
    *,
    contract="C1",
    lifecycle="ACTIVE",
    side="UP",
    opp=1,
    completed=0,
    scanning=False,
    app_ready=True,
    source_fresh=True,
    block_reason=None,
    tier="IDEAL_25_35",
    entry_c=31.0,
    bid_c=34.0,
    gain_c=3.0,
    peak_c=3.0,
    giveback_c=0.0,
):
    return {
        "contract": contract,
        "lifecycle_state": lifecycle,
        "display_state": "WAIT" if not app_ready else lifecycle,
        "side": side,
        "opportunity_index": opp,
        "serial_opportunities_completed": completed,
        "scanning_for_next": scanning,
        "entry_guidance": {
            "tier": tier,
            "label": tier,
            "presentation_only": True,
        },
        "entry_ask_c": entry_c,
        "current_bid_c": bid_c,
        "exec_gain_c": gain_c,
        "peak_exec_gain_c": peak_c,
        "giveback_from_peak_c": giveback_c,
        "source": {
            "app_ready": app_ready,
            "source_fresh": source_fresh,
            "integration_ready": app_ready,
            "block_reason": block_reason,
            "fail_closed": not app_ready,
        },
        "watch_warning": {"visible": False, "certified": False},
        "numeric_flip_risk": {"visible": False, "value": None, "certified": False},
        "manual_execution_only": True,
        "orders": False,
        "order_action": None,
    }


def row_value(model, label):
    for row in model["cards"]["SCALP_OPPORTUNITY"]["rows"]:
        if row["label"] == label:
            return row["value"]
    return None


class DashboardPresentationSessionV1Tests(unittest.TestCase):
    def test_acceptable_entry_survives_stale_wait_then_recovers_to_protect(self):
        session = DashboardPresentationSession()
        first = session.process(combined(), scalp_ui())
        self.assertEqual(first["cards"]["SCALP_OPPORTUNITY"]["action"], "UP #1 · ENTRY AVAILABLE")
        self.assertEqual(first["manual_entry_context"]["state"], "ACCEPTABLE_ENTRY_PATH")

        stale = session.process(
            combined(seconds=580.0),
            scalp_ui(
                lifecycle="ACTIVE",
                app_ready=False,
                source_fresh=False,
                block_reason="SCALP SOURCE STALE",
                tier="UNAVAILABLE",
                entry_c=None,
            ),
        )
        self.assertTrue(stale["cards"]["SCALP_OPPORTUNITY"]["action"].startswith("WAIT ·"))
        self.assertTrue(stale["presentation_session"]["current_fail_closed"])
        self.assertTrue(stale["presentation_session"]["healthy_context_preserved"])

        recovered = session.process(
            combined(seconds=560.0),
            scalp_ui(
                lifecycle="PROTECT",
                tier="UNAVAILABLE",
                entry_c=None,
                bid_c=40.0,
                gain_c=9.0,
                peak_c=10.0,
                giveback_c=1.0,
            ),
        )
        scalp = recovered["cards"]["SCALP_OPPORTUNITY"]
        self.assertEqual(scalp["action"], "PROTECT PROFITS")
        self.assertEqual(row_value(recovered, "Entry Price"), "31¢")
        self.assertEqual(recovered["manual_entry_context"]["state"], "ACCEPTABLE_ENTRY_PATH")
        self.assertFalse(recovered["presentation_session"]["current_fail_closed"])
        self.assertFalse(recovered["safety"]["manual_position_confirmed"])

    def test_tracking_only_survives_stale_wait_and_never_becomes_position_wording(self):
        session = DashboardPresentationSession()
        first = session.process(
            combined(),
            scalp_ui(tier="CAUTION_ABOVE_50", entry_c=71.0, bid_c=72.0),
        )
        self.assertIn("TRACKING ONLY", first["cards"]["SCALP_OPPORTUNITY"]["action"])
        self.assertEqual(first["manual_entry_context"]["state"], "TRACKING_ONLY_NO_POSITION")

        session.process(
            combined(seconds=580.0),
            scalp_ui(
                lifecycle="ACTIVE",
                app_ready=False,
                source_fresh=False,
                block_reason="SCALP SOURCE STALE",
                tier="UNAVAILABLE",
                entry_c=None,
            ),
        )
        recovered = session.process(
            combined(seconds=550.0),
            scalp_ui(
                lifecycle="PROTECT",
                tier="UNAVAILABLE",
                entry_c=None,
                bid_c=78.0,
                gain_c=7.0,
                peak_c=10.0,
                giveback_c=3.0,
            ),
        )
        scalp = recovered["cards"]["SCALP_OPPORTUNITY"]
        self.assertIn("TRACKING ONLY", scalp["action"])
        self.assertNotEqual(scalp["action"], "PROTECT PROFITS")
        self.assertIn("NO POSITION ASSUMED", row_value(recovered, "Profit Protection"))
        self.assertEqual(recovered["manual_entry_context"]["state"], "TRACKING_ONLY_NO_POSITION")

    def test_contract_rollover_resets_entry_context(self):
        session = DashboardPresentationSession()
        old = session.process(combined("C1"), scalp_ui(contract="C1", tier="IDEAL_25_35", entry_c=31.0))
        self.assertEqual(old["manual_entry_context"]["state"], "ACCEPTABLE_ENTRY_PATH")

        new = session.process(
            combined("C2", 899.0),
            scalp_ui(contract="C2", tier="CAUTION_ABOVE_50", entry_c=68.0),
        )
        self.assertEqual(new["contract"], "C2")
        self.assertEqual(new["manual_entry_context"]["state"], "TRACKING_ONLY_NO_POSITION")
        self.assertIn("TRACKING ONLY", new["cards"]["SCALP_OPPORTUNITY"]["action"])
        self.assertTrue(new["session_reducer"]["contract_rollover"])

    def test_out_of_order_scalp_regression_is_quarantined_but_timer_and_final_keep_advancing(self):
        session = DashboardPresentationSession()
        session.process(combined(seconds=600.0), scalp_ui())
        protect = session.process(
            combined(seconds=540.0),
            scalp_ui(lifecycle="PROTECT", bid_c=40.0, gain_c=9.0, peak_c=10.0, giveback_c=1.0),
        )
        self.assertEqual(protect["cards"]["SCALP_OPPORTUNITY"]["action"], "PROTECT PROFITS")

        regressed = session.process(
            combined(seconds=500.0, final_state="LOCK", final_side="UP", final_fair=.94),
            scalp_ui(lifecycle="ACTIVE", bid_c=39.0, gain_c=8.0, peak_c=10.0, giveback_c=2.0),
        )
        self.assertEqual(regressed["cards"]["SCALP_OPPORTUNITY"]["action"], "PROTECT PROFITS")
        self.assertEqual(regressed["cards"]["CONTRACT_TIME_LEFT"]["primary"], "8:20")
        self.assertEqual(regressed["cards"]["FINAL_OUTCOME"]["action"], "LOCK · UP")
        self.assertTrue(regressed["session_reducer"]["scalp_frame_quarantined"])
        self.assertTrue(regressed["presentation_session"]["current_scalp_quarantined"])
        self.assertTrue(regressed["presentation_session"]["healthy_context_preserved"])
        self.assertFalse(session.last_healthy["session_reducer"].get("scalp_frame_quarantined", False))

    def test_fail_closed_wait_is_immediate_even_after_protect(self):
        session = DashboardPresentationSession()
        session.process(combined(), scalp_ui())
        session.process(
            combined(seconds=560.0),
            scalp_ui(lifecycle="PROTECT", bid_c=40.0, gain_c=9.0, peak_c=10.0, giveback_c=1.0),
        )
        stale = session.process(
            combined(seconds=550.0),
            scalp_ui(
                lifecycle="PROTECT",
                app_ready=False,
                source_fresh=False,
                block_reason="SCALP SOURCE STALE",
                tier="UNAVAILABLE",
                entry_c=None,
            ),
        )
        self.assertTrue(stale["cards"]["SCALP_OPPORTUNITY"]["action"].startswith("WAIT ·"))
        self.assertTrue(stale["presentation_session"]["current_fail_closed"])
        self.assertFalse(stale["presentation_session"]["current_scalp_quarantined"])

    def test_reset_clears_both_memories(self):
        session = DashboardPresentationSession()
        session.process(combined(), scalp_ui())
        self.assertIsNotNone(session.accepted)
        self.assertIsNotNone(session.last_healthy)
        session.reset()
        snap = session.snapshot()
        self.assertEqual(snap["processed_frames"], 0)
        self.assertIsNone(snap["accepted"])
        self.assertIsNone(snap["last_healthy"])

    def test_signal_only_safety_is_fixed(self):
        session = DashboardPresentationSession()
        out = session.process(combined(), scalp_ui())
        self.assertFalse(out["safety"]["manual_position_confirmed"])
        self.assertFalse(out["safety"]["presentation_session_signal_filtering"])
        self.assertFalse(out["safety"]["presentation_session_signal_suppression"])
        self.assertFalse(out["safety"]["presentation_session_orders"])
        self.assertFalse(out["presentation_session"]["orders"])


if __name__ == "__main__":
    unittest.main()
