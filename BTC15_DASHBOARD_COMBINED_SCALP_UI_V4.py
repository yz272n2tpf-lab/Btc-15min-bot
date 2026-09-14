#!/usr/bin/env python3
"""
BTC15 combined generalized SCALP in-layout dashboard UI V4.

SHADOW DISPLAY FIX ONLY | SIGNAL ONLY | NO ORDERS

V4 fixes one browser-side contract-sync bug discovered in the iPad shadow
screenshot. The protected dashboard sometimes passes a wrapper object into
applyState, so the visible contract can live at main.contract, main.state.contract,
or main.data.contract. V3 only checked main.contract and could therefore show
WAIT · CONTRACT SYNC even while the backend bridge reported sync=True.

No signal, qualification, management, timing, pricing, or order logic changes.
"""
from pathlib import Path
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V3 as v3

MARKER = "BTC15_COMBINED_SCALP_UI_V4_NESTED_CONTRACT_SYNC"
OLD = "const fresh=Date.now()-okAt<=3500, same=!!(main&&d&&d.contract===main.contract), env=valid(d);"
NEW = "const mc=String(main?.contract||main?.state?.contract||main?.data?.contract||''); const fresh=Date.now()-okAt<=3500, same=!!(mc&&d&&d.contract===mc), env=valid(d);"


def patch_nested_contract_sync(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    changes = []
    if OLD in text:
        text = text.replace(OLD, NEW, 1)
        changes.append("nested-main-contract-sync")
    elif NEW not in text:
        raise RuntimeError("V3 clean-panel contract comparison not found; refusing unsafe patch")
    if MARKER not in text:
        if "</body>" in text:
            text = text.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1)
        else:
            text += f"\n<!-- {MARKER} -->\n"
    path.write_text(text, encoding="utf-8")
    return changes or ["nested-main-contract-sync-already-present"]


def build_dashboard() -> Path:
    html = v3.build_dashboard()
    patch_nested_contract_sync(html)
    return html


def main() -> int:
    html = build_dashboard()
    rendered = html.read_text(encoding="utf-8", errors="replace")
    print("COMBINED SCALP UI V4 | NESTED MAIN CONTRACT SYNC | CLEAN PANEL | SHADOW ONLY | NO ORDERS")
    if "--self-test" in sys.argv:
        assert NEW in rendered
        assert OLD not in rendered
        assert MARKER in rendered
        assert "BTC15_COMBINED_SCALP_UI_V3_CLEAN_PANEL" in rendered
        assert "Arm +5¢ · EXIT at 4¢ giveback" in rendered
        assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in rendered
        assert "flip_risk_percent" not in rendered
        print("COMBINED SCALP UI V4 SELFTEST PASS | NESTED CONTRACT SYNC | NO ORDERS")
        return 0
    wrapper = html.parent / "BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py"
    import os
    os.execv(sys.executable, [sys.executable, "-u", str(wrapper)])


if __name__ == "__main__":
    raise SystemExit(main())
