"""Assemble the entire frozen dashboard, then retire legacy action DOM ownership."""
import hashlib
import json
from pathlib import Path
import re
from btc15_information_install_v1 import assemble as frozen_assemble,replace_once,ROOT

def owned_id(name):
    return name.startswith(('early','final','scalp','opposite')) or name in {
        'flipRisk','flipRiskSub','signalStrength','contextBanner','upOdds','downOdds','upCondition','downCondition','currentContract','liveStatus'}

def assemble(directory):
    d=frozen_assemble(directory);path=d/'BTC_Kalshi_App_Live_v13.html';html=path.read_text()
    owned=sorted({name for name in re.findall(r'id="([^"]+)"',html) if owned_id(name)})
    old='const $ = (id) => document.getElementById(id);'
    if html.count(old)!=1:raise ValueError('PINNED_LEGACY_DOM_SEAM')
    # Detached nodes retain legacy algorithm execution/error behavior, but can
    # never mutate an action card. All non-action chart/timer DOM stays intact.
    new='const retiredActionIds=new Set('+json.dumps(owned)+');\n  const retiredNodes=new Map();\n  const $ = (id) => { if(!retiredActionIds.has(id))return document.getElementById(id); if(!retiredNodes.has(id)){const n=document.getElementById(id);retiredNodes.set(id,n?n.cloneNode(true):null);}return retiredNodes.get(id); };'
    html=html.replace(old,new).replace('DIAGNOSTIC V13.2-P1','V2')
    html=html.replace('if(window.btc15RenderLadders)window.btc15RenderLadders();','')
    # Initial HTML also fails closed before scripts load or when scripts fail.
    for name in owned:
        if name=='signalStrength':continue  # Preserve its original neutral markup.
        html=re.sub(r'(<[^>]+id="'+re.escape(name)+r'"[^>]*>)([^<]*)(</)',
                    lambda m:m[1]+(('—' if 'Arrow' in name else 'WAIT') if m[2].strip() else m[2])+m[3],html)
    html=html.replace('<span>Target exit</span>','<span>Protection</span>').replace('<span>Exit / stop</span>','<span>Exit guidance</span>')
    css='''<style id="v2-product-layout">
      #finalSide{font-size:clamp(1.25rem,5vw,2rem);overflow-wrap:anywhere}
      #finalConfidence{font-size:1rem;color:var(--muted,#aab4c8)}
      #finalAction{font-size:clamp(1.3rem,5vw,2rem);font-weight:850;overflow-wrap:anywhere}
      .wait-mode #finalSide,.wait-mode #finalArrow{color:var(--muted,#aab4c8)}
      .ladder-row strong,.pos strong,.flow-status{min-width:0;overflow-wrap:anywhere}
      #v2QuoteClock{font-size:.8rem;overflow-wrap:anywhere;color:var(--muted,#aab4c8)}
      #upOdds,#downOdds{font-size:clamp(1.1rem,4vw,2rem);overflow-wrap:anywhere}
      #flipRisk{color:var(--muted,#aab4c8);font-size:clamp(1.1rem,4vw,2rem);overflow-wrap:anywhere}
      /* The frozen desktop columns need >1000px; phone reflow ends at 700px. */
      .odds{grid-template-columns:auto minmax(0,1fr)}
      .odds .kalshi-condition{grid-column:1/-1;white-space:normal;overflow-wrap:anywhere}
      @media (min-width:701px) and (max-width:1100px){
        .primary-grid{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:auto auto auto}
        .primary-grid>*{min-width:0}
        .right-stack{grid-column:1/-1;grid-row:2;grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:auto;align-items:start}
        .right-stack>*{min-width:0}
        .chart-card{grid-row:3}
        .odds-grid{grid-template-columns:1fr}
        .secondary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
        .market-card{grid-column:1/-1}
      }
    </style>'''
    html=html.replace('</head>',css+'\n</head>')
    html=html.replace('<script src="/ladders/panel.js"></script>',
        '<p id="v2QuoteClock" role="status">REFRESHING · awaiting executable quotes</p>\n<script src="/ladders/panel.js"></script>')
    path.write_text(html)
    server=d/'BTC15_DASHBOARD_LIVE_SERVER_V1.py'
    replace_once(server,'from btc15_ladder_routes_v1 import serve as serve_ladders','from btc15_v2_product.routes import serve as serve_ladders')
    wrapper=d/'btc15_run_with_rescue_v2_shadow_v1.py'
    replace_once(wrapper,str(ROOT/'btc15_information_native_offpath_candidate.py'),str(ROOT/'btc15_v2_native.py'))
    manifest=dict(schema='BTC15_V2_ASSEMBLED_DASHBOARD_R1',owned_action_ids=owned,
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir()) if p.is_file() and p.name!='manifest.json'},
        signal_only=True,orders=False)
    (d/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return d
