#!/usr/bin/env python3
"""BTC15 combined dashboard UI V15 candidate — responsive core layout.

SHADOW PRESENTATION CANDIDATE ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

V15 wraps the exact V14 generated dashboard and changes presentation only:
- reuses the existing V14 `section.primary-grid`, `div.left-stack`, and
  `div.right-stack` containers rather than moving signal-card DOM nodes;
- preserves one canonical timer;
- uses one-column phone layout and two-column tablet/desktop layouts;
- preserves every existing card id/class, data source, event listener and state;
- adds no network client, no polling, no signal threshold, no order path;
- fails closed to the unchanged V14 layout if the expected stack hierarchy
  drifts.

This file is an isolated candidate and is NOT a production deployment.
"""
from __future__ import annotations

from pathlib import Path
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 as v14

MARKER = "BTC15_COMBINED_SCALP_UI_V15_RESPONSIVE_CANDIDATE"
STYLE_ID = 'id="btc15-v15-responsive-style"'
SCRIPT_ID = 'id="btc15-v15-responsive-script"'

SAFETY_ANCHORS = (
    v14.MARKER,
    "BTC15_COMBINED_SCALP_UI_V13_PLAIN_LANGUAGE",
    "BTC15_COMBINED_SCALP_UI_V12_NO_POSITION_TRACKING",
    "BTC15_COMBINED_STATE_BRIDGE_V6",
    "scalp_entry_price_filter_applied===false",
    "scalp_entry_guidance_is_display_only===true",
    "scalp_completed_display_actionable===false",
    "scalp_ended_unarmed_is_actionable_exit===false",
    "TRACKING ONLY · DON'T CHASE",
    "TRACKING ONLY · NO POSITION ASSUMED",
    "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS",
    "canonical_seconds_left",
)

CARD_ANCHORS = (
    'id="finalCard"',
    'class="card early-card"',
    'class="card timer-card"',
    'id="scalpCard"',
)

NETWORK_PRIMITIVES = (
    "fetch(",
    "XMLHttpRequest",
    "WebSocket",
    "EventSource",
)

V15_CSS = r'''<style id="btc15-v15-responsive-style">
/* V15 owns layout only. Existing V14/V13 styles continue to own card content. */
.primary-grid.v15-primary-grid{
  display:grid!important;
  grid-template-columns:minmax(0,1fr)!important;
  grid-template-areas:
    "final"
    "early"
    "timer"
    "scalp"!important;
  gap:12px!important;
  align-items:stretch!important;
  min-width:0!important;
}
/* The existing stack wrappers become layout-transparent only after the guarded
   runtime hierarchy check succeeds. No card node is moved or recreated. */
.primary-grid.v15-primary-grid > .left-stack.v15-left-stack,
.primary-grid.v15-primary-grid > .right-stack.v15-right-stack{
  display:contents!important;
}
.primary-grid.v15-primary-grid #finalCard{grid-area:final;}
.primary-grid.v15-primary-grid .early-card{grid-area:early;}
.primary-grid.v15-primary-grid .timer-card{grid-area:timer;}
.primary-grid.v15-primary-grid #scalpCard{grid-area:scalp;}
.primary-grid.v15-primary-grid #finalCard,
.primary-grid.v15-primary-grid .early-card,
.primary-grid.v15-primary-grid .timer-card,
.primary-grid.v15-primary-grid #scalpCard{
  width:100%;
  min-width:0;
  max-width:none;
  margin:0!important;
  box-sizing:border-box;
  transition:none!important;
}
/* Preserve any other existing primary-grid child as a full-width section below
   the four core signal cards instead of letting it collide with named areas. */
.primary-grid.v15-primary-grid > :not(.v15-left-stack):not(.v15-right-stack){
  grid-column:1 / -1!important;
}
#finalActionSub,#earlyEntry,#earlyFlow{overflow:hidden!important;}

@media (min-width:768px) and (max-width:1180px){
  .primary-grid.v15-primary-grid{
    grid-template-columns:minmax(0,1fr) minmax(0,1fr)!important;
    grid-template-areas:
      "final final"
      "early timer"
      "scalp scalp"!important;
    gap:14px!important;
  }
}
@media (min-width:1181px){
  .primary-grid.v15-primary-grid{
    grid-template-columns:minmax(0,1.2fr) minmax(0,.8fr)!important;
    grid-template-areas:
      "final early"
      "timer scalp"!important;
    gap:14px!important;
  }
}
</style>'''

V15_JS = r'''<script id="btc15-v15-responsive-script">
(function(){
  'use strict';
  function installV15ResponsiveCore(){
    const finalCard=document.getElementById('finalCard');
    const earlyCard=document.querySelector('.early-card');
    const timerCard=document.querySelector('.timer-card');
    const scalpCard=document.getElementById('scalpCard');
    if([finalCard,earlyCard,timerCard,scalpCard].some(card=>!card)){
      document.documentElement.dataset.v15Layout='guarded-missing-card';
      return false;
    }
    const leftStack=finalCard.parentElement;
    if(!leftStack || earlyCard.parentElement!==leftStack || !leftStack.classList.contains('left-stack')){
      document.documentElement.dataset.v15Layout='guarded-left-stack-drift';
      return false;
    }
    const rightStack=timerCard.parentElement;
    if(!rightStack || scalpCard.parentElement!==rightStack || !rightStack.classList.contains('right-stack')){
      document.documentElement.dataset.v15Layout='guarded-right-stack-drift';
      return false;
    }
    const primaryGrid=leftStack.parentElement;
    if(!primaryGrid || rightStack.parentElement!==primaryGrid || !primaryGrid.classList.contains('primary-grid')){
      document.documentElement.dataset.v15Layout='guarded-primary-grid-drift';
      return false;
    }
    if(primaryGrid.classList.contains('v15-primary-grid')){
      document.documentElement.dataset.v15Layout='installed';
      return true;
    }
    primaryGrid.classList.add('v15-primary-grid');
    leftStack.classList.add('v15-left-stack');
    rightStack.classList.add('v15-right-stack');
    primaryGrid.setAttribute('data-v15-semantic-order','FINAL_EARLY_TIMER_SCALP');
    document.documentElement.dataset.v15Layout='installed';
    return true;
  }
  window.installV15ResponsiveCore=installV15ResponsiveCore;
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',installV15ResponsiveCore,{once:true});
  }else{
    installV15ResponsiveCore();
  }
})();
</script>'''


def _counts(text: str, needles: tuple[str, ...]) -> dict[str, int]:
    return {needle: text.count(needle) for needle in needles}


def patch_v15(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")

    before_safety = _counts(text, SAFETY_ANCHORS)
    missing = {k: v for k, v in before_safety.items() if v < 1}
    if missing:
        raise RuntimeError(f"V15 safety anchor missing before patch: {missing}")

    card_counts = _counts(text, CARD_ANCHORS)
    if any(v != 1 for v in card_counts.values()):
        raise RuntimeError(f"V15 core card DOM drift; refusing layout patch: {card_counts}")

    timer_count = text.count('id="timerRemaining"')
    if timer_count != 1:
        raise RuntimeError(f"V15 requires one canonical timer; found {timer_count}")

    before_network = _counts(text, NETWORK_PRIMITIVES)
    before_cards = dict(card_counts)

    changes: list[str] = []
    if STYLE_ID not in text:
        if "</head>" not in text:
            raise RuntimeError("V15 </head> anchor missing")
        text = text.replace("</head>", V15_CSS + "\n</head>", 1)
        changes.append("inject-v15-responsive-css")

    if SCRIPT_ID not in text:
        if "</body>" not in text:
            raise RuntimeError("V15 </body> anchor missing")
        text = text.replace("</body>", V15_JS + "\n</body>", 1)
        changes.append("inject-v15-responsive-js")

    if MARKER not in text:
        text = text.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1)
        changes.append("v15-marker")

    after_safety = _counts(text, SAFETY_ANCHORS)
    if after_safety != before_safety:
        raise RuntimeError(f"V15 safety anchors changed: before={before_safety} after={after_safety}")

    after_cards = _counts(text, CARD_ANCHORS)
    if after_cards != before_cards:
        raise RuntimeError(f"V15 core card markup count changed: before={before_cards} after={after_cards}")

    after_network = _counts(text, NETWORK_PRIMITIVES)
    if after_network != before_network:
        raise RuntimeError(f"V15 network primitive count changed: before={before_network} after={after_network}")

    if text.count('id="timerRemaining"') != 1:
        raise RuntimeError("V15 duplicated canonical timer")
    if "flip_risk_percent" in text:
        raise RuntimeError("numeric Flip Risk unexpectedly present in V15 output")

    path.write_text(text, encoding="utf-8")
    return changes or ["v15-already-present"]


def build_dashboard() -> Path:
    html = v14.build_dashboard()
    patch_v15(html)
    return html


def main() -> int:
    html = build_dashboard()
    rendered = html.read_text(encoding="utf-8", errors="replace")
    print("COMBINED DASHBOARD UI V15 | RESPONSIVE CANDIDATE | SHADOW ONLY | NO ORDERS")
    if "--self-test" in sys.argv:
        assert rendered.count(STYLE_ID) == 1
        assert rendered.count(SCRIPT_ID) == 1
        assert rendered.count(MARKER) == 1
        assert rendered.count('id="timerRemaining"') == 1
        assert "grid-template-areas:" in rendered
        assert "guarded-left-stack-drift" in rendered
        assert "guarded-right-stack-drift" in rendered
        assert "guarded-primary-grid-drift" in rendered
        assert "data-v15-semantic-order','FINAL_EARLY_TIMER_SCALP'" in rendered
        assert "TRACKING ONLY · DON'T CHASE" in rendered
        assert "TRACKING ONLY · NO POSITION ASSUMED" in rendered
        assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in rendered
        assert "flip_risk_percent" not in rendered
        print("COMBINED DASHBOARD UI V15 SELFTEST PASS | RESPONSIVE STACKS · ONE TIMER · NO NEW POLLING · NO ORDERS")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
