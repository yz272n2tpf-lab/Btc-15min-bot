#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

from scalp_integration_state_bridge_v4 import (
    SOURCE_FRESH_MAX_AGE_SECONDS,
    build_state,
)

NOW = datetime(2026, 9, 14, 15, 0, 0, tzinfo=timezone.utc)


def row(kind, seconds_ago=2, **kw):
    ts = (NOW.timestamp() - seconds_ago)
    d = datetime.fromtimestamp(ts, tz=timezone.utc)
    out = {
        "record_type": kind,
        "timestamp_utc": d.isoformat().replace("+00:00", "Z"),
        "contract": "KXBTC15M-TEST",
    }
    out.update(kw)
    return out


class ScalpIntegrationStateBridgeV4Tests(unittest.TestCase):
    def test_fresh_pass_is_integration_ready_but_not_actionable(self):
        x = build_state([
            row("SNAPSHOT", seconds_left=700),
        ], now=NOW)
        self.assertTrue(x["source_fresh"])
        self.assertTrue(x["integration_ready"])
        self.assertFalse(x["actionable_for_integration"])
        self.assertEqual(x["state"], "PASS")

    def test_fresh_qualified_scalp_can_compose(self):
        x = build_state([
            row("SNAPSHOT", seconds_left=700),
            row(
                "CANDIDATE", 1,
                candidate_id="C1", side="UP", seconds_left=680,
                entry_ask=.40, btc30=22.0,
            ),
        ], now=NOW)
        self.assertTrue(x["source_fresh"])
        self.assertTrue(x["integration_ready"])
        self.assertTrue(x["actionable_for_integration"])
        self.assertEqual(x["state"], "ACTIVE")

    def test_stale_source_fails_closed_without_rewriting_raw_state(self):
        x = build_state([
            row("SNAPSHOT", 30, seconds_left=700),
            row(
                "CANDIDATE", 30,
                candidate_id="C1", side="UP", seconds_left=680,
                entry_ask=.40, btc30=22.0,
            ),
        ], now=NOW)
        self.assertEqual(x["state"], "ACTIVE")
        self.assertFalse(x["source_fresh"])
        self.assertFalse(x["integration_ready"])
        self.assertFalse(x["actionable_for_integration"])
        self.assertEqual(x["integration_block_reason"], "SCALP SOURCE STALE")

    def test_no_timestamp_fails_closed(self):
        x = build_state([], now=NOW)
        self.assertFalse(x["source_fresh"])
        self.assertFalse(x["integration_ready"])
        self.assertFalse(x["actionable_for_integration"])

    def test_future_clock_skew_clamps_age_to_zero(self):
        x = build_state([
            row("SNAPSHOT", -2, seconds_left=700),
        ], now=NOW)
        self.assertEqual(x["source_event_age_sec"], 0.0)
        self.assertTrue(x["source_fresh"])

    def test_safety_envelope_is_preserved(self):
        x = build_state([
            row("SNAPSHOT", seconds_left=700),
        ], now=NOW)
        self.assertEqual(x["version"], "GENERALIZED_SCALP_INTEGRATION_V4")
        self.assertTrue(x["manual_execution_only"])
        self.assertIsNone(x["order_action"])
        self.assertFalse(x["owns_final_outcome"])
        self.assertFalse(x["owns_early_opportunity"])
        self.assertFalse(x["numeric_flip_risk_validated"])
        self.assertEqual(x["canonical_contract_authority"], "MAIN_DASHBOARD")
        self.assertEqual(x["canonical_clock_authority"], "MAIN_DASHBOARD")
        self.assertEqual(x["source_fresh_max_age_sec"], SOURCE_FRESH_MAX_AGE_SECONDS)


if __name__ == "__main__":
    unittest.main()
