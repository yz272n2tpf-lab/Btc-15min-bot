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

def build_dashboard()->Path:
    html=seam.build_dashboard();patch(html);return html

def main():
    html=build_dashboard();t=html.read_text(encoding='utf-8',errors='replace')
    print('RECOVERED V11 FINAL PROBABILITY V1 | INFORMATION ONLY | NO ORDERS')
    if '--self-test' in sys.argv:
        assert MARKER in t and seam.MARKER in t
        assert "btc15RenderInformationalFinal(p)" in t
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
