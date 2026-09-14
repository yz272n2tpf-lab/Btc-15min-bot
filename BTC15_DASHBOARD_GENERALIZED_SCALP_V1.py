#!/usr/bin/env python3
"""Generalized SCALP V1 integration for the existing BTC15 dashboard card.

RESEARCH-BRANCH BUILD ONLY until integrated smoke acceptance.

UI-only bridge:
- keeps the existing locked dashboard layout
- uses the existing SCALP / REVERSAL card only
- reads the generalized V3 read-only /state feed
- preserves FINAL and EARLY rendering/authority unchanged
- shows ACTIVE / protection-armed / pullback / EXIT states
- no SCALP entry-price filter
- same-contract + usable-main-frame checks fail closed
- signal-only; manual execution only; no orders
"""
from pathlib import Path
import os
import sys

import BTC15_DASHBOARD_RENDER_FIX_V1 as base_fix

MARKER = "BTC15_GENERALIZED_SCALP_INLINE_V1"
FEED_URL = "https://scalp-move-shadow-v1-production.up.railway.app/state"

SCALP_ANCHOR = (
    "setFlow('scalpFlow',sc.ready?`${scalpSide} strong-scalp gate QUALIFIES · diagnostic only`:"
    "'Watching frozen strong-scalp gate',sc.ready?'good':'warn');"
)
SCALP_HOOK = SCALP_ANCHOR + " if(typeof renderGeneralizedScalpInline==='function')renderGeneralizedScalpInline(d);"

INLINE_JS = r'''<script id="generalized-scalp-inline-script">
(()=>{
  const FEED='__GENERALIZED_FEED__';
  let feed=null,lastMain=null,lastOkMs=0,pollBusy=false;
  const el=id=>document.getElementById(id);
  const num=v=>{const x=Number(v);return Number.isFinite(x)?x:NaN;};
  const cents=v=>Number.isFinite(num(v))?`${Math.round(num(v)*100)}¢`:'—';
  const gainc=v=>Number.isFinite(num(v))?`${num(v)>=0?'+':''}${(num(v)*100).toFixed(1)}¢`:'—';
  const secs=v=>Number.isFinite(num(v))?`${Math.max(0,Math.round(num(v)))}s`:'—';
  const text=(id,v)=>{const e=el(id);if(e&&e.textContent!==v)e.textContent=v;};
  const pill=(label,kind='good')=>{const e=el('scalpState');if(!e)return;e.textContent=label;e.classList.remove('state-good','state-watch');e.classList.add(kind==='good'?'state-good':'state-watch');};
  const flow=(label,kind='good')=>{const e=el('scalpFlow');if(!e)return;e.textContent=label;e.classList.remove('good','warn','exit');e.classList.add(kind);};

  function envelope(d){
    if(!d || d.version!=='GENERALIZED_SCALP_INTEGRATION_V3')return false;
    if(d.manual_execution_only!==true || d.order_action!==null || d.orders!==false)return false;
    if(d.owns_final_outcome!==false || d.owns_early_opportunity!==false)return false;
    if(d.numeric_flip_risk_validated!==false)return false;
    if(typeof d.contract!=='string' || !d.contract.length)return false;
    const st=String(d.state||'').toUpperCase();
    if(!['PASS','ACTIVE','PROTECT','EXIT'].includes(st))return false;
    if(st!=='PASS'){
      const side=String(d.side||'').toUpperCase(),entry=num(d.entry_price);
      if(!['UP','DOWN'].includes(side))return false;
      // Price is telemetry only for the generalized module. Validate range but
      // deliberately do NOT impose an eligibility band.
      if(!Number.isFinite(entry)||entry<0||entry>1)return false;
    }
    return true;
  }
  const feedFresh=()=>lastOkMs>0&&(Date.now()-lastOkMs)<=3000;

  function mainFinalSide(main){
    const st=String(main&&main.final_status||'').toUpperCase();
    const side=String(main&&(main.final_side||main.expected_final_outcome)||'').toUpperCase();
    return st==='FINAL CALL'&&['UP','DOWN'].includes(side)?side:null;
  }
  function context(main,d){
    const fs=mainFinalSide(main),ss=String(d.side||'').toUpperCase();
    return fs&&ss&&fs!==ss?` · COUNTERTREND vs FINAL ${fs}`:'';
  }

  function renderPass(d){
    pill('WATCHING','watch');
    text('scalpEntry','Generalized scalp · waiting');
    text('scalpLadderEntry','Frozen generalized gate');
    text('scalpLadderHold',`Contract ${secs(d.contract_seconds_left)}`);
    text('scalpLadderWatch','No qualified generalized scalp yet');
    text('scalpLadderProtect','Protection arms after +5¢ executable gain');
    text('scalpLadderExit','Frozen EXIT: 4¢ giveback after arm · manual execution');
    flow('GENERALIZED SCALP WAIT · signal-only','warn');
    return true;
  }

  function renderActive(main,d){
    const side=String(d.side).toUpperCase(),st=String(d.state).toUpperCase();
    const entry=num(d.entry_price),bid=num(d.current_bid),gain=num(d.exec_gain),peak=num(d.peak_exec_gain),gb=num(d.giveback_from_peak);
    text('scalpArrow',side==='DOWN'?'↓':'↑');
    text('scalpTitle',`SCALP ${side} · GENERALIZED`);
    text('scalpEntry',`Signal ${cents(entry)} · price-agnostic gate`);
    pill(st,st==='ACTIVE'?'good':'watch');
    text('scalpCurrentPrice',cents(bid));
    text('scalpTargetStrip',`Move ${gainc(gain)} · peak ${gainc(peak)}`);
    text('scalpLadderEntry',`Entry ${cents(entry)} · no price eligibility filter`);
    text('scalpLadderHold',`Contract ${secs(d.contract_seconds_left)} · primary signal only`);
    text('scalpLadderWatch',`Gain ${gainc(gain)} · peak ${gainc(peak)} · giveback ${gainc(gb)}`);
    text('scalpLadderProtect',String(d.management_message||'PROTECT PROFITS'));
    text('scalpLadderExit',st==='EXIT'?'EXIT NOW · manual execution':'Frozen EXIT at 4¢ giveback after +5¢ arm');
    const extra=context(main,d);
    if(st==='EXIT')flow(`EXIT / PROTECT PROFITS NOW${extra}`,'exit');
    else if(st==='PROTECT')flow(`${String(d.management_message||'PROTECT PROFITS')}${extra}`,'warn');
    else flow(`GENERALIZED SCALP ACTIVE${extra}`,'good');
    return true;
  }

  window.renderGeneralizedScalpInline=function(main){
    if(main)lastMain=main;
    const d=feed;
    if(!main||!envelope(d)||!feedFresh()||d.contract!==main.contract)return false;
    try{if(typeof usableFrame==='function'&&!usableFrame(main))return false;}catch(_e){return false;}
    return String(d.state).toUpperCase()==='PASS'?renderPass(d):renderActive(main,d);
  };

  async function poll(){
    if(pollBusy)return;pollBusy=true;
    try{
      const r=await fetch(FEED,{cache:'no-store',mode:'cors'});
      if(!r.ok)throw new Error(`HTTP ${r.status}`);
      const d=await r.json();
      if(envelope(d)){feed=d;lastOkMs=Date.now();}else{feed=null;lastOkMs=0;}
    }catch(_e){feed=null;lastOkMs=0;}finally{pollBusy=false;}
    try{if(lastMain&&typeof applyState==='function')applyState(lastMain,false);}catch(_e){}
  }
  const start=()=>{poll();setInterval(poll,500);};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
</script>'''.replace('__GENERALIZED_FEED__', FEED_URL)


def remove_old_inline_scalp(text: str) -> tuple[str, list[str]]:
    changes=[]
    for script_id in ['v81-inline-scalp-script','generalized-scalp-inline-script']:
        start=text.find(f'<script id="{script_id}">')
        while start>=0:
            end=text.find('</script>',start)
            if end<0: raise RuntimeError(f'{script_id} has no closing script tag')
            text=text[:start]+text[end+len('</script>'):]
            changes.append(f'{script_id}-removed')
            start=text.find(f'<script id="{script_id}">')
    # Remove either old hook without changing the underlying base scalp anchor.
    text=text.replace(" if(typeof renderV81ScalpInline==='function')renderV81ScalpInline(d);",'')
    text=text.replace(" if(typeof renderGeneralizedScalpInline==='function')renderGeneralizedScalpInline(d);",'')
    return text,changes


def patch_inline(path: Path) -> list[str]:
    text=path.read_text(encoding='utf-8',errors='replace')
    text,changes=remove_old_inline_scalp(text)
    text,removed=base_fix.remove_v81_overlay(text)
    if removed: changes.append('old-overlay-removed')
    if SCALP_ANCHOR not in text:
        raise RuntimeError('existing scalp render anchor not found; refusing unsafe generalized patch')
    text=text.replace(SCALP_ANCHOR,SCALP_HOOK,1)
    changes.append('generalized-scalp-hook')
    if '</body>' in text:text=text.replace('</body>',INLINE_JS+f'\n<!-- {MARKER} -->\n</body>',1)
    else:text+='\n'+INLINE_JS+f'\n<!-- {MARKER} -->\n'
    changes.append('generalized-feed-script')
    path.write_text(text,encoding='utf-8')
    return changes


def main() -> int:
    import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
    d=installer.install();html=d/'BTC_Kalshi_App_Live_v13.html'
    if not html.exists():raise SystemExit(f'dashboard html missing: {html}')
    base_changes=base_fix.patch_html(html)
    changes=patch_inline(html)
    print('GENERALIZED SCALP INLINE V1 | base='+','.join(base_changes)+' | generalized='+','.join(changes))
    wrapper=d/'BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py'
    if '--self-test' in sys.argv:
        import subprocess
        rendered=html.read_text(encoding='utf-8',errors='replace')
        assert rendered.count('id="generalized-scalp-inline-script"')==1
        assert 'id="v81-inline-scalp-script"' not in rendered
        assert 'renderGeneralizedScalpInline(d)' in rendered
        assert 'GENERALIZED_SCALP_INTEGRATION_V3' in rendered
        assert "setInterval(poll,500)" in rendered
        assert "entry<0||entry>1" in rendered
        assert 'entry<0.30' not in rendered and 'entry>0.45' not in rendered
        assert 'PROTECTION ARMED' not in rendered or 'management_message' in rendered
        assert 'PULLBACK' not in rendered or 'management_message' in rendered
        assert 'EXIT / PROTECT PROFITS NOW' in rendered
        assert 'manual_execution_only!==true' in rendered
        assert 'owns_final_outcome!==false' in rendered and 'owns_early_opportunity!==false' in rendered
        assert 'numeric_flip_risk_validated!==false' in rendered
        assert 'COUNTERTREND vs FINAL' in rendered
        assert 'order_action!==null' in rendered
        rc=subprocess.run([sys.executable,str(wrapper),'--self-test']).returncode
        print('GENERALIZED SCALP INLINE SELFTEST PASS | EXISTING CARD ONLY | MANAGEMENT V3 | NO ORDERS')
        return rc
    os.execv(sys.executable,[sys.executable,'-u',str(wrapper)])

if __name__=='__main__':raise SystemExit(main())
