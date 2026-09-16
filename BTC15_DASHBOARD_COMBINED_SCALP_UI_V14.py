#!/usr/bin/env python3
"""
BTC15 combined dashboard UI V14 — presentation stability.

SHADOW PRESENTATION ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

V14 is deliberately narrow. It builds the exact V13 candidate and changes only
presentation behavior proven by generated-DOM/source audits:
- stop the BTC numeric readout from being assigned yellow by JS when stale;
- disable BTC numeric pulse/transition animation;
- use tabular numerals and reserved widths for changing numeric fields;
- bound FINAL action-subtext height while preserving the already-existing V4
  fixed FINAL reason box;
- reserve stable EARLY entry/status text height.

No EARLY/FINAL/SCALP qualification, lifecycle, timer authority, Kalshi pricing,
data-source authority, or order behavior changes.
"""
from __future__ import annotations

from pathlib import Path
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V13 as v13

MARKER = "BTC15_COMBINED_SCALP_UI_V14_PRESENTATION_STABILITY"

# Exact generated-source mutation found by the V13 stability source audit.
OLD_BTC_COLOR_JS = "price.style.color=record&&!current?'var(--yellow)':'';"
NEW_BTC_COLOR_JS = "price.style.color='';"

REQUIRED_UNIQUE_ANCHORS = (
    'id="btcPrice"',
    'id="finalCard"',
    'id="finalReason"',
    'id="finalActionSub"',
    'class="card early-card"',
    'id="earlyEntry"',
    'id="earlyFlow"',
    'class="card timer-card"',
    'id="timerRemaining"',
    'id="timerEnd"',
    'id="scalpCard"',
)

SAFETY_ANCHORS = (
    "BTC15_COMBINED_SCALP_UI_V12_NO_POSITION_TRACKING",
    "BTC15_COMBINED_SCALP_UI_V13_PLAIN_LANGUAGE",
    "BTC15_COMBINED_STATE_BRIDGE_V6",
    "scalp_entry_price_filter_applied===false",
    "scalp_entry_guidance_is_display_only===true",
    "scalp_completed_display_actionable===false",
    "scalp_ended_unarmed_is_actionable_exit===false",
    "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS",
    "canonical_seconds_left",
)

V14_CSS = r'''<style id="btc15-v14-stability-style">
/* Numeric stability: content still updates; glyph widths/color do not jump. */
#btcPrice{
  color:#f3f5f7!important;
  opacity:1!important;
  text-shadow:none!important;
  animation:none!important;
  transition:none!important;
  font-variant-numeric:tabular-nums lining-nums!important;
  font-feature-settings:"tnum" 1,"lnum" 1!important;
  min-inline-size:8.6ch;
  display:inline-block;
  text-align:right;
}
#btcPrice.data-pulse{animation:none!important;transition:none!important;}
#timerRemaining,#timerEnd,#finalConfidence,#upOdds,#downOdds,
#earlyCurrentPrice,#scalpCurrentPrice,#earlyYourEntry,#scalpYourEntry,
#btcGap{
  font-variant-numeric:tabular-nums lining-nums!important;
  font-feature-settings:"tnum" 1,"lnum" 1!important;
}
#timerRemaining{min-inline-size:5.4ch;display:inline-block;text-align:center;}
#timerEnd{min-inline-size:8.2ch;display:inline-block;text-align:right;}
#finalConfidence{min-inline-size:5.4ch;display:inline-block;}
#upOdds,#downOdds{min-inline-size:4.2ch;display:inline-block;text-align:right;}
#earlyCurrentPrice,#scalpCurrentPrice,#earlyYourEntry,#scalpYourEntry{min-inline-size:4.2ch;display:inline-block;}

/* Existing render-fix already owns #finalReason at a fixed 3-line height.
   Stabilize the adjacent changing subtext so it cannot expand the card. */
#finalActionSub{
  min-height:2.8em!important;
  height:2.8em!important;
  max-height:2.8em!important;
  line-height:1.4em!important;
  overflow:hidden!important;
  display:-webkit-box!important;
  -webkit-line-clamp:2!important;
  -webkit-box-orient:vertical!important;
}

/* Reserve ordinary two-line space for EARLY state copy. */
#earlyEntry,#earlyFlow{
  min-height:2.8em;
  line-height:1.4em;
  box-sizing:border-box;
}

/* Keep dynamic cards aligned within their existing layout; no new grid. */
#finalCard,.early-card,#scalpCard,.timer-card{min-width:0;}

@media(max-width:700px){
  #btcPrice{min-inline-size:8.2ch;}
  #timerRemaining{min-inline-size:5.2ch;}
  #finalActionSub{min-height:3em!important;height:3em!important;max-height:3em!important;line-height:1.5em!important;}
  #earlyEntry,#earlyFlow{min-height:3em;line-height:1.5em;}
}
</style>'''


def _count_snapshot(text: str, anchors: tuple[str, ...]) -> dict[str, int]:
    return {a: text.count(a) for a in anchors}


def patch_v14(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")

    # Fail closed on DOM drift. These were inventoried from exact generated V13 HTML.
    bad = {a: text.count(a) for a in REQUIRED_UNIQUE_ANCHORS if text.count(a) != 1}
    if bad:
        raise RuntimeError(f"V14 DOM anchors drifted; refusing stability patch: {bad}")

    before_safety = _count_snapshot(text, SAFETY_ANCHORS)
    if any(v < 1 for v in before_safety.values()):
        raise RuntimeError(f"V14 safety marker missing before patch: {before_safety}")

    changes: list[str] = []
    n_old = text.count(OLD_BTC_COLOR_JS)
    if n_old == 1:
        text = text.replace(OLD_BTC_COLOR_JS, NEW_BTC_COLOR_JS, 1)
        changes.append("neutralize-btc-price-color-mutation")
    elif n_old == 0 and text.count(NEW_BTC_COLOR_JS) >= 1:
        changes.append("btc-price-color-already-neutral")
    else:
        raise RuntimeError(f"unexpected BTC price color mutation count={n_old}; refusing V14 patch")

    if 'id="btc15-v14-stability-style"' not in text:
        if "</head>" not in text:
            raise RuntimeError("V14 </head> anchor missing; refusing CSS injection")
        text = text.replace("</head>", V14_CSS + "\n</head>", 1)
        changes.append("inject-v14-stability-css")

    if MARKER not in text:
        if "</body>" not in text:
            raise RuntimeError("V14 </body> anchor missing; refusing marker injection")
        text = text.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1)
        changes.append("v14-marker")

    after_safety = _count_snapshot(text, SAFETY_ANCHORS)
    if after_safety != before_safety:
        raise RuntimeError(f"V14 safety marker counts changed: before={before_safety} after={after_safety}")

    # Existing FINAL reason stability remains owned by the older render-fix.
    # Check semantic fragments independently so benign whitespace formatting cannot
    # make an unchanged inherited rule fail this V14 gate.
    required_existing = (
        'id="btc15-render-fix-v4"',
        "#finalReason",
        "min-height:4.2em !important",
        "height:4.2em !important",
        "-webkit-line-clamp:3",
        "#v81ScalpCard",
        "display:none !important",
    )
    for a in required_existing:
        if a not in text:
            raise RuntimeError(f"existing render stability invariant missing after V14: {a}")

    if "flip_risk_percent" in text:
        raise RuntimeError("numeric Flip Risk unexpectedly present in V14 output")

    path.write_text(text, encoding="utf-8")
    return changes or ["v14-already-present"]


def build_dashboard() -> Path:
    html = v13.build_dashboard()
    patch_v14(html)
    return html


def main() -> int:
    html = build_dashboard()
    rendered = html.read_text(encoding="utf-8", errors="replace")
    print("COMBINED DASHBOARD UI V14 | PRESENTATION STABILITY | SHADOW ONLY | NO ORDERS")
    if "--self-test" in sys.argv:
        assert OLD_BTC_COLOR_JS not in rendered
        assert NEW_BTC_COLOR_JS in rendered
        assert rendered.count('id="btc15-v14-stability-style"') == 1
        assert "#btcPrice.data-pulse{animation:none!important;transition:none!important;}" in rendered
        assert "font-variant-numeric:tabular-nums lining-nums!important;" in rendered
        assert "#timerRemaining{min-inline-size:5.4ch" in rendered
        assert "#finalActionSub{" in rendered and "height:2.8em!important" in rendered
        assert "#earlyEntry,#earlyFlow{" in rendered
        assert rendered.count('id="timerRemaining"') == 1
        assert rendered.count("CONTRACT TIMER") >= 1
        assert '<span>Contract time left</span>' not in rendered
        assert "BTC15_COMBINED_SCALP_UI_V13_PLAIN_LANGUAGE" in rendered
        assert MARKER in rendered
        assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in rendered
        assert "flip_risk_percent" not in rendered
        print("COMBINED DASHBOARD UI V14 SELFTEST PASS | NO BLINK MUTATION · STABLE NUMERICS/TEXT | NO ORDERS")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
