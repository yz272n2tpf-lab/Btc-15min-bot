#!/usr/bin/env python3
"""
BTC15 V14 state-transition presentation audit V1.

OFFLINE QA ONLY | PRESENTATION ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

Purpose
-------
Freeze the user-facing meaning of SCALP lifecycle transitions without changing
or reimplementing strategy qualification. The audit models only presentation
semantics already present in V12/V13/V14 and checks the generated V14 HTML for
the exact safety anchors that make those semantics true.

Critical rule
-------------
If the frozen backend has ACTIVE/PROTECT/EXIT but the displayed entry zone is
TOO_EXPENSIVE, the user-facing state must remain TRACKING / NO POSITION. A
backend lifecycle state is measurement evidence; it is not permission to imply
that the user entered a manual position.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 as v14

VERSION = "BTC15_DASHBOARD_V14_STATE_TRANSITION_AUDIT_V1"


@dataclass(frozen=True)
class ScalpView:
    pill: str
    main: str
    position_assumed: bool
    user_exit_instruction: bool
    protection_row: str


def expected_scalp_view(
    shown: str,
    *,
    guide_zone: str = "GOOD",
    usable: bool = True,
    completed_hold: bool = False,
    last_done_state: str | None = None,
    fresh: bool = True,
    envelope_ok: bool = True,
    contract_same: bool = True,
    aligned: bool = True,
    source_fresh: bool = True,
    integration_ready: bool = True,
) -> ScalpView:
    """Presentation-only reference model for already-frozen UI semantics."""
    shown = str(shown or "PASS").upper()
    guide_zone = str(guide_zone or "").upper()

    if completed_hold:
        if str(last_done_state or "").upper() == "EXIT":
            main = "COMPLETED · PROTECTED EXIT · SCANNING"
        else:
            main = "ENDED · NO PROTECTED EXIT · SCANNING"
        return ScalpView(
            pill="COMPLETED",
            main=main,
            position_assumed=False,
            user_exit_instruction=False,
            protection_row="WATCHING FOR NEXT SCALP",
        )

    if shown == "PASS":
        if not fresh:
            main = "WAIT · DATA NOT FRESH"
        elif not envelope_ok:
            main = "WAIT · CHECKING DATA"
        elif not contract_same:
            main = "WAIT · SYNCING CONTRACT"
        elif not aligned:
            main = "WAIT · SYNCING SCALP"
        elif not source_fresh:
            main = "WAIT · SCALP DATA NOT FRESH"
        elif not integration_ready:
            main = "WAIT · SCALP NOT READY"
        else:
            main = "WATCHING FOR SCALP"
        return ScalpView(
            pill="WATCHING",
            main=main,
            position_assumed=False,
            user_exit_instruction=False,
            protection_row="+5¢ ARM · EXIT AFTER 4¢ GIVEBACK",
        )

    no_entry_tracking = bool(
        usable
        and guide_zone == "TOO_EXPENSIVE"
        and shown in {"ACTIVE", "PROTECT", "EXIT"}
    )
    if no_entry_tracking:
        return ScalpView(
            pill="TRACKING",
            main="TRACKING ONLY · DON'T CHASE",
            position_assumed=False,
            user_exit_instruction=False,
            protection_row="TRACKING ONLY · NO POSITION ASSUMED",
        )

    main = {
        "ACTIVE": "HOLD · MOVE STILL BUILDING",
        "PROTECT": "PROTECT PROFITS",
        "EXIT": "EXIT NOW · PROTECT PROFITS",
    }.get(shown, shown)
    return ScalpView(
        pill=shown,
        main=main,
        position_assumed=shown in {"ACTIVE", "PROTECT", "EXIT"},
        user_exit_instruction=shown == "EXIT",
        protection_row="+5¢ ARM · EXIT AFTER 4¢ GIVEBACK",
    )


def transition_matrix() -> list[dict[str, Any]]:
    """Return the frozen QA cases; this is not a strategy or scoring table."""
    cases: list[tuple[str, ScalpView]] = [
        ("PASS_READY", expected_scalp_view("PASS")),
        ("PASS_STALE", expected_scalp_view("PASS", fresh=False)),
        ("PASS_BAD_ENVELOPE", expected_scalp_view("PASS", envelope_ok=False)),
        ("PASS_CONTRACT_SYNC", expected_scalp_view("PASS", contract_same=False)),
        ("PASS_SCALP_SYNC", expected_scalp_view("PASS", aligned=False)),
        ("PASS_SOURCE_STALE", expected_scalp_view("PASS", source_fresh=False)),
        ("PASS_NOT_READY", expected_scalp_view("PASS", integration_ready=False)),
        ("ACTIVE_AFFORDABLE", expected_scalp_view("ACTIVE")),
        ("PROTECT_AFFORDABLE", expected_scalp_view("PROTECT")),
        ("EXIT_AFFORDABLE", expected_scalp_view("EXIT")),
        ("ACTIVE_TOO_EXPENSIVE", expected_scalp_view("ACTIVE", guide_zone="TOO_EXPENSIVE")),
        ("PROTECT_TOO_EXPENSIVE", expected_scalp_view("PROTECT", guide_zone="TOO_EXPENSIVE")),
        ("EXIT_TOO_EXPENSIVE", expected_scalp_view("EXIT", guide_zone="TOO_EXPENSIVE")),
        (
            "COMPLETED_PROTECTED_EXIT",
            expected_scalp_view("PASS", completed_hold=True, last_done_state="EXIT"),
        ),
        (
            "COMPLETED_NO_PROTECTED_EXIT",
            expected_scalp_view("PASS", completed_hold=True, last_done_state="ENDED_UNARMED"),
        ),
    ]
    return [
        {
            "case": name,
            "pill": view.pill,
            "main": view.main,
            "position_assumed": view.position_assumed,
            "user_exit_instruction": view.user_exit_instruction,
            "protection_row": view.protection_row,
        }
        for name, view in cases
    ]


def audit_generated_v14() -> dict[str, Any]:
    path = v14.build_dashboard()
    text = path.read_text(encoding="utf-8", errors="replace")

    required_fragments = (
        "currentGuideZone==='TOO_EXPENSIVE'",
        "['ACTIVE','PROTECT','EXIT'].includes(shown)",
        "noEntryTracking?'TRACKING'",
        "TRACKING ONLY · DON'T CHASE",
        "TRACKING ONLY · NO POSITION ASSUMED",
        "HOLD · MOVE STILL BUILDING",
        "PROTECT PROFITS",
        "EXIT NOW · PROTECT PROFITS",
        "WATCHING FOR SCALP",
        "WAIT · DATA NOT FRESH",
        "WAIT · CHECKING DATA",
        "WAIT · SYNCING CONTRACT",
        "WAIT · SYNCING SCALP",
        "WAIT · SCALP DATA NOT FRESH",
        "WAIT · SCALP NOT READY",
        "ENDED · NO PROTECTED EXIT · SCANNING",
        "PROTECTED EXIT · SCANNING",
        "scalp_completed_display_actionable===false",
        "scalp_ended_unarmed_is_actionable_exit===false",
        "scalp_armed_no_exit_reset_allowed===false",
        "scalp_entry_price_filter_applied===false",
        "scalp_entry_guidance_is_display_only===true",
        "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS",
        "BTC15_COMBINED_SCALP_UI_V14_PRESENTATION_STABILITY",
    )
    missing = [x for x in required_fragments if x not in text]
    if missing:
        raise AssertionError(f"V14 transition safety anchors missing: {missing}")

    unique_ids = ("timerRemaining", "finalCard", "finalReason", "finalAction", "earlyFlow", "scalpCard")
    bad_ids = {x: text.count(f'id="{x}"') for x in unique_ids if text.count(f'id="{x}"') != 1}
    if bad_ids:
        raise AssertionError(f"V14 unique transition/display IDs drifted: {bad_ids}")

    if "flip_risk_percent" in text:
        raise AssertionError("numeric Flip Risk unexpectedly exposed in V14 generated HTML")

    # V14 must retain the anti-blink and stable-height protections while lifecycle
    # wording changes underneath them.
    for frag in (
        "#btcPrice.data-pulse{animation:none!important;transition:none!important;}",
        "#finalActionSub{",
        "#earlyEntry,#earlyFlow{",
        "font-variant-numeric:tabular-nums lining-nums!important",
    ):
        if frag not in text:
            raise AssertionError(f"V14 stability anchor missing during transition audit: {frag}")

    return {
        "version": VERSION,
        "matrix_cases": len(transition_matrix()),
        "generated_html_audit": "PASS",
        "single_canonical_timer": True,
        "expensive_backend_states_imply_position": False,
        "completed_unarmed_is_exit": False,
        "numeric_flip_risk_exposed": False,
        "strategy_changed": False,
        "manual_execution_only": True,
        "orders": False,
    }


def main() -> int:
    result = audit_generated_v14()
    print(
        f"{VERSION} PASS | cases={result['matrix_cases']} | "
        "EXPENSIVE ACTIVE/PROTECT/EXIT => TRACKING/NO POSITION | "
        "COMPLETED UNARMED => SCANNING/NO EXIT | ONE TIMER | NO ORDERS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
