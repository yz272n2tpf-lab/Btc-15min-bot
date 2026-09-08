#!/usr/bin/env python3
"""UI-only runtime patch for BTC 15m dashboard.

Goals:
- stop visible chart/price flashing caused by repeated redraw styling
- keep live BTC price color stable
- keep FINAL OUTCOME card height stable when reasoning text length changes

No trading/scoring logic is modified.
"""
from pathlib import Path
import os
import sys

MARKER = "BTC15_UI_STABILITY_PATCH_V1"

CSS = r'''<style id="btc15-ui-stability-css">
/* BTC15_UI_STABILITY_PATCH_V1 */
html, body { background:#07090d !important; }
* { animation:none !important; transition:none !important; }
canvas, svg { opacity:1 !important; visibility:visible !important; }
[data-btc15-final-card="1"] {
  min-height: 210px !important;
  height: 210px !important;
  max-height: 210px !important;
  overflow: hidden !important;
  box-sizing: border-box !important;
}
[data-btc15-final-reason="1"] {
  max-height: 92px !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  overscroll-behavior: contain !important;
}
[data-btc15-live-price="1"] {
  color: #f3f5f7 !important;
  opacity: 1 !important;
  text-shadow: none !important;
}
</style>'''

JS = r'''<script id="btc15-ui-stability-js">
(() => {
  const MARK = 'BTC15_UI_STABILITY_PATCH_V1';
  const priceRx = /^\s*\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?\s*$/;

  function text(el){ return (el && el.textContent || '').replace(/\s+/g,' ').trim(); }

  function closestCard(el){
    let n = el;
    for(let i=0; n && i<8; i++, n=n.parentElement){
      const r = n.getBoundingClientRect ? n.getBoundingClientRect() : null;
      const t = text(n).toUpperCase();
      if(r && r.width > 180 && r.height > 80 && t.includes('FINAL OUTCOME')) return n;
    }
    return null;
  }

  function stabilizeFinalOutcome(){
    const all = Array.from(document.querySelectorAll('body *'));
    const label = all.find(el => {
      const t = text(el).toUpperCase();
      return t === 'FINAL OUTCOME' || t.startsWith('FINAL OUTCOME ');
    });
    if(!label) return;
    const card = closestCard(label);
    if(!card) return;
    card.setAttribute('data-btc15-final-card','1');

    const candidates = Array.from(card.querySelectorAll('div,p,span'))
      .filter(el => {
        const t = text(el);
        return t.length > 28 && !t.toUpperCase().startsWith('FINAL OUTCOME');
      });
    if(candidates.length){
      candidates.sort((a,b) => text(b).length - text(a).length);
      candidates[0].setAttribute('data-btc15-final-reason','1');
    }
  }

  function stabilizeLivePrice(){
    const nodes = Array.from(document.querySelectorAll('body *')).filter(el => {
      if(el.children.length) return false;
      const t = text(el);
      if(!priceRx.test(t)) return false;
      const v = Number(t.replace(/[$,]/g,''));
      return Number.isFinite(v) && v > 1000;
    });
    if(!nodes.length) return;

    // Prefer the price nearest a chart/canvas/svg, otherwise the largest price-like label.
    let best = nodes[0], bestScore = -1;
    for(const el of nodes){
      const r = el.getBoundingClientRect();
      let score = Math.max(0, 80 - Math.abs(r.top - window.innerHeight * 0.45));
      let p = el.parentElement;
      for(let i=0; p && i<6; i++, p=p.parentElement){
        if(p.querySelector && p.querySelector('canvas,svg')) score += 120;
      }
      score += Math.min(40, parseFloat(getComputedStyle(el).fontSize) || 0);
      if(score > bestScore){ bestScore = score; best = el; }
    }
    best.setAttribute('data-btc15-live-price','1');
    best.style.setProperty('color','#f3f5f7','important');
    best.style.setProperty('opacity','1','important');
  }

  function stabilizeChart(){
    document.querySelectorAll('canvas,svg').forEach(el => {
      el.style.setProperty('opacity','1','important');
      el.style.setProperty('visibility','visible','important');
      el.style.setProperty('transition','none','important');
      el.style.setProperty('animation','none','important');
    });
  }

  let scheduled = false;
  function apply(){
    scheduled = false;
    stabilizeFinalOutcome();
    stabilizeLivePrice();
    stabilizeChart();
  }
  function schedule(){
    if(scheduled) return;
    scheduled = true;
    requestAnimationFrame(apply);
  }

  document.addEventListener('DOMContentLoaded', apply, {once:true});
  if(document.readyState !== 'loading') apply();
  new MutationObserver(schedule).observe(document.documentElement, {
    subtree:true, childList:true, characterData:true, attributes:true,
    attributeFilter:['class','style']
  });
  setInterval(apply, 1000);
  console.info(MARK, 'active');
})();
</script>'''


def patch_html(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    if "</head>" in text:
        text = text.replace("</head>", CSS + "\n</head>", 1)
    else:
        text = CSS + "\n" + text
    if "</body>" in text:
        text = text.replace("</body>", JS + "\n</body>", 1)
    else:
        text += "\n" + JS
    path.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
    d = installer.install()
    html = d / "BTC_Kalshi_App_Live_v13.html"
    if not html.exists():
        raise SystemExit(f"dashboard html missing: {html}")
    changed = patch_html(html)
    print(f"UI STABILITY PATCH | {'applied' if changed else 'already present'} | {html}")
    wrapper = d / "BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py"
    if "--self-test" in sys.argv:
        import subprocess
        return subprocess.run([sys.executable, str(wrapper), "--self-test"]).returncode
    os.execv(sys.executable, [sys.executable, "-u", str(wrapper)])


if __name__ == "__main__":
    raise SystemExit(main())
