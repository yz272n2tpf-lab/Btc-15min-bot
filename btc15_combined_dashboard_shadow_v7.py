#!/usr/bin/env python3
"""
Off-production V13 dashboard shadow V7 using V11 scalp clarity UI + V6 display bridge.

DISPLAY / ACCEPTANCE ONLY | SIGNAL ONLY | NO ORDERS
"""
from __future__ import annotations

import btc15_combined_dashboard_shadow_v1 as base
from BTC15_DASHBOARD_COMBINED_SCALP_UI_V11 import build_dashboard

DISPLAY_V6_URL = "https://scalp-display-bridge-v6-production.up.railway.app/combined-state"

base.build_dashboard = build_dashboard
base.COMBINED_STATE_URL = DISPLAY_V6_URL
base.ACCEPTED_COMBINED_BRIDGES.add("BTC15_COMBINED_STATE_BRIDGE_V6")

_original_status = base.build_shadow_status


def build_shadow_status(main_state, combined_state) -> dict:
    out = _original_status(main_state, combined_state)
    if combined_state.get("version") == "BTC15_COMBINED_STATE_BRIDGE_V6":
        display_safe = bool(
            combined_state.get("scalp_lifecycle_metadata_only") is True
            and combined_state.get("scalp_ended_unarmed_is_actionable_exit") is False
            and combined_state.get("scalp_armed_no_exit_reset_allowed") is False
            and combined_state.get("scalp_display_metadata_only") is True
            and combined_state.get("scalp_completed_display_actionable") is False
            and combined_state.get("scalp_last_completed_is_display_memory_only") is True
            and combined_state.get("scalp_entry_guidance_is_display_only") is True
            and combined_state.get("scalp_entry_price_filter_applied") is False
            and combined_state.get("orders") is False
            and combined_state.get("manual_execution_only") is True
            and combined_state.get("order_action") is None
        )
        out["display_v6_safe"] = display_safe
        out["serial_lifecycle_safe"] = bool(out.get("serial_lifecycle_safe") and display_safe)
        out["safety_envelope"] = bool(out.get("safety_envelope") and display_safe)
        out["completed_display_actionable"] = combined_state.get("scalp_completed_display_actionable")
        out["entry_guidance_display_only"] = combined_state.get("scalp_entry_guidance_is_display_only")
        out["entry_price_filter_applied"] = combined_state.get("scalp_entry_price_filter_applied")
        out["last_completed_opportunity_index"] = combined_state.get("scalp_last_completed_opportunity_index")
        out["last_completed_side"] = combined_state.get("scalp_last_completed_side")
        out["hold_completed_while_scanning"] = combined_state.get("scalp_hold_completed_while_scanning")
        out["all_safety_checks_pass"] = bool(
            out.get("contract_match")
            and out.get("safety_envelope")
            and out.get("actionable_scalp_guarded")
        )
    return out


base.build_shadow_status = build_shadow_status


def main():
    print(
        "BTC15 COMBINED DASHBOARD SHADOW V7 | UI V11 + DISPLAY BRIDGE V6 | "
        "COMPLETED SCALP PERSISTENCE | ENTRY GUIDANCE DISPLAY-ONLY | "
        "SINGLE VISIBLE CONTRACT TIMER | NO ORDERS",
        flush=True,
    )
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
