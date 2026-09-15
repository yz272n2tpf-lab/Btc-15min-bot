#!/usr/bin/env python3
"""
BTC15 combined generalized SCALP in-layout dashboard UI V7.

SHADOW DISPLAY FIX ONLY | SIGNAL ONLY | NO ORDERS

V7 fixes the live iPad timer mismatch found after V6. V6 searched for any
MM:SS element whose ancestor happened to contain CONTRACT TIMER; that selector
could pick an unrelated wall-clock minute:second value from a larger shared
ancestor. V7 instead scopes the read to the smallest visible subtree containing
both CONTRACT TIMER and REMAINING, then extracts the countdown adjacent to
REMAINING. The combined bridge remains fallback-only for display.

No signal, qualification, management, price, timing threshold, EARLY/FINAL, or
order behavior changes.
"""
from pathlib import Path
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V6 as v6

MARKER = "BTC15_COMBINED_SCALP_UI_V7_SCOPED_MAIN_TIMER"
OLD_LEFT = v6.NEW_LEFT
NEW_LEFT = r"""const left=usable?n(d.canonical_seconds_left):NaN; const mainClock=(()=>{const norm=x=>String(x||'').replace(/\s+/g,' ').trim();const fmt=x=>{const p=String(x||'').split(':');return p.length===2?`${p[0].padStart(2,'0')}:${p[1]}`:null;};const cards=[...document.querySelectorAll('body *')].filter(e=>{const t=norm(e.textContent);return /CONTRACT TIMER/i.test(t)&&/REMAINING/i.test(t);}).sort((a,b)=>norm(a.textContent).length-norm(b.textContent).length);for(const e of cards){const t=norm(e.textContent);let m=t.match(/(\d{1,2}:\d{2})\s*REMAINING\b/i);if(!m)m=t.match(/\bREMAINING\s*(\d{1,2}:\d{2})/i);if(m)return fmt(m[1]);for(const c of e.querySelectorAll('*')){const ct=norm(c.textContent);if(!/^\d{1,2}:\d{2}$/.test(ct))continue;let p=c;for(let i=0;i<3&&p;i++,p=p.parentElement){if(/REMAINING/i.test(norm(p.textContent)))return fmt(ct);}}}return null;})();"""


def patch_scoped_timer(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if OLD_LEFT in text:
        text = text.replace(OLD_LEFT, NEW_LEFT, 1)
        changes = ["scoped-main-contract-timer"]
    elif NEW_LEFT in text:
        changes = ["scoped-main-contract-timer-already-present"]
    else:
        raise RuntimeError("V6 timer selector not found; refusing unsafe patch")

    if MARKER not in text:
        text = text.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1) if "</body>" in text else text + f"\n<!-- {MARKER} -->\n"
    path.write_text(text, encoding="utf-8")
    return changes


def build_dashboard() -> Path:
    html = v6.build_dashboard()
    patch_scoped_timer(html)
    return html


def main() -> int:
    html = build_dashboard()
    rendered = html.read_text(encoding="utf-8", errors="replace")
    print("COMBINED SCALP UI V7 | SCOPED MAIN CONTRACT TIMER | CLEAN PANEL | SHADOW ONLY | NO ORDERS")
    if "--self-test" in sys.argv:
        assert NEW_LEFT in rendered
        assert OLD_LEFT not in rendered
        assert MARKER in rendered
        assert "/CONTRACT TIMER/i" in rendered
        assert "/REMAINING/i" in rendered
        assert "sort((a,b)=>norm(a.textContent).length-norm(b.textContent).length)" in rendered
        assert "mainClock||secs(left)" in rendered
        assert "BTC15_COMBINED_SCALP_UI_V5_DOM_CONTRACT_SYNC" in rendered
        assert "scalp_contract_aligned===true" in rendered
        assert "Arm +5¢ · EXIT at 4¢ giveback" in rendered
        assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in rendered
        assert "flip_risk_percent" not in rendered
        print("COMBINED SCALP UI V7 SELFTEST PASS | TIMER CARD SCOPED | BACKEND GUARDS PRESERVED | NO ORDERS")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
