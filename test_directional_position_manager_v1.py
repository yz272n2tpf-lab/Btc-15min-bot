"""Offline synthetic control/safety tests; no forward-validation sample access."""
import ast
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
import inspect
import json
import unittest

import BTC15_DIRECTIONAL_POSITION_MANAGER_V1 as manager
from BTC15_DIRECTIONAL_POSITION_MANAGER_V1 import (
    Action, DangerAssessment, DangerRule, State, update,
)
from directional_shadow_examples_v1 import (
    START, SYNTHETIC_EXIT_RULE, advance, examples, fixture,
)


class DirectionalTests(unittest.TestCase):
    def buy(self, **kwargs):
        return advance(State(), fixture(**kwargs))

    def hold(self):
        state, _ = self.buy()
        return advance(state, fixture(305, final_ready=True))

    def protect(self):
        state, _ = self.hold()
        return advance(state, fixture(310))

    def assessment(self, state, raw, **changes):
        result = DangerAssessment(state.position.position_id, state.contract_id,
                                  state.position.side,
                                  datetime.fromisoformat(raw["source_timestamp_utc"]),
                                  SYNTHETIC_EXIT_RULE.rule_id, SYNTHETIC_EXIT_RULE.validation_ref,
                                  Action.EXIT, severe=True)
        return replace(result, **changes)

    def exit(self):
        state, _ = self.protect()
        raw = fixture(315, final_side="DOWN")
        return advance(state, raw, danger=self.assessment(state, raw),
                       reviewed_rules=(SYNTHETIC_EXIT_RULE,))

    def test_01_early_creates_one_position_at_actual_side_ask(self):
        for side in ("UP", "DOWN"):
            with self.subTest(side=side):
                state, view = self.buy(side=side)
                self.assertEqual(state.position.entry_ask, .32)
                self.assertEqual(state.position.side, side)
                self.assertEqual(view["event"], "BUY")
                self.assertEqual(view["early"]["entry_ask_cents"], 32)
                self.assertEqual(view["early"]["entry_basis"], "HYPOTHETICAL_OBSERVED_ASK_NO_FILL")

    def test_02_no_duplicate_buy(self):
        state, _ = self.buy()
        entry = state.position.position_id
        for offset in range(305, 355, 5):
            state, view = advance(state, fixture(offset))
            self.assertNotEqual(view["event"], "BUY")
            self.assertEqual(state.position.position_id, entry)
            self.assertEqual(state.position.entry_ask, .32)

    def test_03_strong_final_supports_hold(self):
        state, view = self.hold()
        self.assertEqual(state.position.action, Action.HOLD)
        self.assertEqual(view["final"]["safety_light"], "STRONG CONFIRMATION")

    def test_04_deterioration_escalates_protect(self):
        state, view = self.protect()
        self.assertEqual(state.position.action, Action.PROTECT)
        self.assertEqual(view["action"]["label"], "PROTECT PROFITS")
        self.assertEqual(view["final"]["safety_light"], "PROTECT WARNING")

    def test_05_reviewed_synthetic_severe_deterioration_exits(self):
        state, view = self.exit()
        self.assertEqual(state.position.action, Action.EXIT)
        self.assertEqual(view["final"]["safety_light"], "EXIT WARNING")
        self.assertEqual(view["management_validation"], "RESEARCH / UNVALIDATED")

    def test_06_final_alone_is_never_buy_even_at_high_prices(self):
        state, view = self.buy(early_ready=False, final_ready=True, bid=.94, ask=.96)
        self.assertIsNone(state.position)
        self.assertEqual(view["state"], "NO_POSITION")
        self.assertTrue(view["final"]["visible"])
        self.assertEqual(view["final"]["protected_view"]["confidence"], .94)

    def test_07_missing_prices_and_evidence_fail_closed(self):
        initial, _ = self.hold()
        for field, key in (("market", "up_bid"), ("market", "up_ask"),
                           ("early", "fair"), ("early", "edge"), ("final", "confidence")):
            with self.subTest(field=field, key=key):
                raw = fixture(310)
                del raw[field][key]
                _, view = advance(initial, raw)
                self.assertFalse(view["level_inputs_ready"])
                self.assertIsNone(view["levels"]["protect_zone_cents"])
                self.assertIsNone(view["levels"]["exit_zone_cents"])
                self.assertFalse(view["action"]["actionable"])

    def test_08_rollover_clears_position(self):
        state, _ = self.buy()
        state, view = advance(state, fixture(905, close_offset=1800, early_ready=False))
        self.assertIsNone(state.position)
        self.assertTrue(view["rollover_cleared_position"])
        self.assertIsNone(view["early"]["entry_ask_cents"])
        self.assertEqual(view["state"], "NO_POSITION")

    def test_09_exit_is_terminal_and_never_rebuys(self):
        state, _ = self.exit()
        for offset in range(320, 380, 5):
            state, view = advance(state, fixture(offset, final_ready=True))
            self.assertEqual(state.position.action, Action.EXIT)
            self.assertIsNone(view["event"])
            self.assertEqual(view["final"]["safety_light"], "EXIT WARNING")

    def test_10_scalp_is_not_consumed_or_mutated(self):
        class ExplodesOnRead(dict):
            def get(self, *args):
                raise AssertionError("SCALP was accessed")
        raw = fixture()
        raw["scalp"] = ExplodesOnRead()
        _, view = advance(State(), raw)
        self.assertEqual(view["state"], "BUY")
        source = inspect.getsource(manager)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                self.assertFalse(node.args and isinstance(node.args[0], ast.Constant)
                                 and node.args[0].value in ("scalp", "position_protection"))

    def test_11_no_orders_io_execution_or_production_import_path(self):
        tree = ast.parse(inspect.getsource(manager))
        allowed = {"__future__", "copy", "dataclasses", "datetime", "enum", "math", "typing", "zoneinfo"}
        forbidden = {"open", "eval", "exec", "compile", "__import__", "getattr", "setattr",
                     "globals", "locals", "input", "print", "breakpoint"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(x.name in allowed for x in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, forbidden)
        for view in examples()["examples"]:
            self.assertTrue(view["signal_only"])
            self.assertTrue(view["manual_execution_only"])
            self.assertFalse(view["orders_enabled"])
            self.assertIsNone(view["order_action"])

    def test_no_numeric_levels_claimed_with_complete_inputs(self):
        _, view = self.hold()
        self.assertTrue(view["level_inputs_ready"])
        self.assertEqual(view["levels"]["reason"], "NO_VALIDATED_CENTS_MODEL")
        self.assertIsNone(view["levels"]["exit_zone_cents"])

    def test_level_context_contains_all_inputs_and_preserves_sides(self):
        state, _ = self.hold()
        raw = fixture(310, side="DOWN", bid=.38, ask=.40)
        frame = manager.read_protected_snapshot(raw, START + timedelta(seconds=310))
        context = manager.level_context(state.position, frame, manager.Light.PROTECT)
        self.assertEqual(context.side, "UP")
        self.assertEqual(context.early_side, "DOWN")
        self.assertEqual(context.final_side, "DOWN")
        self.assertEqual(context.entry_ask, .32)
        self.assertAlmostEqual(context.current_bid, .60)
        self.assertEqual(context.seconds_remaining, 590)
        self.assertEqual(context.entry_edge, .50)
        self.assertEqual(context.early_fair, .82)

    def test_entry_requires_actual_ask_not_bid_or_other_side(self):
        for bad in (.30, .70, 32, None, True, float("nan")):
            with self.subTest(bad=bad):
                raw = fixture()
                raw["early"]["ask"] = bad
                state, view = advance(State(), raw)
                self.assertIsNone(state.position)
                self.assertIsNone(view["event"])

    def test_crossed_missing_or_nonfinite_quote_cannot_enter(self):
        for bid, ask in ((.7, .3), (None, .3), (.3, None), (float("inf"), .3), (True, .3)):
            raw = fixture()
            raw["market"].update(up_bid=bid, up_ask=ask)
            self.assertIsNone(advance(State(), raw)[0].position)

    def test_unpaired_quotes_cannot_enter_or_produce_levels(self):
        raw = fixture()
        raw["health"]["paired_quotes"] = False
        self.assertIsNone(advance(State(), raw)[0].position)

    def test_no_confirmation_when_brti_stale(self):
        state, _ = self.hold()
        raw = fixture(310, final_ready=True)
        raw["health"]["brti_fresh"] = False
        state, view = advance(state, raw)
        self.assertEqual(state.position.action, Action.PROTECT)
        self.assertFalse(view["level_inputs_ready"])

    def test_missing_evidence_does_not_manufacture_exit(self):
        state, _ = self.hold()
        raw = fixture(310)
        raw["final"] = {}
        new, view = advance(state, raw)
        self.assertEqual(new.position.action, Action.HOLD)
        self.assertFalse(view["action"]["actionable"])
        self.assertEqual(view["final"]["safety_light"], "CAUTION")

    def test_recorded_final_cannot_hide_current_deterioration(self):
        state, _ = self.hold()
        raw = fixture(310, final_side="DOWN")
        raw["final"].update(recorded_final_call=True, recorded_side="UP", recorded_confidence=.99)
        state, view = advance(state, raw)
        self.assertEqual(state.position.action, Action.PROTECT)
        self.assertEqual(view["final"]["protected_view"], raw["final"])
        self.assertEqual(view["final"]["safety_light"], "PROTECT WARNING")

    def test_protect_does_not_flicker_on_recovery(self):
        state, _ = self.protect()
        for offset in range(315, 370, 5):
            state, view = advance(state, fixture(offset, final_ready=offset % 10 == 0))
            self.assertEqual(state.position.action, Action.PROTECT)
            self.assertEqual(view["final"]["safety_light"], "PROTECT WARNING")

    def test_unreviewed_or_unbound_exit_assessments_rejected(self):
        state, _ = self.hold()
        raw = fixture(310, final_ready=True)
        changes = ({"rule_id": "unknown"}, {"validation_ref": "unreviewed"},
                   {"side": "DOWN"}, {"contract_id": "OLD"}, {"position_id": "OLD"},
                   {"source_timestamp": START}, {"severe": False})
        for change in changes:
            with self.subTest(change=change):
                result, _ = advance(state, raw, danger=self.assessment(state, raw, **change),
                                    reviewed_rules=(SYNTHETIC_EXIT_RULE,))
                self.assertNotEqual(result.position.action, Action.EXIT)
        self.assertNotEqual(advance(state, raw, danger=self.assessment(state, raw))[0].position.action, Action.EXIT)

    def test_clean_forward_rule_scope_cannot_authorize_exit(self):
        state, _ = self.hold()
        raw = fixture(310, final_ready=True)
        bad_rule = replace(SYNTHETIC_EXIT_RULE, scope="CLEAN_FORWARD")
        result, _ = advance(state, raw, danger=self.assessment(state, raw), reviewed_rules=(bad_rule,))
        self.assertEqual(result.position.action, Action.HOLD)

    def test_severe_reviewed_danger_can_skip_protect(self):
        state, _ = self.buy()
        raw = fixture(305, final_ready=True)
        result, view = advance(state, raw, danger=self.assessment(state, raw), reviewed_rules=(SYNTHETIC_EXIT_RULE,))
        self.assertEqual(result.position.action, Action.EXIT)
        self.assertEqual(view["final"]["safety_light"], "EXIT WARNING")

    def test_source_replays_and_reordering_do_not_emit_or_reenable_buy(self):
        state, _ = self.buy()
        for offset in (300, 299):
            raw = fixture(offset)
            result, view = update(state, raw, now_utc=START + timedelta(seconds=301))
            self.assertEqual(result, state)
            self.assertIsNone(view["event"])
            self.assertFalse(view["action"]["actionable"])

    def test_stale_data_fail_closed(self):
        state, _ = self.hold()
        result, view = update(state, fixture(310), now_utc=START + timedelta(seconds=326))
        self.assertEqual(result, state)
        self.assertEqual(view["blocked_reason"], "STALE_SOURCE")
        self.assertFalse(view["action"]["actionable"])
        self.assertIsNone(view["early"]["current_bid_cents"])

    def test_future_and_naive_source_fail_closed(self):
        raw = fixture(310)
        result, view = update(State(), raw, now_utc=START + timedelta(seconds=309))
        self.assertIsNone(result.position)
        raw["source_timestamp_utc"] = "2026-01-01T12:05:10"
        result, view = update(State(), raw, now_utc=START + timedelta(seconds=310))
        self.assertEqual(view["blocked_reason"], "INVALID_UTC_TIMESTAMP")

    def test_rollover_new_position_has_new_entry_and_no_old_warning(self):
        state, _ = self.exit()
        state, view = advance(state, fixture(905, close_offset=1800, side="DOWN", bid=.40, ask=.42))
        self.assertEqual(view["event"], "BUY")
        self.assertEqual(state.position.entry_ask, .42)
        self.assertEqual(state.position.side, "DOWN")
        self.assertFalse(state.position.saw_strong_final)
        self.assertEqual(view["final"]["safety_light"], "CAUTION")

    def test_expiry_during_outage_clears_position(self):
        state, _ = self.buy()
        state, view = update(state, {}, now_utc=START + timedelta(seconds=900))
        self.assertIsNone(state.position)
        self.assertTrue(state.buy_emitted)
        self.assertTrue(view["rollover_cleared_position"])

    def test_old_contract_cannot_return_after_rollover_even_if_clock_regresses(self):
        state, _ = self.buy()
        state, _ = advance(state, fixture(905, close_offset=1800, early_ready=False))
        result, view = advance(state, fixture(310))
        self.assertEqual(result, state)
        self.assertEqual(view["blocked_reason"], "OLDER_CONTRACT_REJECTED")
        self.assertEqual(view["final"]["protected_view"], {})

    def test_foreign_stale_final_never_displays_under_current_position(self):
        state, _ = self.buy()
        state, _ = advance(state, fixture(905, close_offset=1800, side="DOWN"))
        _, view = update(state, fixture(310), now_utc=START + timedelta(seconds=910))
        self.assertEqual(view["early"]["side"], "DOWN")
        self.assertEqual(view["final"]["protected_view"], {})
        self.assertFalse(view["action"]["actionable"])

    def test_small_logged_clock_precision_change_does_not_fake_rollover(self):
        state, _ = self.buy()
        raw = fixture(305, final_ready=True)
        raw["timer"]["close_utc"] = (START + timedelta(seconds=899.999)).isoformat()
        state, view = advance(state, raw)
        self.assertEqual(state.position.action, Action.HOLD)
        self.assertIsNone(view["blocked_reason"])

    def test_contract_id_and_timer_mismatch_rejected(self):
        for kind in ("id", "timer", "close"):
            raw = fixture()
            if kind == "id":
                raw["contract"] = "OTHER_CONTRACT"
            elif kind == "timer":
                raw["timer"]["seconds_left"] = 42
            else:
                raw["timer"]["close_utc"] = (START + timedelta(seconds=1000)).isoformat()
            self.assertIsNone(advance(State(), raw)[0].position)

    def test_schema_flags_and_source_names_are_strict(self):
        for section, key, value in (("early", "ready", "true"), ("early", "source", "other"),
                                    ("final", "ready", 1), ("final", "source", "other"),
                                    ("safety", "orders_enabled", True), ("safety", "read_only", False)):
            raw = fixture()
            raw[section][key] = value
            self.assertIsNone(advance(State(), raw)[0].position)

    def test_final_opposition_blocks_new_entry_without_changing_model(self):
        raw = fixture(final_side="DOWN", final_ready=True)
        original = deepcopy(raw)
        state, view = advance(State(), raw)
        self.assertIsNone(state.position)
        self.assertEqual(view["blocked_reason"], "FINAL_DISAGREES_WITH_EARLY")
        self.assertEqual(raw, original)
        self.assertTrue(raw["early"]["ready"])

    def test_inputs_state_and_output_do_not_alias(self):
        raw = fixture()
        original = deepcopy(raw)
        state = State()
        new, view = advance(state, raw)
        view["final"]["protected_view"]["conditions"]["changed"] = True
        self.assertEqual(raw, original)
        self.assertEqual(state, State())
        self.assertIsNotNone(new.position)

    def test_display_has_exactly_one_action_and_no_final_cents_boxes(self):
        for view in examples()["examples"]:
            self.assertIn(view["state"], [a.value for a in Action])
            self.assertIsInstance(view["action"]["label"], str)
            self.assertNotIn("protect_zone_cents", view["final"])
            self.assertNotIn("exit_zone_cents", view["final"])
            json.dumps(view, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
