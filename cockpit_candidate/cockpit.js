/* Presentation only. Native eligibility, clocks and retention belong to P2/P3. */
(function(){
  'use strict';
  const node=id=>document.getElementById(id),finite=Number.isFinite;
  let connected=false,disconnect=null;
  // In live mode each descriptive field has one presentation owner below.
  // Never paint an adapter placeholder and then overwrite it on every 100ms tick.
  const resolvedFields=new Set(['final-reason','early-reason','scalp-reason',
    'scalp-up-status','scalp-down-status','remaining','quote-status',
    'btc-price','btc-timestamp','health-status','health-continuity','health-quotes',
    'health-brti','health-at','evidence-score','flip-risk','market-momentum']);
  const same=(a,b)=>!!a&&!!b&&['contract','target','official_open','official_close'].every(k=>a[k]===b[k]);
  const stamp=v=>finite(v)?new Date(v*1000).toISOString():'Unavailable';
  const text=(id,value,source)=>{const n=node(id);if(!n)return;if(n.textContent!==String(value))n.textContent=String(value);if(source)n.dataset.source=source;};
  function label(id,value,state){text(id,value);const n=node(id);if(n){n.hidden=!value;n.dataset.displayState=state||'unavailable';}}
  function table(id,rows){
    const parent=node(id);if(!parent)return;
    // Stable disclosure descendants: refresh text without replacing focused nodes.
    rows.forEach(([key,value],index)=>{let row=parent.children[index];if(!row){row=document.createElement('div');row.append(document.createElement('dt'),document.createElement('dd'));parent.append(row);}if(row.children[0].textContent!==key)row.children[0].textContent=key;if(row.children[1].textContent!==String(value))row.children[1].textContent=String(value);});
    while(parent.children.length>rows.length)parent.lastElementChild.remove();
  }
  function preserveDetails(fn){
    const details=node('details'),anchor=details?.open?details:null,top=anchor?.getBoundingClientRect().top;
    const result=fn();if(anchor){const delta=anchor.getBoundingClientRect().top-top;if(delta)window.scrollBy(0,delta);}return result;
  }
  function paint(view,scalpDisplaySide=view.scalpSide){
    for(const [id,value] of Object.entries(view.fields))if(!connected||!resolvedFields.has(id))text(id,value,view.trace[id]);
    node('final-direction').className='direction '+(view.finalSide==='UP'?'up':view.finalSide==='DOWN'?'down':'');
    for(const [prefix,active] of Object.entries(view.activeRungs))for(const row of node(prefix+'-ladder').children){
      if(row.dataset.rung===active)row.setAttribute('aria-current','step');else row.removeAttribute('aria-current');
      if(prefix==='early'&&row.dataset.rung==='exit')row.setAttribute('aria-disabled','true');
    }
    const guidance=node('scalp-guidance'),slot=scalpDisplaySide?document.querySelector(`.scalp-direction[data-side="${scalpDisplaySide}"]`):null;
    if(slot){if(guidance.parentElement!==slot)slot.insertBefore(guidance,slot.querySelector('ol'));}
    else if(guidance.previousElementSibling!==node('scalp-heading'))node('scalp-heading').after(guidance);
    if(!connected)table('identity-details',view.identityDetails);
    table('authority-details',view.authorityDetails);table('source-details',view.sourceDetails);
  }
  function notes(values){const parent=node('gaps');values.forEach((value,index)=>{let li=parent.children[index];if(!li){li=document.createElement('li');parent.append(li);}if(li.textContent!==value)li.textContent=value;});while(parent.children.length>values.length)parent.lastElementChild.remove();}
  function render(snapshot){
    // P2 live.js calls render({}) on connect/disconnect and sends a native-only
    // snapshot ONLY at its next resolution. Inspection here never replays on connect.
    if(connected)return renderResolved(Object.hasOwn(snapshot||{},'main')?window.BTC15LadderOwner.getResolvedView():null);
    return preserveDetails(()=>{const view=window.BTC15SnapshotAdapter.project(snapshot);paint(view);notes(view.gaps.filter(v=>/binding conflict/.test(v)).concat('Offline snapshot review. Timed source owners run only in the explicitly selected live mode.'));return view;});
  }
  const history=(lane,identity)=>same(lane?.retained_payload?.official_identity,identity)?lane.retained_payload:null;
  function laneState(lane){
    if(lane?.eligible)return 'CURRENT';
    if(lane?.reason_code&&lane.reason_code!=='SOURCE_EXPIRED')return 'UNAVAILABLE';
    return lane?.selection==='retained'||lane?.reason_code==='SOURCE_EXPIRED'?'REFRESHING':'UNAVAILABLE';
  }
  function nativeSnapshot(v){const lanes=v?.lanes||{};return {main:lanes.main?.eligible?lanes.main.current_payload:{status:'UNAVAILABLE',official_identity:v?.identity,reason:lanes.main?.reason_code},scalp:lanes.scalp?.eligible?lanes.scalp.current_payload:null,quote:lanes.quote?.eligible?lanes.quote.current_payload:null};}
  function renderResolved(v){
    return preserveDetails(()=>{
      const view=window.BTC15SnapshotAdapter.project(nativeSnapshot(v));
      const lanes=v?.lanes||{},identity=v?.identity,m=lanes.main,s=lanes.scalp,q=lanes.quote;
      const oldMain=history(m,identity),oldScalp=history(s,identity),oldQuote=history(q,identity);
      // P1 performs the SAME immutable-ID and terminal validation for historical
      // text. Historical projections are never passed to paint or rung activation.
      const old=window.BTC15SnapshotAdapter.project({main:oldMain||{official_identity:identity},scalp:oldScalp,quote:oldQuote});
      // Keep the historical explanation in its validated same-contract column
      // during a lease gap. Only placement uses history; fields and active rungs
      // still come exclusively from the current native projection.
      paint(view,view.scalpSide||(!s?.eligible?old.scalpSide:null));
      const sourceReasons=[];
      for(const [name,lane] of [['final',m],['early',m],['scalp',s]]){
        const action=view.fields[name+'-action'],unusable=/unavailable/i.test(action),phase=laneState(lane);
        // Reuse only the owner's same-contract retained publication, with the
        // adapter's immutable origin/terminal validation. This is explanatory
        // history, never a lease, current action, price, or active ladder rung.
        const retained=!lane?.eligible&&!!history(lane,identity)&&!/unavailable/i.test(old.fields[name+'-action']);
        const reason=(retained?old:view).fields[name+'-reason'];
        const deliveryReason=lane?.reason_code||lane?.reason_text;
        const failure=lane?.reason_code&&lane.reason_code!=='SOURCE_EXPIRED'?String(deliveryReason).replaceAll('_',' '):null;
        label(name+'-freshness',(lane?.eligible&&unusable?'UNAVAILABLE':phase)+(lane?.eligible?' · current publication':failure?' · '+failure:' · no current action authority')+(retained?'\nLAST QUALIFIED explanation · historical':''),lane?.eligible&&!unusable?'current':'unavailable');
        sourceReasons.push([name.toUpperCase()+' explanation provenance',retained?'Last qualified; historical only':'Current native projection'],[name.toUpperCase()+' source explanation',view.fields[name+'-reason']]);
        text(name+'-reason',reason,retained?'Last qualified native explanation; historical only':'Native qualification and lifecycle explanation');
        node(name+'-reason').dataset.displayState=retained?'retained':lane?.eligible&&!unusable?'current':'unavailable';
      }
      const native=m?.eligible?m.current_payload:!/unavailable/i.test(old.fields['early-action'])?oldMain:null;
      const early=native?.early,opportunity=native?.early_opportunity;
      text('early-context',early?(!m?.eligible?'LAST QUALIFIED · ':'')+'Model fair '+(early.fair*100).toFixed(1)+'% · entry limit 45¢ · '+(opportunity?.price_zone||opportunity?.status||'No manual opportunity'):'Awaiting a qualified EARLY evaluation');
      const scalpHistorical=!s?.eligible&&oldScalp&&!/unavailable/i.test(old.fields['scalp-action']);
      const scalp=s?.eligible?s.current_payload:scalpHistorical?oldScalp:null;
      for(const side of ['UP','DOWN']){
        const current=(scalpHistorical?old:view).scalpSide===side,scan=scalp?.diagnostics?.find(d=>d.side===side);
        const explain=scan?(window.BTC15SnapshotAdapter.reasonLabels[scan.reason]||String(scan.reason).replaceAll('_',' ')):null;
        text('scalp-'+side.toLowerCase()+'-status',current?'Published '+scalp.guidance+' · '+side:scalp?(explain?'No new '+side+' entry · '+explain:'No new '+side+' opportunity published'):'No qualified '+side+' explanation');
        label('scalp-'+side.toLowerCase()+'-freshness',scalpHistorical?'LAST QUALIFIED · historical; no current authority':s?.eligible?'CURRENT · source diagnostic':'UNAVAILABLE · no current source',scalpHistorical?'retained':s?.eligible?'current':'unavailable');
      }
      // History is in Details; inserting/removing duplicate history paragraphs
      // above the guidance moved otherwise unchanged reasons during every gap.
      for(const name of ['final','early','scalp','quote'])label(name+'-retained','','retained');
      text('quote-status',q?.eligible?'CURRENT Kalshi ASK · source '+stamp(q.current_payload.exchange_ts):laneState(q)+' · no executable buy quote','P2 quote eligibility');
      table('explanation-details',sourceReasons.concat([
        ['Historical FINAL publication',stamp(oldMain?.published_ts)],['Historical FINAL outcome',oldMain?.final?old.fields['final-direction']+' · '+old.fields['final-probability']+' · no current call':'None'],['Historical EARLY',old.fields['early-price']||'None'],
        ['Historical SCALP',old.fields['scalp-price']||'None'],['Historical quote source',stamp(oldQuote?.exchange_ts)],
        ['Historical UP / DOWN ASK',oldQuote?old.fields['up-buy']+' / '+old.fields['down-buy']:'None']
      ]));
      text('health-status','Source publications and reported diagnostics');
      for(const [name,lane] of [['main',m],['scalp',s]])text('health-'+name,laneState(lane)+(lane?.eligible?' · '+lane.current_payload.status:' · no current authority'),'P2 publication eligibility; not service uptime');
      text('health-quotes',q?.eligible?'CURRENT executable quote':laneState(q)+' · no current quote','P2 quote eligibility');
      text('health-at','Native diagnostics retain their own publication clocks; the BRTI label uses the market source clock.');
      text('health-continuity',[['MAIN',m],['SCALP',s]].map(([name,lane])=>name+' '+(lane?.payload?.continuity||'Unavailable')+(lane?.payload&&!lane.eligible?' (last qualified)':'')).join(' · '),'P2 selected native continuity');
      const diagnostic=lane=>lane?.current_payload||lane?.payload;
      text('health-workers',[['MAIN',m],['SCALP',s]].map(([name,lane])=>{const d=diagnostic(lane),h=d?.handoff,j=d?.journal;return name+' '+(h?'worker '+(h.worker_alive===true?'alive':h.worker_alive===false?'not alive':'unavailable')+' · queue '+h.queue_depth+' · drops '+h.dropped:j?'journal queue '+j.queue_depth+' · drops '+j.drops:'worker state unavailable')+(d&&!lane?.current_payload?' (last qualified)':'');}).join(' / '),'Native handoff.worker_alive/queue_depth/dropped; journal diagnostics');
      if(!m?.eligible&&oldMain){text('flip-risk',old.fields['flip-risk']+' · LAST QUALIFIED MAIN','P2 retained main.flip_risk_pct');}
      else if(m?.eligible)text('flip-risk',view.fields['flip-risk']+' · CURRENT MAIN','P2 eligible main.flip_risk_pct');
      else text('flip-risk','Unavailable');
      table('identity-details',[
        ['Ticker',identity?.contract||'Official identity refreshing'],['Official open',stamp(identity?.official_open)],['Official close',stamp(identity?.official_close)],['Exact target',identity?.target??'Unavailable'],['Identity owner','Protected P2 MAIN / quote acceptance'],['Mode','Read-only source binding; no orders']
      ]);
      const retainedRows=[];
      for(const [name,lane] of Object.entries(lanes)){
        const r=lane.retained_payload,d=lane.current_payload;
        retainedRows.push([name.toUpperCase()+' selection',lane.selection],[name.toUpperCase()+' action eligibility',String(lane.eligible)],[name.toUpperCase()+' refresh reason',lane.reason_code||lane.reason_text],[name.toUpperCase()+' retained contract',r?.official_identity?.contract||'None'],[name.toUpperCase()+' retained publication',stamp(r?.published_ts)],[name.toUpperCase()+' retained expiry',stamp(r?.expires_at)],[name.toUpperCase()+' original client deadline (monotonic ms)',lane.lease?.deadline??'None'],[name.toUpperCase()+' request RTT (ms)',lane.lease?.rtt??'None'],[name.toUpperCase()+' retained origin',r?.origin?.origin_id||'None'],[name.toUpperCase()+' retained source diagnostics',JSON.stringify({health:r?.health,input_provenance:r?.input_provenance,handoff:r?.handoff,journal:r?.journal})],[name.toUpperCase()+' current publication diagnostics',JSON.stringify({health:d?.health,input_provenance:d?.input_provenance,handoff:d?.handoff,journal:d?.journal})]);
      }
      table('retained-details',retainedRows);
      notes(view.gaps.filter(x=>/binding conflict/.test(x)).concat('Publication expiry is enforced by the unchanged source owners. PASS is an evaluated opportunity state, not a service outage. Live production; source clocks and contract boundaries remain authoritative.'));
      // These calls repaint descriptive outputs only; no ladder rendering on a
      // market/information notification and no second cache, clock or poller.
      renderMarket(window.BTC15MarketViewOwner?.getResolvedView(),v);
      renderInformation(window.BTC15InformationOwner?.getResolvedView());
      return view;
    });
  }
  function marketMatches(m,v){const i=v?.identity;return !!i&&m?.contract===i.contract&&m.source?.target===i.target&&m.clock?.closeMs===i.official_close*1000;}
  function mountChart(m){
    const parent=node('chart-surface');if(!m?.chart?.svg)return;
    if(parent.dataset.sourceSvg===m.chart.svg)return;
    const template=document.createElement('template');template.innerHTML=m.chart.svg;const svg=template.content.firstElementChild;if(svg?.tagName.toLowerCase()!=='svg')return;
    parent.replaceChildren(svg);parent.dataset.sourceSvg=m.chart.svg;
    // Original renderMainChart pointer presentation, using its resolved samples
    // and geometry. No history reconstruction, interpolation or new timeframe.
    const signature=m.chart.signature?JSON.parse(m.chart.signature):null,pts=signature?.[4];if(!pts?.length)return;
    const w=signature[1],left=10,right=w-89,end=m.clock.closeMs,begin=end-900000,x=t=>left+(right-left)*(t-begin)/(end-begin);
    const tip=svg.lastElementChild,cross=tip.previousElementSibling;
    svg.onpointermove=event=>{const rect=svg.getBoundingClientRect(),px=(event.clientX-rect.left)/rect.width*w,t=begin+(px-left)/(right-left)*(end-begin);let best=pts[0];for(const p of pts)if(Math.abs(p.t-t)<Math.abs(best.t-t))best=p;
      cross.setAttribute('x1',x(best.t));cross.setAttribute('x2',x(best.t));cross.setAttribute('visibility','visible');
      tip.textContent='BRTI $'+best.v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})+' · '+new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true}).format(new Date(best.t))+' ET · sampled';tip.setAttribute('visibility','visible');};
    svg.onpointerleave=()=>{cross.setAttribute('visibility','hidden');tip.setAttribute('visibility','hidden');};
  }
  function renderMarket(m,v=window.BTC15LadderOwner?.getResolvedView()){
    if(!connected||!m)return;
    preserveDetails(()=>{
      const aligned=marketMatches(m,v),source=m.brti?.record,priceCurrent=aligned&&m.brti.price_state==='fresh';
      text('remaining',aligned?m.values.timerRemaining:'—','P3 liveCountdown; matched P2 official identity');
      label('clock-status',aligned?m.values.timerEnd+' · '+m.reason:'Waiting for matching official contract / countdown','display');
      text('btc-price',m.values.btcPrice,'P3 renderBrtiDisplay (BRTI only)');
      const priceLabel=(source&&!aligned?'HISTORICAL · '+source.contract+' · ':'')+m.brti.label;
      text('btc-timestamp',priceLabel,'P3 original BRTI label + explicit contract alignment');node('btc-price').title=m.brti.title;node('btc-price').dataset.displayState=priceCurrent?'current':source?'retained':'unavailable';
      mountChart(m);text('chart-note','BRTI reference history · 15-minute view · '+(m.chart.contract||'No contract')+' · '+(m.chart.refreshing?'LAST QUALIFIED / REFRESHING':m.chart.stale==='true'?'STALE / HISTORICAL':'source display')+(aligned?'':' · awaiting matching official identity'),'P3 chart retention/identity/stale flags');
      text('evidence-score',m.values.evidenceScore,'P3 applyState / lowerHistory; original seven diagnostics');
      text('market-momentum',m.values.momentumBadge+' · '+m.values.momentumSub,'P3 applyState / lowerHistory');
      label('context-status',(aligned&&m.lower.qualified?'CURRENT market sample':Object.values(m.lower.history).some(x=>x.contract===m.lower.contract)?'LAST QUALIFIED / REFRESHING market display':'UNAVAILABLE / REFRESHING market context')+' · '+(m.lower.contract||'No contract')+' · informational only','display');
      table('market-details',[
        ['Market source contract',m.contract||'Unavailable'],['Market source generated UTC',m.source?.generated_utc||'Unavailable'],['Market source timestamp UTC',m.source?.source_timestamp_utc||'Unavailable'],['Market target (USD)',m.source?.target??'Unavailable'],['BRTI retained contract',source?.contract||'None'],['BRTI original observed time (epoch ms)',source?.observed??'Unavailable'],['BRTI price state',m.brti.price_state||'unavailable'],['BRTI gap at retained/source sample',m.values.btcGap],['Market original reason',m.reason],['Clock trusted / network healthy',m.clock_trusted+' / '+m.network_healthy],['Countdown source',m.values.timerRemaining+' · '+m.values.nextContract],['Chart retained / refreshing',String(m.chart.refreshing)],['Chart points / geometry signature',m.chart.signature||'None'],['Lower context qualified',String(m.lower.qualified)],['Trend',m.values.contextTrend],['Range',m.values.contextRange],['BRTI context',m.values.contextBrti],['Original diagnostic levels',m.values.contextLevels],['Parity',m.values.parityFooter]
      ]);
      renderSourceInformation(window.BTC15InformationOwner?.getResolvedView());
    });
  }
  function renderInformation(i){
    if(!connected||!i)return;
    preserveDetails(()=>{
      renderSourceInformation(i);
      table('information-details',[
      ['Information status',i.labels.status],['Information assessment',i.labels.assessment],['Information selection',i.selection],['Information ticker',i.display?.ticker||'Unavailable'],['Information target (USD)',(i.current.assessment?i.delivery:i.retained_source)?.payload.target??'Unavailable'],['Information source reason',(i.current.assessment?i.delivery:i.retained_source)?.payload.reason||'Unavailable'],['Information original publication',stamp((i.current.assessment?i.delivery:i.retained_source)?.payload.published_ts)],['Information original display deadline',stamp((i.current.assessment?i.delivery:i.retained_source)?.payload.display_until)],['Information original expiry',stamp((i.current.assessment?i.delivery:i.retained_source)?.payload.expires_at)],['Information authority','Descriptive only; never native FINAL / EARLY / SCALP']
    ]);});
  }
  function renderSourceInformation(i){
    const v=window.BTC15LadderOwner?.getResolvedView(),identity=v?.identity;
    const p=i?.delivery?.payload,a=i?.current?.assessment;
    const qualified=!!a&&p?.ticker===identity?.contract&&p?.target===identity?.target&&finite(a.probability_up)&&finite(a.probability_down);
    const retained=i?.retained_source?.payload;
    const old=retained&&identity&&retained.ticker===identity.contract&&retained.target===identity.target&&finite(retained.probability_up)&&finite(retained.probability_down)?retained:null;
    const model=qualified?a:old;
    text('model-information',model?'UP '+(model.probability_up*100).toFixed(1)+'% · DOWN '+(model.probability_down*100).toFixed(1)+'% · '+String(model.protection_phase||'Phase unavailable').replaceAll('_',' '):'Model information refreshing; native guidance above retains its own qualification');
    text('model-information-note',qualified?'CURRENT descriptive assessment · BRTI '+(a.brti_agrees?'agrees':'differs')+' · no additional action authority':old?'LAST QUALIFIED · historical assessment · no current action authority':'No current descriptive assessment; no entry or exit inferred');
    const m=window.BTC15MarketViewOwner?.getResolvedView();
    const marketCurrent=marketMatches(m,v)&&m.network_healthy&&m.lower?.qualified;
    const now=qualified?p.checked_ts+(performance.now()-i.delivery.requestStartedMs)/1000:NaN;
    const btcAge=now-p?.btc_source_ts,brtiAge=now-p?.brti_source_ts;
    const money=x=>finite(x)?'$'+x.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}):'Unavailable';
    text('spot-price',qualified&&finite(btcAge)&&btcAge>=0&&btcAge<=10?money(p.btc_price):marketCurrent?money(m.source?.btc_price):'Refreshing');
    text('spot-age',qualified&&finite(btcAge)&&btcAge>=0&&btcAge<=10?'BTC spot · source '+stamp(p.btc_source_ts)+' · '+btcAge.toFixed(1)+'s':marketCurrent?'BTC spot at market snapshot '+m.source.source_timestamp_utc:'No current BTC spot receipt');
    const freshBrti=qualified&&finite(brtiAge)&&brtiAge>=0&&brtiAge<=5;
    text('brti-latest',freshBrti?money(p.brti_value):m?.values?.btcPrice||'BRTI refreshing');
    text('brti-latest-age',freshBrti?'BRTI · source '+stamp(p.brti_source_ts)+' · '+brtiAge.toFixed(1)+'s':m?.brti?.label||'No current BRTI receipt');
    // One formatter resolves all diagnostic BRTI inputs, independent of which
    // owner notified us. Delivery refreshes never compete with market wording.
    const lane=v?.lanes?.main,d=lane?.current_payload?.delivery,clock=lane?.clock;
    const at=clock?clock.server+(performance.now()-clock.received)/1000:NaN;
    const age=d&&finite(d.brti_source_ts)?at-d.brti_source_ts:NaN;
    const brtiReceipt=d?.schema==='BTC15_DELIVERY_HEALTH_R1'&&d.authority==='DIAGNOSTIC_ONLY'&&
      d.signal_only===true&&d.orders===false&&d.brti==='CURRENT'&&
      finite(d.brti_received_ts)&&d.brti_source_ts<=d.brti_received_ts&&d.brti_received_ts<=d.observed_ts&&
      d.observed_ts<=at&&finite(age)&&age>=0&&age<=5;
    const receiptAge=freshBrti?brtiAge:brtiReceipt?age:null;
    const priceLabel=(m?.brti?.record&&!marketMatches(m,v)?'HISTORICAL · '+m.brti.record.contract+' · ':'')+(m?.brti?.label||'No current BRTI receipt');
    text('health-brti',receiptAge!==null?'CURRENT BRTI receipt · '+receiptAge.toFixed(1)+'s · diagnostic only':priceLabel,'Original qualified BRTI timestamps / market source label; no action authority');
  }
  function connectResolved(){
    if(disconnect)return disconnect;
    if(window.BTC15Review||!window.BTC15LadderOwner||!window.BTC15MarketViewOwner||!window.BTC15InformationOwner||!window.BTC15CockpitLive)throw Error('BTC15_RESOLVED_BINDING_DEPENDENCY');
    connected=true;
    const offMarket=window.BTC15MarketViewOwner.subscribe(v=>renderMarket(v)),offInfo=window.BTC15InformationOwner.subscribe(renderInformation),offNative=window.BTC15CockpitLive.connect();
    let active=true;disconnect=()=>{if(!active)return;active=false;offMarket();offInfo();offNative();connected=false;disconnect=null;};return disconnect;
  }
  window.BTC15Cockpit=Object.freeze({render,renderResolved,connectResolved});
})();
