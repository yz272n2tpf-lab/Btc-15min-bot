#!/usr/bin/env python3
"""
BTC15 combined generalized SCALP in-layout dashboard UI V5.

SHADOW DISPLAY FIX ONLY | SIGNAL ONLY | NO ORDERS

V5 fixes the remaining false browser-side CONTRACT SYNC warning seen on iPad.
The visible dashboard header already contains the authoritative current Kalshi
ticker, so this shadow-only patch checks that DOM ticker first, then falls back
to the nested applyState object. Backend scalp_contract_aligned/fresh/ready
remain mandatory. No signal, timing, price, management, or order rules change.
"""
from pathlib import Path
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V4 as v4

MARKER = "BTC15_COMBINED_SCALP_UI_V5_DOM_CONTRACT_SYNC"
OLD = "const mc=String(main?.contract||main?.state?.contract||main?.data?.contract||''); const fresh=Date.now()-okAt<=3500, same=!!(mc&&d&&d.contract===mc), env=valid(d);"
NEW = "const ht=String(document.getElementById('currentContract')?.textContent||''); const hm=ht.match(/KXBTC15M-[A-Z0-9-]+/i); const mc=String(hm?.[0]||main?.contract||main?.state?.contract||main?.data?.contract||''); const fresh=Date.now()-okAt<=3500, same=!!(mc&&d&&d.contract===mc&&d.scalp_contract_aligned===true&&d.scalp_source_fresh===true&&d.scalp_integration_ready===true), env=valid(d);"


def patch_dom_contract_sync(path: Path) -> list[str]:
    text=path.read_text(encoding="utf-8",errors="replace")
    if OLD in text:
        text=text.replace(OLD,NEW,1)
    elif NEW not in text:
        raise RuntimeError("V4 nested contract comparison not found; refusing unsafe patch")
    if MARKER not in text:
        text=text.replace("</body>",f"<!-- {MARKER} -->\n</body>",1) if "</body>" in text else text+f"\n<!-- {MARKER} -->\n"
    path.write_text(text,encoding="utf-8")
    return ["dom-first-contract-sync"]


def build_dashboard() -> Path:
    html=v4.build_dashboard();patch_dom_contract_sync(html);return html


def main() -> int:
    html=build_dashboard();rendered=html.read_text(encoding="utf-8",errors="replace")
    print("COMBINED SCALP UI V5 | DOM-FIRST CONTRACT SYNC | CLEAN PANEL | SHADOW ONLY | NO ORDERS")
    if "--self-test" in sys.argv:
        assert NEW in rendered and OLD not in rendered and MARKER in rendered
        assert "currentContract" in rendered
        assert "scalp_contract_aligned===true" in rendered
        assert "scalp_source_fresh===true" in rendered
        assert "scalp_integration_ready===true" in rendered
        assert "Arm +5¢ · EXIT at 4¢ giveback" in rendered
        assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in rendered
        assert "flip_risk_percent" not in rendered
        print("COMBINED SCALP UI V5 SELFTEST PASS | DOM-FIRST SYNC + BACKEND GUARDS | NO ORDERS")
        return 0
    return 0


if __name__=='__main__':raise SystemExit(main())
