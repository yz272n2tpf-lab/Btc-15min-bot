#!/usr/bin/env python3
import copy
import unittest

import btc15_dashboard_visual_stability_guard_v1 as guard
import btc15_mobile_dashboard_view_model_v1 as vm


def combined(*, up_ask=.44, seconds_left=600.0, final_state="WATCH", final_side=None, final_fair=None):
    return {
        "contract": "KXBTC15M-T",
        "canonical_seconds_left": seconds_left,
        "up_ask": up_ask,
        "down_ask": 1.0 - up_ask,
        "early": {"state": "PASS", "side": None, "ask": None, "fair": None, "edge": None},
        "final": {"state": final_state, "side": final_side, "fair": final_fair},
    }


def ui(*, lifecycle="ACTIVE", tier="GOOD_36_50", ask_c=44, bid_c=47,
       gain_c=3, peak_c=3, giveback_c=0, opp=1, completed=0, scanning=False):
    return {
        "contract": "KXBTC15M-T",
        "display_state": lifecycle,
        "lifecycle_state": lifecycle,
        "side": "UP",
        "opportunity_index": opp,
        "serial_opportunities_completed": completed,
        "scanning_for_next": scanning,
        "entry_guidance": {"tier": tier},
        "entry_ask_c": ask_c,
        "current_bid_c": bid_c,
        "exec_gain_c": gain_c,
        "peak_exec_gain_c": peak_c,
        "giveback_from_peak_c": giveback_c,
        "source": {"app_ready": True, "source_fresh": True, "integration_ready": True, "block_reason": None},
    }


def model(c=None, s=None):
    return vm.build_mobile_dashboard_view_model(c or combined(), s or ui())


class DashboardVisualStabilityGuardV1Tests(unittest.TestCase):
    def test_raw_price_tick_does_not_trigger_emphasis_animation(self):
        a = model(s=ui(bid_c=47, gain_c=3, peak_c=3))
        b = model(s=ui(bid_c=48, gain_c=4, peak_c=4))
        d = guard.decide_visual_update(a, b)
        self.assertFalse(d.semantic_changed)
        self.assertTrue(d.value_only_update)
        self.assertFalse(d.animate_emphasis)
        self.assertEqual(d.reason, "VALUE_TICK_NO_SEMANTIC_CHANGE")

    def test_timer_tick_does_not_trigger_animation(self):
        a = model(c=combined(seconds_left=600))
        b = model(c=combined(seconds_left=599))
        d = guard.decide_visual_update(a, b)
        self.assertTrue(d.value_only_update)
        self.assertFalse(d.animate_emphasis)

    def test_active_to_protect_is_semantic_change(self):
        a = model(s=ui(lifecycle="ACTIVE", tier="GOOD_36_50"))
        b = model(s=ui(lifecycle="PROTECT", tier="GOOD_36_50", gain_c=8, peak_c=10, giveback_c=2))
        d = guard.decide_visual_update(a, b)
        self.assertTrue(d.semantic_changed)
        self.assertTrue(d.animate_emphasis)

    def test_good_to_dont_chase_is_semantic_change(self):
        a = model(s=ui(lifecycle="ACTIVE", tier="GOOD_36_50", ask_c=49))
        b = model(s=ui(lifecycle="ACTIVE", tier="CAUTION_ABOVE_50", ask_c=51))
        d = guard.decide_visual_update(a, b)
        self.assertTrue(d.semantic_changed)
        self.assertTrue(d.animate_emphasis)
        self.assertTrue(b["cards"]["SCALP_OPPORTUNITY"]["tracking_only"])

    def test_final_kalshi_tick_inside_same_entry_tier_is_value_only(self):
        a = model(c=combined(up_ask=.82, final_state="LOCK", final_side="UP", final_fair=.94))
        b = model(c=combined(up_ask=.83, final_state="LOCK", final_side="UP", final_fair=.94))
        d = guard.decide_visual_update(a, b)
        self.assertFalse(d.semantic_changed)
        self.assertTrue(d.value_only_update)
        self.assertFalse(d.animate_emphasis)

    def test_reason_text_change_does_not_change_semantic_signature(self):
        a = model()
        b = copy.deepcopy(a)
        b["cards"]["FINAL_OUTCOME"]["rows"][-1]["value"] = "A different explanation that should stay in the same slot."
        d = guard.decide_visual_update(a, b)
        self.assertFalse(d.semantic_changed)
        self.assertTrue(d.value_only_update)
        self.assertFalse(d.animate_emphasis)

    def test_geometry_guard_rejects_missing_row(self):
        x = model()
        x["cards"]["SCALP_OPPORTUNITY"]["rows"].pop()
        ok, reason = guard.validate_geometry(x)
        self.assertFalse(ok)
        self.assertEqual(reason, "ROW_COUNT_DRIFT:SCALP_OPPORTUNITY")

    def test_geometry_guard_rejects_second_timer(self):
        x = model()
        x["cards"]["CONTRACT_TIME_LEFT"]["visible_timer_count"] = 2
        ok, reason = guard.validate_geometry(x)
        self.assertFalse(ok)
        self.assertEqual(reason, "CANONICAL_TIMER_DRIFT")

    def test_geometry_guard_rejects_card_reorder(self):
        x = model()
        x["card_order"] = list(reversed(x["card_order"]))
        ok, reason = guard.validate_geometry(x)
        self.assertFalse(ok)
        self.assertEqual(reason, "CARD_ORDER_DRIFT")

    def test_initial_render_is_not_animated(self):
        d = guard.decide_visual_update(None, model())
        self.assertTrue(d.semantic_changed)
        self.assertFalse(d.animate_emphasis)
        self.assertEqual(d.reason, "INITIAL_RENDER")

    def test_no_order_capability(self):
        d = guard.decide_visual_update(None, model())
        self.assertTrue(d.manual_execution_only)
        self.assertFalse(d.orders)


if __name__ == "__main__":
    unittest.main()
