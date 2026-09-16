#!/usr/bin/env python3
"""BTC15 combined dashboard UI V15 candidate — responsive core layout.

SHADOW PRESENTATION CANDIDATE ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

V15 wraps the exact V14 generated dashboard and changes presentation only:
- groups the existing FINAL / EARLY / TIMER / SCALP cards into one responsive
  core-grid container at runtime;
- preserves one canonical timer;
- uses one-column phone layout and two-column tablet/desktop layouts;
- preserves every existing card id/class, data source, event listener and state;
- adds no network client, no polling, no signal threshold, no order path;
- fails closed to the unchanged V14 layout if the expected four cards do not
  share one DOM parent.

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
#v15CoreGrid{
  width:100%;
  min-width:0;
  box-sizing:border-box;
  grid-column:1 / -1;
}
.v15-core-grid{
  display:grid!important;
  grid-template-columns:minmax(0,1fr);
  grid-template-areas:
    "final"
    "early"
    "timer"
    "scalp";
  gap:12px!important;
  align-items:stretch;
}
.v15-core-grid > #finalCard{grid-area:final;}
.v15-core-grid > .early-card{grid-area:early;}
.v15-core-grid > .timer-card{grid-area:timer;}
.v15-core-grid > #scalpCard{grid-area:scalp;}
.v15-core-grid > #finalCard,
.v15-core-grid > .early-card,
.v15-core-grid > .timer-card,
.v15-core-grid > #scalpCard{
  width:100%;
  min-width:0;
  max-width:none;
  margin:0!important;
  box-sizing:border-box;
}
/* Prevent whole-card transition flicker. Semantic classes may still change instantly. */
.v15-core-grid > #finalCard,
.v15-core-grid > .early-card,
.v15-core-grid > .timer-card,
.v15-core-grid > #scalpCard{transition:none!important;}
/* Keep long changing copy inside already-reserved slots. */
#finalActionSub,#earlyEntry,#earlyFlow{overflow:hidden!important;}

@media (min-width:768px) and (max-width:1180px){
  .v15-core-grid{
    grid-template-columns:minmax(0,1fr) minmax(0,1fr);
    grid-template-areas:
      "final final"
      "early timer"
      "scalp scalp";
    gap:14px!important;
  }
}
@media (min-width:1181px){
  .v15-core-grid{
    grid-template-columns:minmax(0,1.2fr) minmax(0,.8fr);
    grid-template-areas:
      "final early"
      "timer scalp";
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
    const cards=[finalCard,earlyCard,timerCard,scalpCard];
    if(cards.some(card=>!card)){
      document.documentElement.dataset.v15Layout='guarded-missing-card';
      return false;
    }
    if(document.getElementById('v15CoreGrid')){
      document.documentElement.dataset.v15Layout='installed';
      return true;
    }
    const parent=finalCard.parentElement;
    if(!parent || cards.some(card=>card.parentElement!==parent)){
      document.documentElement.dataset.v15Layout='guarded-parent-drift';
      return false;
    }
    const children=Array.from(parent.children);
    const indexes=cards.map(card=>children.indexOf(card));
    if(indexes.some(index=>index<0)){
      document.documentElement.dataset.v15Layout='guarded-index-drift';
      return false;
    }
    const firstIndex=Math.min(...indexes);
    const reference=children[firstIndex];
    const grid=document.createElement('section');
    grid.id='v15CoreGrid';
    grid.className='v15-core-grid';
    grid.setAttribute('aria-label','Primary BTC 15 minute signal cards');
    parent.insertBefore(grid,reference);
    /* Frozen semantic order: FINAL, EARLY, canonical TIMER, SCALP. */
    cards.forEach(card=>grid.appendChild(card));
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
        assert "guarded-parent-drift" in rendered
        assert "TRACKING ONLY · DON'T CHASE" in rendered
        assert "TRACKING ONLY · NO POSITION ASSUMED" in rendered
        assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in rendered
        assert "flip_risk_percent" not in rendered
        print("COMBINED DASHBOARD UI V15 SELFTEST PASS | RESPONSIVE · ONE TIMER · NO NEW POLLING · NO ORDERS")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
