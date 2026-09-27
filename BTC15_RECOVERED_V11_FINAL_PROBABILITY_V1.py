#!/usr/bin/env python3
"""Recovered V11 FINAL probability integration V1.

OFF-PRODUCTION PRESENTATION ONLY. Reuses the historical FINAL presentation path.
Informational probability may decorate FINAL; it can never create FINAL authority.
"""
from pathlib import Path
import sys
import BTC15_RECOVERED_V11_INFORMATION_SEAM_V1 as seam

MARKER="BTC15_RECOVERED_V11_FINAL_PROBABILITY_V1"
PATCH=r'''<script id="btc15-recovered-final-probability-v1">
(()=>{
'use strict';
const _set=window.setText;
if(typeof _set!=='function')return;
window.btc15RenderInformationalFinal=function(p){
  if(!p||p.schema!=='BTC15_INFORMATION_V1'||p.authority!=='INFORMATIONAL_READ_ONLY'||
     p.status!=='AVAILABLE'||p.signal_only!==true||p.orders!==false)return false;
  const up=Number(p.probability_up),down=Number(p.probability_down);
  if(!Number.isFinite(up)||!Number.isFinite(down)||up<0||down<0||up>1||down>1||Math.abs(up+down-1)>1e-6)return false;
  const side=up>=down?'UP':'DOWN',prob=Math.max(up,down);
  _set('finalActionSub','Continuous '+side+' probability · '+(prob*100).toFixed(1)+'% · FINAL qualification unchanged');
  return true;
};
})();
</script>'''

def patch(path:Path):
    text=path.read_text(encoding='utf-8',errors='replace')
    if MARKER in text:return ['already-present']
    # Proven historical FINAL presentation anchors. No new card/layout.
    for required in (seam.MARKER,"finalActionSub","FINAL not qualified"):
        if required not in text: raise RuntimeError('Recovered FINAL presentation anchor missing; refusing patch')
    text=text.replace('</body>',PATCH+'\n<!-- '+MARKER+' -->\n</body>',1)
    path.write_text(text,encoding='utf-8');return ['final-informational-probability']

def connect_information_render(path:Path):
    text=path.read_text(encoding='utf-8',errors='replace')
    # The seam source is already independently qualified. Anchor the composed
    # artifact by its unique script id and marker, then inject immediately
    # before that script closes; never search unrelated dashboard JS.
    script_id='<script id="btc15-recovered-information-seam-v1">'
    marker='BTC15_RECOVERED_V11_INFORMATION_SEAM_V1'
    call="if(typeof window.btc15RenderInformationalFinal==='function')window.btc15RenderInformationalFinal(p);"
    if call in text:return ['already-connected']
    a=text.find(script_id)
    if a<0 or marker not in text:raise RuntimeError('Qualified information seam missing; refusing FINAL connection')
    z=text.find('</script>',a)
    if z<0:raise RuntimeError('Qualified information seam close missing; refusing FINAL connection')
    # Inject a wrapper around seam render, preserving its validated p/view logic.
    hook="const _btc15InfoRender=render; render=function(){_btc15InfoRender(); const p=view(token,performance.now()); if(p&&typeof window.btc15RenderInformationalFinal==='function')window.btc15RenderInformationalFinal(p);};\n"
    text=text[:z]+hook+text[z:]
    path.write_text(text,encoding='utf-8');return ['information-to-final-wrapper']

def build_dashboard()->Path:
    html=seam.build_dashboard();patch(html);connect_information_render(html);return html

def main():
    html=build_dashboard();t=html.read_text(encoding='utf-8',errors='replace')
    print('RECOVERED V11 FINAL PROBABILITY V1 | INFORMATION ONLY | NO ORDERS')
    if '--self-test' in sys.argv:
        assert MARKER in t and seam.MARKER in t
        assert "window.btc15RenderInformationalFinal(p)" in t\n        assert "const _btc15InfoRender=render" in t
        assert "p.authority!=='INFORMATIONAL_READ_ONLY'" in t
        assert "p.status!=='AVAILABLE'" in t
        assert "p.signal_only!==true||p.orders!==false" in t
        assert "const side=up>=down?'UP':'DOWN'" in t
        assert "FINAL qualification unchanged" in t
        for forbidden in ('final.ready=','final_status=','early.ready=','scalp.ready=','latchedFinal=','PROTECT','EXIT'):
            assert forbidden not in PATCH
        assert 'SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS' in t
        print('RECOVERED V11 FINAL PROBABILITY V1 SELFTEST PASS | INFORMATION CANNOT QUALIFY FINAL | UP/DOWN SYMMETRIC | NO ORDERS')
    return 0
if __name__=='__main__':raise SystemExit(main())
