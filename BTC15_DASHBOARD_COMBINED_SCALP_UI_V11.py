#!/usr/bin/env python3
"""
BTC15 combined generalized SCALP dashboard UI V11.

SHADOW DISPLAY CLARITY ONLY | SIGNAL ONLY | NO ORDERS

V11 fixes the fast-lifecycle usability gap observed live: an official scalp can
complete correctly in V5 and immediately disappear from the card when scanning
for the next opportunity. V11 keeps the most recent completed scalp visible as
NON-ACTIONABLE context until a new official scalp becomes active or the contract
rolls. It also separates signal validity from entry-price quality.

No qualification, lifecycle, protection, timer, EARLY, FINAL, price filter, or
order behavior changes. Entry guidance is display-only.
"""
from pathlib import Path
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V10 as v10

MARKER = "BTC15_COMBINED_SCALP_UI_V11_COMPLETED_PERSISTENCE_ENTRY_GUIDANCE"
OLD_FEED = "https://scalp-move-shadow-v1-production.up.railway.app/combined-state"
NEW_FEED = "https://scalp-display-bridge-v6-production.up.railway.app/combined-state"

OLD_VALID = v10.NEW_VALID
NEW_VALID = "const valid=d=>d&&['BTC15_COMBINED_STATE_BRIDGE_V3','BTC15_COMBINED_STATE_BRIDGE_V4','BTC15_COMBINED_STATE_BRIDGE_V5','BTC15_COMBINED_STATE_BRIDGE_V6'].includes(d.version)&&d.manual_execution_only===true&&d.orders===false&&d.order_action===null&&d.numeric_flip_risk_validated===false&&d.contract&&(d.version!=='BTC15_COMBINED_STATE_BRIDGE_V5'||(d.scalp_lifecycle_metadata_only===true&&d.scalp_ended_unarmed_is_actionable_exit===false&&d.scalp_armed_no_exit_reset_allowed===false))&&(d.version!=='BTC15_COMBINED_STATE_BRIDGE_V6'||(d.scalp_lifecycle_metadata_only===true&&d.scalp_ended_unarmed_is_actionable_exit===false&&d.scalp_armed_no_exit_reset_allowed===false&&d.scalp_display_metadata_only===true&&d.scalp_completed_display_actionable===false&&d.scalp_entry_guidance_is_display_only===true&&d.scalp_entry_price_filter_applied===false));"

OLD_USABLE = v10.NEW_USABLE
NEW_USABLE = "const usable=fresh&&same&&env; const opp=usable?Math.max(1,Number(d?.scalp_opportunity_index||1)):1; const lastTerminal=usable?String(d?.scalp_last_terminal_state||'').toUpperCase():''; const scanNext=!!(usable&&d?.scalp_scanning_for_next===true); const lastDoneSide=usable?String(d?.scalp_last_completed_side||'').toUpperCase():''; const lastDoneIdx=usable?Number(d?.scalp_last_completed_opportunity_index||0):0; const lastDoneState=usable?String(d?.scalp_last_completed_state||'').toUpperCase():''; const lastDoneEntry=usable?n(d?.scalp_last_completed_entry_price):NaN; const lastDonePeak=usable?n(d?.scalp_last_completed_peak_gain):NaN; const lastDoneExit=usable?n(d?.scalp_last_completed_exit_gain):NaN; const completedHold=!!(usable&&state==='PASS'&&d?.scalp_hold_completed_while_scanning===true&&d?.scalp_last_completed_available===true&&lastDoneIdx>0); const currentGuideZone=usable?String(d?.scalp_current_entry_guidance?.zone||''):''; const currentGuideLabel=usable?String(d?.scalp_current_entry_guidance?.label||''):''; const completedGuideLabel=usable?String(d?.scalp_completed_entry_guidance?.label||''):''; const lifeNote=completedHold?(lastDoneState==='EXIT'?`${lastDoneSide||'SCALP'} #${lastDoneIdx} completed protected EXIT · now scanning #${opp}`:`${lastDoneSide||'SCALP'} #${lastDoneIdx} ended unarmed · reset only · now scanning #${opp}`):lastTerminal==='ENDED_UNARMED'?'Prior scalp ended unarmed · lifecycle reset only':lastTerminal==='EXIT'?'Prior scalp completed protected EXIT':scanNext?'Scanning for next qualified scalp':'';"

OLD_SIDE = v10.NEW_SIDE
NEW_SIDE = "const sideText=completedHold?`✓ ${lastDoneSide||'SCALP'} · #${lastDoneIdx} COMPLETED`:shown==='PASS'?'SCALP / REVERSAL':`${side==='DOWN'?'↓':'↑'} ${side} · #${opp}`;"

OLD_MAIN = "const guardText=!fresh?'WAIT · FEED STALE':!env?'WAIT · INVALID ENVELOPE':!domSame?'WAIT · CONTRACT SYNC':!aligned?'WAIT · SCALP ALIGNMENT':!srcFresh?'WAIT · SCALP SOURCE STALE':!ready?'WAIT · SCALP INTEGRATION':'WAITING FOR QUALIFIED SCALP'; const mainText=shown==='PASS'?guardText:(shown==='EXIT'?'EXIT / PROTECT PROFITS NOW':shown==='PROTECT'?'PROTECT PROFITS':'SCALP ACTIVE · BUILDING');"
NEW_MAIN = "const guardText=!fresh?'WAIT · FEED STALE':!env?'WAIT · INVALID ENVELOPE':!domSame?'WAIT · CONTRACT SYNC':!aligned?'WAIT · SCALP ALIGNMENT':!srcFresh?'WAIT · SCALP SOURCE STALE':!ready?'WAIT · SCALP INTEGRATION':'WAITING FOR QUALIFIED SCALP'; const mainText=completedHold?(lastDoneState==='EXIT'?`#${lastDoneIdx} COMPLETED · PROTECTED EXIT · SCANNING #${opp}`:`#${lastDoneIdx} ENDED UNARMED · SCANNING #${opp}`):shown==='PASS'?guardText:(shown==='EXIT'?'EXIT / PROTECT PROFITS NOW':shown==='PROTECT'?'PROTECT PROFITS':currentGuideZone==='TOO_EXPENSIVE'?\"MOVE VALID · ENTRY TOO EXPENSIVE · DON'T CHASE\":'SCALP ACTIVE · BUILDING');"

OLD_STATS = '<div class="csc-stats"><div class="csc-stat"><div class="csc-lab">ENTRY</div><div class="csc-val">${cents(entry)}</div></div><div class="csc-stat"><div class="csc-lab">CURRENT BID</div><div class="csc-val">${cents(bid)}</div></div><div class="csc-stat"><div class="csc-lab">EXEC GAIN</div><div class="csc-val">${sc(gain)}</div></div></div>'
NEW_STATS = '<div class="csc-stats"><div class="csc-stat"><div class="csc-lab">${completedHold?\'COMPLETED ENTRY\':\'ENTRY\'}</div><div class="csc-val">${cents(completedHold?lastDoneEntry:entry)}</div></div><div class="csc-stat"><div class="csc-lab">${completedHold?\'STATUS\':\'CURRENT BID\'}</div><div class="csc-val">${completedHold?\'DONE\':cents(bid)}</div></div><div class="csc-stat"><div class="csc-lab">${completedHold?\'EXIT / PEAK\':\'EXEC GAIN\'}</div><div class="csc-val">${completedHold?sc(Number.isFinite(lastDoneExit)?lastDoneExit:lastDonePeak):sc(gain)}</div></div></div>'

OLD_GRID = v10.GRID_WITH_LIFECYCLE
NEW_GRID = "      <div class=\"csc-row ${usable&&!completedHold&&currentGuideZone==='TOO_EXPENSIVE'?'entry-too-expensive':usable&&!completedHold&&['IDEAL','GOOD'].includes(currentGuideZone)?'entry-good':''}\"><span>Entry guidance</span><strong>${usable?(completedHold?(completedGuideLabel||'COMPLETED'):(currentGuideLabel||'WATCHING')):'FAIL-CLOSED'}</strong></div>\n      <div class=\"csc-row\"><span>Lifecycle</span><strong>${usable?(completedHold?(lastDoneState==='EXIT'?`${lastDoneSide} #${lastDoneIdx} completed · protected exit`:`${lastDoneSide} #${lastDoneIdx} ended unarmed · reset only`):lastTerminal==='ENDED_UNARMED'?'Prior ended unarmed · reset only':lastTerminal==='EXIT'?'Prior protected EXIT':scanNext?'Scanning next qualified scalp':`Opportunity #${opp}`):'FAIL-CLOSED'}</strong></div>\n" + v10.GRID_ANCHOR

CSS = """<style id=\"btc15-scalp-v11-clarity-style\">\n#combinedScalpClean .csc-row.entry-too-expensive strong{color:#ffcf66!important;font-weight:950!important;}\n#combinedScalpClean .csc-row.entry-good strong{color:#76efaa!important;font-weight:950!important;}\n</style>"""


def patch_v11(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    changes = []
    for old, new, label in (
        (OLD_FEED, NEW_FEED, "use-v6-display-bridge"),
        (OLD_VALID, NEW_VALID, "accept-v6-display-safety-envelope"),
        (OLD_USABLE, NEW_USABLE, "derive-completed-display-memory"),
        (OLD_SIDE, NEW_SIDE, "persist-completed-scalp-heading"),
        (OLD_MAIN, NEW_MAIN, "separate-move-valid-from-entry-quality"),
        (OLD_STATS, NEW_STATS, "show-completed-scalp-stats"),
        (OLD_GRID, NEW_GRID, "add-entry-guidance-and-completed-lifecycle"),
    ):
        if old in text:
            text = text.replace(old, new, 1)
            changes.append(label)
        elif new not in text:
            raise RuntimeError(f"{label} anchor not found; refusing unsafe patch")

    if 'id="btc15-scalp-v11-clarity-style"' not in text:
        if "</head>" in text:
            text = text.replace("</head>", CSS + "\n</head>", 1)
        else:
            text = CSS + "\n" + text
    if MARKER not in text:
        text = text.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1) if "</body>" in text else text + f"\n<!-- {MARKER} -->\n"
    path.write_text(text, encoding="utf-8")
    return changes or ["v11-already-present"]


def build_dashboard() -> Path:
    html = v10.build_dashboard()
    patch_v11(html)
    return html


def main() -> int:
    html = build_dashboard()
    rendered = html.read_text(encoding="utf-8", errors="replace")
    print("COMBINED SCALP UI V11 | COMPLETED SCALP PERSISTENCE + ENTRY GUIDANCE | SHADOW ONLY | NO ORDERS")
    if "--self-test" in sys.argv:
        assert NEW_FEED in rendered and OLD_FEED not in rendered
        assert NEW_VALID in rendered and OLD_VALID not in rendered
        assert "BTC15_COMBINED_STATE_BRIDGE_V6" in rendered
        assert "scalp_display_metadata_only===true" in rendered
        assert "scalp_completed_display_actionable===false" in rendered
        assert "scalp_entry_guidance_is_display_only===true" in rendered
        assert "scalp_entry_price_filter_applied===false" in rendered
        assert "COMPLETED · PROTECTED EXIT · SCANNING" in rendered
        assert "MOVE VALID · ENTRY TOO EXPENSIVE · DON'T CHASE" in rendered
        assert "Entry guidance" in rendered
        assert "completed protected EXIT · now scanning" in rendered
        assert "Arm +5¢ · EXIT at 4¢ giveback" in rendered
        assert '<span>Contract time left</span>' not in rendered
        assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in rendered
        assert "flip_risk_percent" not in rendered
        assert MARKER in rendered
        print("COMBINED SCALP UI V11 SELFTEST PASS | COMPLETED CONTEXT RETAINED | PRICE GUIDANCE DISPLAY-ONLY | NO ORDERS")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
