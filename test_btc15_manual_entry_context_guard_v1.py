#!/usr/bin/env python3
import copy
import unittest

import btc15_manual_entry_context_guard_v1 as g


def card(*, lifecycle="ACTIVE", opp=1, manual=False, tracking=False, action=None, entry="—"):
    if action is None:
        action = "UP #1 · ENTRY AVAILABLE" if manual else "UP #1 · TRACKING ONLY"
    return {
        "id": "SCALP_OPPORTUNITY",
        "action": action,
        "primary": "HOLD · MOVE STILL BUILDING" if manual else "MOVE VALID · NO ENTRY · DON'T CHASE",
        "tone": "positive" if manual else "caution",
        "rows": [
            {"label": "Entry Price", "value": entry, "visible": True},
            {"label": "Profit Protection", "value": "PROTECTION NOT ARMED" if manual else "MODEL TRACKING ONLY · NO POSITION ASSUMED", "visible": True},
        ],
        "tracking_only": tracking,
        "manual_entry_path_available": manual,
        "underlying_lifecycle_state": lifecycle,
        "opportunity_index": opp,
        "serial_opportunities_completed": 0,
        "scanning_for_next": False,
    }


def model(contract="C1", scalp=None, context=None):
    out = {
        "contract": contract,
        "cards": {"SCALP_OPPORTUNITY": scalp or card()},
        "safety": {"orders": False},
    }
    if context is not None:
        out["manual_entry_context"] = context
    return out


def row_value(c, label):
    return next(r["value"] for r in c["rows"] if r["label"] == label)


class ManualEntryContextGuardV1Tests(unittest.TestCase):
    def test_initial_good_entry_becomes_acceptable_context(self):
        cur = model(scalp=card(manual=True, tracking=False, entry="44¢"))
        x = g.resolve_manual_entry_context(None, cur)
        self.assertEqual(x.state, g.ACCEPTABLE)
        self.assertEqual(x.contract, "C1")
        self.assertEqual(x.opportunity_index, 1)
        self.assertEqual(x.origin_entry_price_text, "44¢")
        self.assertTrue(x.sticky)
        self.assertFalse(x.manual_position_confirmed)

    def test_initial_tracking_only_becomes_sticky_no_position_context(self):
        cur = model(scalp=card(manual=False, tracking=True, entry="68¢"))
        x = g.resolve_manual_entry_context(None, cur)
        self.assertEqual(x.state, g.TRACKING)
        self.assertEqual(x.origin_tier, "ABOVE_50_OR_NONENTRY")
        self.assertTrue(x.sticky)
        self.assertFalse(x.manual_position_confirmed)

    def test_tracking_only_cannot_retroactively_become_entry_path_same_opportunity(self):
        prev = model(scalp=card(manual=False, tracking=True, entry="68¢"))
        prev_ctx = g.resolve_manual_entry_context(None, prev).to_dict()
        prev["manual_entry_context"] = prev_ctx
        cur = model(scalp=card(manual=True, tracking=False, entry="44¢"))
        x = g.resolve_manual_entry_context(prev, cur)
        self.assertEqual(x.state, g.TRACKING)
        self.assertEqual(x.source, "STICKY_TRACKING_CONTEXT")
        adjusted = g.apply_manual_entry_context_to_scalp_card(cur["cards"]["SCALP_OPPORTUNITY"], x)
        self.assertTrue(adjusted["tracking_only"])
        self.assertFalse(adjusted["manual_entry_path_available"])
        self.assertIn("TRACKING ONLY", adjusted["action"])
        self.assertIn("DON'T CHASE", adjusted["primary"])
        self.assertEqual(row_value(adjusted, "Profit Protection"), "MODEL TRACKING ONLY · NO POSITION ASSUMED")

    def test_acceptable_context_survives_later_missing_entry_field(self):
        prev = model(scalp=card(manual=True, tracking=False, entry="31¢"))
        prev_ctx = g.resolve_manual_entry_context(None, prev).to_dict()
        prev["manual_entry_context"] = prev_ctx
        cur_card = card(lifecycle="PROTECT", manual=False, tracking=True, action="UP #1 · TRACKING ONLY", entry="—")
        cur = model(scalp=cur_card)
        x = g.resolve_manual_entry_context(prev, cur)
        self.assertEqual(x.state, g.ACCEPTABLE)
        self.assertEqual(x.origin_entry_price_text, "31¢")
        adjusted = g.apply_manual_entry_context_to_scalp_card(cur_card, x)
        self.assertFalse(adjusted["tracking_only"])
        self.assertTrue(adjusted["manual_entry_path_available"])
        self.assertEqual(adjusted["action"], "PROTECT PROFITS")
        self.assertEqual(adjusted["primary"], "MOVE REACHED PROTECTION LEVEL")
        self.assertEqual(row_value(adjusted, "Entry Price"), "31¢")
        self.assertEqual(row_value(adjusted, "Profit Protection"), "WATCH FOR GIVEBACK")

    def test_acceptable_context_restores_exit_wording_after_telemetry_blip(self):
        prev = model(scalp=card(manual=True, tracking=False, entry="44¢"))
        prev_ctx = g.resolve_manual_entry_context(None, prev).to_dict()
        prev["manual_entry_context"] = prev_ctx
        cur_card = card(lifecycle="EXIT", manual=False, tracking=True, action="UP #1 · TRACKING ONLY", entry="—")
        x = g.resolve_manual_entry_context(prev, model(scalp=cur_card))
        adjusted = g.apply_manual_entry_context_to_scalp_card(cur_card, x)
        self.assertEqual(adjusted["action"], "EXIT NOW · PROTECT PROFITS")
        self.assertEqual(adjusted["primary"], "VALIDATED GIVEBACK EXIT")
        self.assertEqual(row_value(adjusted, "Profit Protection"), "PROTECTED EXIT")

    def test_new_opportunity_resets_context(self):
        prev = model(scalp=card(opp=1, manual=False, tracking=True, entry="68¢"))
        prev["manual_entry_context"] = g.resolve_manual_entry_context(None, prev).to_dict()
        cur_card = card(opp=2, manual=True, tracking=False, action="UP #2 · ENTRY AVAILABLE", entry="31¢")
        cur = model(scalp=cur_card)
        x = g.resolve_manual_entry_context(prev, cur)
        self.assertEqual(x.state, g.ACCEPTABLE)
        self.assertEqual(x.opportunity_index, 2)
        self.assertEqual(x.source, "CURRENT_ACCEPTABLE_ENTRY")

    def test_contract_rollover_resets_context(self):
        prev = model("C1", scalp=card(manual=False, tracking=True, entry="68¢"))
        prev["manual_entry_context"] = g.resolve_manual_entry_context(None, prev).to_dict()
        cur = model("C2", scalp=card(manual=True, tracking=False, entry="31¢"))
        x = g.resolve_manual_entry_context(prev, cur)
        self.assertEqual(x.state, g.ACCEPTABLE)
        self.assertEqual(x.contract, "C2")
        self.assertEqual(x.source, "CURRENT_ACCEPTABLE_ENTRY")

    def test_pass_or_scanning_state_has_no_active_entry_context(self):
        cur = model(scalp=card(lifecycle="PASS", opp=None, manual=False, tracking=False, action="WATCHING FOR SCALP", entry="—"))
        x = g.resolve_manual_entry_context(None, cur)
        self.assertEqual(x.state, g.NONE)
        self.assertFalse(x.sticky)

    def test_apply_does_not_change_underlying_lifecycle(self):
        original = card(lifecycle="PROTECT", manual=False, tracking=True, entry="68¢")
        before = copy.deepcopy(original)
        ctx = g.ManualEntryContext(g.VERSION, g.TRACKING, "C1", 1, True, "ABOVE_50_OR_NONENTRY", "68¢", "TEST")
        adjusted = g.apply_manual_entry_context_to_scalp_card(original, ctx)
        self.assertEqual(original, before)
        self.assertEqual(adjusted["underlying_lifecycle_state"], "PROTECT")
        self.assertFalse(adjusted["manual_position_confirmed"])

    def test_guard_is_signal_neutral_and_orderless(self):
        x = g.resolve_manual_entry_context(None, model(scalp=card(manual=True, entry="44¢")))
        self.assertFalse(x.signal_filtering)
        self.assertFalse(x.signal_suppression)
        self.assertFalse(x.orders)
        self.assertFalse(x.manual_position_confirmed)


if __name__ == "__main__":
    unittest.main()
