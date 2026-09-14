#!/usr/bin/env python3
"""
BTC15 combined generalized SCALP in-layout dashboard UI V6.

SHADOW DISPLAY FIX ONLY | SIGNAL ONLY | NO ORDERS

V6 makes the SCALP card's displayed contract time use the already-visible main
CONTRACT TIMER whenever available. The main dashboard remains canonical clock
authority. The combined bridge seconds-left value is only a fail-safe display
fallback. No signal, qualification, management, pricing, timing threshold, or
order behavior changes.
"""
from pathlib import Path
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V5 as v5

MARKER = "BTC15_COMBINED_SCALP_UI_V6_MAIN_TIMER_DISPLAY"
OLD_LEFT = "const left=usable?n(d.canonical_seconds_left):NaN;"
NEW_LEFT = "const left=usable?n(d.canonical_seconds_left):NaN; const mainClock=(()=>{for(const e of document.querySelectorAll('body *')){const t=String(e.textContent||'').trim();if(!/^\\d{2}:\\d{2}$/.test(t))continue;let p=e;for(let i=0;i<5&&p;i++,p=p.parentElement){if(String(p.textContent||'').includes('CONTRACT TIMER'))return t;}}return null;})();"
OLD_ROW = "<div class=\"csc-row\"><span>Contract time left</span><strong>${secs(left)}</strong></div>"
NEW_ROW = "<div class=\"csc-row\"><span>Contract time left</span><strong>${mainClock||secs(left)}</strong></div>"


def patch_main_timer_display(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    changes = []
    if OLD_LEFT in text:
        text = text.replace(OLD_LEFT, NEW_LEFT, 1)
        changes.append("main-timer-dom-read")
    elif NEW_LEFT not in text:
        raise RuntimeError("clean SCALP left-time declaration not found; refusing unsafe patch")

    if OLD_ROW in text:
        text = text.replace(OLD_ROW, NEW_ROW, 1)
        changes.append("main-timer-display-authority")
    elif NEW_ROW not in text:
        raise RuntimeError("clean SCALP contract-time row not found; refusing unsafe patch")

    if MARKER not in text:
        text = text.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1) if "</body>" in text else text + f"\n<!-- {MARKER} -->\n"
    path.write_text(text, encoding="utf-8")
    return changes or ["main-timer-display-already-present"]


def build_dashboard() -> Path:
    html = v5.build_dashboard()
    patch_main_timer_display(html)
    return html


def main() -> int:
    html = build_dashboard()
    rendered = html.read_text(encoding="utf-8", errors="replace")
    print("COMBINED SCALP UI V6 | MAIN TIMER DISPLAY AUTHORITY | CLEAN PANEL | SHADOW ONLY | NO ORDERS")
    if "--self-test" in sys.argv:
        assert NEW_LEFT in rendered and OLD_LEFT not in rendered
        assert NEW_ROW in rendered and OLD_ROW not in rendered
        assert MARKER in rendered
        assert "CONTRACT TIMER" in rendered
        assert "BTC15_COMBINED_SCALP_UI_V5_DOM_CONTRACT_SYNC" in rendered
        assert "scalp_contract_aligned===true" in rendered
        assert "Arm +5¢ · EXIT at 4¢ giveback" in rendered
        assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in rendered
        assert "flip_risk_percent" not in rendered
        print("COMBINED SCALP UI V6 SELFTEST PASS | MAIN CLOCK DISPLAY | BACKEND GUARDS PRESERVED | NO ORDERS")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
