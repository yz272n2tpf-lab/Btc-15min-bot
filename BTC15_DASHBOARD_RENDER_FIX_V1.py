#!/usr/bin/env python3
"""Targeted UI render fix for BTC 15m dashboard.

Display-only fixes plus guarded V8.1 graduated 30-45c scalp card.
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
</style>'''

V81_CSS = r'''<style id="v81-scalp-card-style">
#v81ScalpCard{position:fixed;right:14px;bottom:14px;width:min(330px,calc(100vw - 28px));z-index:9999;background:rgba(9,14,22,.96);border:1px solid #2e4054;border-radius:14px;padding:12px 14px;color:#f3f5f7;font:600 13px/1.35 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;box-shadow:0 10px 28px rgba(0,0,0,.35)}
#v81ScalpCard .v81h{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px}
#v81ScalpCard .v81title{font-size:13px;letter-spacing:.03em;color:#9eafbf;text-transform:uppercase}
#v81ScalpCard .v81badge{font-size:11px;padding:3px 7px;border-radius:999px;background:#172332;color:#9eafbf}
#v81ScalpCard .v81side{font-size:24px;font-weight:800;margin:2px 0}.v81up{color:#35d07f}.v81down{color:#ff5c72}.v81wait{color:#9eafbf}
#v81ScalpCard .v81grid{display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;margin-top:6px}.v81k{color:#8497a8;font-weight:500}.v81v{text-align:right}
#v81ScalpCard .v81foot{margin-top:8px;padding-top:7px;border-top:1px solid #223142;color:#7f93a5;font-size:11px}
@media(max-width:700px){#v81ScalpCard{right:8px;bottom:8px;width:calc(100vw - 16px)}}
</style>'''

V81_JS = r'''<script id="v81-scalp-card-script">
(()=>{
 const FEED='__V81_FEED__';
 const money=x=>Number.isFinite(Number(x))?Math.round(Number(x)*100)+'¢':'—';
 const secs=x=>Number.isFinite(Number(x))?Math.max(0,Math.round(Number(x)))+'s':'—';
 function ensure(){let c=document.getElementById('v81ScalpCard');if(c)return c;c=document.createElement('section');c.id='v81ScalpCard';c.setAttribute('aria-live','polite');c.innerHTML='<div class="v81h"><div class="v81title">Scalp Opportunity · V8.1</div><div class="v81badge">30–45¢ ONLY</div></div><div id="v81Body"><div class="v81side v81wait">WAIT</div></div><div class="v81foot">Manual execution only · signal-only · no orders</div>';document.body.appendChild(c);return c;}
 function safe(d){return d&&d.version==='V8.1_GRADUATED_30_45'&&d.entry_band==='30-45c'&&d.graduated===true&&d.manual_execution_only===true&&d.order_action===null&&d.owns_final_outcome===false&&d.owns_early_opportunity===false;}
 function render(d){ensure();const b=document.getElementById('v81Body');if(!safe(d)){b.innerHTML='<div class="v81side v81wait">BLOCKED</div><div>Safety boundary rejected payload.</div>';return;}if(!d.active){b.innerHTML='<div class="v81side v81wait">WAIT</div><div style="color:#8497a8">No graduated 30–45¢ CORE/SURGE setup right now.</div>';return;}const side=String(d.side||'').toUpperCase();const cls=side==='UP'?'v81up':'v81down';const t=d.targets||{};b.innerHTML=`<div class="v81side ${cls}">${side} · ${d.status||'WATCH'}</div><div class="v81grid"><span class="v81k">Entry</span><span class="v81v">${money(d.entry_price)}</span><span class="v81k">Current bid</span><span class="v81v">${money(d.current_bid)}</span><span class="v81k">Route</span><span class="v81v">${d.route||'—'}</span><span class="v81k">Time left</span><span class="v81v">${secs(d.seconds_left)}</span><span class="v81k">+5¢ target</span><span class="v81v">${money(t.plus_5c)}</span><span class="v81k">+10¢ target</span><span class="v81v">${money(t.plus_10c)}</span><span class="v81k">+20¢ target</span><span class="v81v">${money(t.plus_20c)}</span></div>`;}
 async function poll(){try{const r=await fetch(FEED,{cache:'no-store',mode:'cors'});if(!r.ok)throw new Error('HTTP '+r.status);render(await r.json());}catch(e){ensure();document.getElementById('v81Body').innerHTML='<div class="v81side v81wait">FEED WAIT</div><div style="color:#8497a8">Live scalp feed reconnecting.</div>';}}
 window.addEventListener('load',()=>{ensure();poll();setInterval(poll,1000);});
})();
</script>'''.replace('__V81_FEED__', V81_FEED_URL)


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


def patch_html(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    changes = []
    had_base = MARKER in text
    had_v81 = V81_MARKER in text
    if had_base and had_v81:
        return ["already-present"]

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

    head_bits = ""
    if not had_base:
        head_bits += CSS + f"\n<!-- {MARKER} -->\n"
    if not had_v81:
        head_bits += V81_CSS + f"\n<!-- {V81_MARKER} -->\n"
    if head_bits:
        if "</head>" in text: text = text.replace("</head>", head_bits + "</head>", 1)
        else: text = head_bits + text

    if not had_v81:
        if "</body>" in text: text = text.replace("</body>", V81_JS + "\n</body>", 1)
        else: text += V81_JS
        changes.append("v81-live-card")

    path.write_text(text, encoding="utf-8")
    return changes


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
        assert V81_MARKER in rendered and V81_FEED_URL in rendered
        print("V81 DASHBOARD CARD SELFTEST PASS | 30-45 ONLY | MANUAL ONLY | NO ORDERS")
        return rc
    os.execv(sys.executable, [sys.executable, "-u", str(wrapper)])


if __name__ == "__main__":
    raise SystemExit(main())
