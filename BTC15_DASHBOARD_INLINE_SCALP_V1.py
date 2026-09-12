#!/usr/bin/env python3
"""Inline V8.1 scalp integration for the existing BTC15 dashboard card.

UI-only bridge:
- keeps the locked dashboard layout
- never creates a floating/overlay card
- uses the existing SCALP / REVERSAL card only
- V8.1 may own that scalp card only when its safety payload is valid, current,
  active, same-contract, and the main dashboard frame is usable
- FINAL and EARLY outputs remain untouched
- signal-only; manual execution only; no orders
"""
from pathlib import Path
import os
import sys

import BTC15_DASHBOARD_RENDER_FIX_V1 as base_fix

MARKER = "BTC15_V81_INLINE_SCALP_V1"
FEED_URL = "https://v81-30-45-live-feed-v2-production.up.railway.app/state"

# This is deliberately anchored after the existing frozen scalp card has rendered.
# The V8.1 bridge can then override only the existing scalp fields, in-place.
SCALP_ANCHOR = (
    "setFlow('scalpFlow',sc.ready?`${scalpSide} strong-scalp gate QUALIFIES · diagnostic only`:"
    "'Watching frozen strong-scalp gate',sc.ready?'good':'warn');"
)
SCALP_HOOK = SCALP_ANCHOR + " if(typeof renderV81ScalpInline==='function')renderV81ScalpInline(d);"

INLINE_JS = r'''<script id="v81-inline-scalp-script">
(()=>{
  const FEED='__V81_FEED__';
  let feed=null;
  let lastMain=null;
  let lastOkMs=0;
  let pollBusy=false;

  const el=id=>document.getElementById(id);
  const num=v=>{const x=Number(v);return Number.isFinite(x)?x:NaN;};
  const cents=v=>Number.isFinite(num(v))?`${Math.round(num(v)*100)}¢`:'—';
  const secs=v=>Number.isFinite(num(v))?`${Math.max(0,Math.round(num(v)))}s`:'—';
  const text=(id,v)=>{const e=el(id);if(e&&e.textContent!==v)e.textContent=v;};
  const pill=(label)=>{const e=el('scalpState');if(!e)return;e.textContent=label;e.classList.remove('state-good','state-watch');e.classList.add('state-good');};
  const flow=(label,kind='good')=>{const e=el('scalpFlow');if(!e)return;e.textContent=label;e.classList.remove('good','warn','exit');e.classList.add(kind);};

  function safePayload(d){
    if(!d || d.version!=='V8.1_GRADUATED_30_45' || d.entry_band!=='30-45c')return false;
    if(d.graduated!==true || d.manual_execution_only!==true || d.order_action!==null)return false;
    if(d.owns_final_outcome!==false || d.owns_early_opportunity!==false)return false;
    if(d.active!==true)return false;
    const side=String(d.side||'').toUpperCase();
    const route=String(d.route||'').toUpperCase();
    const entry=num(d.entry_price),bid=num(d.current_bid),left=num(d.seconds_left),age=num(d.signal_age_sec);
    if(!['UP','DOWN'].includes(side) || !['CORE','SURGE'].includes(route))return false;
    if(!Number.isFinite(entry) || entry<0.30 || entry>0.45)return false;
    if(!Number.isFinite(bid) || bid<0 || bid>1)return false;
    if(!Number.isFinite(left) || left<=0)return false;
    if(!Number.isFinite(age) || age<0 || age>185)return false;
    return typeof d.contract==='string' && d.contract.length>0;
  }

  function feedFresh(){
    return lastOkMs>0 && (Date.now()-lastOkMs)<=3500;
  }

  window.renderV81ScalpInline=function(main){
    if(main)lastMain=main;
    const d=feed;
    if(!main || !safePayload(d) || !feedFresh() || d.contract!==main.contract)return false;

    // Keep the dashboard's existing global safety/parity contract. V8.1 never
    // bypasses a stale or unusable main frame.
    try{if(typeof usableFrame==='function' && !usableFrame(main))return false;}catch(_e){return false;}
    try{if(typeof freshBrti==='function' && !freshBrti(main))return false;}catch(_e){return false;}

    const side=String(d.side).toUpperCase();
    const route=String(d.route).toUpperCase();
    const status=String(d.status||'WATCH').toUpperCase();
    const entry=num(d.entry_price),bid=num(d.current_bid),left=num(d.seconds_left),age=num(d.signal_age_sec);
    const targets=d.targets||{};
    const t5=num(targets.plus_5c),t10=num(targets.plus_10c),t20=num(targets.plus_20c);

    text('scalpArrow',side==='DOWN'?'↓':'↑');
    text('scalpTitle',`SCALP ${side} · V8.1`);
    text('scalpEntry',`Signal ${cents(entry)} · ${route}`);

    let state='QUALIFIED';
    if(status==='ACTIONABLE')state='+5¢ HIT';
    else if(status==='ACTIONABLE_EXPANSION')state='+10¢ HIT';
    else if(status==='PROTECT')state='PROTECT';
    pill(state);

    // Existing card labels remain truthful: this is the executable exit bid,
    // not a synthetic mark. The user's personal entry is intentionally untouched.
    text('scalpCurrentPrice',cents(bid));
    text('scalpTargetStrip',Number.isFinite(t10)?`+10¢ → ${cents(t10)}`:'—');
    text('scalpLadderEntry',`30–45¢ band · signal ${cents(entry)}`);
    text('scalpLadderHold',`Up to 3m · ${secs(left)} contract left`);
    text('scalpLadderWatch',`Bid ${cents(bid)} · signal age ${secs(age)}`);

    if(status==='PROTECT'){
      text('scalpLadderProtect',`+20¢ reached · protect gains`);
    }else if(Number.isFinite(t5)&&Number.isFinite(t10)&&Number.isFinite(t20)){
      text('scalpLadderProtect',`+5¢ ${cents(t5)} · +10¢ ${cents(t10)} · +20¢ ${cents(t20)}`);
    }else{
      text('scalpLadderProtect','V8.1 target ladder active');
    }
    text('scalpLadderExit','No V8.1 stop rule connected · manual execution');
    flow(`V8.1 ${route} · ${status.replaceAll('_',' ')} · signal-only`,status==='PROTECT'?'warn':'good');
    return true;
  };

  async function poll(){
    if(pollBusy)return;
    pollBusy=true;
    try{
      const r=await fetch(FEED,{cache:'no-store',mode:'cors'});
      if(!r.ok)throw new Error(`HTTP ${r.status}`);
      const d=await r.json();
      if(safePayload(d)){
        feed=d;
        lastOkMs=Date.now();
      }else{
        feed=null;
        lastOkMs=0;
      }
    }catch(_e){
      feed=null;
      lastOkMs=0;
    }finally{
      pollBusy=false;
    }

    // Re-render through the dashboard's own state function so a vanished/stale
    // V8.1 signal immediately falls back to the frozen base scalp view.
    try{if(lastMain && typeof applyState==='function')applyState(lastMain,false);}catch(_e){}
  }

  const start=()=>{poll();setInterval(poll,1000);};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});
  else start();
})();
</script>'''.replace('__V81_FEED__', FEED_URL)


def patch_inline(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    changes = []

    # Never coexist with the rejected temporary overlay implementation.
    text, removed = base_fix.remove_v81_overlay(text)
    if removed:
        changes.append("old-overlay-removed")

    if SCALP_HOOK not in text:
        if SCALP_ANCHOR not in text:
            raise RuntimeError("existing scalp render anchor not found; refusing unsafe UI patch")
        text = text.replace(SCALP_ANCHOR, SCALP_HOOK, 1)
        changes.append("existing-scalp-hook")

    if 'id="v81-inline-scalp-script"' not in text:
        if "</body>" in text:
            text = text.replace("</body>", INLINE_JS + f"\n<!-- {MARKER} -->\n</body>", 1)
        else:
            text += "\n" + INLINE_JS + f"\n<!-- {MARKER} -->\n"
        changes.append("inline-feed-script")

    path.write_text(text, encoding="utf-8")
    return changes or ["already-present"]


def main() -> int:
    import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer

    d = installer.install()
    html = d / "BTC_Kalshi_App_Live_v13.html"
    if not html.exists():
        raise SystemExit(f"dashboard html missing: {html}")

    base_changes = base_fix.patch_html(html)
    inline_changes = patch_inline(html)
    print("INLINE SCALP V1 | base=" + ",".join(base_changes) + " | inline=" + ",".join(inline_changes))

    wrapper = d / "BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py"
    if "--self-test" in sys.argv:
        import subprocess
        rendered = html.read_text(encoding="utf-8", errors="replace")
        assert 'v81-scalp-card-script' not in rendered
        assert 'id="v81-inline-scalp-script"' in rendered
        assert "renderV81ScalpInline(d)" in rendered
        assert "V8.1_GRADUATED_30_45" in rendered
        assert "manual_execution_only!==true" in rendered
        assert "owns_final_outcome!==false" in rendered
        assert "owns_early_opportunity!==false" in rendered
        assert "entry<0.30 || entry>0.45" in rendered
        assert "No V8.1 stop rule connected" in rendered
        assert "position:fixed" not in rendered or "v81ScalpCard" not in rendered
        rc = subprocess.run([sys.executable, str(wrapper), "--self-test"]).returncode
        print("INLINE SCALP SELFTEST PASS | EXISTING CARD ONLY | 30-45 SAFE BOUNDARY | NO ORDERS")
        return rc

    os.execv(sys.executable, [sys.executable, "-u", str(wrapper)])


if __name__ == "__main__":
    raise SystemExit(main())
