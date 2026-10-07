"""BTC15 operator-cockpit presentation overlay.

Display-only cleanup over the reviewed 1bd5b44d product assembly.
No strategy/model/threshold/authority/source/scoring/order behavior changes.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path

MARKER = "BTC15_OPERATOR_COCKPIT_V1"

CSS = r'''<style id="btc15-operator-cockpit-v1">
/* FINAL: one call surface, no management ladder. */
#finalBuyZone,#finalHoldZone,#finalWatchZone,#finalProtectZone,#finalExitZone,#finalActionSub{display:none!important}
/* EARLY: ladder is primary; remove duplicate authority/edge chatter. */
#earlyYourEntry,#earlyEdge,#earlyAfterEntry,#earlyFlow{display:none!important}
/* SCALP: one reusable ladder; separate reversal/re-entry panel and yellow chatter leave the cockpit. */
#oppositeEntry,#oppositeState,#oppositeArrow,#scalpYourEntry,#scalpTargetStrip,#scalpFlow{display:none!important}
/* Kalshi: main operator view shows only the UP/DOWN buy prices. */
#upCondition,#downCondition,#v2QuoteClock{display:none!important}
/* Redundant lower scoring/context chrome leaves the cockpit; values remain available in Details. */
#flipRisk,#flipRiskSub,#evidenceScore,#momentumBadge,#momentumSub,
#contextTrend,#contextRange,#contextBrti,#contextLevels,#contextBanner{display:none!important}
#botHealthReason{margin-top:.35rem;color:var(--muted,#aab4c8);font-size:.82rem;line-height:1.35}
#operatorMarketContext{margin-top:.75rem}
#operatorMarketContextValue{font-weight:760;line-height:1.4;overflow-wrap:anywhere}
#operatorDetails{margin-top:1rem;border:1px solid rgba(170,180,200,.22);border-radius:12px;padding:.7rem .85rem}
#operatorDetails summary{cursor:pointer;font-weight:800;letter-spacing:.04em}
#operatorDetailsBody{padding-top:.65rem;color:var(--muted,#aab4c8);font-size:.82rem;line-height:1.45}
#operatorDetailsBody .detail-line{margin:.32rem 0;overflow-wrap:anywhere}
</style>'''

JS = r'''<script id="btc15-operator-cockpit-v1-script">
(()=>{
  'use strict';
  const byId=id=>document.getElementById(id);
  const value=n=>(n?.textContent||'').replace(/\s+/g,' ').trim();
  const leaves=()=>Array.from(document.querySelectorAll('body *')).filter(n=>!n.children.length);
  const exact=label=>leaves().find(n=>value(n).toUpperCase()===label);
  const card=n=>{for(let p=n,i=0;p&&i<7;p=p.parentElement,i++)if(p.classList?.contains('card'))return p;return null;};
  const row=n=>{for(let p=n,i=0;p&&i<4;p=p.parentElement,i++)if(p.classList?.contains('ladder-row')||p.classList?.contains('pos'))return p;return n;};
  const hideRow=id=>{const n=byId(id);if(n)row(n).style.setProperty('display','none','important');};
  const hideCard=label=>{const c=card(exact(label));if(c)c.style.setProperty('display','none','important');};
  const esc=s=>String(s||'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');

  function ensureHealth(){
    const label=exact('SIGNAL STRENGTH'); if(label)label.textContent='BOT HEALTH';
    const n=byId('signalStrength'); if(!n)return;
    let reason=byId('botHealthReason');
    if(!reason){reason=document.createElement('div');reason.id='botHealthReason';n.insertAdjacentElement('afterend',reason);}
  }
  function updateHealth(){
    const status=value(byId('liveStatus')).toUpperCase();
    const main=status.includes('MAIN TRACKING'),scalp=status.includes('SCALP TRACKING');
    const uq=value(byId('upCondition')).toUpperCase(),dq=value(byId('downCondition')).toUpperCase();
    const quote=uq.startsWith('ASK')&&dq.startsWith('ASK');
    const health=main&&scalp&&quote?'HEALTHY':(main||scalp||quote?'DEGRADED':'ISSUE');
    const n=byId('signalStrength'),r=byId('botHealthReason');
    if(n&&value(n)!==health)n.textContent=health;
    const missing=[main?'':'MAIN',scalp?'':'SCALP',quote?'':'KALSHI'].filter(Boolean);
    const why=health==='HEALTHY'?'MAIN, SCALP and Kalshi quote feeds tracking':'Refreshing: '+missing.join(' + ');
    if(r&&value(r)!==why)r.textContent=why;
  }
  function ensureMarketContext(){
    if(byId('operatorMarketContext'))return;
    const anchor=card(byId('signalStrength'))||document.querySelector('.secondary-grid')||document.querySelector('main')||document.body;
    const c=document.createElement('section');c.id='operatorMarketContext';c.className='card';
    c.innerHTML='<div class="eyebrow">MARKET CONTEXT</div><div id="operatorMarketContextValue">REFRESHING</div>';
    anchor.insertAdjacentElement('afterend',c);
  }
  function updateMarketContext(){
    const out=byId('operatorMarketContextValue'),src=byId('contextBanner');if(!out)return;
    const v=value(src),next=v&&v!=='—'?v:'Waiting for qualified market context';
    if(value(out)!==next)out.textContent=next;
  }
  function plainFinal(){
    const action=byId('finalAction'),reason=byId('finalReason');if(!action)return;
    const raw=value(action).toUpperCase(),side=value(byId('finalSide')).toUpperCase();
    let next=raw;
    if(raw.includes('NOT LOCKED')||raw.includes('REFRESHING'))next='WAIT';
    else if(raw.includes('FINAL LOCK')||raw.includes('QUALIFIED'))next='HOLD '+(side==='UP'||side==='DOWN'?side:'');
    next=next.trim();
    if(value(action)!==next)action.textContent=next;
    if(reason){
      let r=value(reason);
      r=r.replace(/FINAL lock not qualified/gi,'Final confirmation is not strong enough yet')
         .replace(/Probability live;\s*/gi,'')
         .replace(/no new action authority/gi,'waiting for fresh confirmation')
         .replace(/qualified/gi,'confirmed');
      if(value(reason)!==r)reason.textContent=r;
    }
  }
  function cleanEarlyLanguage(){
    const title=byId('earlyTitle'),state=byId('earlyState'),entry=byId('earlyEntry'),price=byId('earlyCurrentPrice');
    // Keep only direction/status + current action/reason + necessary price above ladder.
    ['earlyYourEntry','earlyEdge','earlyAfterEntry','earlyFlow'].forEach(id=>{const n=byId(id);if(n)n.style.setProperty('display','none','important');});
    const replacements=[
      ['earlyLadderHold',/No protected position assumed/gi,'No active EARLY entry'],
      ['earlyLadderProtect',/Protection begins only after a protected origin/gi,'Protection starts after an EARLY entry'],
      ['earlyLadderExit',/Directional EXIT authority not yet validated[^·]*/gi,'EXIT when the live ladder reaches Exit Now'],
      ['earlyLadderExit',/PROTECT is manual risk guidance/gi,'Protect profits when shown']
    ];
    replacements.forEach(([id,re,to])=>{const n=byId(id);if(n){const v=value(n).replace(re,to);if(value(n)!==v)n.textContent=v;}});
    if(entry){
      let v=value(entry).replace(/No protected origin/gi,'No EARLY entry').replace(/manual opportunity guidance only/gi,'waiting for an EARLY setup');
      if(value(entry)!==v)entry.textContent=v;
    }
  }
  function cleanBotHealth(){
    const h=byId('signalStrength');if(!h)return;
    const c=card(h);if(!c)return;
    // Old signal-strength bars/agreement visuals are not Bot Health.
    c.querySelectorAll('.strength-bar,.strength-bars,.signal-bars,.bar,.agreement,.agreement-row').forEach(n=>n.style.setProperty('display','none','important'));
    Array.from(c.querySelectorAll('*')).forEach(n=>{
      const t=value(n).toUpperCase();
      if(t==='CURRENT AGREEMENT'||t.startsWith('CURRENT AGREEMENT '))n.style.setProperty('display','none','important');
    });
  }
  function stripLegacyLowerChrome(){
    // Quick Notes and the large Market information diagnostics are developer
    // surfaces; preserve their values for Details but remove them from cockpit.
    ['QUICK NOTES','MARKET INFORMATION'].forEach(hideCard);
    // Exactly one operator Market Context: legacy context/momentum cards are diagnostics.
    const op=byId('operatorMarketContext');
    Array.from(document.querySelectorAll('.card')).forEach(c=>{
      if(c===op)return;
      const t=value(c).toUpperCase();
      if(t.startsWith('MARKET CONTEXT')||t.startsWith('MARKET MOMENTUM'))c.style.setProperty('display','none','important');
    });
    // Indicator/timeframe diagnostics are preserved in the legacy DOM for Details,
    // but are not part of the normal cockpit.
    document.querySelectorAll('.indicator-row').forEach(n=>n.style.setProperty('display','none','important'));
  }
  function ensureDetails(){
    if(byId('operatorDetails'))return;
    const host=document.querySelector('main')||document.body,d=document.createElement('details');
    d.id='operatorDetails';d.innerHTML='<summary>DETAILS</summary><div id="operatorDetailsBody"></div>';host.appendChild(d);
  }
  function updateDetails(){
    const body=byId('operatorDetailsBody');if(!body)return;
    const rows=[];
    const add=(label,id)=>{const v=value(byId(id));if(v)rows.push('<div class="detail-line"><strong>'+label+':</strong> '+esc(v)+'</div>');};
    add('UP quote detail','upCondition');add('DOWN quote detail','downCondition');add('Quote provenance','v2QuoteClock');
    add('Flip risk','flipRisk');add('Evidence score','evidenceScore');add('Momentum','momentumBadge');add('Momentum detail','momentumSub');
    add('Trend','contextTrend');add('Range','contextRange');add('BRTI context','contextBrti');add('Levels','contextLevels');
    add('EARLY diagnostics','earlyFlow');add('SCALP diagnostics','scalpFlow');
    const info=byId('btc15-information-assessment');if(info&&value(info))rows.push('<div class="detail-line"><strong>Information diagnostics:</strong> '+esc(value(info))+'</div>');
    const next=rows.join('')||'<div class="detail-line">Diagnostics refreshing.</div>';
    if(body.innerHTML!==next)body.innerHTML=next;
  }
  function cleanStructure(){
    ['finalBuyZone','finalHoldZone','finalWatchZone','finalProtectZone','finalExitZone',
     'earlyYourEntry','earlyEdge','earlyAfterEntry','scalpYourEntry','scalpTargetStrip'].forEach(hideRow);
    hideCard('FLIP RISK');hideCard('EVIDENCE SCORE');hideCard('MARKET MOMENTUM');
    // Never hide a legacy parent card by inference: on iPad the reversal node can
    // share the SCALP card. Hide only the reversal/re-entry nodes themselves.
    ['oppositeEntry','oppositeState','oppositeArrow','oppositeTitle'].forEach(id=>{
      const n=byId(id);if(n)n.style.setProperty('display','none','important');
    });
    // SCALP is a required operator surface. Force its action fields and all five
    // ladder rows visible even if legacy responsive CSS tried to collapse them.
    ['scalpEntry','scalpLadderEntry','scalpLadderHold','scalpLadderWatch','scalpLadderProtect','scalpLadderExit'].forEach(id=>{
      const n=byId(id);if(n){n.style.removeProperty('display');const r=row(n);if(r)r.style.removeProperty('display');}
    });
  }
  function apply(){ensureHealth();ensureMarketContext();ensureDetails();cleanStructure();plainFinal();cleanEarlyLanguage();cleanBotHealth();stripLegacyLowerChrome();updateHealth();updateMarketContext();updateDetails();}
  document.addEventListener('DOMContentLoaded',apply,{once:true});if(document.readyState!=='loading')apply();
  setInterval(apply,250);
  console.info('BTC15_OPERATOR_COCKPIT_V1 active');
})();
</script>'''

def patch_html(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    if "</head>" not in text or "</body>" not in text:
        raise ValueError("DASHBOARD_HTML_SEAM")
    text = text.replace("</head>", CSS + "\n</head>", 1)
    text = text.replace("</body>", JS + "\n<!-- " + MARKER + " -->\n</body>", 1)
    path.write_text(text, encoding="utf-8")
    return True

def refresh_assembled_manifest(directory: Path) -> None:
    manifest_path=directory/"manifest.json"
    if not manifest_path.exists():
        return
    manifest=json.loads(manifest_path.read_text())
    html=directory/"BTC_Kalshi_App_Live_v13.html"
    if html.exists() and isinstance(manifest.get("files"),dict):
        manifest["files"][html.name]=hashlib.sha256(html.read_bytes()).hexdigest()
    manifest["operator_cockpit"]=MARKER
    manifest_path.write_text(json.dumps(manifest,indent=2)+"\n")

def assemble(directory: Path):
    from btc15_v2_product.installer import assemble as reviewed_assemble
    d=reviewed_assemble(directory)
    html=d/"BTC_Kalshi_App_Live_v13.html"
    if not html.exists():
        raise ValueError("DASHBOARD_HTML_MISSING")
    patch_html(html)
    refresh_assembled_manifest(d)
    return d

def preview_main(directory: Path):
    """Serve only the assembled cockpit shell, proxying live read-only endpoints.

    This preview never loads Kalshi credentials and never runs a trading/native
    worker. It consumes the already-reviewed production HTTP presentation feeds.
    """
    import http.server
    import urllib.request
    from urllib.parse import urlsplit
    d=assemble(directory)
    upstream=os.getenv("BTC15_PREVIEW_UPSTREAM","").rstrip("/")
    if not upstream.startswith("https://"):
        raise ValueError("PREVIEW_UPSTREAM_REQUIRED")
    port=int(os.getenv("PORT","8080"))
    # Mirror every read-only presentation route used by the reviewed dashboard.
    # /information is required for model context/chart/timer identity continuity;
    # /ladders/* carries MAIN, quotes, indicators and panel assets.
    proxy_paths=("/ladders","/information","/dashboard_state.json","/health","/btc15-information")
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(d),**kwargs)
        def do_GET(self):
            path=urlsplit(self.path).path
            if any(path==p or path.startswith(p+"/") for p in proxy_paths):
                try:
                    headers={"Accept":self.headers.get("Accept","*/*"),"User-Agent":"BTC15-operator-preview/2"}
                    nonce=self.headers.get("X-BTC15-Information-Nonce")
                    if nonce: headers["X-BTC15-Information-Nonce"]=nonce
                    req=urllib.request.Request(upstream+self.path,headers=headers)
                    with urllib.request.urlopen(req,timeout=4) as r:
                        body=r.read();self.send_response(r.status)
                        self.send_header("Content-Type",r.headers.get("Content-Type","application/json"))
                        self.send_header("Cache-Control","no-store")
                        nonce_reply=r.headers.get("X-BTC15-Information-Nonce")
                        if nonce_reply:self.send_header("X-BTC15-Information-Nonce",nonce_reply)
                        self.end_headers();self.wfile.write(body)
                except Exception:
                    self.send_response(503);self.send_header("Content-Type","application/json");self.end_headers()
                    self.wfile.write(b'{"status":"UNAVAILABLE","reason":"PREVIEW_UPSTREAM"}')
                return
            if path=="/":
                self.path="/BTC_Kalshi_App_Live_v13.html"
            return super().do_GET()
        def log_message(self,format,*args): pass
    http.server.ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lane",choices=["main"],default="main")
    p.add_argument("--run-reviewed-production",action="store_true")
    p.add_argument("--preview",action="store_true")
    p.add_argument("--directory",type=Path,default=Path("/tmp/btc15_operator_cockpit_v1"))
    a=p.parse_args()
    from btc15_v2_product.release import verify_files,verify_environment,ROOT
    verify_files("main")
    if a.preview:
        return preview_main(a.directory)
    if not a.run_reviewed_production:
        d=assemble(a.directory)
        print(d/"manifest.json")
        return 0
    verify_environment("main")
    if os.getenv("BTC15_ENABLE_INFORMATION_EXPORT")!="1":
        raise ValueError("INFORMATION_EXPORT_OPT_IN_REQUIRED")
    if Path.cwd().resolve()!=ROOT:
        raise ValueError("REPOSITORY_WORKING_DIRECTORY_REQUIRED")
    from btc15_information_install_v1 import supervise
    with open("/tmp/btc15-two-clock.lock","a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return supervise(assemble(a.directory),worker_script=ROOT/"btc15_v2_product/worker.py")

if __name__=="__main__":
    raise SystemExit(main())
