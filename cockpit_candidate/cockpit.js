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
    'health-brti','health-at','evidence-score','flip-risk','market-momentum',
    'early-action','early-direction','early-price','scalp-action','scalp-price',
    'early-entry','early-hold','early-watch','early-protect','early-exit','final-action']);
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
    for(const [prefix,active] of Object.entries(view.activeRungs))for(const row of node(prefix+'-ladder')?.children||[]){
      if(connected)continue; // Issued record is the single live ladder owner.
      if(row.dataset.rung===active)row.setAttribute('aria-current','step');else row.removeAttribute('aria-current');
      if(prefix==='early'&&row.dataset.rung==='exit')row.setAttribute('aria-disabled','true');
    }
    const guidance=node('scalp-guidance');
    if(guidance.previousElementSibling!==node('scalp-heading'))node('scalp-heading').after(guidance);
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
  const centsValue=v=>finite(v)?(v*100).toFixed(2)+'¢':'Unavailable';
  const dollarsValue=v=>finite(v)?v.toFixed(2)+' USD':'Unavailable';
  const percentValue=v=>finite(v)?(v*100).toFixed(1)+'%':'Unavailable';
  const shortCents=v=>finite(v)?Number((v*100).toFixed(2))+'¢':'unavailable';
  const clockTime=v=>finite(v)?new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(v*1000))+' ET':'time unavailable';
  const shortReasons={
    DIRECTIONAL_THESIS_INVALIDATED:'Direction reversed',NET_BID_EXCEEDS_WEAKENING_MODEL_VALUE:'Model value weakened',
    ARM5_GIVEBACK4:'4¢ giveback',BTC_NOT_ON_HELD_SIDE_OF_TARGET:'BTC crossed against signal',
    BRTI_NOT_ON_HELD_SIDE_OF_TARGET:'BRTI crossed against signal',DIRECTIONAL_SUPPORT_WEAKENING:'Support weakening',
    EXECUTABLE_PRICE_PULLBACK:'BID pulled back',FINAL_THREE_MINUTES_LIMITED_EXIT_RUNWAY:'Limited exit time',
    FINAL_FIVE_MINUTES_MONITOR_SUPPORT_AND_EXECUTABLE_BID:'Final five minutes',
    SUPPORT_WEAKENED_OR_MOMENTUM_UNAVAILABLE:'Support weakening or uncertain',
    DIRECTIONAL_DETERIORATION_CORROBORATED_BY_MARKET:'Market support deteriorating',
    ESTABLISHED_PROTECTION_REMAINS_LATCHED:'Protection remains warranted',
    POSITIVE_LIQUIDATION_SCENARIO_WITH_DETERIORATION:'Positive net; support weakening'};
  function renderFinal(lane){
    const p=lane?.eligible?lane.current_payload:null,f=p?.final,a=p?.opportunity_analysis;
    const c=a?.contract===p?.contract?a?.candidates?.find(c=>c.side===f?.side):null,e=c?.economics;
    text('final-action',f?.state==='FINAL_CALL'?'QUALIFIED CALL':f?.state==='PASS'?'PASS':'Unavailable');
    const gap=v=>finite(v)?Math.abs(v).toFixed(2)+' USD '+(v>0?'above':v<0?'below':'at')+' target':'unavailable';
    text('final-targets',c?'BTC '+gap(c.target_gap)+' · BRTI '+gap(c.brti_gap):'Target relationship unavailable');
    text('final-market',c?'Kalshi '+c.side+' BID / ASK '+shortCents(c.bid)+' / '+shortCents(c.ask)+' · at model snapshot':'Market odds unavailable');
    text('final-summary',!f?'Current qualification unavailable':f.ready&&f.lock_state==='QUALIFIED'&&f.state==='FINAL_CALL'?'Qualified settlement call · not a BUY':finite(f.confidence)&&f.confidence<.90?'PASS · model below 90% lock requirement':'PASS · other lock conditions not met');
    const verified=e?.valid_book===true&&e.series_fee_verified===true;
    const supported=verified&&finite(e.stress_net_model_ev_scenario)&&e.stress_net_model_ev_scenario>0;
    text('final-value',!verified?'Uncertain · current book or applicable fees unavailable':supported?'Positive model value at '+shortCents(c.ask)+' ASK · not an entry signal':'PASS · '+c.side+' ASK '+shortCents(c.ask)+' lacks supported value after costs');
    table('final-value-details',c?[
      ['Native model / ASK',percentValue(c.fair)+' / '+centsValue(c.ask)],
      ['Entry fee / spread',centsValue(e?.entry_fee_scenario)+' / '+centsValue(e?.spread)],
      ['Model value after fee / spread stress',centsValue(e?.net_model_ev_scenario)+' / '+centsValue(e?.stress_net_model_ev_scenario)],
      ['Qualification',f?.state+' · '+f?.lock_state+' · existing 90% and all other native gates'],
      ['Meaning','Model-implied settlement scenario, not calibrated expected profit, a scalp forecast, a BUY or a fill. Market prices do not guarantee settlement.']
    ]:[]);
  }
  function renderCompactTrade(t,lane,name){
    const r=t.record,x=r?.terminal,p=t.current?lane.current_payload:null,e=t.economics||x?.economics;
    const state=t.entry?'BUY ISSUED':t.current?(t.management==='CAUTION'?'WATCH · CAUTION':t.management):t.completed?'COMPLETED EXIT':t.historical?'HISTORICAL SIGNAL':r?'SOURCE REFRESHING':'NO ISSUED BUY';
    text(name+'-action',state);
    text(name+'-reason',t.entry?'Current entry signal · manual execution':t.current?'Existing signal under management · no new entry':t.completed?'Completed recommendation · no new entry':t.historical?'Entry expired · history only':r?'Current action unavailable':'WATCH / PASS scans are separate');
    text(name+'-price',r?r.side+' · original ASK '+shortCents(r.original_ask)+' · '+(r.serial_index==null?'':'#'+r.serial_index+' · ')+clockTime(r.signal_ts):'No recorded BUY');
    label(name+'-freshness',t.current?'Current source · '+(finite(t.bid)?'same-side BID '+shortCents(t.bid):'awaiting later BID'):r&&!t.completed&&!t.historical?'Current source unavailable · no executable price':'',t.current?'current':'unavailable');
    const evidence=p?.management?.evidence,context=p?.context;
    const warning=evidence?.model_opposes?'Model opposes original direction':evidence&&(evidence.btc_held_side_gap<=0||evidence.brti_held_side_gap<=0)?'BTC / BRTI against signal':evidence?.recent_momentum_adverse?'Momentum turned against signal':context?.reasons?.length?(shortReasons[context.reasons[0]]||'Market support needs attention'):name==='scalp'&&t.management==='PROTECT'?'Risk trigger armed':(shortReasons[t.reason]||'Support weakening or uncertain');
    const passive=t.completed?'Completed':t.historical?'Historical':r?'Source unavailable':'No issued signal';
    const rows={entry:r?'BUY '+r.side+' · '+shortCents(r.original_ask)+(t.entry?' · current':' · recorded'):'No BUY issued',
      hold:t.current?(t.management==='HOLD'?'Original thesis supported':t.entry?'Awaiting next evaluation':'Needs attention'):passive,
      watch:t.current?(['WATCH','CAUTION','PROTECT'].includes(t.management)?warning:'No new warning'):passive,
      protect:t.current?(t.management==='PROTECT'?(e?.meaningful_positive_net?'Positive net scenario · protect':'Defensive risk · profit unproven'):'Not triggered'):passive,
      exit:t.completed?'Recorded · '+(shortReasons[x.reason]||'Native exit')+' · BID '+shortCents(x.observed_bid)+' · '+clockTime(x.trigger_ts):t.historical?'No current exit':t.current?'No exit recommendation':'Unavailable'};
    const active=t.current?({ENTER:'entry',HOLD:'hold',WATCH:'watch',CAUTION:'watch',PROTECT:'protect',EXIT:'exit'}[t.management]):null;
    for(const [key,value] of Object.entries(rows))text(name+'-'+key,value);
    for(const item of node(name+'-ladder')?.children||[]){item.removeAttribute('aria-disabled');if(item.dataset.rung===active)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');}
    text(name+'-value-note',name==='scalp'&&r?'Momentum call · profit potential unproven. '+(t.current&&e?.meaningful_positive_net?'Observed net scenario '+shortCents(e.net_after_execution_reserve)+' after costs.':''):r?'Signal only · execution unconfirmed.':'');
  }
  function renderValueAnalysis(native,current){
    const a=native?.opportunity_analysis;
    const valid=a?.schema==='BTC15_NATIVE_VALUE_ANALYSIS_V1'&&a.contract===native.contract;
    const prefix=current?'POTENTIAL OPPORTUNITIES — NOT ISSUED BUY signals':'HISTORICAL analysis — NOT ISSUED BUY signals';
    text('value-freshness',valid?prefix+' · '+stamp(native.published_ts):'Awaiting native value analysis');
    text('value-best',valid?(current?'':'HISTORICAL · ')+(a.best_directional?a.best_directional.status+' · '+a.best_directional.side+' · '+a.best_directional.reason:'PASS · No directional candidate qualifies or meets the observational value conditions'):'No current native value selection');
    text('value-selection',valid?a.selection_reason:'Native strategy states appear independently as their sources arrive');
    for(const side of ['UP','DOWN']){
      const c=valid?a.candidates.find(c=>c.side===side):null,e=c?.economics;
      text('value-'+side.toLowerCase()+'-status',c?c.status+' · '+c.reason:'Awaiting native '+side+' evaluation');
      table('value-'+side.toLowerCase(),c?[
        ['BID / ASK',centsValue(c.bid)+' / '+centsValue(c.ask)],
        ['Model fair / gross edge',percentValue(c.fair)+' / '+centsValue(c.edge)],
        ['Fee / spread stress',centsValue(e.entry_fee_scenario)+' / '+centsValue(e.spread)],
        ['Model EV after fee / stress',centsValue(e.net_model_ev_scenario)+' / '+centsValue(e.stress_net_model_ev_scenario)],
        ['Settlement win / loss scenario',centsValue(e.win_profit_scenario)+' / '+centsValue(e.loss_scenario)],
        ['Reward / risk ratio',finite(e.reward_risk_scenario)?e.reward_risk_scenario.toFixed(2):'Unavailable'],
        ['Break-even probability',percentValue(e.break_even_probability)],
        ['Entry qualification',c.qualification_basis],
        ['Native safeguards',c.value_qualification?Object.entries(c.value_qualification.conditions).map(([k,v])=>(v?'PASS ':'WAIT ')+k.replaceAll('_',' ')).join('; '):'This side has no supported value-entry assessment'],
        ['FINAL support',c.final_relation],
        ['Native momentum / trend',c.value_qualification?dollarsValue(c.value_qualification.risk?.move1)+' / '+dollarsValue(c.value_qualification.risk?.move5)+' (existing 1m / 5m features)':'Unavailable'],
        ['Round-trip stress value margin',centsValue(c.value_qualification?.economics?.round_trip_stress_value_margin)],
        ['Model flip risk',percentValue(c.value_qualification?.risk?.model_flip_probability)],
        ['BTC / BRTI target gap',dollarsValue(c.target_gap)+' / '+dollarsValue(c.brti_gap)],
        ['Recent native BTC move',c.btc_move_since_previous_native===null?'Causal prior sample unavailable':c.btc_move_since_previous_native.toFixed(2)+' USD / '+c.native_interval_seconds.toFixed(1)+'s'],
        ['Secondary / pullback',c.secondary_state+' · '+c.secondary_reason],
        ['What must improve',c.improvements.length?c.improvements.join('; '):'Native entry policy qualifies; confirm executable price and fees manually']
      ]:[]);
    }
    text('value-risk',valid?'Model probabilities: UP '+percentValue(a.model.probability_up)+' / DOWN '+percentValue(a.model.probability_down)+' · '+a.model.reliability+' · 5m BTC range '+dollarsValue(a.volatility.range5)+' · Reversal '+a.reversal.status+': '+a.reversal.reason:'Probability, volatility and reversal context require a valid native publication');
    const fees=a?.value_entry_policy?.fee_schedule;
    text('value-costs',valid?'Cost scenario: '+(fees?.observed_ts?'published series multiplier '+fees.multiplier+' · checked '+stamp(fees.observed_ts):'unverified general M=1 fallback; cannot authorize the supported-value route')+'; one contract, conservatively cent-rounded; stress adds one observed spread. Event/account overrides, size, depth and slippage unverified. No fill assumed. EV is model-implied, not established expected profit.':'Cost scenarios are unavailable until native analysis arrives');
  }
  function renderIssued(lane,identity,name){
    const t=window.BTC15TradeRecords.project(lane,identity,name),r=t.record;
    const completedReasons={DIRECTIONAL_THESIS_INVALIDATED:'The original directional thesis failed: the model, BTC/BRTI target support and causal momentum turned against that signal.',NET_BID_EXCEEDS_WEAKENING_MODEL_VALUE:'The observed net BID exceeded the weakening held-side model value.',ARM5_GIVEBACK4:'A defensive giveback exit was recommended after the gross-movement risk trigger fired. This does not establish a profitable scalp.'};
    const reasonLabel=reason=>(t.completed&&completedReasons[reason])||window.BTC15SnapshotAdapter.reasonLabels[reason]||String(reason||'').replaceAll('_',' ');
    const why=reasonLabel(t.reason);
    if(name==='early')text('early-direction',r?r.side+(t.historical?' · historical':''):'No issued direction');
    text(name+'-management-detail',why);
    table(name+'-issued',r?[
      ['Original BUY',r.side+' · '+r.contract],['Issued at',stamp(r.signal_ts)],
      ['Original Kalshi ASK',centsValue(r.original_ask)],['Immutable signal ID',r.origin_id],
      ['Serial / status',(r.serial_index==null?'EARLY':('#'+r.serial_index))+' · '+(t.completed?'Closed recommendation; execution unconfirmed':t.historical?'Expired / historical':t.current?'Active management':'Historical record; source unavailable')],
      ['Entry qualification',r.entry_reason],['Entry rule',r.entry_policy||'Native entry'],
      ['Current management',t.current?(t.entry?'BUY ISSUED':t.management):t.completed?'Completed EXIT recommendation':('Unavailable; last recorded '+(r.management_state||'unknown'))],
      ['Entry authority',t.entry?'Current native BUY publication; verify book manually':'NOT CURRENT — original BUY is a recorded event']
    ]:[]);
    const x=r?.terminal;
    text(name+'-exit-record',x?(x.state==='EXIT'?'COMPLETED EXIT RECOMMENDATION':'EXPIRED SIGNAL — NO EXECUTABLE EXIT')+' · '+stamp(x.trigger_ts)+' · observed trigger BID '+centsValue(x.observed_bid)+' · '+reasonLabel(x.reason)+' · no fill or realized profit assumed':'');
    table(name+'-signal-history',t.records.slice().reverse().map(a=>[a.contract+' · '+(a.serial_index==null?'EARLY':'#'+a.serial_index)+' · '+a.side,
      stamp(a.signal_ts)+' · original ASK '+centsValue(a.original_ask)+' · '+(a.terminal?.state==='EXIT'?'COMPLETED EXIT':a.terminal?'EXPIRED':a.origin_id===r?.origin_id&&!t.historical?'ISSUED RECORD':'HISTORICAL')+' · ID '+a.origin_id]));
    if(name==='early'&&!t.current)text('early-management',t.completed?'The EXIT recommendation is completed and recorded above. '+(x.economics?'Recorded trigger scenario: gross movement '+centsValue(x.economics.gross_movement_cents/100)+' · estimated net liquidation '+centsValue(x.economics.net_liquidation_scenario)+' · historical observed prices. ':'')+'No actual exit or realized profit is assumed.':'No current executable liquidation scenario; original BUY identity remains visible above.');
    if(name==='scalp'){
      const risk=r?.entry_risk;
      table('scalp-entry-risk',risk?[
        ['AT ISSUE · entry / sale fee budget',centsValue(risk.entry_fee_estimate)+' / '+centsValue(risk.exit_fee_budget)],
        ['AT ISSUE · spread / extra execution reserve',centsValue(risk.observed_spread)+' / '+centsValue(risk.execution_reserve)],
        ['AT ISSUE · same-side BID change / BTC30',centsValue(risk.observed_bid_change_30s)+' / '+dollarsValue(risk.btc30)],
        ['Cost hurdle for >2¢ net · NOT a forecast','Later BID must exceed '+centsValue(risk.bid_hurdle_exclusive)],
        ['Theoretical net price room / possible full loss',centsValue(risk.net_price_room)+' / '+centsValue(risk.maximum_entry_loss)+' · $1 payout bound; no probability assigned'],
        ['Configured protection trigger',centsValue(risk.management_arm_bid)+' BID · movement trigger, not profitable exit'],
        ['Observed movement versus cost hurdle',risk.observed_move_covers_cost_hurdle===true?'Recent BID move exceeded the cost hurdle; continuation unproven':risk.observed_move_covers_cost_hurdle===false?'Recent BID move did not cover the cost hurdle; trade value unproven':'Not recorded for this historical signal'],
        ['Expected profit','UNESTABLISHED · momentum call with cost room; no guaranteed exit or fill']
      ]:[]);
      const e=t.economics||x?.economics;
      text('scalp-economics',e?(t.completed?'HISTORICAL EXIT SCENARIO · ':'')+'Observed gross movement '+centsValue(e.gross_movement_cents/100)+' · entry / exit fee estimate '+centsValue(e.entry_fee_scenario)+' / '+centsValue(e.exit_fee_scenario)+' · net liquidation '+centsValue(e.net_liquidation_scenario)+' · after execution reserve '+centsValue(e.net_after_execution_reserve)+' · '+(e.meaningful_positive_net?'Meaningful positive net scenario':'Profitable scalp NOT established')+' · no fill or realized profit assumed':'No current verified net liquidation scenario. Entries require native momentum and cost room; expected profit remains unestablished. Profit-oriented protection requires an observed scenario above 2¢ net after fees and execution reserve. Defensive exits remain available.');
    }
    renderCompactTrade(t,lane,name);
    // Completed or historical recommendations never light an active action rung.
    const prefixes=name==='early'?['early']:['scalp-up','scalp-down'];
    for(const prefix of prefixes){
      const list=node(prefix+'-ladder');if(!list)continue;
      if(!t.current)for(const item of list.children){item.removeAttribute('aria-current');}
    }
  }
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
      for(const [name,lane] of [['final',m]]){
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
      text('early-context',early?(!m?.eligible?'LAST QUALIFIED · ':'')+'Model fair '+(early.fair*100).toFixed(1)+'% · all prices evaluated for value · historical Tier-1 is separate · '+(opportunity?.status||'Awaiting native analysis'):'Awaiting a qualified EARLY evaluation');
      if(['EARLY_SUPPORTED_VALUE_V1','EARLY_CAUSAL_VALUE_V2'].includes(native?.origin?.entry_policy)){
        const o=native.origin,eq=o.qualification,ec=eq.economics;
        text('early-context',(!m?.eligible?'LAST QUALIFIED · ':'')+'Supported-value origin · entry model '+percentValue(o.entry_provenance.fair[o.side.toLowerCase()+'_fair'])+' · current model '+percentValue(native.final[o.side==='UP'?'probability_up':'probability_down'])+' · entry fee/stress model EV '+centsValue(ec.net_model_ev_scenario)+' / '+centsValue(ec.stress_net_model_ev_scenario)+' · settlement reward/risk '+centsValue(ec.win_profit_scenario)+' / '+centsValue(ec.loss_scenario)+' · '+Math.max(0,Math.round(native.official_close-native.published_ts))+'s at native observation · win rate unestablished');
      }
      if(native?.origin&&native.management){
        const e=native.management.economics,ev=native.management.evidence;
        text('early-management',(!m?.eligible?'HISTORICAL · ':'')+'If manually entered: observed gross ASK→BID movement '+centsValue(e.gross_movement_cents/100)+
          ' · estimated entry / exit fees '+centsValue(e.entry_fee_scenario)+' / '+centsValue(e.exit_fee_scenario)+
          ' · net liquidation scenario '+centsValue(e.net_liquidation_scenario)+' · not realized profit. '+
          'FINAL held-side model '+percentValue(ev.held_model_probability)+' · momentum '+(ev.causal_momentum_available?(ev.recent_momentum_adverse?'adverse':'supporting or flat'):'unavailable')+
          ' · closure unconfirmed; depth, size and actual fills unverified.');
      }else text('early-management','Current EARLY management unavailable; see the retained issued record. No entry or exit fill assumed.');
      renderValueAnalysis(native,!!m?.eligible);
      renderFinal(m);
      const scalpHistorical=!s?.eligible&&oldScalp&&!/unavailable/i.test(old.fields['scalp-action']);
      const scalp=s?.eligible?s.current_payload:scalpHistorical?oldScalp:null;
      for(const side of ['UP','DOWN']){
        const current=(scalpHistorical?old:view).scalpSide===side,scan=scalp?.diagnostics?.find(d=>d.side===side);
        const explain=scan?(window.BTC15SnapshotAdapter.reasonLabels[scan.reason]||String(scan.reason).replaceAll('_',' ')):null;
        const coverage=scalp?.opportunity_coverage?.find(c=>c.side===side);
        text('scalp-'+side.toLowerCase()+'-status',coverage?coverage.status+' · '+coverage.reason+' · '+coverage.next_condition:current?'Published '+scalp.guidance+' · '+side:scalp?(explain?'No new '+side+' entry · '+explain:'No new '+side+' opportunity published'):'No qualified '+side+' explanation');
        label('scalp-'+side.toLowerCase()+'-freshness',scalpHistorical?'LAST QUALIFIED · historical; no current authority':s?.eligible?'CURRENT · source diagnostic':'UNAVAILABLE · no current source',scalpHistorical?'retained':s?.eligible?'current':'unavailable');
      }
      renderIssued(m,identity,'early');
      renderIssued(s,identity,'scalp');
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

