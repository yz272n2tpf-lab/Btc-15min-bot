"""Self-contained OFFLINE UI fixture, no local server or external source access."""
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'qualification/v2_product_20261004'

def build():
    html=(OUT/'dashboard/BTC_Kalshi_App_Live_v13.html').read_text()
    fixture=json.loads((OUT/'ui_fixture.json').read_text())
    script='''<script>
    const fixtureData=FIXTURE, previewStart=performance.now();
    window.fetch=async function(url,options={}){
      let lane=String(url).includes('fixture-v81')?'scalp':url==='/ladders'?'main':url==='/ladders/quotes'?'quote':null;
      let data=lane?JSON.parse(JSON.stringify(fixtureData[lane])):{status:'WAIT'};
      if(lane){const delta=(performance.now()-previewStart)/1000;for(const key of ['published_ts','served_ts','expires_at','exchange_ts','accepted_ts'])if(Number.isFinite(data[key]))data[key]+=delta;}
      if(location.hash==='#unavailable'&&lane){data.status='UNAVAILABLE';data.reason='SOURCE_EXPIRED';delete data.expires_at;delete data.final;}
      return {ok:true,headers:{get:()=>null},json:async()=>data};
    };
    </script>'''.replace('FIXTURE',json.dumps(fixture))
    html=html.replace('<script>',script+'\n<script>',1)
    replacements={'/information/view.js':'btc15_information_view_v1.js','/information/panel.js':'btc15_information_panel_v1.js','/ladders/panel.js':'btc15_v2_product/panel.js'}
    for src,name in replacements.items():
        raw=(ROOT/name).read_text().replace('__V81_LADDERS_URL__',json.dumps('/fixture-v81/ladders'))
        html=html.replace('<script src="'+src+'"></script>','<script>\n'+raw+'\n</script>')
    html=html.replace('<body>','<body><div style="padding:12px;background:#675000;color:white">OFFLINE FIXTURES · NO LIVE INPUTS · NO ORDERS</div>')
    (OUT/'browser_fixture.html').write_text(html)
    harness='''<!doctype html><meta charset="utf-8"><title>BTC15 offline visual qualification</title>
    <style>body{background:#111827;color:white;font:16px sans-serif}button{padding:10px;margin:6px}iframe{display:block;background:#0b1020;border:2px solid #64748b;height:1600px;max-width:100%}</style>
    <h1>BTC15 offline visual qualification</h1><p>Real assembled scripts with synthetic transport only. No production connection.</p>
    <button onclick="document.getElementById('preview').style.width='390px'">Phone 390px</button>
    <button onclick="document.getElementById('preview').style.width='820px'">Tablet 820px</button>
    <button onclick="document.getElementById('preview').style.width='1180px'">Desktop 1180px</button>
    <button onclick="document.getElementById('preview').src='browser_fixture.html#unavailable'">Unavailable fixture</button>
    <button onclick="document.getElementById('preview').src='browser_fixture.html'">Fresh fixture</button>
    <iframe id="preview" title="Assembled V2 dashboard" src="browser_fixture.html" style="width:1180px"></iframe>'''
    (OUT/'browser_preview.html').write_text(harness)
    print(OUT/'browser_preview.html')

if __name__=='__main__':build()
