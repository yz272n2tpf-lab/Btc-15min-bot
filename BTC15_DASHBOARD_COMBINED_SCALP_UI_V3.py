#!/usr/bin/env python3
"""
BTC15 combined generalized SCALP in-layout dashboard UI V3.

SHADOW DISPLAY ONLY | SIGNAL ONLY | NO ORDERS

V3 keeps the existing V13 card footprint but replaces the crowded legacy
inside-card scalp rows with one clean generalized SCALP panel. It does not
change EARLY, FINAL, SCALP qualification, management thresholds, contract
alignment, source freshness, or order behavior.
"""
from pathlib import Path
import os
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V2 as v2

MARKER = "BTC15_COMBINED_SCALP_UI_V3_CLEAN_PANEL"
FEED_URL = "https://scalp-move-shadow-v1-production.up.railway.app/combined-state"

CSS = r'''<style id="btc15-combined-scalp-clean-style">
#scalpCard{position:relative!important;overflow:hidden!important;min-height:390px!important;}
#scalpCard.btc15-clean-scalp-ready > *:not(#combinedScalpClean){display:none!important;}
#combinedScalpClean{display:flex!important;flex-direction:column!important;gap:10px!important;padding:14px!important;box-sizing:border-box!important;width:100%!important;min-height:390px!important;color:#eef4f8!important;font-family:inherit!important;}
#combinedScalpClean .csc-head{display:flex;align-items:center;justify-content:space-between;gap:10px;}
#combinedScalpClean .csc-title{font-size:15px;font-weight:900;letter-spacing:.3px;color:#9ecbff;}
#combinedScalpClean .csc-pill{font-size:12px;font-weight:900;padding:5px 10px;border-radius:999px;background:#263441;color:#d9e5ee;white-space:nowrap;}
#combinedScalpClean .csc-pill.active{background:#1f6f4a;color:#d9ffe9;}
#combinedScalpClean .csc-pill.protect{background:#7a6218;color:#fff0a8;}
#combinedScalpClean .csc-pill.exit{background:#812d3a;color:#ffdce2;}
#combinedScalpClean .csc-main{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;padding:10px 0 4px;border-bottom:1px solid rgba(255,255,255,.12);}
#combinedScalpClean .csc-side{font-size:30px;font-weight:950;line-height:1;}
#combinedScalpClean .csc-side.up{color:#53e58e;} #combinedScalpClean .csc-side.down{color:#ff6f83;} #combinedScalpClean .csc-side.pass{color:#b6c1ca;font-size:22px;}
#combinedScalpClean .csc-context{text-align:right;font-size:11px;line-height:1.25;color:#b8c6d1;max-width:58%;}
#combinedScalpClean .csc-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;}
#combinedScalpClean .csc-stat{border:1px solid rgba(145,180,205,.35);border-radius:8px;padding:8px;min-width:0;background:rgba(6,20,31,.35);}
#combinedScalpClean .csc-lab{font-size:10px;color:#9fb0bd;margin-bottom:3px;} #combinedScalpClean .csc-val{font-size:18px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
#combinedScalpClean .csc-manage{border-radius:9px;padding:10px 12px;font-weight:900;font-size:14px;line-height:1.25;background:rgba(45,61,73,.55);}
#combinedScalpClean .csc-manage.active{background:rgba(26,111,74,.33);color:#76efaa;} #combinedScalpClean .csc-manage.protect{background:rgba(122,98,24,.40);color:#ffe477;} #combinedScalpClean .csc-manage.exit{background:rgba(129,45,58,.48);color:#ff9baa;}
#combinedScalpClean .csc-grid{display:grid;grid-template-columns:1fr;gap:6px;font-size:12px;line-height:1.25;}
#combinedScalpClean .csc-row{display:flex;justify-content:space-between;gap:12px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.07);}
#combinedScalpClean .csc-row span:first-child{color:#9fb0bd;} #combinedScalpClean .csc-row strong{text-align:right;color:#eef4f8;}
#combinedScalpClean .csc-safe{margin-top:auto;font-size:10px;color:#7f919f;text-align:center;letter-spacing:.2px;}
@media(max-width:700px){#combinedScalpClean{min-height:360px;padding:12px;gap:8px}#combinedScalpClean .csc-side{font-size:26px}#combinedScalpClean .csc-val{font-size:16px}}
</style>'''

JS = r'''<script id="btc15-combined-scalp-clean-script">
(()=>{
 const FEED='__FEED__'; let last=null,okAt=0,busy=false;
 const n=v=>{const x=Number(v);return Number.isFinite(x)?x:NaN};
 const cents=v=>Number.isFinite(n(v))?`${Math.round(n(v)*100)}¢`:'—';
 const sc=v=>Number.isFinite(n(v))?`${n(v)>=0?'+':''}${Math.round(n(v)*100)}¢`:'—';
 const secs=v=>Number.isFinite(n(v))?`${Math.max(0,Math.round(n(v)))}s`:'—';
 const valid=d=>d&&['BTC15_COMBINED_STATE_BRIDGE_V3','BTC15_COMBINED_STATE_BRIDGE_V4'].includes(d.version)&&d.manual_execution_only===true&&d.orders===false&&d.order_action===null&&d.numeric_flip_risk_validated===false&&d.contract;
 function panel(){
   const card=document.getElementById('scalpCard'); if(!card)return null;
   let p=document.getElementById('combinedScalpClean');
   if(!p){p=document.createElement('div');p.id='combinedScalpClean';card.appendChild(p);card.classList.add('btc15-clean-scalp-ready');}
   return p;
 }
 function ctx(d){const a=Array.isArray(d.context_labels)?d.context_labels:[];const fs=String(d.final?.side||'').toUpperCase();if(a.includes('COUNTERTREND_SCALP'))return `COUNTERTREND · FINAL ${fs||'—'}`;if(a.includes('MIXED_HORIZONS'))return 'MIXED HORIZONS';if(a.includes('ALIGNED'))return 'ALIGNED HORIZONS';return 'GENERALIZED SCALP';}
 function draw(d,main){
   const p=panel(); if(!p)return;
   const fresh=Date.now()-okAt<=3500, same=!!(main&&d&&d.contract===main.contract), env=valid(d);
   const s=(d&&d.scalp)||{}, state=String(s.state||'PASS').toUpperCase();
   const usable=fresh&&same&&env;
   const shown=usable?state:'PASS'; const side=usable?String(s.side||'').toUpperCase():'';
   const entry=usable?n(s.entry_ask):NaN,bid=usable?n(s.current_bid):NaN,gain=usable?n(s.exec_gain):NaN,peak=usable?n(s.peak_exec_gain):NaN;
   const gb=(Number.isFinite(peak)&&Number.isFinite(gain))?Math.max(0,peak-gain):NaN;
   const left=usable?n(d.canonical_seconds_left):NaN;
   const klass=shown==='EXIT'?'exit':shown==='PROTECT'?'protect':shown==='ACTIVE'?'active':'';
   const mainText=shown==='PASS'?(env&&!same?'WAIT · CONTRACT SYNC':fresh?'WAITING FOR QUALIFIED SCALP':'WAIT · FEED STALE'):(shown==='EXIT'?'EXIT / PROTECT PROFITS NOW':shown==='PROTECT'?'PROTECT PROFITS':'SCALP ACTIVE · BUILDING');
   const reason=usable?(d.scalp_block_reason||ctx(d)):(env&&!same?'Main/scalp contracts do not match':fresh?'No qualified generalized scalp':'Generalized scalp feed is stale/unavailable');
   const sideText=shown==='PASS'?'SCALP / REVERSAL':`${side==='DOWN'?'↓':'↑'} ${side}`;
   const sideClass=shown==='PASS'?'pass':side==='DOWN'?'down':'up';
   p.innerHTML=`
    <div class="csc-head"><div class="csc-title">◉ SCALP / REVERSAL</div><div class="csc-pill ${klass}">${shown==='PASS'?'WATCHING':shown}</div></div>
    <div class="csc-main"><div class="csc-side ${sideClass}">${sideText}</div><div class="csc-context">${reason}</div></div>
    <div class="csc-stats"><div class="csc-stat"><div class="csc-lab">ENTRY</div><div class="csc-val">${cents(entry)}</div></div><div class="csc-stat"><div class="csc-lab">CURRENT BID</div><div class="csc-val">${cents(bid)}</div></div><div class="csc-stat"><div class="csc-lab">EXEC GAIN</div><div class="csc-val">${sc(gain)}</div></div></div>
    <div class="csc-manage ${klass}">${mainText}</div>
    <div class="csc-grid">
      <div class="csc-row"><span>Running peak</span><strong>${sc(peak)}</strong></div>
      <div class="csc-row"><span>Giveback from peak</span><strong>${sc(gb)}</strong></div>
      <div class="csc-row"><span>Contract time left</span><strong>${secs(left)}</strong></div>
      <div class="csc-row"><span>Protection rule</span><strong>Arm +5¢ · EXIT at 4¢ giveback</strong></div>
      <div class="csc-row"><span>Context</span><strong>${usable?ctx(d):'FAIL-CLOSED'}</strong></div>
    </div>
    <div class="csc-safe">SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS</div>`;
 }
 async function poll(){if(busy)return;busy=true;try{const r=await fetch(FEED,{cache:'no-store',mode:'cors'});if(!r.ok)throw new Error(`HTTP ${r.status}`);const d=await r.json();if(!valid(d))throw new Error('INVALID ENVELOPE');last=d;okAt=Date.now();}catch(e){last=null;okAt=0;}finally{busy=false;}try{draw(last,window.__btc15LastMain||null)}catch(e){}}
 const oldApply=window.applyState;
 function hook(){if(typeof window.applyState==='function'&&!window.applyState.__cleanScalpHook){const orig=window.applyState;const wrapped=function(d,...rest){window.__btc15LastMain=d;const out=orig.call(this,d,...rest);try{draw(last,d)}catch(e){}return out};wrapped.__cleanScalpHook=true;window.applyState=wrapped;}}
 const start=()=>{panel();hook();poll();setInterval(()=>{hook();poll()},1000)};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
</script>'''.replace('__FEED__', FEED_URL)


def patch_clean_panel(path: Path) -> list[str]:
    text=path.read_text(encoding='utf-8',errors='replace'); changes=[]
    for sid in ('btc15-combined-scalp-clean-style','btc15-combined-scalp-clean-script'):
        tag='style' if sid.endswith('style') else 'script'
        start=text.find(f'<{tag} id="{sid}">')
        if start>=0:
            end=text.find(f'</{tag}>',start)
            if end>=0:text=text[:start]+text[end+len(f'</{tag}>'):];changes.append(f'replace-{sid}')
    if '</head>' in text:text=text.replace('</head>',CSS+'\n</head>',1)
    else:text=CSS+'\n'+text
    if '</body>' in text:text=text.replace('</body>',JS+f'\n<!-- {MARKER} -->\n</body>',1)
    else:text+='\n'+JS+f'\n<!-- {MARKER} -->\n'
    changes.append('clean-single-panel')
    path.write_text(text,encoding='utf-8'); return changes


def build_dashboard() -> Path:
    html=v2.build_dashboard();patch_clean_panel(html);return html


def main() -> int:
    html=build_dashboard();rendered=html.read_text(encoding='utf-8',errors='replace')
    print('COMBINED SCALP UI V3 | CLEAN SINGLE PANEL | SHADOW ONLY | NO ORDERS')
    if '--self-test' in sys.argv:
        assert MARKER in rendered
        assert rendered.count('id="combinedScalpClean"')==0  # created at runtime only
        assert rendered.count('id="btc15-combined-scalp-clean-script"')==1
        assert rendered.count('id="btc15-combined-scalp-clean-style"')==1
        assert 'Arm +5¢ · EXIT at 4¢ giveback' in rendered
        assert 'SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS' in rendered
        assert "btc15-clean-scalp-ready > *:not(#combinedScalpClean)" in rendered
        assert 'flip_risk_percent' not in rendered
        print('COMBINED SCALP UI V3 SELFTEST PASS | LEGACY INNER ROWS HIDDEN | CLEAN PANEL | NO ORDERS')
        return 0
    wrapper=html.parent/'BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py'
    os.execv(sys.executable,[sys.executable,'-u',str(wrapper)])


if __name__=='__main__':raise SystemExit(main())
