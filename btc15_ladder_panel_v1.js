(() => {
  const panel=document.createElement('section');
  panel.style.cssText='margin:16px;padding:20px;border:1px solid #476780;border-radius:16px;background:#101c2b;color:#edf5ff;font:15px/1.5 system-ui';
  panel.innerHTML='<h2>BTC15 · SIGNAL ONLY</h2><div id="lp-body">Waiting for current ladder state…</div><p>Manual execution · No orders</p>';
  document.body.appendChild(panel);
  const body=panel.querySelector('#lp-body');let current=null;
  const fmt=(p)=>Number.isFinite(p)?(100*p).toFixed(1)+'%':'Unavailable';
  const line=(text)=>{const e=document.createElement('p');e.textContent=text;body.appendChild(e);};
  function render(){
    body.replaceChildren();const s=current,now=Date.now()/1000;
    if(!s || s.status==='UNAVAILABLE' || !(s.published_ts<=now && now<s.expires_at)){
      line('UNAVAILABLE · '+(s?.reason||'Waiting for fresh causal inputs'));return;
    }
    line(`${s.contract} · target $${s.target.toLocaleString()} · ${s.phase.replaceAll('_',' ')}`);
    line(`FINAL: UP ${fmt(s.final.probability_up)} / DOWN ${fmt(s.final.probability_down)} · ${s.final.state.replaceAll('_',' ')}`);
    line(`EARLY: ${s.early.guidance} ${s.origin?.side||s.early.side} · ${s.origin?'original ASK '+(s.origin.original_ask*100).toFixed(1)+'¢':s.early.pass_reasons.join(', ')}`);
    line('Value target ≤50¢ · ideal 25–35¢ · current qualified entry ceiling 45¢');
    line(`EARLY protection: ${s.warning||'No linked EARLY origin'} · Flip risk ${s.flip_risk_pct.toFixed(1)}%`);
    line('Executable EXIT rule unavailable. No long-run accuracy claim.');
    line(`Journal #${s.journal.sequence} · BRTI age ${(now-(s.published_ts-s.health.brti_age)).toFixed(2)}s`);
  }
  async function poll(){try{const r=await fetch('/ladders',{cache:'no-store'});current=await r.json();}catch{current=null;}render();}
  setInterval(poll,1000);setInterval(render,250);poll();
})();
