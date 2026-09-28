#!/usr/bin/env python3
"""Recovered V11/V13 presentation integration V1.

OFF-PRODUCTION DISPLAY ONLY | SIGNAL ONLY | NO ORDERS

Adds a strictly informational display seam to the exact recovered V13 lineage.
It does not replace FINAL/EARLY/SCALP/protection logic and does not alter layout.
"""
from pathlib import Path
import sys
import BTC15_DASHBOARD_COMBINED_SCALP_UI_V13 as v13

MARKER="BTC15_RECOVERED_V11_INFORMATION_SEAM_V1"
SCRIPT=r'''<script id="btc15-recovered-information-seam-v1">
(()=>{
'use strict';
let token=null,busy=false,generation=0;
const captured=new WeakSet();
const byId=id=>document.getElementById(id);
function guardNode(){let n=byId('btc15QualifiedGuardState');if(n)return n;const f=byId('flipRisk');if(!f||!f.parentElement)return null;n=document.createElement('div');n.id='btc15QualifiedGuardState';n.dataset.authority='INFORMATIONAL_READ_ONLY';n.style.cssText='font-size:11px;margin-top:6px;font-weight:900;letter-spacing:.04em';f.parentElement.appendChild(n);return n;}
function infoFreshnessNode(){let n=byId('btc15QualifiedBrtiFreshness');if(n)return n;const f=byId('flipRisk');if(!f||!f.parentElement)return null;n=document.createElement('div');n.id='btc15QualifiedBrtiFreshness';n.dataset.authority='INFORMATIONAL_READ_ONLY';n.style.cssText='font-size:10px;margin-top:6px;opacity:.82;letter-spacing:.02em';f.parentElement.appendChild(n);return n;}
function clearInfo(){
  const f=byId('flipRisk'); if(f){f.textContent='—';f.dataset.info='unavailable';}
  const g=guardNode();if(g){g.textContent='GUARD STATE · DATA NOT FRESH';g.dataset.phase='DATA_STALE';}
  const q=infoFreshnessNode();if(q){q.textContent='Qualified BRTI: unavailable · waiting for ≤5s frame';q.dataset.fresh='false';}
  document.documentElement.dataset.btc15InfoPhase='DATA_STALE';
}
function capture(payload,started,received){
  const t=Object.freeze({payload:Object.freeze(structuredClone(payload)),started,received});
  captured.add(t);return t;
}
function view(t,now){
  if(!t||!captured.has(t)||!Number.isFinite(now)||now<t.received)return null;
  const p=t.payload;
  if(!p||p.schema!=='BTC15_INFORMATION_V1'||p.authority!=='INFORMATIONAL_READ_ONLY'||
     p.status!=='AVAILABLE'||p.signal_only!==true||p.orders!==false||
     !Number.isFinite(p.checked_ts)||!Number.isFinite(p.display_until)||!Number.isFinite(p.expires_at)||
     !Number.isFinite(p.brti_source_ts))return null;
  const nowS=p.checked_ts+(now-t.started)/1000;
  if(nowS<p.checked_ts||nowS>=p.display_until||nowS>=p.expires_at||nowS-p.brti_source_ts>5)return null;
  return p;
}
function render(){
  const p=view(token,performance.now()); if(!p){clearInfo();return;}
  // Never write FINAL/EARLY/SCALP action labels. Informational decoration only.
  const f=byId('flipRisk');
  if(f&&Number.isFinite(p.flip_risk_pct)){f.textContent=Number(p.flip_risk_pct).toFixed(1)+'%';f.dataset.info='informational';}
  const q=infoFreshnessNode(),age=Number(p.brti_age_seconds);if(q&&Number.isFinite(age)&&age>=0&&age<=5){q.textContent='Qualified BRTI: fresh · '+age.toFixed(1)+'s · live qualification feed';q.dataset.fresh='true';}
  const phase=p.three_minute_guard===true?'3M_GUARD':p.five_minute_caution===true?'5M_CAUTION':'NORMAL';
  const g=guardNode();if(g){g.textContent=phase==='3M_GUARD'?'3M GUARD':phase==='5M_CAUTION'?'5M CAUTION':'NORMAL WINDOW';g.dataset.phase=phase;}
  document.documentElement.dataset.btc15InfoPhase=phase;
}
async function poll(){
  if(busy||document.hidden)return;busy=true;const mine=generation,started=performance.now();
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),700);
  try{
    const nonce=crypto.randomUUID().replaceAll('-','');
    const r=await fetch('/information',{cache:'no-store',signal:controller.signal,headers:{'X-BTC15-Information-Nonce':nonce}});
    if(!r.ok||r.headers.get('X-BTC15-Information-Nonce')!==nonce)throw Error('unavailable');
    const p=await r.json();
    if(mine===generation)token=capture(p,started,performance.now());
  }catch(_){if(mine===generation)token=null;}finally{clearTimeout(timeout);busy=false;render();}
}
function invalidate(){generation++;token=null;clearInfo();}
addEventListener('pagehide',invalidate);addEventListener('offline',invalidate);
addEventListener('pageshow',()=>{invalidate();poll();});addEventListener('online',()=>{invalidate();poll();});
document.addEventListener('visibilitychange',()=>{invalidate();if(!document.hidden)poll();});
setInterval(render,100);setInterval(poll,500);clearInfo();poll();
})();
</script>'''

def patch(path:Path):
    text=path.read_text(encoding='utf-8',errors='replace')
    if MARKER in text:return ['already-present']
    # Fail closed: this seam requires the recovered V13 safety markers.
    for required in (v13.MARKER,'SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS'):
        if required not in text: raise RuntimeError('Recovered V13 safety anchor missing')
    text=text.replace('</body>',SCRIPT+'\n<!-- '+MARKER+' -->\n</body>',1)
    path.write_text(text,encoding='utf-8');return ['information-seam']

def build_dashboard()->Path:
    html=v13.build_dashboard();patch(html);return html

def main():
    html=build_dashboard();t=html.read_text(encoding='utf-8',errors='replace')
    print('RECOVERED V11 INFORMATION SEAM V1 | DISPLAY ONLY | NO ORDERS')
    if '--self-test' in sys.argv:
        assert MARKER in t and v13.MARKER in t
        assert "p.authority!=='INFORMATIONAL_READ_ONLY'" in t
        assert "p.status!=='AVAILABLE'" in t
        assert "p.signal_only!==true||p.orders!==false" in t
        assert "nowS>=p.display_until||nowS>=p.expires_at||nowS-p.brti_source_ts>5" in t
        assert "addEventListener('offline',invalidate)" in t
        assert "document.addEventListener('visibilitychange'" in t
        assert "byId('flipRisk')" in t
        assert "btc15QualifiedBrtiFreshness" in t and "Qualified BRTI: fresh" in t and "live qualification feed" in t and "waiting for ≤5s frame" in t
        assert "btc15QualifiedGuardState" in t and "3M GUARD" in t and "5M CAUTION" in t and "NORMAL WINDOW" in t and "GUARD STATE · DATA NOT FRESH" in t
        assert "p.brti_age_seconds" in t
        # No action-card mutation in this seam.
        assert "finalAction" not in SCRIPT and "earlyAction" not in SCRIPT and "combinedScalpClean" not in SCRIPT
        for forbidden in ("brtiAge","brtiStatus","btcPrice","brtiPrice","targetPrice","dashboard_state.json"): assert forbidden not in SCRIPT
        assert 'SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS' in t
        print('RECOVERED V11 INFORMATION SEAM V1 SELFTEST PASS | STALE FAIL-CLOSED | ACTION CARDS UNTOUCHED | NO ORDERS')
    return 0
if __name__=='__main__':raise SystemExit(main())
