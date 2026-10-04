/* The three existing cards consume committed guidance. No trading controls. */
(() => {
  const CANDIDATE='BTC15_LADDER_COMPLETION_20261003_V2';
  const SCALP_URL="https://v81-live-diagnostics-production.up.railway.app/ladders";
  const caches={main:null,scalp:null},busy={main:false,scalp:false}; let epoch=0;
  const text=(id,value)=>{const el=document.getElementById(id);if(el)el.textContent=value;};
  const cents=v=>Number.isFinite(v)?(100*v).toFixed(1)+'¢':'Unavailable';
  const pct=v=>Number.isFinite(v)?(100*v).toFixed(1)+'%':'Unavailable';
  const human=v=>String(v||'').replaceAll('_',' ').toLowerCase();
  function current(lane){const c=caches[lane];return c&&performance.now()<c.deadline&&document.visibilityState!=='hidden'?c.data:null;}
  function pill(id,value){const el=document.getElementById(id);if(!el)return;el.textContent=value;el.className='state-pill '+(['EXIT','PROTECT','CAUTION','UNAVAILABLE'].includes(value)?'state-watch':'state-good');}
  function unavailable(prefix,reason,origin){
    pill(prefix+'State','UNAVAILABLE');text(prefix+'Entry',reason);text(prefix+'CurrentPrice','Unavailable');
    text(prefix+'YourEntry',origin?'Origin ASK '+cents(origin.original_ask)+' · historical':'No accepted origin');
    for(const key of ['Entry','Hold','Watch','Protect','Exit'])text(prefix+'Ladder'+key,'UNAVAILABLE · fresh evidence required');
    text(prefix+'Flow','SIGNAL ONLY · NO ORDERS · '+reason);
  }
  function render(){
    const m=current('main'),s=current('scalp');
    const qualified=m&&m.status!=='UNAVAILABLE';
    const f=m?.final;
    if(f&&(qualified||m.final_status==='AVAILABLE')){
      text('finalArrow',f.side==='DOWN'?'↓':'↑');text('finalSide',f.side);text('finalConfidence',pct(f.confidence));
      text('finalAction',f.lock_state);text('finalActionSub',`UP ${pct(f.probability_up)} · DOWN ${pct(f.probability_down)}`);
      text('finalReason',f.ready?'Independent FINAL call qualified':'Independent probability available · FINAL entry PASS');
      text('finalBuyZone',m.origin&&f.early_origin_id===m.origin.origin_id&&m.origin.contract===m.contract?'Linked EARLY '+m.origin.side:'No linked EARLY origin');
      text('finalHoldZone',f.helper?.confirmed?'EARLY confirmed · '+f.helper.state:human(f.state));
      text('finalWatchZone',f.helper?human(f.helper.relation)+' · '+human(f.helper.probability_trend):'Independent FINAL; no position assumed');
      text('finalProtectZone',f.helper?.protect_latched?'PROTECT · confirmation lost or opposition':f.helper?'Protection monitoring active':'No linked origin');
      text('finalExitZone','EARLY exit threshold unsupported · no automatic EXIT');
    } else {
      for(const id of ['finalSide','finalConfidence','finalAction','finalActionSub','finalReason','finalBuyZone','finalHoldZone','finalWatchZone','finalProtectZone','finalExitZone'])text(id,'UNAVAILABLE');
    }
    if(!qualified){
      unavailable('early',m?.reason||'Waiting for fresh native evidence',m?.origin);
      text('earlyAfterEntry','No current guidance');text('earlyEdge','Unavailable');
      text('flipRisk','Unavailable');text('flipRiskSub','Fresh model inputs required');
    } else {
      const e=m.early,o=m.origin,h=f.helper,ctx=m.context;
      pill('earlyState',e.guidance);text('earlyTitle',o?'EARLY '+o.side:'EARLY · '+e.guidance);
      text('earlyEntry',o?'Origin ASK '+cents(o.original_ask):'Current ASK '+cents(e.ask));
      text('earlyYourEntry',o?cents(o.original_ask)+' · signal ASK':'No accepted origin');
      text('earlyCurrentPrice',o?'BID '+cents(m.executable_current_bid):'ASK '+cents(e.ask));
      text('earlyEdge',o?m.movement_cents.toFixed(1)+'¢ gross movement':cents(e.edge)+' model edge');
      text('earlyAfterEntry',o?e.guidance+' · '+human(h.relation):'PASS · '+e.pass_reasons.map(human).join(', '));
      text('earlyLadderEntry','Qualified ceiling 45¢ · target ≤50¢ · ideal 25–35¢');
      text('earlyLadderHold',h?.confirmed?'FINAL confirms · '+e.guidance:o?e.guidance:'No position assumed');
      text('earlyLadderWatch',ctx?human(ctx.phase)+' · '+ctx.reasons.map(human).join('; '):'Await qualified value entry');
      text('earlyLadderProtect',h?.protect_latched?'PROTECT · review exposure at current bid':o?'Monitor FINAL support and executable bid':'No origin to protect');
      text('earlyLadderExit','No supported EARLY EXIT rule · PROTECT is risk guidance');
      text('earlyFlow',`${m.contract} · ${o?'If manually entered: '+e.guidance:'PASS'} · SIGNAL ONLY / NO ORDERS`);
      text('flipRisk',m.flip_risk_pct.toFixed(1)+'%');text('flipRiskSub','Model context only · no exit authority');
      text('contextBanner',`${m.phase.replaceAll('_',' ')} · ${ctx?ctx.reasons.map(human).join('; '):'No active EARLY origin'} · BRTI freshness enforced ≤5s`);
    }
    const aligned=qualified&&s&&s.status!=='UNAVAILABLE'&&s.contract===m.contract&&s.target===m.target&&s.official_open===m.official_open&&s.official_close===m.official_close;
    if(!aligned){unavailable('scalp',s?.reason||'Waiting for aligned SCALP lifecycle',s?.origin);text('scalpTargetStrip','Unavailable');return;}
    const o=s.origin;
    pill('scalpState',s.guidance);text('scalpTitle','SCALP '+(o?.side||'PASS'));text('scalpArrow',o?.side==='DOWN'?'↓':o?'↑':'—');
    text('scalpEntry',o?'Origin ASK '+cents(o.original_ask):'30–45¢ · CORE/SURGE · waiting for confirmation');
    text('scalpYourEntry',o?cents(o.original_ask)+' · signal ASK':'No accepted origin');
    text('scalpCurrentPrice',o?cents(s.executable_current_bid):'No active origin');
    text('scalpTargetStrip',o?s.movement_cents.toFixed(1)+'¢ gross':'PASS');
    text('scalpLadderEntry',o?human(o.lane)+' · #'+o.serial_index:'30–45¢ · ideal overlap 30–35¢');
    text('scalpLadderHold',o?s.guidance+' · maximum 180s signal horizon':'No position assumed');
    text('scalpLadderWatch',s.context?human(s.context.phase)+' · '+s.context.reasons.map(human).join('; '):'Fresh qualifying observations required');
    text('scalpLadderProtect',s.presentation?.protection_armed?'PROTECT · trail trigger '+cents(s.trailing_trigger_bid):'Arms at +5¢ executable gain');
    text('scalpLadderExit',s.guidance==='EXIT'?'EXIT · current BID '+cents(s.executable_current_bid)+' · trigger BID '+cents(s.terminal.executable_exit_bid):'EXIT at 4¢ peak giveback after arm, or 180s horizon');
    text('scalpFlow',`${o?'If manually entered: '+s.guidance+'. ':''}${s.terminal?human(s.terminal.reason)+'. ':''}No assumed fill; fees excluded. SIGNAL ONLY / NO ORDERS`);
    text('oppositeTitle','SERIAL REVERSAL / RE-ENTRY');text('oppositeEntry',o?'Next origin requires a later qualified setup after EXIT':'Both sides evaluated');text('oppositeState',s.guidance==='EXIT'?'RECONFIRM':'WAIT');
  }
  async function poll(lane,url){
    if(busy[lane])return;busy[lane]=true;
    const sent=performance.now(),generation=epoch;
    try{
      const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(3000)});if(!r.ok)throw Error('HTTP');
      const data=await r.json(),received=performance.now();
      if(generation!==epoch)return;
      if(data.candidate!==CANDIDATE||data.signal_only!==true||data.orders!==false||!Number.isFinite(data.served_ts)||!Number.isFinite(data.expires_at)||data.published_ts>data.served_ts)throw Error('UNQUALIFIED');
      caches[lane]={data,deadline:received+Math.max(0,(data.expires_at-data.served_ts)*1000)-(received-sent)};
    }catch{if(generation===epoch)caches[lane]=null;}finally{busy[lane]=false;}
    render();
  }
  window.btc15RenderLadders=render;
  function refresh(){if(document.visibilityState!=='hidden'){poll('main','/ladders');poll('scalp',SCALP_URL);}}
  document.addEventListener('visibilitychange',()=>{epoch++;caches.main=caches.scalp=null;render();refresh();});
  window.addEventListener('pagehide',()=>{epoch++;caches.main=caches.scalp=null;render();});
  window.addEventListener('pageshow',refresh);
  setInterval(refresh,1000);setInterval(render,250);render();refresh();
})();
