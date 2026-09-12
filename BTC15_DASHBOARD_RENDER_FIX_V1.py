#!/usr/bin/env python3
"""Targeted UI render fix for BTC 15m dashboard.

Display-only fixes. V8.1 live feed remains available on the backend, but no
new floating/overlay card is allowed in the locked production dashboard.
No trading, scoring, Kalshi, or order logic is changed.
"""
from pathlib import Path
import os
import sys

MARKER = "BTC15_RENDER_FIX_V4"
V81_MARKER = "V81_SCALP_CARD_V1"
V81_FEED_URL = "https://v81-30-45-live-feed-v2-production.up.railway.app/state"

CSS = r'''<style id="btc15-render-fix-v4">
#btcPrice { color:#f3f5f7 !important; opacity:1 !important; text-shadow:none !important; }
.chart-card > svg { opacity:1 !important; visibility:visible !important; transition:none !important; animation:none !important; }
#finalReason {
  min-height:4.2em !important;
  height:4.2em !important;
  line-height:1.4em !important;
  overflow:hidden !important;
  display:-webkit-box !important;
  -webkit-line-clamp:3 !important;
  -webkit-box-orient:vertical !important;
}
#finalActionSub { min-height:2.8em !important; }
/* UI LOCK: never allow the temporary V8.1 overlay to alter the frozen layout. */
#v81ScalpCard { display:none !important; }
</style>'''

# The backend V8.1 feed stays live for the next proper in-layout integration.
# No new DOM card is injected in production while the dashboard aesthetics are frozen.


def inject_gap_color_at_render_end(text: str) -> tuple[str, bool]:
    sig = "function renderBrtiDisplay("
    start = text.find(sig)
    if start < 0:
        return text, False
    next_fn = text.find("function ", start + len(sig))
    if next_fn < 0:
        next_fn = len(text)
    segment = text[start:next_fn]
    close = segment.rfind("}")
    if close < 0:
        return text, False
    code = (
        " if(gap){const _gt=(gap.textContent||'').trim();"
        "const _neg=/[-\\u2212]/.test(_gt);"
        "const _hasNum=/\\d/.test(_gt);"
        "gap.style.setProperty('color',_neg?'#ff4d67':(_hasNum?'#35d07f':'#f3f5f7'),'important');}"
    )
    abs_close = start + close
    return text[:abs_close] + code + text[abs_close:], True


def remove_v81_overlay(text: str) -> tuple[str, bool]:
    """Remove the temporary injected V8.1 style/script if present in persisted HTML."""
    changed = False
    style_start = text.find('<style id="v81-scalp-card-style">')
    if style_start >= 0:
        style_end = text.find('</style>', style_start)
        if style_end >= 0:
            text = text[:style_start] + text[style_end + len('</style>'):]
            changed = True
    script_start = text.find('<script id="v81-scalp-card-script">')
    if script_start >= 0:
        script_end = text.find('</script>', script_start)
        if script_end >= 0:
            text = text[:script_start] + text[script_end + len('</script>'):]
            changed = True
    text = text.replace(f'<!-- {V81_MARKER} -->', '')
    return text, changed


def patch_html(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    changes = []

    text, removed = remove_v81_overlay(text)
    if removed:
        changes.append("v81-overlay-removed")

    old = "if(chart){chart.style.opacity=current?'1':'.4';chart.dataset.stale=current?'false':'true';}"
    new = "if(chart){chart.style.opacity='1';chart.dataset.stale=current?'false':'true';}"
    if old in text:
        text = text.replace(old, new); changes.append("chart-opacity")

    old2 = "const chart=document.querySelector('.chart-card > svg');if(chart){chart.style.opacity='.4';chart.dataset.stale='true';}"
    new2 = "const chart=document.querySelector('.chart-card > svg');if(chart){chart.style.opacity='1';chart.dataset.stale='true';}"
    if old2 in text:
        text = text.replace(old2, new2); changes.append("chart-unavailable-opacity")

    old3 = "svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.textContent='';"
    new3 = "const oldChartNodes=Array.from(svg.childNodes);svg.setAttribute('viewBox',`0 0 ${w} ${h}`);"
    if old3 in text:
        text = text.replace(old3, new3); changes.append("chart-no-preclear")

    old4 = "if(!pts.length){add('text',{x:12,y:28,fill:'#9eafbf','font-size':12},'BRTI history unavailable — no substitute price');return;}"
    new4 = "if(!pts.length){add('text',{x:12,y:28,fill:'#9eafbf','font-size':12},'BRTI history unavailable — no substitute price');oldChartNodes.forEach(n=>n.remove());return;}"
    if old4 in text:
        text = text.replace(old4, new4); changes.append("chart-empty-cleanup")

    old5 = "svg.onpointermove=event=>{"
    new5 = "oldChartNodes.forEach(n=>n.remove());svg.onpointermove=event=>{"
    if old5 in text:
        text = text.replace(old5, new5, 1); changes.append("chart-postdraw-swap")

    price_hook = "function renderBrtiDisplay(d,forcedUnavailable=false){ const price=$('btcPrice'), gap=$('btcGap');"
    price_new = "function renderBrtiDisplay(d,forcedUnavailable=false){ const price=$('btcPrice'), gap=$('btcGap'); if(price){price.style.setProperty('color','#f3f5f7','important');price.style.setProperty('opacity','1','important');}"
    if price_hook in text:
        text = text.replace(price_hook, price_new); changes.append("price-fixed-color")

    text, gap_ok = inject_gap_color_at_render_end(text)
    if gap_ok: changes.append("gap-native-red-green")

    old6 = "setText('finalActionSub',f.ready?`${pref} FINAL qualified · ${fmtPct(conf,1)}`:`Continuous ${pref||'direction'} probability · FINAL not qualified`);"
    new6 = "setText('finalActionSub',f.ready?`${pref} FINAL qualified · ${fmtPct(conf,1)}`:(Number.isFinite(conf)&&conf>=0.90?`${pref} probability ${fmtPct(conf,1)} · FINAL gate still pending`:`Continuous ${pref||'direction'} probability · FINAL not qualified`));"
    if old6 in text:
        text = text.replace(old6, new6); changes.append("final-90-pending-label")

    latch_anchor = "let lastBrtiDisplay=null; let lastChartSignature=null;"
    latch_new = "let lastBrtiDisplay=null; let lastChartSignature=null; let latchedFinal=null;"
    if latch_anchor in text:
        text = text.replace(latch_anchor, latch_new, 1); changes.append("final-latch-state")

    apply_old = "function applyState(d,drawChart=true){ const usable=usableFrame(d); // Keep raw qualification diagnostics but never present stale data as action. d={...d,final:{...d.final,ready:usable && freshBrti(d) && d.final?.ready===true}, early:{...d.early,ready:usable && d.early?.ready===true}, scalp:{...d.scalp,ready:usable && d.scalp?.ready===true}};"
    apply_new = "function applyState(d,drawChart=true){ const usable=usableFrame(d); const rawFinalReady=d.final?.ready===true; if(latchedFinal&&latchedFinal.contract!==d.contract)latchedFinal=null; if(usable&&freshBrti(d)&&rawFinalReady){latchedFinal={contract:d.contract,side:(d.final?.side||d.market?.preferred_side||'').toUpperCase(),confidence:N(d.final?.confidence)};} const finalLatched=Boolean(latchedFinal&&latchedFinal.contract===d.contract); d={...d,final:{...d.final,ready:(usable && freshBrti(d) && rawFinalReady)||finalLatched,side:finalLatched?(d.final?.side||latchedFinal.side):d.final?.side,confidence:finalLatched&& !Number.isFinite(N(d.final?.confidence))?latchedFinal.confidence:d.final?.confidence}, early:{...d.early,ready:usable && d.early?.ready===true}, scalp:{...d.scalp,ready:usable && d.scalp?.ready===true}};"
    if apply_old in text:
        text = text.replace(apply_old, apply_new, 1); changes.append("final-qualified-latch")

    if MARKER not in text:
        if "</head>" in text:
            text = text.replace("</head>", CSS + f"\n<!-- {MARKER} -->\n</head>", 1)
        else:
            text = CSS + f"\n<!-- {MARKER} -->\n" + text
    elif '#v81ScalpCard { display:none !important; }' not in text:
        if "</head>" in text:
            text = text.replace("</head>", '<style id="v81-ui-lock">#v81ScalpCard{display:none!important}</style>\n</head>', 1)

    path.write_text(text, encoding="utf-8")
    return changes or ["ui-lock-preserved"]


def main() -> int:
    import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
    d = installer.install()
    html = d / "BTC_Kalshi_App_Live_v13.html"
    if not html.exists():
        raise SystemExit(f"dashboard html missing: {html}")
    changes = patch_html(html)
    print("RENDER FIX V4 | " + ",".join(changes))

    wrapper = d / "BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py"
    if "--self-test" in sys.argv:
        import subprocess
        rc = subprocess.run([sys.executable, str(wrapper), "--self-test"]).returncode
        rendered = html.read_text(encoding="utf-8", errors="replace")
        assert 'v81-scalp-card-script' not in rendered
        assert 'position:fixed' not in rendered or 'v81ScalpCard' not in rendered
        print("UI LOCK SELFTEST PASS | NO V8.1 OVERLAY | EXISTING DASHBOARD LAYOUT PRESERVED")
        return rc
    os.execv(sys.executable, [sys.executable, "-u", str(wrapper)])


if __name__ == "__main__":
    raise SystemExit(main())
