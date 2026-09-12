#!/usr/bin/env python3
"""V8.1 inline scalp bridge V2 — diagnostic visibility only.

Adds read-only reasons for WAIT/rejection to the existing SCALP / REVERSAL card.
No new card, no overlay, no FINAL/EARLY ownership, no signal threshold changes,
no orders. Active V8.1 signals still use the exact V1 safety boundary.
"""
from pathlib import Path
import os, sys

import BTC15_DASHBOARD_INLINE_SCALP_V1 as v1

MARKER = "BTC15_V81_INLINE_SCALP_DIAG_V2"
FEED_URL = "https://v81-live-diagnostics-production.up.railway.app/state"

DIAG_JS = r'''<script id="v81-inline-scalp-script">
(()=>{
  const FEED='__V81_FEED__';
  let feed=null,lastMain=null,lastOkMs=0,pollBusy=false;
  const el=id=>document.getElementById(id);
  const num=v=>{const x=Number(v);return Number.isFinite(x)?x:NaN;};
  const cents=v=>Number.isFinite(num(v))?`${Math.round(num(v)*100)}¢`:'—';
  const secs=v=>Number.isFinite(num(v))?`${Math.max(0,Math.round(num(v)))}s`:'—';
  const signed=(v,d=1)=>Number.isFinite(num(v))?`${num(v)>=0?'+':''}${num(v).toFixed(d)}`:'—';
  const text=(id,v)=>{const e=el(id);if(e&&e.textContent!==v)e.textContent=v;};
  const setPill=(label,good=false)=>{const e=el('scalpState');if(!e)return;e.textContent=label;e.classList.remove('state-good','state-watch');e.classList.add(good?'state-good':'state-watch');};
  const flow=(label,kind='warn')=>{const e=el('scalpFlow');if(!e)return;e.textContent=label;e.classList.remove('good','warn','exit');e.classList.add(kind);};

  function envelope(d){
    if(!d || d.version!=='V8.1_GRADUATED_30_45' || d.entry_band!=='30-45c')return false;
    if(d.graduated!==true || d.manual_execution_only!==true || d.order_action!==null)return false;
    if(d.owns_final_outcome!==false || d.owns_early_opportunity!==false)return false;
    if(d.diagnostic_version!=='V81_GATE_DIAG_V1')return false;
    return typeof d.contract==='string' && d.contract.length>0;
  }
  function activePayload(d){
    if(!envelope(d) || d.active!==true)return false;
    const side=String(d.side||'').toUpperCase(),route=String(d.route||'').toUpperCase();
    const entry=num(d.entry_price),bid=num(d.current_bid),left=num(d.seconds_left),age=num(d.signal_age_sec);
    if(!['UP','DOWN'].includes(side)||!['CORE','SURGE'].includes(route))return false;
    if(!Number.isFinite(entry)||entry<0.30||entry>0.45)return false;
    if(!Number.isFinite(bid)||bid<0||bid>1)return false;
    if(!Number.isFinite(left)||left<=0)return false;
    if(!Number.isFinite(age)||age<0||age>185)return false;
    return true;
  }
  function feedFresh(){return lastOkMs>0&&(Date.now()-lastOkMs)<=3500;}
  function pretty(r){
    const m={
      NO_SIDE_IN_30_45C:'no side priced 30–45¢',PRICE_OUTSIDE_30_45C:'outside 30–45¢',
      FEATURES_NOT_READY:'features warming',BRTI_NOT_FRESH:'BRTI confirmation missing',
      BASE_NOT_READY:'base impulse gate not ready',STRUCTURE_BLOCK:'30s structure against setup',
      EVIDENCE_BELOW_CORE_SURGE:'CORE/SURGE evidence too weak',READY_CONFIRMING:'confirmation building',
      CONFIRMING_0_OF_2:'confirmation 0/2',CONFIRMING_1_OF_2:'confirmation 1/2',QUALIFIED:'qualified'
    };
    return m[String(r||'').toUpperCase()]||String(r||'waiting').replaceAll('_',' ').toLowerCase();
  }
  function bestDiag(d){
    const a=Array.isArray(d.diagnostics)?d.diagnostics.filter(x=>x&&x.in_30_45_band===true):[];
    a.sort((x,y)=>(num(y.evidence_ratio)||-999)-(num(x.evidence_ratio)||-999));
    return a[0]||null;
  }
  function metrics(q){
    if(!q)return 'Waiting for 30–45¢ price';
    return `BTC5 ${signed(q.btc5)} · BTC15 ${signed(q.btc15)} · BRTI5 ${signed(q.brti5)} · BRTI15 ${signed(q.brti15)}`;
  }
  function renderWait(d){
    const q=bestDiag(d);
    setPill('WATCHING',false);
    if(!q){
      text('scalpEntry','V8.1 waiting · no 30–45¢ side');
      text('scalpLadderEntry','V8.1 lane 30–45¢');
      text('scalpLadderHold','No in-band side right now');
      text('scalpLadderWatch','Price gate only · thresholds unchanged');
      flow('V8.1 WAIT · no side priced 30–45¢','warn');
      return true;
    }
    const why=pretty(q.reason);
    text('scalpEntry',`${q.side} ${cents(q.ask)} · ${why}`);
    text('scalpLadderEntry',`V8.1 30–45¢ · ${q.side} ${cents(q.ask)}`);
    text('scalpLadderHold',q.confirm_count>0?`Confirmation ${q.confirm_count}/2`:`Gate: ${why}`);
    text('scalpLadderWatch',metrics(q));
    flow(`V8.1 WAIT · ${q.side} ${cents(q.ask)} · ${why}`,'warn');
    return true;
  }
  function renderActive(d){
    const side=String(d.side).toUpperCase(),route=String(d.route).toUpperCase(),status=String(d.status||'WATCH').toUpperCase();
    const entry=num(d.entry_price),bid=num(d.current_bid),left=num(d.seconds_left),age=num(d.signal_age_sec),targets=d.targets||{};
    const t5=num(targets.plus_5c),t10=num(targets.plus_10c),t20=num(targets.plus_20c);
    text('scalpArrow',side==='DOWN'?'↓':'↑');text('scalpTitle',`SCALP ${side} · V8.1`);text('scalpEntry',`Signal ${cents(entry)} · ${route}`);
    let state='QUALIFIED';if(status==='ACTIONABLE')state='+5¢ HIT';else if(status==='ACTIONABLE_EXPANSION')state='+10¢ HIT';else if(status==='PROTECT')state='PROTECT';setPill(state,true);
    text('scalpCurrentPrice',cents(bid));text('scalpTargetStrip',Number.isFinite(t10)?`+10¢ → ${cents(t10)}`:'—');
    text('scalpLadderEntry',`30–45¢ band · signal ${cents(entry)}`);text('scalpLadderHold',`Up to 3m · ${secs(left)} contract left`);text('scalpLadderWatch',`Bid ${cents(bid)} · signal age ${secs(age)}`);
    if(status==='PROTECT')text('scalpLadderProtect','+20¢ reached · protect gains');
    else if(Number.isFinite(t5)&&Number.isFinite(t10)&&Number.isFinite(t20))text('scalpLadderProtect',`+5¢ ${cents(t5)} · +10¢ ${cents(t10)} · +20¢ ${cents(t20)}`);
    else text('scalpLadderProtect','V8.1 target ladder active');
    text('scalpLadderExit','No V8.1 stop rule connected · manual execution');
    flow(`V8.1 ${route} · ${status.replaceAll('_',' ')} · signal-only`,status==='PROTECT'?'warn':'good');
    return true;
  }

  window.renderV81ScalpInline=function(main){
    if(main)lastMain=main;const d=feed;
    if(!main||!envelope(d)||!feedFresh()||d.contract!==main.contract)return false;
    try{if(typeof usableFrame==='function'&&!usableFrame(main))return false;}catch(_e){return false;}
    try{if(typeof freshBrti==='function'&&!freshBrti(main))return false;}catch(_e){return false;}
    return activePayload(d)?renderActive(d):renderWait(d);
  };

  async function poll(){
    if(pollBusy)return;pollBusy=true;
    try{const r=await fetch(FEED,{cache:'no-store',mode:'cors'});if(!r.ok)throw new Error(`HTTP ${r.status}`);const d=await r.json();
      if(envelope(d)){feed=d;lastOkMs=Date.now();}else{feed=null;lastOkMs=0;}
    }catch(_e){feed=null;lastOkMs=0;}finally{pollBusy=false;}
    try{if(lastMain&&typeof applyState==='function')applyState(lastMain,false);}catch(_e){}
  }
  const start=()=>{poll();setInterval(poll,1000);};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
</script>'''.replace('__V81_FEED__', FEED_URL)


def replace_inline_script(path: Path) -> list[str]:
    text = path.read_text(encoding='utf-8', errors='replace')
    changes=[]
    if v1.SCALP_HOOK not in text:
        if v1.SCALP_ANCHOR not in text:
            raise RuntimeError('existing scalp render anchor not found; refusing diagnostic patch')
        text=text.replace(v1.SCALP_ANCHOR,v1.SCALP_HOOK,1);changes.append('existing-scalp-hook')
    start=text.find('<script id="v81-inline-scalp-script">')
    if start>=0:
        end=text.find('</script>',start)
        if end<0: raise RuntimeError('existing inline scalp script has no closing tag')
        text=text[:start]+text[end+len('</script>'):]
        changes.append('v1-inline-script-removed')
    if '</body>' in text:
        text=text.replace('</body>',DIAG_JS+f'\n<!-- {MARKER} -->\n</body>',1)
    else:
        text+='\n'+DIAG_JS+f'\n<!-- {MARKER} -->\n'
    changes.append('diag-v2-script')
    path.write_text(text,encoding='utf-8')
    return changes


def main() -> int:
    import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
    d=installer.install();html=d/'BTC_Kalshi_App_Live_v13.html'
    if not html.exists(): raise SystemExit(f'dashboard html missing: {html}')
    base=v1.base_fix.patch_html(html)
    v1.patch_inline(html)
    changes=replace_inline_script(html)
    print('INLINE SCALP DIAG V2 | base='+','.join(base)+' | diag='+','.join(changes))
    wrapper=d/'BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py'
    if '--self-test' in sys.argv:
        import subprocess
        rendered=html.read_text(encoding='utf-8',errors='replace')
        assert rendered.count('id="v81-inline-scalp-script"')==1
        assert 'v81-scalp-card-script' not in rendered
        assert 'V81_GATE_DIAG_V1' in rendered
        assert 'V8.1 WAIT' in rendered
        assert 'BRTI confirmation missing' in rendered
        assert 'entry<0.30||entry>0.45' in rendered
        assert 'owns_final_outcome!==false' in rendered and 'owns_early_opportunity!==false' in rendered
        assert 'No V8.1 stop rule connected' in rendered
        assert 'position:fixed' not in rendered or 'v81ScalpCard' not in rendered
        rc=subprocess.run([sys.executable,str(wrapper),'--self-test']).returncode
        print('INLINE SCALP DIAG V2 SELFTEST PASS | WAIT REASONS VISIBLE | EXISTING CARD ONLY | NO ORDERS')
        return rc
    os.execv(sys.executable,[sys.executable,'-u',str(wrapper)])

if __name__=='__main__': raise SystemExit(main())
