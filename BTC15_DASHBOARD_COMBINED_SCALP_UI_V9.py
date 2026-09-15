#!/usr/bin/env python3
"""
BTC15 combined generalized SCALP in-layout dashboard UI V9.

SHADOW DISPLAY CLEANUP ONLY | SIGNAL ONLY | NO ORDERS

Decision locked from live review:
- The top-right main CONTRACT TIMER remains the one visible contract countdown.
- The duplicate "Contract time left" row inside SCALP / REVERSAL is removed.
- Internal seconds-left data, qualification, full-contract scanning, management,
  contract alignment, source freshness, EARLY, FINAL, and all scoring remain
  unchanged.

This eliminates a redundant UI clock without changing any SCALP outcome logic.
"""
from pathlib import Path
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V8 as v8

MARKER = "BTC15_COMBINED_SCALP_UI_V9_SINGLE_VISIBLE_CONTRACT_TIMER"
DEPLOY_TRIGGER = "2026-09-14T22:39-04:00"
OLD_ROW = '<div class="csc-row"><span>Contract time left</span><strong>${mainClock||secs(left)}</strong></div>'


def patch_remove_duplicate_timer(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if OLD_ROW in text:
        text = text.replace(OLD_ROW, "", 1)
        changes = ["remove-redundant-scalp-timer-row"]
    elif "<span>Contract time left</span>" not in text:
        changes = ["redundant-scalp-timer-row-already-absent"]
    else:
        raise RuntimeError("unexpected SCALP timer markup; refusing unsafe patch")

    if MARKER not in text:
        text = text.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1) if "</body>" in text else text + f"\n<!-- {MARKER} -->\n"
    path.write_text(text, encoding="utf-8")
    return changes


def build_dashboard() -> Path:
    html = v8.build_dashboard()
    patch_remove_duplicate_timer(html)
    return html


def main() -> int:
    html = build_dashboard()
    rendered = html.read_text(encoding="utf-8", errors="replace")
    print("COMBINED SCALP UI V9 | SINGLE VISIBLE CONTRACT TIMER | SHADOW ONLY | NO ORDERS")
    if "--self-test" in sys.argv:
        assert MARKER in rendered
        assert OLD_ROW not in rendered
        assert '<span>Contract time left</span>' not in rendered
        # Internal contract-time data remains available to the signal/integration stack.
        assert "canonical_seconds_left" in rendered
        assert "scalp_contract_aligned===true" in rendered
        assert "scalp_source_fresh===true" in rendered
        assert "scalp_integration_ready===true" in rendered
        assert "Arm +5¢ · EXIT at 4¢ giveback" in rendered
        assert "Running peak" in rendered
        assert "Giveback from peak" in rendered
        assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in rendered
        assert "flip_risk_percent" not in rendered
        print("COMBINED SCALP UI V9 SELFTEST PASS | DUPLICATE TIMER REMOVED | INTERNAL TIMING PRESERVED | NO ORDERS")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
