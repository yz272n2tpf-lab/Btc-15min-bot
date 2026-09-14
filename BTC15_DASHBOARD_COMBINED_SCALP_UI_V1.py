#!/usr/bin/env python3
"""
BTC15 combined generalized SCALP in-layout dashboard UI V1.

DISPLAY / INTEGRATION ONLY | SIGNAL ONLY | NO ORDERS

Purpose:
- Preserve the locked production dashboard layout.
- Leave protected EARLY and FINAL rendering under the existing main service.
- Replace only the existing SCALP / REVERSAL card's legacy V8.1 feed with the
  proven `/combined-state` generalized scalp output.
- Surface COUNTERTREND_SCALP / MIXED_HORIZONS labels inside that existing card.
- Show ACTIVE -> PROTECT -> EXIT management without inventing a new threshold.
- Fail closed on feed loss, contract mismatch, or invalid safety envelope.

This file is prepared and self-tested on the research branch before any main
production dashboard deployment.
"""
from pathlib import Path
import os
import sys

import BTC15_DASHBOARD_RENDER_FIX_V1 as base_fix
import BTC15_DASHBOARD_INLINE_SCALP_V1 as v1

MARKER = "BTC15_COMBINED_SCALP_UI_V1"
FEED_URL = "https://scalp-move-shadow-v1-production.up.railway.app/combined-state"

COMBINED_HOOK = (
    v1.SCALP_ANCHOR
    + " if(typeof renderCombinedScalpInline==='function')renderCombinedScalpInline(d);"
)

COMBINED_JS = r'''<script id="btc15-combined-scalp-script">
(()=>{
  const FEED='__COMBINED_FEED__';
  let feed=null,lastMain=null,lastOkMs=0,pollBusy=false,lastError='';

  const el=id=>document.getElementById(id);
  const num=v=>{const x=Number(v);return Number.isFinite(x)?x:NaN;};
  const text=(id,v)=>{const e=el(id);if(e&&e.textContent!==v)e.textContent=v;};
  const cents=v=>Number.isFinite(num(v))?`${Math.round(num(v)*100)}¢`:'—';
  const signedCents=v=>Number.isFinite(num(v))?`${num(v)>=0?'+':''}${Math.round(num(v)*100)}¢`:'—';
  const secs=v=>Number.isFinite(num(v))?`${Math.max(0,Math.round(num(v)))}s`:'—';
  const target=(entry,delta)=>Number.isFinite(num(entry))?cents(Math.min(1,Math.max(0,num(entry)+delta))):'—';

  function envelope(d){
    if(!d || d.version!=='BTC15_COMBINED_STATE_BRIDGE_V3')return false;
    if(d.manual_execution_only!==true || d.order_action!==null || d.orders!==false)return false;
    if(d.numeric_flip_risk_validated!==false)return false;
    if(typeof d.contract!=='string'||!d.contract)return false;
    if(!d.early||!d.final||!d.scalp)return false;
    const s=String(d.scalp.state||'').toUpperCase();
    return ['PASS','ACTIVE','PROTECT','EXIT'].includes(s);
  }
  function browserFresh(){return lastOkMs>0&&(Date.now()-lastOkMs)<=3500;}
  function pill(label,good=false){
    const e=el('scalpState');if(!e)return;
    e.textContent=label;e.classList.remove('state-good','state-watch');
    e.classList.add(good?'state-good':'state-watch');
  }
  function flow(label,kind='warn'){
    const e=el('scalpFlow');if(!e)return;
    e.textContent=label;e.classList.remove('good','warn','exit');e.classList.add(kind);
  }
  function unavailable(reason){
    text('scalpArrow','↔');text('scalpTitle','SCALP / REVERSAL');
    text('scalpEntry',reason);pill('WAITING',false);
    text('scalpCurrentPrice','—');text('scalpTargetStrip','—');
    text('scalpLadderEntry','Generalized scalp feed unavailable');
    text('scalpLadderHold','No stale scalp action will be shown');
    text('scalpLadderWatch','Protected EARLY / FINAL remain unchanged');
    text('scalpLadderProtect','Profit protection unavailable until feed recovers');
    text('scalpLadderExit','WAIT · do not infer an exit from stale data');
    flow(`SCALP WAIT · ${reason}`,'warn');return true;
  }
  function context(d,side,state){
    const labels=Array.isArray(d.context_labels)?d.context_labels:[];
    const fside=String(d.final?.side||'').toUpperCase();
    if(labels.includes('COUNTERTREND_SCALP'))return `COUNTERTREND SCALP · ${side} vs FINAL ${fside||'—'}`;
    if(labels.includes('MIXED_HORIZONS'))return `MIXED HORIZONS · SCALP ${side}`;
    if(labels.includes('ALIGNED'))return `ALIGNED HORIZONS · ${side}`;
    return state==='PASS'?'NO QUALIFIED SCALP':`GENERALIZED SCALP · ${side}`;
  }
  function render(d){
    const s=d.scalp||{},state=String(s.state||'PASS').toUpperCase();
    const side=String(s.side||'').toUpperCase();
    const entry=num(s.entry_ask),bid=num(s.current_bid),gain=num(s.exec_gain),peak=num(s.peak_exec_gain);
    const giveback=(Number.isFinite(peak)&&Number.isFinite(gain))?Math.max(0,peak-gain):NaN;
    const left=num(d.canonical_seconds_left),ctx=context(d,side,state);
    const block=String(d.scalp_block_reason||'').trim();

    if(state==='PASS'){
      text('scalpArrow','↔');text('scalpTitle','SCALP / REVERSAL');
      text('scalpEntry',block?`WAIT · ${block.replaceAll('_',' ')}`:'No qualified generalized scalp');
      pill('WATCHING',false);text('scalpCurrentPrice','—');text('scalpTargetStrip','—');
      text('scalpLadderEntry','Waiting for frozen generalized scalp gate');
      text('scalpLadderHold',`Contract time left ${secs(left)}`);
      text('scalpLadderWatch',block?`Blocked: ${block.replaceAll('_',' ')}`:'Watching both UP / DOWN movement');
      text('scalpLadderProtect','Protection arms after +5¢ executable gain');
      text('scalpLadderExit','Validated EXIT after 4¢ giveback from armed running peak');
      flow(ctx,'warn');return true;
    }

    const arrow=side==='DOWN'?'↓':'↑';
    text('scalpArrow',arrow);text('scalpTitle',`SCALP ${side}`);
    text('scalpEntry',`Signal ${cents(entry)} · generalized`);
    text('scalpCurrentPrice',cents(bid));
    text('scalpTargetStrip',`Executable gain ${signedCents(gain)}`);
    text('scalpLadderEntry',`Entry ${cents(entry)} · +5¢ ${target(entry,.05)} · +10¢ ${target(entry,.10)} · +20¢ ${target(entry,.20)}`);
    text('scalpLadderHold',`Current bid ${cents(bid)} · ${secs(left)} contract left`);
    text('scalpLadderWatch',`Current ${signedCents(gain)} · peak ${signedCents(peak)}`);

    if(state==='ACTIVE'){
      pill('ACTIVE',true);
      text('scalpLadderProtect','Protection arms automatically after +5¢ executable gain');
      text('scalpLadderExit','After arm: validated EXIT at 4¢ giveback from running peak');
      flow(`${ctx} · BUILDING`,'good');return true;
    }
    if(state==='PROTECT'){
      pill('PROTECT',true);
      text('scalpLadderProtect',`PROTECT PROFITS · peak ${signedCents(peak)} · current ${signedCents(gain)}`);
      text('scalpLadderExit',`Running giveback ${signedCents(giveback)} · EXIT at validated 4¢ giveback`);
      flow(`${ctx} · PROTECT PROFITS`,'warn');return true;
    }
    if(state==='EXIT'){
      pill('EXIT',false);
      text('scalpLadderProtect',`Peak ${signedCents(peak)} · current ${signedCents(gain)}`);
      text('scalpLadderExit',`EXIT / PROTECT PROFITS NOW · giveback ${signedCents(giveback)}`);
      flow(`${ctx} · EXIT / PROTECT PROFITS NOW`,'exit');return true;
    }
    return false;
  }

  window.renderCombinedScalpInline=function(main){
    if(main)lastMain=main;
    if(!main)return false;
    try{if(typeof usableFrame==='function'&&!usableFrame(main))return unavailable('MAIN FRAME NOT USABLE');}catch(_e){return unavailable('MAIN FRAME NOT USABLE');}
    if(!browserFresh()||!envelope(feed))return unavailable(lastError||'COMBINED FEED UNAVAILABLE');
    if(feed.contract!==main.contract)return unavailable('CONTRACT SYNC');
    return render(feed);
  };

  async function poll(){
    if(pollBusy)return;pollBusy=true;
    try{
      const r=await fetch(FEED,{cache:'no-store',mode:'cors'});
      if(!r.ok)throw new Error(`HTTP ${r.status}`);
      const d=await r.json();
      if(!envelope(d))throw new Error('INVALID SAFETY ENVELOPE');
      feed=d;lastOkMs=Date.now();lastError='';
    }catch(e){feed=null;lastOkMs=0;lastError=String(e?.message||'COMBINED FEED UNAVAILABLE');}
    finally{pollBusy=false;}
    try{if(lastMain&&typeof applyState==='function')applyState(lastMain,false);}catch(_e){}
  }
  const start=()=>{poll();setInterval(poll,1000);};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
</script>'''.replace('__COMBINED_FEED__', FEED_URL)


def _remove_script(text: str, script_id: str) -> tuple[str, bool]:
    start = text.find(f'<script id="{script_id}">')
    if start < 0:
        return text, False
    end = text.find('</script>', start)
    if end < 0:
        raise RuntimeError(f'{script_id} has no closing script tag')
    return text[:start] + text[end + len('</script>'):], True


def patch_combined(path: Path) -> list[str]:
    text = path.read_text(encoding='utf-8', errors='replace')
    changes=[]

    # Keep the existing in-layout hook position but remove the legacy V8.1 renderer.
    if v1.SCALP_HOOK in text:
        text=text.replace(v1.SCALP_HOOK,COMBINED_HOOK,1);changes.append('combined-scalp-hook')
    elif COMBINED_HOOK not in text:
        if v1.SCALP_ANCHOR not in text:
            raise RuntimeError('existing scalp render anchor not found; refusing unsafe patch')
        text=text.replace(v1.SCALP_ANCHOR,COMBINED_HOOK,1);changes.append('combined-scalp-hook')

    text,removed=_remove_script(text,'v81-inline-scalp-script')
    if removed:changes.append('legacy-v81-script-removed')
    text,removed2=_remove_script(text,'btc15-combined-scalp-script')
    if removed2:changes.append('old-combined-script-replaced')

    if '</body>' in text:
        text=text.replace('</body>',COMBINED_JS+f'\n<!-- {MARKER} -->\n</body>',1)
    else:
        text+='\n'+COMBINED_JS+f'\n<!-- {MARKER} -->\n'
    changes.append('combined-scalp-script')
    path.write_text(text,encoding='utf-8')
    return changes


def build_dashboard() -> Path:
    import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
    d=installer.install()
    html=d/'BTC_Kalshi_App_Live_v13.html'
    if not html.exists():raise RuntimeError(f'dashboard html missing: {html}')
    base_fix.patch_html(html)
    v1.patch_inline(html)
    patch_combined(html)
    return html


def main() -> int:
    html=build_dashboard()
    print('COMBINED SCALP UI V1 | existing card only | generalized feed | NO ORDERS')
    if '--self-test' in sys.argv:
        import subprocess
        rendered=html.read_text(encoding='utf-8',errors='replace')
        assert rendered.count('id="btc15-combined-scalp-script"')==1
        assert 'id="v81-inline-scalp-script"' not in rendered
        assert "renderCombinedScalpInline(d)" in rendered
        assert FEED_URL in rendered
        assert 'BTC15_COMBINED_STATE_BRIDGE_V3' in rendered
        assert "numeric_flip_risk_validated!==false" in rendered
        assert "order_action!==null" in rendered and "d.orders!==false" in rendered
        assert 'No V8.1 stop rule connected' not in rendered
        assert 'COUNTERTREND_SCALP' in rendered and 'MIXED_HORIZONS' in rendered
        assert 'Protection arms automatically after +5¢ executable gain' in rendered
        assert 'validated 4¢ giveback' in rendered
        assert 'flip_risk_percent' not in rendered
        assert 'position:fixed' not in rendered or 'v81ScalpCard' not in rendered
        wrapper=html.parent/'BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py'
        rc=subprocess.run([sys.executable,str(wrapper),'--self-test']).returncode
        print('COMBINED SCALP UI V1 SELFTEST PASS | LOCKED LAYOUT | PROTECTED EARLY/FINAL UNCHANGED | NO ORDERS')
        return rc
    wrapper=html.parent/'BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py'
    os.execv(sys.executable,[sys.executable,'-u',str(wrapper)])


if __name__=='__main__':raise SystemExit(main())
