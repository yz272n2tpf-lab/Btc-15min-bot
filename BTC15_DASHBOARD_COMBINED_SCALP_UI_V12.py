#!/usr/bin/env python3
"""
BTC15 combined generalized SCALP dashboard UI V12.

SHADOW DISPLAY CLARITY ONLY | SIGNAL ONLY | NO ORDERS

V12 fixes the user-facing contradiction observed live when an official scalp is
qualified above the user's preferred entry range. The frozen V5 backend may
correctly move ACTIVE -> PROTECT -> EXIT for measurement, but if V6 labels the
entry TOO_EXPENSIVE / DON'T CHASE, the dashboard must not imply the user owns a
position or has profits to protect.

For those expensive-entry paths only, V12 changes presentation to TRACKING /
NO ENTRY while preserving the underlying backend scalp state unchanged.
Qualification, serial lifecycle, +5c arm, 4c giveback, EARLY, FINAL, timer,
entry filtering, and order behavior are unchanged.
"""
from pathlib import Path
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V11 as v11

MARKER = "BTC15_COMBINED_SCALP_UI_V12_NO_POSITION_TRACKING"

OLD_KLASS = "const klass=shown==='EXIT'?'exit':shown==='PROTECT'?'protect':shown==='ACTIVE'?'active':'';"
NEW_KLASS = "const noEntryTracking=!!(usable&&!completedHold&&currentGuideZone==='TOO_EXPENSIVE'&&['ACTIVE','PROTECT','EXIT'].includes(shown)); const klass=noEntryTracking?'':shown==='EXIT'?'exit':shown==='PROTECT'?'protect':shown==='ACTIVE'?'active':'';"

OLD_PILL = '<div class="csc-head"><div class="csc-title">◉ SCALP / REVERSAL</div><div class="csc-pill ${klass}">${shown===\'PASS\'?\'WATCHING\':shown}</div></div>'
NEW_PILL = '<div class="csc-head"><div class="csc-title">◉ SCALP / REVERSAL</div><div class="csc-pill ${klass}">${noEntryTracking?\'TRACKING\':shown===\'PASS\'?\'WATCHING\':shown}</div></div>'

OLD_MAIN = v11.NEW_MAIN
NEW_MAIN = "const guardText=!fresh?'WAIT · FEED STALE':!env?'WAIT · INVALID ENVELOPE':!domSame?'WAIT · CONTRACT SYNC':!aligned?'WAIT · SCALP ALIGNMENT':!srcFresh?'WAIT · SCALP SOURCE STALE':!ready?'WAIT · SCALP INTEGRATION':'WAITING FOR QUALIFIED SCALP'; const mainText=completedHold?(lastDoneState==='EXIT'?`#${lastDoneIdx} COMPLETED · PROTECTED EXIT · SCANNING #${opp}`:`#${lastDoneIdx} ENDED UNARMED · SCANNING #${opp}`):shown==='PASS'?guardText:(noEntryTracking?\"MOVE VALID · NO ENTRY · DON'T CHASE\":shown==='EXIT'?'EXIT / PROTECT PROFITS NOW':shown==='PROTECT'?'PROTECT PROFITS':'SCALP ACTIVE · BUILDING');"

OLD_PROTECT_ROW = v11.v10.GRID_ANCHOR
NEW_PROTECT_ROW = "      <div class=\"csc-row\"><span>Protection</span><strong>${noEntryTracking?'MODEL TRACKING ONLY · no manual position assumed':'Arm +5¢ · EXIT at 4¢ giveback'}</strong></div>"


def patch_v12(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    changes = []
    for old, new, label in (
        (OLD_KLASS, NEW_KLASS, "derive-no-entry-tracking-state"),
        (OLD_PILL, NEW_PILL, "replace-protect-pill-with-tracking-when-no-entry"),
        (OLD_MAIN, NEW_MAIN, "suppress-user-protect-instruction-when-no-entry"),
        (OLD_PROTECT_ROW, NEW_PROTECT_ROW, "label-model-protection-as-non-position-tracking"),
    ):
        if old in text:
            text = text.replace(old, new, 1)
            changes.append(label)
        elif new not in text:
            raise RuntimeError(f"{label} anchor not found; refusing unsafe patch")

    if MARKER not in text:
        text = text.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1) if "</body>" in text else text + f"\n<!-- {MARKER} -->\n"
    path.write_text(text, encoding="utf-8")
    return changes or ["v12-already-present"]


def build_dashboard() -> Path:
    html = v11.build_dashboard()
    patch_v12(html)
    return html


def main() -> int:
    html = build_dashboard()
    rendered = html.read_text(encoding="utf-8", errors="replace")
    print("COMBINED SCALP UI V12 | EXPENSIVE ENTRY = TRACKING / NO POSITION | SHADOW ONLY | NO ORDERS")
    if "--self-test" in sys.argv:
        assert NEW_KLASS in rendered and OLD_KLASS not in rendered
        assert NEW_PILL in rendered and OLD_PILL not in rendered
        assert NEW_MAIN in rendered and OLD_MAIN not in rendered
        assert NEW_PROTECT_ROW in rendered
        assert "currentGuideZone==='TOO_EXPENSIVE'" in rendered
        assert "['ACTIVE','PROTECT','EXIT'].includes(shown)" in rendered
        assert "MOVE VALID · NO ENTRY · DON'T CHASE" in rendered
        assert "MODEL TRACKING ONLY · no manual position assumed" in rendered
        assert "Arm +5¢ · EXIT at 4¢ giveback" in rendered
        assert "BTC15_COMBINED_STATE_BRIDGE_V6" in rendered
        assert "scalp_entry_price_filter_applied===false" in rendered
        assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in rendered
        assert "flip_risk_percent" not in rendered
        assert v11.MARKER in rendered
        assert MARKER in rendered
        print("COMBINED SCALP UI V12 SELFTEST PASS | BACKEND PROTECT PRESERVED · USER NO-POSITION WORDING | NO ORDERS")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# deployment trigger: user-facing no-position tracking semantics
