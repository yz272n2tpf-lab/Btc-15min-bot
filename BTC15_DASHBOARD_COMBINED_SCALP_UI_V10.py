#!/usr/bin/env python3
"""
BTC15 combined generalized SCALP dashboard UI V10.

SHADOW DISPLAY / SAFETY COMPAT ONLY | SIGNAL ONLY | NO ORDERS

V10 extends the clean V9 panel for combined bridge V5 serial lifecycle metadata.
It does not make ENDED_UNARMED a signal state. Current actionability remains only
PASS / ACTIVE / PROTECT / EXIT. ENDED_UNARMED is displayed only as prior
lifecycle context, explicitly labeled reset-only / non-actionable.

Browser-side V5 acceptance is fail-closed unless:
- scalp_lifecycle_metadata_only === true
- scalp_ended_unarmed_is_actionable_exit === false
- scalp_armed_no_exit_reset_allowed === false

No qualification, +5c arm, 4c giveback, price, EARLY, FINAL, timer, or order
behavior changes.
"""
from pathlib import Path
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V9 as v9

MARKER = "BTC15_COMBINED_SCALP_UI_V10_SERIAL_LIFECYCLE"

OLD_VALID = "const valid=d=>d&&['BTC15_COMBINED_STATE_BRIDGE_V3','BTC15_COMBINED_STATE_BRIDGE_V4'].includes(d.version)&&d.manual_execution_only===true&&d.orders===false&&d.order_action===null&&d.numeric_flip_risk_validated===false&&d.contract;"
NEW_VALID = "const valid=d=>d&&['BTC15_COMBINED_STATE_BRIDGE_V3','BTC15_COMBINED_STATE_BRIDGE_V4','BTC15_COMBINED_STATE_BRIDGE_V5'].includes(d.version)&&d.manual_execution_only===true&&d.orders===false&&d.order_action===null&&d.numeric_flip_risk_validated===false&&d.contract&&(d.version!=='BTC15_COMBINED_STATE_BRIDGE_V5'||(d.scalp_lifecycle_metadata_only===true&&d.scalp_ended_unarmed_is_actionable_exit===false&&d.scalp_armed_no_exit_reset_allowed===false));"

OLD_USABLE = "const usable=fresh&&same&&env;"
NEW_USABLE = "const usable=fresh&&same&&env; const opp=usable?Math.max(1,Number(d?.scalp_opportunity_index||1)):1; const lastTerminal=usable?String(d?.scalp_last_terminal_state||'').toUpperCase():''; const scanNext=!!(usable&&d?.scalp_scanning_for_next===true); const lifeNote=lastTerminal==='ENDED_UNARMED'?'Prior scalp ended unarmed · lifecycle reset only':lastTerminal==='EXIT'?'Prior scalp completed protected EXIT':scanNext?'Scanning for next qualified scalp':'';"

OLD_SIDE = "const sideText=shown==='PASS'?'SCALP / REVERSAL':`${side==='DOWN'?'↓':'↑'} ${side}`;"
NEW_SIDE = "const sideText=shown==='PASS'?'SCALP / REVERSAL':`${side==='DOWN'?'↓':'↑'} ${side} · #${opp}`;"

OLD_REASON = "const reason=usable?(d.scalp_block_reason||ctx(d)):(!fresh?'Generalized scalp feed is stale/unavailable':!env?'Invalid scalp safety envelope':!domSame?'Main/scalp contract IDs do not match':!aligned?'Scalp backend contract alignment pending':!srcFresh?'Scalp source is stale':!ready?'Scalp integration not ready':'No qualified generalized scalp');"
NEW_REASON = "const reasonBase=usable?(d.scalp_block_reason||ctx(d)):(!fresh?'Generalized scalp feed is stale/unavailable':!env?'Invalid scalp safety envelope':!domSame?'Main/scalp contract IDs do not match':!aligned?'Scalp backend contract alignment pending':!srcFresh?'Scalp source is stale':!ready?'Scalp integration not ready':'No qualified generalized scalp'); const reason=usable&&lifeNote?`${reasonBase} · ${lifeNote}`:reasonBase;"

GRID_ANCHOR = "      <div class=\"csc-row\"><span>Protection rule</span><strong>Arm +5¢ · EXIT at 4¢ giveback</strong></div>"
GRID_WITH_LIFECYCLE = "      <div class=\"csc-row\"><span>Lifecycle</span><strong>${usable?(lastTerminal==='ENDED_UNARMED'?'Prior ended unarmed · reset only':lastTerminal==='EXIT'?'Prior protected EXIT':scanNext?'Scanning next qualified scalp':`Opportunity #${opp}`):'FAIL-CLOSED'}</strong></div>\n" + GRID_ANCHOR


def patch_v10(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    changes = []
    for old, new, label in (
        (OLD_VALID, NEW_VALID, "accept-v5-with-lifecycle-safety"),
        (OLD_USABLE, NEW_USABLE, "derive-serial-lifecycle-context"),
        (OLD_SIDE, NEW_SIDE, "show-current-opportunity-index"),
        (OLD_REASON, NEW_REASON, "show-prior-lifecycle-context"),
        (GRID_ANCHOR, GRID_WITH_LIFECYCLE, "add-lifecycle-row"),
    ):
        if old in text:
            text = text.replace(old, new, 1)
            changes.append(label)
        elif new not in text:
            raise RuntimeError(f"{label} anchor not found; refusing unsafe patch")

    if MARKER not in text:
        text = text.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1) if "</body>" in text else text + f"\n<!-- {MARKER} -->\n"
    path.write_text(text, encoding="utf-8")
    return changes or ["v10-already-present"]


def build_dashboard() -> Path:
    html = v9.build_dashboard()
    patch_v10(html)
    return html


def main() -> int:
    html = build_dashboard()
    rendered = html.read_text(encoding="utf-8", errors="replace")
    print("COMBINED SCALP UI V10 | SERIAL LIFECYCLE CONTEXT | SHADOW ONLY | NO ORDERS")
    if "--self-test" in sys.argv:
        assert NEW_VALID in rendered and OLD_VALID not in rendered
        assert NEW_USABLE in rendered and OLD_USABLE not in rendered
        assert NEW_SIDE in rendered and OLD_SIDE not in rendered
        assert NEW_REASON in rendered and OLD_REASON not in rendered
        assert GRID_WITH_LIFECYCLE in rendered
        assert "BTC15_COMBINED_STATE_BRIDGE_V5" in rendered
        assert "scalp_lifecycle_metadata_only===true" in rendered
        assert "scalp_ended_unarmed_is_actionable_exit===false" in rendered
        assert "scalp_armed_no_exit_reset_allowed===false" in rendered
        assert "Prior scalp ended unarmed · lifecycle reset only" in rendered
        assert "Prior ended unarmed · reset only" in rendered
        assert "lastTerminal==='ENDED_UNARMED'" in rendered
        assert "const shown=usable?state:'PASS';" in rendered
        assert "Opportunity #${opp}" in rendered
        assert "Arm +5¢ · EXIT at 4¢ giveback" in rendered
        assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in rendered
        assert '<span>Contract time left</span>' not in rendered
        assert "canonical_seconds_left" in rendered
        assert "flip_risk_percent" not in rendered
        assert MARKER in rendered
        print("COMBINED SCALP UI V10 SELFTEST PASS | V5 LIFECYCLE METADATA ONLY | NO ORDERS")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
