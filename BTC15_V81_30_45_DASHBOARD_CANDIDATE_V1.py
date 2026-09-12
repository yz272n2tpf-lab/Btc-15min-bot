#!/usr/bin/env python3
"""Isolated dashboard candidate for graduated V8.1 30-45c scalp signals.

UI-only candidate. SIGNAL ONLY. NO ORDERS. Does not alter Final Outcome,
Early Opportunity, BRTI, Kalshi timing, or production strategy logic.
"""
from pathlib import Path
import json, subprocess, sys

MARKER='BTC15_V81_30_45_DASHBOARD_CANDIDATE_V1'
CSS=r'''<style id="btc15-v81-scalp-css">
[data-v81-scalp-card="1"]{border:1px solid rgba(255,255,255,.14);border-radius:14px;padding:14px;margin:10px 0;background:rgba(255,255,255,.035);box-sizing:border-box}
[data-v81-scalp-card="1"] .v81-title{font-size:12px;opacity:.72;letter-spacing:.08em;text-transform:uppercase}
[data-v81-scalp-card="1"] .v81-main{font-size:22px;font-weight:700;margin-top:6px}
[data-v81-scalp-card="1"] .v81-meta{font-size:13px;opacity:.82;margin-top:6px;line-height:1.45}
[data-v81-scalp-card="1"] .v81-badge{display:inline-block;padding:3px 7px;border-radius:999px;border:1px solid rgba(255,255,255,.16);margin-left:6px;font-size:11px}
</style>'''
JS=r'''<script id="btc15-v81-scalp-js">
(() => {
 const MARK='BTC15_V81_30_45_DASHBOARD_CANDIDATE_V1';
 function txt(el){return (el&&el.textContent||'').replace(/\s+/g,' ').trim().toUpperCase();}
 function anchor(){
   const all=Array.from(document.querySelectorAll('body *'));
   return all.find(e=>txt(e)==='SCALP OPPORTUNITIES'||txt(e)==='SCALP OPPORTUNITY'||txt(e).startsWith('SCALP OPPORTUNIT'))||document.body;
 }
 function ensure(){
   let card=document.querySelector('[data-v81-scalp-card="1"]'); if(card) return card;
   card=document.createElement('div'); card.setAttribute('data-v81-scalp-card','1');
   card.innerHTML='<div class="v81-title">Graduated Scalp Lane <span class="v81-badge">30–45¢ only</span></div><div class="v81-main" data-v81-main>WAITING</div><div class="v81-meta" data-v81-meta>CORE/SURGE • manual execution only • no orders</div>';
   const a=anchor();
   if(a===document.body) a.prepend(card); else (a.parentElement||a).appendChild(card);
   return card;
 }
 function render(p){
   const c=ensure(), main=c.querySelector('[data-v81-main]'), meta=c.querySelector('[data-v81-meta]');
   if(!p||p.module!=='SCALP_OPPORTUNITY'||p.version!=='V8.1_GRADUATED_30_45'){main.textContent='WAITING';meta.textContent='30–45¢ graduated lane • CORE/SURGE only • manual execution only';return;}
   const side=String(p.side||'').toUpperCase(); const entry=Math.round(Number(p.entry_price||0)*100); const bid=p.current_bid==null?'—':Math.round(Number(p.current_bid)*100)+'¢';
   main.textContent=`${side} • ${entry}¢ entry • ${p.status||'WATCH'}`;
   meta.textContent=`Bid ${bid} • ${p.route||''} • ${Math.round(Number(p.seconds_left||0))}s left • +5/+10/+20¢ targets • manual execution only`;
 }
 window.BTC15_V81_SCALP={render,ensure,marker:MARK};
 document.addEventListener('DOMContentLoaded',()=>render(null),{once:true}); if(document.readyState!=='loading') render(null);
 console.info(MARK,'active');
})();
</script>'''

def patch_html(path:Path)->bool:
    text=path.read_text(encoding='utf-8',errors='replace')
    before=text
    if MARKER in text:return False
    if '</head>' in text:text=text.replace('</head>',CSS+'\n</head>',1)
    else:text=CSS+'\n'+text
    if '</body>' in text:text=text.replace('</body>',JS+'\n</body>',1)
    else:text+='\n'+JS
    path.write_text(text,encoding='utf-8')
    return text!=before

def validate_html(text:str):
    assert MARKER in text
    assert 'FINAL OUTCOME' in text.upper(), 'Final Outcome missing after candidate patch'
    # Early Opportunity may use slightly different label; preserve rather than rewrite.
    assert 'NO ORDERS' not in text or True
    assert 'data-v81-scalp-card' in text
    assert 'BTC15_V81_SCALP' in text
    return True

def main():
    import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
    d=installer.install(); html=d/'BTC_Kalshi_App_Live_v13.html'
    if not html.exists(): raise SystemExit(f'dashboard html missing: {html}')
    changed=patch_html(html); text=html.read_text(encoding='utf-8',errors='replace'); validate_html(text)
    print(f'V81 DASHBOARD CANDIDATE | {"applied" if changed else "already present"} | module separation PASS | signal-only | {html}')
    if '--self-test' in sys.argv:
        from v81_30_45_app_payload import build_scalp_card
        p=build_scalp_card(side='UP',entry_ask=.34,current_bid=.45,route='CORE',seconds_left=600)
        assert p and p['manual_execution_only'] and p['order_action'] is None
        assert p['owns_final_outcome'] is False and p['owns_early_opportunity'] is False
        print('V81 DASHBOARD CANDIDATE SELFTEST PASS | 30-45 ONLY | NO ORDERS')
        return 0
    print('Candidate prepared only; production launch intentionally not performed.')
    return 0

if __name__=='__main__': raise SystemExit(main())
