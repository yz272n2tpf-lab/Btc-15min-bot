#!/usr/bin/env python3
"""
BTC15 V14 mobile layout invariant audit V1.

OFFLINE STATIC QA ONLY | PRESENTATION ONLY | NO ORDERS

This does not emulate Safari and does not replace human iPhone/iPad review.
It checks structural invariants that should be true before visual acceptance:
- responsive viewport metadata exists;
- critical card/number/timer anchors are unique;
- one canonical timer remains;
- V14 phone media override exists;
- dynamic numeric fields use tabular numerals / reserved widths;
- top dynamic cards can shrink inside responsive layouts;
- BTC color mutation/pulse is neutralized;
- FINAL/EARLY dynamic copy has reserved height;
- protected safety and no-orders markers remain.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 as v14

VERSION = "BTC15_DASHBOARD_V14_MOBILE_LAYOUT_AUDIT_V1"

UNIQUE_ANCHORS = (
    'id="btcPrice"',
    'id="finalCard"',
    'id="finalReason"',
    'id="finalActionSub"',
    'id="earlyEntry"',
    'id="earlyFlow"',
    'id="timerRemaining"',
    'id="timerEnd"',
    'id="scalpCard"',
)

REQUIRED_SNIPPETS = (
    'name="viewport"',
    'width=device-width',
    'id="btc15-v14-stability-style"',
    '@media(max-width:700px)',
    'font-variant-numeric:tabular-nums lining-nums!important',
    '#timerRemaining{min-inline-size:5.4ch',
    '#timerEnd{min-inline-size:8.2ch',
    '#finalConfidence{min-inline-size:5.4ch',
    '#finalCard,.early-card,#scalpCard,.timer-card{min-width:0;}',
    '#finalActionSub{',
    '#earlyEntry,#earlyFlow{',
    '#btcPrice.data-pulse{animation:none!important;transition:none!important;}',
    "price.style.color='';",
    'canonical_seconds_left',
    'SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS',
    'BTC15_COMBINED_STATE_BRIDGE_V6',
)

FORBIDDEN_SNIPPETS = (
    "price.style.color=record&&!current?'var(--yellow)':'';",
    '<span>Contract time left</span>',
    'flip_risk_percent',
)


def audit_html(text: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    for anchor in UNIQUE_ANCHORS:
        count = text.count(anchor)
        checks.append({
            "check": f"unique:{anchor}",
            "pass": count == 1,
            "detail": f"count={count}",
        })

    for snippet in REQUIRED_SNIPPETS:
        checks.append({
            "check": f"required:{snippet}",
            "pass": snippet in text,
            "detail": "present" if snippet in text else "missing",
        })

    for snippet in FORBIDDEN_SNIPPETS:
        checks.append({
            "check": f"forbidden:{snippet}",
            "pass": snippet not in text,
            "detail": "absent" if snippet not in text else "present",
        })

    timer_count = text.count('id="timerRemaining"')
    checks.append({
        "check": "single-canonical-visible-timer",
        "pass": timer_count == 1 and "canonical_seconds_left" in text,
        "detail": f"timerRemaining={timer_count}",
    })

    # V14's mobile override must preserve reserved space, not remove it.
    phone_block_ok = all(x in text for x in (
        '@media(max-width:700px)',
        '#btcPrice{min-inline-size:8.2ch;}',
        '#timerRemaining{min-inline-size:5.2ch;}',
        '#finalActionSub{min-height:3em!important;height:3em!important;max-height:3em!important;line-height:1.5em!important;}',
        '#earlyEntry,#earlyFlow{min-height:3em;line-height:1.5em;}',
    ))
    checks.append({
        "check": "phone-override-reserves-dynamic-space",
        "pass": phone_block_ok,
        "detail": "700px phone rules intact" if phone_block_ok else "phone stability rule missing",
    })

    passed = sum(bool(c["pass"]) for c in checks)
    failed = len(checks) - passed
    return {
        "version": VERSION,
        "status": "STATIC_MOBILE_PREFLIGHT_PASS" if failed == 0 else "STATIC_MOBILE_PREFLIGHT_FAIL",
        "passed": passed,
        "failed": failed,
        "checks": checks,
        "device_review_targets": {
            "iphone": "human visual review required on actual phone layout",
            "ipad": "human visual review required on actual tablet layout",
            "real_rollover": "required before any V14 promotion",
        },
        "human_visual_review_still_required": True,
        "changes_signal_logic": False,
        "changes_thresholds": False,
        "orders": False,
    }


def audit_generated_v14() -> dict[str, Any]:
    path: Path = v14.build_dashboard()
    text = path.read_text(encoding="utf-8", errors="replace")
    return audit_html(text)


def main() -> int:
    report = audit_generated_v14()
    print(
        f"{VERSION} | {report['status']} | passed={report['passed']} failed={report['failed']} | "
        "STATIC ONLY · HUMAN IPHONE/IPAD REVIEW STILL REQUIRED · NO ORDERS",
        flush=True,
    )
    for c in report["checks"]:
        if not c["pass"]:
            print(f"FAIL | {c['check']} | {c['detail']}", flush=True)
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
