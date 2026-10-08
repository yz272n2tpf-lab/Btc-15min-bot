/* Snapshot-only projection of pinned processor outputs. No strategy, clocks, caches or IO. */
(function(root){
  'use strict';
  const finite=v=>typeof v==='number'&&Number.isFinite(v);
  const presentId=v=>typeof v==='string'&&v.trim().length>0;
  const price=v=>finite(v)&&v>=0&&v<=1;
  const money=v=>finite(v)?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(v):'—';
  const cents=v=>finite(v)?`${new Intl.NumberFormat('en-US',{minimumFractionDigits:1,maximumFractionDigits:8}).format(v*100)}¢`:'—';
  const pct=v=>finite(v)?`${(v*100).toFixed(1)}%`:'—';
  const human=v=>typeof v==='string'?v.replaceAll('_',' '):'';
  const stamp=v=>finite(v)?new Date(v*1000).toISOString():'Unavailable';
  const seconds=v=>finite(v)?`${v.toFixed(3)} s`:'Unverified';
  const reasonLabels=Object.freeze({
    ask_le45:'The signal ask exceeds the protected 45¢ entry limit',
    fair_ge75:'Target-aware fair probability is below 75%',
    remaining_2_to10:'Remaining time is outside the protected 2–10 minute window',
    gap_ge25:'The absolute BTC-to-exact-target distance is below $25',
    fair_ge90:'FINAL probability is below 90%',remaining_le8:'More than eight minutes remain',
    gap_ok:'The required BTC-to-target distance is not met',distance_range_ge1:'The required distance-to-range ratio is not met',
    target_side:'BTC is not on the selected side of the target',brti_side:'BRTI does not meet the required side and distance condition',
    FINAL_OPPOSES_OR_CONFIRMATION_LOST:'FINAL opposes the entry or its confirmation has been lost',
    STRENGTHENING:'FINAL support is strengthening',WEAKENING:'FINAL support is weakening',
    CONFIRMING:'FINAL support is unchanged',OPPOSING:'FINAL opposes the entry direction',
    MIXED:'FINAL evidence is mixed',FLIP_ALERT:'FINAL has qualified in the opposite direction',
    BTC_NOT_ON_HELD_SIDE_OF_TARGET:'BTC is not on the entry side of the target',
    BRTI_NOT_ON_HELD_SIDE_OF_TARGET:'BRTI is not on the entry side of the target',
    DIRECTIONAL_SUPPORT_WEAKENING:'Directional support is weakening',EXECUTABLE_PRICE_PULLBACK:'The executable price has pulled back',
    FINAL_THREE_MINUTES_LIMITED_EXIT_RUNWAY:'Final three minutes: limited exit time',
    FINAL_FIVE_MINUTES_MONITOR_SUPPORT_AND_EXECUTABLE_BID:'Final five minutes: monitor support and the executable bid',
    ARM5_GIVEBACK4:'The protected 4¢ giveback exit fired after the 5¢ arm',
    ENDED_UNARMED:'The opportunity ended unarmed; this is not an executable exit',
    BTC30_BELOW_15:'Side-aligned BTC30 is below $15',
    BTC30_HISTORY_REFRESHING:'The causal 30-second history is refreshing',
    NEW_ENTRY_REQUIRES_120S:'A new SCALP entry requires at least 120 seconds remaining',
    SOURCE_EXPIRED:'The source publication has expired',BRTI_SOURCE_UNAVAILABLE:'BRTI source data is unavailable',
    QUOTE_SOURCE_UNAVAILABLE:'Timestamped quote data is unavailable',QUOTE_SOURCE_EXPIRED_OR_FUTURE:'The quote source time is expired or in the future'
  });
  const reason=v=>reasonLabels[v]||human(v)||'Reason unavailable from source';
  function project(snapshot){
    const input=snapshot||{},trace={},fields={},gaps=[];
    const activeRungs={early:null,'scalp-up':null,'scalp-down':null};
    const stateRows={ENTER:'entry',HOLD:'hold',WATCH:'watch',CAUTION:'watch',PROTECT:'protect',EXIT:'exit'};
    function read(path){return path.split('.').reduce((o,k)=>o?.[k],input);}
    function set(id,path,format=v=>v??'Unavailable'){
      trace[id]=path;fields[id]=format(read(path));return read(path);
    }
    function literal(id,value,path){fields[id]=value;trace[id]=path||'blueprint presentation / missing source';}
    for(const prefix of Object.keys(activeRungs))for(const rung of ['entry','hold','watch','protect','exit'])literal(`${prefix}-${rung}`,'—','No matching published lifecycle value');
    literal('early-exit','Unsupported','main.exit_reason + main.final.helper.exit_authority=false; no directional EARLY exit');
    const m=input.main,s=input.scalp,q=input.quote;
    const i=m?.official_identity;
    const identity=a=>!!a&&presentId(a.contract)&&['target','official_open','official_close'].every(k=>finite(a[k]));
    const same=(a,b)=>identity(a)&&identity(b)&&['contract','target','official_open','official_close'].every(k=>a[k]===b[k]);
    // This is structural consistency for a saved review snapshot, not a freshness policy.
    const mainOK=m?.signal_only===true&&m?.orders===false&&['AVAILABLE','PASS'].includes(m?.status)&&!!i&&same(m,i);
    const scalpOK=s?.signal_only===true&&s?.orders===false&&['AVAILABLE','PASS'].includes(s?.status)&&same(s?.official_identity,i)&&same(s,s?.official_identity);
    const quoteOK=q?.signal_only===true&&q?.orders===false&&q?.status==='AVAILABLE'&&same(q?.official_identity,i);
    const rawOK=mainOK&&same(input.raw,i)&&input.raw?.source_timestamp_utc===m.source_timestamp_utc;
    if(i&&finite(i.official_open)&&finite(i.official_close)){
      const dt=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
      const end=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit',timeZoneName:'short'});
      literal('contract-window',`${dt.format(new Date(i.official_open*1000))} – ${end.format(new Date(i.official_close*1000))}`,'main.official_identity.official_open + official_close → America/New_York');
      set('target-price','main.official_identity.target',money);
    }else{literal('contract-window','Contract window unavailable');literal('target-price','—');}
    if(rawOK){set('remaining','raw.timer.seconds_left',v=>finite(v)?`${String(Math.floor(v/60)).padStart(2,'0')}:${String(Math.floor(v%60)).padStart(2,'0')}`:'—:—');}
    else literal('remaining','—:—');
    set('guard','main.phase',v=>!mainOK||v==='NORMAL'?'':human(v));
    if(mainOK&&m.final){
      set('final-direction','main.final.side',v=>v==='UP'?'↑ UP':v==='DOWN'?'↓ DOWN':'—');
      set('final-probability','main.final.confidence',pct);
      set('final-lock','main.final.lock_state',v=>v==='UNLOCKED'?'NOT LOCKED':v==='QUALIFIED'?'QUALIFIED LOCK':human(v)||'Lock unavailable');
      // Display the native call state; neither value is a BUY/HOLD/EXIT instruction.
      set('final-action','main.final.state',v=>['PASS','FINAL_CALL'].includes(v)?v:'Action unavailable');
      const failed=Object.entries(m.final.conditions||{}).filter(([,v])=>v===false).map(([k])=>reason(k));
      literal('final-reason',m.final.reason?reason(m.final.reason):failed.length?`${failed.join('; ')}.`:m.final.state==='FINAL_CALL'?'Native FINAL call · signal only; no trade action supplied.':'Reason unavailable from source.',m.final.reason?'main.final.reason':'main.final.conditions (false values only) / main.final.state');
    }else{
      for(const [id,v] of Object.entries({'final-direction':'—','final-probability':'—','final-lock':'Lock unavailable','final-action':'Action unavailable'}))literal(id,v);
      literal('final-reason',m?.reason?reason(m.reason):'Authoritative FINAL output is unavailable.',m?.reason?'main.reason':null);
    }
    literal('confidence','');
    if(quoteOK){set('up-buy','quote.up_ask',cents);set('down-buy','quote.down_ask',cents);literal('quote-status','Kalshi buy quotes · cents per contract · recorded sample','quote.status');}
    else{literal('up-buy','—');literal('down-buy','—');literal('quote-status',same(q?.official_identity,i)?reason(q?.reason):'Same-contract Kalshi buy quotes are unavailable.','quote.reason / official_identity');}
    if(mainOK&&m.early){
      const o=m.origin,e=m.early,h=m.final?.helper;
      const originOK=same(o,i)&&presentId(o.origin_id)&&['UP','DOWN'].includes(o.side);
      const lifecycleOK=originOK&&presentId(h?.origin_id)&&h.origin_id===o.origin_id&&
        presentId(m.final?.early_origin_id)&&m.final.early_origin_id===o.origin_id&&
        h.state===e.guidance&&h.exit_authority===false&&e.guidance!=='EXIT';
      set('early-direction',originOK?'main.origin.side':'main.early.side',v=>human(v)||'Direction unavailable');
      set('early-action','main.early.guidance',v=>human(v)||'Action unavailable');
      if(lifecycleOK){
        const detail=h?.reason?reason(h.reason):'Reason unavailable from source';
        literal('early-reason',`If manually entered ${o.side}: ${detail}.`,'main.origin.side + main.final.helper.reason; manual_fill=null');
        literal('early-price',`${o.side} signal entry ${cents(o.original_ask)} · ${o.side} executable bid ${cents(m.executable_current_bid)}`,'main.origin.original_ask + main.executable_current_bid');
        activeRungs.early=stateRows[e.guidance]||null;
        literal('early-entry',`Signal ASK ${cents(o.original_ask)}`,'main.origin.original_ask (immutable)');
        if(e.guidance==='HOLD')literal('early-hold','HOLD','main.early.guidance + main.final.helper.state');
        if(['WATCH','CAUTION'].includes(e.guidance))literal('early-watch',e.guidance,'main.early.guidance + main.final.helper.state; CAUTION severity retained');
        if(e.guidance==='PROTECT')literal('early-protect',h.protect_latched===true?'Protection latched':'Latch unavailable','main.final.helper.protect_latched');
      }else if(!o&&!stateRows[e.guidance]){
        literal('early-reason',e.pass_reasons?.length?e.pass_reasons.map(reason).join('; ')+'.':'Reason unavailable from source.','main.early.pass_reasons (already failed protected gates)');
        literal('early-price',`${e.side} current buy ${cents(e.ask)}`,'main.early.ask + side; no origin inferred');
      }
      if((o&&!lifecycleOK)||(!o&&stateRows[e.guidance])){
        literal('early-action','Action unavailable','Conflicting or missing EARLY origin/helper binding');
        literal('early-direction','Direction unavailable','Rejected EARLY origin/helper binding');
        literal('early-price','','Rejected EARLY origin/helper binding; no management price');
        literal('early-reason','The published EARLY lifecycle has a missing or conflicting origin/helper binding.');
        gaps.push('EARLY lifecycle binding conflict: a management action requires the matching immutable origin and FINAL helper state.');
      }
    }else{
      literal('early-direction','Direction unavailable');literal('early-action','Action unavailable');literal('early-price','');
      literal('early-reason',reason(m?.reason),'main.reason');
    }
    let scalpSide=null;
    if(scalpOK){
      const o=s.origin,t=s.terminal;
      const originMatches=a=>!!a&&presentId(a.origin_id)&&['UP','DOWN'].includes(a.side)&&
        same({contract:a.contract,target:a.target,official_open:a.open_ts,official_close:a.close_ts},i);
      const originOK=originMatches(o);
      const terminalBound=originOK&&originMatches(t?.origin)&&t.origin.origin_id===o.origin_id&&
        t.origin.side===o.side&&t.origin.original_ask===o.original_ask;
      const exitOK=terminalBound&&t.state==='EXIT'&&t.actionable_exit===true&&price(t.executable_exit_bid);
      const terminalOK=t==null?s.guidance!=='EXIT':terminalBound&&(s.guidance==='EXIT'?exitOK:
        s.guidance==='PASS'&&t.actionable_exit===false&&['ENDED_UNARMED','UNAVAILABLE'].includes(t.state));
      const bindingOK=originOK&&terminalOK;
      if(bindingOK)scalpSide=o.side;
      set('scalp-action','scalp.guidance',v=>human(v)||'Action unavailable');
      const scanReasons=!o&&s.guidance==='PASS'&&Array.isArray(s.diagnostics)?s.diagnostics
        .filter(d=>['UP','DOWN'].includes(d?.side)&&presentId(d.reason))
        .map(d=>`${d.side} PASS — ${reason(d.reason)}`).join('; '):'';
      const detail=scanReasons||((bindingOK&&t?.reason)?reason(t.reason):s.context?.reasons?.length?s.context.reasons.map(reason).join('; '):s.presentation?.message||s.reason&&reason(s.reason)||'Reason unavailable from source');
      literal('scalp-reason',`${scalpSide?'If manually entered '+scalpSide+': ':''}${detail}.`,scanReasons?'scalp.diagnostics[].side + reason (published PASS reasons)':'scalp.terminal.reason / context.reasons / presentation.message / reason; manual_fill=null');
      const exit=bindingOK&&s.guidance==='EXIT'&&exitOK?` · ${scalpSide} exit trigger bid ${cents(t.executable_exit_bid)}`:'';
      literal('scalp-price',scalpSide?`${scalpSide} signal entry ${cents(o.original_ask)} · ${scalpSide} executable bid ${cents(s.executable_current_bid)}${exit}`:'','scalp.origin.original_ask + executable_current_bid + terminal.executable_exit_bid');
      if(bindingOK){
        const prefix=`scalp-${scalpSide.toLowerCase()}`;
        activeRungs[prefix]=stateRows[s.guidance]||null;
        literal(`${prefix}-entry`,`Signal ASK ${cents(o.original_ask)}`,'scalp.origin.original_ask (immutable)');
        if(s.guidance==='HOLD')literal(`${prefix}-hold`,`BID ${cents(s.executable_current_bid)}`,'scalp.guidance + scalp.executable_current_bid (strictly later same-side source value)');
        if(['WATCH','CAUTION'].includes(s.guidance))literal(`${prefix}-watch`,s.guidance,'scalp.guidance; CAUTION maps to Watch without changing severity');
        if(s.presentation?.protection_armed===true)literal(`${prefix}-protect`,`Protective BID ${cents(s.trailing_trigger_bid)}`,'scalp.presentation.protection_armed + scalp.trailing_trigger_bid (not calculated here)');
        else if(!s.terminal&&finite(s.policy?.arm))literal(`${prefix}-protect`,`Arm +${cents(s.policy.arm)}`,'scalp.policy.arm (conditional source policy, not active selection)');
        if(s.guidance==='EXIT')literal(`${prefix}-exit`,`Trigger BID ${cents(s.terminal.executable_exit_bid)}`,'scalp.terminal.actionable_exit + executable_exit_bid; observed trigger, never fill');
        else if(s.terminal?.state==='ENDED_UNARMED')literal(`${prefix}-exit`,'Not triggered','scalp.terminal.state=ENDED_UNARMED; guidance=PASS, actionable_exit=false');
        else if(!s.terminal&&finite(s.policy?.giveback))literal(`${prefix}-exit`,`After arm: ${cents(s.policy.giveback)} giveback`,'scalp.policy.giveback (conditional source policy, not active selection)');
      }else if(o||t!=null||stateRows[s.guidance]){
        literal('scalp-action','Action unavailable','Conflicting or missing SCALP origin/actionable-terminal binding');
        literal('scalp-price','','Rejected SCALP origin/terminal binding; no management or terminal price');
        literal('scalp-reason','The published SCALP lifecycle has a missing or conflicting origin/terminal binding.');
        gaps.push('SCALP lifecycle binding conflict: management requires a matching origin; EXIT also requires its actionable terminal.');
      }
    }else{literal('scalp-action','Action unavailable');literal('scalp-price','');literal('scalp-reason',same(s?.official_identity,i)?reason(s?.reason):'A matching SCALP contract output is unavailable.','scalp.reason / official_identity');}
    for(const side of ['UP','DOWN'])literal(`scalp-${side.toLowerCase()}-status`,scalpSide===side?'Source-managed direction':'No directional state published','scalp.origin.side (no invented inactive action)');
    literal('btc-price','—');literal('btc-timestamp','Current BTC price and timestamp unavailable');
    literal('health-status','Overall status unavailable','No aggregate system-health field in selected public envelopes');
    set('health-continuity','main.continuity',v=>mainOK?human(v)||'Unavailable':'Unavailable');
    // Use MAIN's own quote-age sample, with its timestamp, rather than combining two sample clocks.
    literal('health-quotes',mainOK&&finite(m.health?.quote_age)?`${quoteOK?'AVAILABLE':'Quote unavailable'} · source age ${seconds(m.health.quote_age)}`:'Quote unavailable · source age unverified','quote.status / official_identity + main.health.quote_age');
    set('health-brti','main.health.brti_age',v=>mainOK?seconds(v):'Unverified');
    literal('health-at',`Source ages at MAIN publication: ${stamp(m?.published_ts)}`,'main.published_ts');
    literal('evidence-score','Unavailable','No Evidence Score field in selected envelope');
    set('flip-risk','main.flip_risk_pct',v=>mainOK&&finite(v)?`${v.toFixed(1)}%`:'Unavailable');
    literal('market-momentum','Unavailable','No Market Momentum field in selected envelope');
    gaps.push('The protected browser continuity owner does not expose a read-only resolved-view interface. Runtime integration, retained state and contract-handoff parity remain blocked.');
    gaps.push('BTC history, current BTC, timeframe inventory, Evidence Score, Market Momentum and aggregate Bot Health are not in the selected public envelopes. Their other existing owners are not connected.');
    gaps.push('Snapshot timer comes from the existing protected_frame output. There is no new browser clock. A live timer owner has not been connected.');
    const identityDetails=[['Ticker',i?.contract||'Unavailable'],['Official open',stamp(i?.official_open)],['Official close',stamp(i?.official_close)],['Target source','main.official_identity.target'],['Snapshot time',stamp(input.at)],['Mode','Offline synthetic test output; never live authority']];
    const authorityDetails=[['FINAL publication state',m?.final?.state||'Unavailable'],['FINAL source status',m?.status||'Unavailable'],['EARLY native guidance',m?.early?.guidance||'Unavailable'],['EARLY opportunity status',m?.early_opportunity?.status||'Unavailable'],['EARLY origin',m?.origin?.origin_id||'None published'],['EARLY manual fill',m?.origin?.manual_fill??'Not supplied; execution not assumed'],['EARLY protection latch',String(m?.final?.helper?.protect_latched??'Unavailable')],['EARLY exit limitation',m?.exit_reason||'Unavailable'],['SCALP lifecycle',s?.lifecycle_state||'Unavailable'],['SCALP origin',s?.origin?.origin_id||'None published'],['SCALP serial opportunity',s?.origin?.serial_index??'Unavailable'],['SCALP lane',s?.origin?.lane||'Unavailable'],['SCALP predecessor',s?.origin?.predecessor_id||'None published'],['SCALP protection armed',String(s?.presentation?.protection_armed??'Unavailable')],['SCALP protective bid',cents(s?.trailing_trigger_bid)],['SCALP manual fill',s?.origin?.manual_fill??'Not supplied; execution not assumed'],['SCALP actionable exit',String(s?.terminal?.actionable_exit??'No terminal output')],['SCALP contract',s?.official_identity?.contract||'Unavailable']];
    const sourceDetails=[['Quote contract',q?.official_identity?.contract||'Unavailable'],['Quote exchange source time',stamp(q?.exchange_ts)],['Quote accepted/receipt time',stamp(q?.accepted_ts)],['Quote publication time',stamp(q?.published_ts)],['Quote sequence',q?.sequence??'Unavailable'],['UP bid',cents(q?.up_bid)],['UP ask',cents(q?.up_ask)],['DOWN bid',cents(q?.down_bid)],['DOWN ask',cents(q?.down_ask)],['BRTI true source age',seconds(m?.health?.brti_age)],['BRTI receipt age','Not exported in MAIN health; not substituted for true source age'],['BRTI true source-age acceptance','At or below 5 s remains a protected requirement; no live acceptance claim'],['MAIN expiry',stamp(m?.expires_at)],['SCALP expiry',stamp(s?.expires_at)],['Historical accuracy','No current live qualification claimed']];
    authorityDetails.push(['EARLY manual-opportunity origin authority',String(m?.early_opportunity?.origin_authority??'Unavailable')],['EARLY manual-opportunity reason',m?.early_opportunity?.reason||'Not exported; does not control the Tier-1 rows'],['EARLY target-aware fair',pct(m?.early?.fair)],['EARLY source edge',finite(m?.early?.edge)?`${(m.early.edge*100).toFixed(1)} pt`:'Unavailable'],['SCALP protection arm',cents(s?.policy?.arm)],['SCALP peak giveback rule',cents(s?.policy?.giveback)],['SCALP observed peak gain',cents(s?.path?.mfe)],['SCALP observed giveback',cents(s?.path?.giveback)],['SCALP terminal time',stamp(s?.terminal?.ts)],['SCALP realized profit',s?.terminal?.realized_profit??'Not supplied; execution not assumed']);
    return {fields,trace,gaps,activeRungs,scalpSide,finalSide:mainOK?m.final?.side:null,identityDetails,authorityDetails,sourceDetails};
  }
  const api=Object.freeze({project,reasonLabels});
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.BTC15SnapshotAdapter=api;
})(typeof window!=='undefined'?window:globalThis);
