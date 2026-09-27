#!/usr/bin/env python3
"""Recovered V11 FINAL informational probability integration V2.

OFF-PRODUCTION PRESENTATION ONLY | SIGNAL ONLY | NO ORDERS.
Composes only with the qualified recovered information seam and only writes
the existing non-authoritative FINAL subtext while FINAL is not qualified.
"""
from pathlib import Path
import sys
import BTC15_RECOVERED_V11_INFORMATION_SEAM_V1 as seam

MARKER="BTC15_RECOVERED_V11_FINAL_PROBABILITY_V2"
HOOK_MARKER="BTC15_INFO_TO_FINAL_HOOK_V2"
RENDERER=r'''<script id="btc15-recovered-final-probability-v2">
(()=>{
'use strict';
const el=()=>document.getElementById('finalActionSub');
const safeNonFinal=()=>{const e=el();const s=(e?.textContent||'');return !!e && !/FINAL qualified/i.test(s) && (/FINAL not qualified|FINAL gate still pending|Continuous .* probability|FINAL qualification unchanged|Information unavailable/i.test(s));};
window.btc15RenderInformationalFinal=function(p){
  const e=el(); if(!e)return false;
  if(p===null){
    if(e.dataset.btc15InfoFinal==='1'&&safeNonFinal())e.textContent='Information unavailable · FINAL not qualified';
    delete e.dataset.btc15InfoFinal; return false;
  }
  if(!p||p.schema!=='BTC15_INFORMATION_V1'||p.authority!=='INFORMATIONAL_READ_ONLY'||p.status!=='AVAILABLE'||p.signal_only!==true||p.orders!==false)return false;
  if(!safeNonFinal())return false;
  const up=Number(p.probability_up),down=Number(p.probability_down);
  if(!Number.isFinite(up)||!Number.isFinite(down)||up<0||down<0||up>1||down>1||Math.abs(up+down-1)>1e-6)return false;
  const side=up>=down?'UP':'DOWN',prob=Math.max(up,down);
  e.textContent='Continuous '+side+' probability · '+(prob*100).toFixed(1)+'% · FINAL not qualified';
  e.dataset.btc15InfoFinal='1'; return true;
};
})();
</script>'''

def patch_renderer(path:Path):
    text=path.read_text(encoding='utf-8',errors='replace')
    if MARKER in text:return ['renderer-present']
    for required in (seam.MARKER,'finalActionSub','FINAL not qualified','SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS'):
        if required not in text:raise RuntimeError('Recovered FINAL presentation contract missing; refusing patch')
    if '</body>' not in text:raise RuntimeError('Dashboard body close missing; refusing patch')
    text=text.replace('</body>',RENDERER+'\n<!-- '+MARKER+' -->\n</body>',1)
    path.write_text(text,encoding='utf-8');return ['renderer-added']

def connect_seam(path:Path):
    text=path.read_text(encoding='utf-8',errors='replace')
    if HOOK_MARKER in text:return ['hook-present']
    sid='<script id="btc15-recovered-information-seam-v1">'
    a=text.find(sid)
    if a<0 or seam.MARKER not in text:raise RuntimeError('Qualified information seam missing; refusing FINAL connection')
    z=text.find('</script>',a)
    if z<0:raise RuntimeError('Qualified information seam close missing; refusing FINAL connection')
    segment=text[a:z]
    clear_anchor="document.documentElement.dataset.btc15InfoPhase='DATA_STALE';"
    valid_anchor="document.documentElement.dataset.btc15InfoPhase=phase;"
    if clear_anchor not in segment or valid_anchor not in segment:raise RuntimeError('Qualified seam render anchors missing; refusing FINAL connection')
    segment=segment.replace(clear_anchor,clear_anchor+" if(typeof window.btc15RenderInformationalFinal==='function')window.btc15RenderInformationalFinal(null);",1)
    segment=segment.replace(valid_anchor,valid_anchor+" if(typeof window.btc15RenderInformationalFinal==='function')window.btc15RenderInformationalFinal(p);",1)
    segment+='\n/* '+HOOK_MARKER+' */\n'
    text=text[:a]+segment+text[z:]
    path.write_text(text,encoding='utf-8');return ['hook-added']

def build_dashboard()->Path:
    html=seam.build_dashboard()
    patch_renderer(html)
    connect_seam(html)
    return html

def main():
    html=build_dashboard();t=html.read_text(encoding='utf-8',errors='replace')
    print('RECOVERED V11 FINAL PROBABILITY V2 | INFORMATION ONLY | NO ORDERS')
    if '--self-test' in sys.argv:
        assert MARKER in t and HOOK_MARKER in t and seam.MARKER in t
        assert t.count('btc15-recovered-information-seam-v1')==1
        assert t.count(HOOK_MARKER)==1
        assert "btc15RenderInformationalFinal(null)" in t
        assert "btc15RenderInformationalFinal(p)" in t
        assert "p.authority!=='INFORMATIONAL_READ_ONLY'" in t
        assert "p.status!=='AVAILABLE'" in t
        assert "p.signal_only!==true||p.orders!==false" in t
        assert "const side=up>=down?'UP':'DOWN'" in t
        assert "!safeNonFinal()" in t
        assert "FINAL not qualified" in RENDERER
        for forbidden in ('final.ready=','final_status=','early.ready=','scalp.ready=','latchedFinal=','order_action','place_order'):assert forbidden not in RENDERER
        assert 'SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS' in t
        print('RECOVERED V11 FINAL PROBABILITY V2 SELFTEST PASS | FRESH+STALE WIRED | QUALIFIED FINAL PROTECTED | UP/DOWN SYMMETRIC | NO ORDERS')
    return 0
if __name__=='__main__':raise SystemExit(main())
