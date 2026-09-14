#!/usr/bin/env python3
"""
BTC15 combined generalized SCALP in-layout dashboard UI V2.

DISPLAY / INTEGRATION ONLY | SIGNAL ONLY | NO ORDERS

V2 is a surgical compatibility wrapper around the already-self-tested V1 UI.
It changes only the accepted read-only combined bridge version list so the
shadow dashboard can transition from V3 to the incremental-cache V4 bridge
without changing layout, state semantics, or management thresholds.
"""
from pathlib import Path
import os
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V1 as v1

MARKER = "BTC15_COMBINED_SCALP_UI_V2"
OLD = "if(!d || d.version!=='BTC15_COMBINED_STATE_BRIDGE_V3')return false;"
NEW = "if(!d || !['BTC15_COMBINED_STATE_BRIDGE_V3','BTC15_COMBINED_STATE_BRIDGE_V4'].includes(d.version))return false;"


def patch_v2_compat(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    changes = []
    if OLD in text:
        text = text.replace(OLD, NEW, 1)
        changes.append("accept-combined-v3-v4")
    elif NEW not in text:
        raise RuntimeError("combined scalp safety-envelope version check not found")
    if MARKER not in text:
        text = text.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1) if "</body>" in text else text + f"\n<!-- {MARKER} -->\n"
    path.write_text(text, encoding="utf-8")
    return changes or ["v3-v4-compat-already-present"]


def build_dashboard() -> Path:
    html = v1.build_dashboard()
    patch_v2_compat(html)
    return html


def main() -> int:
    html = build_dashboard()
    rendered = html.read_text(encoding="utf-8", errors="replace")
    print("COMBINED SCALP UI V2 | V3+V4 read-only bridge compatibility | EXISTING CARD ONLY | NO ORDERS")
    if "--self-test" in sys.argv:
        assert NEW in rendered
        assert "BTC15_COMBINED_STATE_BRIDGE_V3" in rendered
        assert "BTC15_COMBINED_STATE_BRIDGE_V4" in rendered
        assert rendered.count('id="btc15-combined-scalp-script"') == 1
        assert 'id="v81-inline-scalp-script"' not in rendered
        assert "COUNTERTREND_SCALP" in rendered
        assert "validated 4¢ giveback" in rendered
        assert "flip_risk_percent" not in rendered
        assert "order_action!==null" in rendered and "d.orders!==false" in rendered
        print("COMBINED SCALP UI V2 SELFTEST PASS | V3+V4 ONLY | LOCKED LAYOUT | NO ORDERS")
        return 0
    wrapper = html.parent / "BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py"
    os.execv(sys.executable, [sys.executable, "-u", str(wrapper)])


if __name__ == "__main__":
    raise SystemExit(main())
