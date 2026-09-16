#!/usr/bin/env python3
import unittest
from unittest.mock import patch

import btc15_scalp_ui_state_shadow_v1 as shadow


def combined():
    return {
        "contract": "KXBTC15M-T",
        "canonical_seconds_left": 500.0,
        "headline": "SCALP_ACTIVE",
        "early": {"state": "PASS", "side": None},
        "final": {"state": "WATCH", "side": None},
        "context_labels": [],
        "scalp": {
            "state": "ACTIVE",
            "side": "UP",
            "entry_ask": .42,
            "current_bid": .45,
            "peak_exec_gain": .03,
            "exec_gain": .03,
            "seconds_left": 499.0,
        },
        "scalp_contract_aligned": True,
        "scalp_source_fresh": True,
        "scalp_source_age_sec": 1.0,
        "scalp_integration_ready": True,
        "scalp_block_reason": None,
        "scalp_timer_delta_sec": 1.0,
        "scalp_management_message": "SCALP ACTIVE · BUILDING",
        "scalp_opportunity_index": 1,
        "scalp_serial_opportunities_completed": 0,
        "scalp_scanning_for_next": False,
    }


def direct():
    return {
        "contract": "KXBTC15M-T",
        "state": "ACTIVE",
        "side": "UP",
        "entry_price": .42,
        "current_bid": .45,
        "exec_gain": .03,
        "peak_exec_gain": .03,
        "opportunity_index": 1,
        "serial_opportunities_completed": 0,
        "scanning_for_next": False,
        "armed": False,
        "pullback_detected": False,
        "exit_triggered": False,
    }


class ScalpUIStateShadowV1Tests(unittest.TestCase):
    def test_build_shadow_state_is_read_only_and_hides_uncertified_fields(self):
        out = shadow.build_shadow_state(combined(), direct())
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "READY")
        self.assertEqual(out["source"]["transport"], "GET_ONLY")
        self.assertFalse(out["orders"])
        self.assertIsNone(out["order_action"])
        self.assertFalse(out["production_logic_changed"])
        self.assertFalse(out["signal_thresholds_changed"])
        self.assertFalse(out["watch_warning_certified"])
        self.assertFalse(out["numeric_flip_risk_visible"])
        self.assertFalse(out["ui"]["watch_warning"]["visible"])
        self.assertFalse(out["ui"]["numeric_flip_risk"]["visible"])

    def test_fetch_source_states_uses_only_two_get_sources(self):
        seen = []

        def fake_get(url):
            seen.append(url)
            return {"url": url}

        with patch.object(shadow, "_get_json", side_effect=fake_get):
            a, b = shadow.fetch_source_states()
        self.assertEqual(seen, [shadow.COMBINED_URL, shadow.SCALP_URL])
        self.assertEqual(a["url"], shadow.COMBINED_URL)
        self.assertEqual(b["url"], shadow.SCALP_URL)

    def test_fail_closed_state_is_wait_and_safe(self):
        out = shadow.fail_closed(RuntimeError("boom"))
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "FAIL_CLOSED_SOURCE_UNAVAILABLE")
        self.assertEqual(out["ui"]["display_state"], "WAIT")
        self.assertTrue(out["ui"]["source"]["fail_closed"])
        self.assertFalse(out["orders"])
        self.assertIsNone(out["order_action"])
        self.assertFalse(out["ui"]["watch_warning"]["visible"])
        self.assertFalse(out["ui"]["numeric_flip_risk"]["visible"])

    def test_http_handler_has_no_post_action(self):
        self.assertFalse(hasattr(shadow.Handler, "do_POST"))


if __name__ == "__main__":
    unittest.main()
