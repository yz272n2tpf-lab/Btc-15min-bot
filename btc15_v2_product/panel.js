/* Sole owner of V2 action cards and executable price readouts. SIGNAL ONLY. */
(() => {
  'use strict';
  const REVISION='BTC15_V2_PRODUCT_20261004_R1',STRATEGY='BTC15_LADDER_COMPLETION_20261003_V2';
  const caches={main:null,scalp:null,quote:null},requests={main:null,scalp:null,quote:null};
  const clocks={main:null,scalp:null,quote:null}; // Monotonic floor survives hide/resume; cached replies cannot renew leases.
  let epoch=0,identity=null,quoteHistory=null;const receipts=[];
  let indicators=null,indicatorRequest=null,indicatorClock=null,lastIndicators=null;
  // Strings only, display-only: never read by accept(), current(), or any action gate.
  const history={main:null,scalp:null,quote:null};
  const infoIds={main:['finalConfidence','finalActionSub','earlyEntry','earlyYourEntry','earlyCurrentPrice','earlyEdge','flipRisk','signalStrength'],scalp:['scalpYourEntry','scalpCurrentPrice','scalpTargetStrip'],quote:['upOdds','downOdds']};
  const node=id=>document.getElementById(id);
  const text=(id,v)=>{const n=node(id);if(n&&n.textContent!==String(v))n.textContent=String(v);};
  const cents=v=>Number.isFinite(v)?(100*v).toFixed(1)+'¢':'REFRESHING';
  const pct=v=>Number.isFinite(v)?(100*v).toFixed(1)+'%':'REFRESHING';
  const human=v=>String(v||'').replace(/_/g,' ').toLowerCase();
  const finite=Number.isFinite;
  const key=i=>i&&[i.contract,i.target,i.official_open,i.official_close].join('|');
  function official(i,at){
    if(!(i&&finite(i.target)&&i.target>0&&finite(i.official_open)&&i.official_open%900===0&&i.official_close-i.official_open===900&&i.official_open<=at&&at<i.official_close))return false;
    const p=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'2-digit',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(i.official_close*1000)).map(p=>[p.type,p.value]));
    return i.contract===`KXBTC15M-${p.year}${p.month.toUpperCase()}${p.day}${p.hour}${p.minute}-${p.minute}`;
  }
  function current(lane){const c=caches[lane];return c&&performance.now()<c.deadline&&document.visibilityState!=='hidden'?c.data:null;}
  function classes(id,value){const n=node(id);if(n&&n.className!==value)n.className=value;}
  function pill(id,v){text(id,v);classes(id,'state-pill '+(['ENTER','HOLD','AVAILABLE','QUALIFIED'].includes(v)?'state-good':'state-watch'));}
  const reasons={
    REVALIDATION_DISAGREES_WAIT_NATIVE:'native revalidation disagrees; awaiting next native observation',
    REVALIDATION_IDENTITY_OR_CLOCK:'identity / clock refresh pending',
    REVALIDATION_EXPIRED_OR_NONCAUSAL:'source refresh pending',
    REVALIDATION_PENDING:'native revalidation pending',
    TIMESTAMPED_QUOTES_UNAVAILABLE:'timestamped quote refresh pending',
    OFFICIAL_MARKET_UNQUALIFIED:'official market refresh pending',
    SOURCE_EXPIRED:'source refresh pending',
    PRICE_OUTSIDE_30_45C:'price outside 30–45¢',
    NO_SIDE_IN_30_45C:'price outside 30–45¢',
    BASE_NOT_READY:'base not ready',
    EVIDENCE_BELOW_CORE_SURGE:'evidence below CORE/SURGE',
    READY_CONFIRMING:'confirmation pending', FEATURES_NOT_READY:'feature history not ready',
    BRTI_NOT_FRESH:'BRTI refresh pending',
    ask_le45:'current ask is above 45¢',
    fair_ge75:'model fair below 75%',
    remaining_2_to10:'outside EARLY entry window (requires 2–10m remaining)',
    gap_ge25:'BTC gap below $25'
  };
  const reasonText=v=>reasons[v]||human(v||'source refresh pending').replace(/unavailable|not connected/g,'refresh pending');
  function remember(lane,ident,at){
    history[lane]={identity:key(ident),contract:ident.contract,at,values:Object.fromEntries(infoIds[lane].map(id=>[id,node(id)?.textContent]))};
  }
  function retained(lane,id,ident,label=true){
    const h=history[lane],value=h?.values[id];
    return value&&(!ident||h.identity===key(ident))?value+(label?' · LAST QUALIFIED':'')+(!ident?' · '+h.contract:''):'REFRESHING';
  }
  function waiting(prefix,reason,ident){
    pill(prefix+'State','WAIT');text(prefix+'Title',prefix.toUpperCase()+' · REFRESHING');text(prefix+'Arrow','—');
    text(prefix+'Entry','WAIT — '+reasonText(reason));
    const lane=prefix==='early'?'main':'scalp';
    text(prefix+'CurrentPrice',retained(lane,prefix+'CurrentPrice',ident));
    text(prefix+'YourEntry',retained(lane,prefix+'YourEntry',ident));
    for(const k of ['Entry','Hold','Watch','Protect','Exit'])text(prefix+'Ladder'+k,'WAIT · current authority refresh pending');
    text(prefix+'Flow','WAIT — '+reasonText(reason)+' · SIGNAL ONLY / NO ORDERS');
  }
  function scalpPass(s){
    const ds=Array.isArray(s.diagnostics)?s.diagnostics.filter(d=>d&&d.reason):[];
    if(!ds.length)return 'PASS — '+reasonText(s.reason||'native gates not qualified');
    if(ds.every(d=>d.reason===ds[0].reason))return 'PASS — '+reasonText(ds[0].reason);
    return ds.map(d=>(['UP','DOWN'].includes(d.side)?d.side+' ':'')+'PASS — '+reasonText(d.reason)).join(' · ');
  }
  function earlyPass(e,prices){
    const rs=Array.isArray(e?.pass_reasons)?e.pass_reasons:[];
    const why=rs.length?rs.map(reasonText).join(' · '):'native EARLY gates not qualified';
    const quotes=prices&&['up_ask','down_ask'].every(k=>finite(prices[k]))
      ?`UP ASK ${cents(prices.up_ask)} · DOWN ASK ${cents(prices.down_ask)}`
      :'WAIT — executable quotes refreshing';
    return {reason:'PASS — '+why,quotes};
  }
  function render(){
    const now=performance.now(),m=current('main'),s=current('scalp'),q=current('quote');
    if(identity&&now>=identity.deadline)identity=null;
    const ident=identity?.value;
    const iv=indicators&&now<indicators.deadline&&document.visibilityState!=='hidden'?indicators.data:null;
    const cells=document.querySelectorAll('.indicator-row .indicator-unavailable');
    const number=v=>Math.abs(v)>=10000?v.toPrecision(5):v.toFixed(2);
    if(iv)lastIndicators=iv;
    const shownIndicators=iv||lastIndicators;
    const values=shownIndicators?[finite(shownIndicators.rsi)?number(shownIndicators.rsi):null,finite(shownIndicators.macd)?`${number(shownIndicators.macd)} / ${number(shownIndicators.signal)} / ${number(shownIndicators.histogram)}`:null,number(shownIndicators.volume)+' BTC']:[];
    cells.forEach((n,index)=>{const value=values[index]?(values[index]+(!iv?' · LAST QUALIFIED / REFRESHING':'')):'WAIT — indicator history refresh pending';if(n.textContent!==value)n.textContent=value;});
    const qualified=m&&m.status!=='UNAVAILABLE'&&key(m.official_identity)===key(ident);
    const aligned=s&&s.status!=='UNAVAILABLE'&&ident&&key(s.official_identity)===key(ident);
    text('currentContract',ident?'BTC 15-MINUTE · '+ident.contract+' · V2':'BTC 15-MINUTE · WAIT — official identity refresh pending');
    text('liveStatus','MAIN '+(qualified?m.status:'WAIT / REFRESHING')+' · SCALP '+(aligned?s.status:'WAIT / REFRESHING'));
    classes('liveStatus','live-status '+(qualified?'live-ok':'live-warn'));
    const f=qualified?m.final:null;
    classes('finalCard','card final-card '+(f?.ready?(f.side==='DOWN'?'down-mode':''):'wait-mode'));
    // Original V13 display classification (8e25678); no strategy authority.
    const probability=f?.confidence;
    text('signalStrength',finite(probability)?(probability>=.90?'STRONG':probability>=.75?'GOOD':probability>=.60?'MODERATE':'WEAK'):retained('main','signalStrength',ident));
    if(f){
      text('finalArrow',f.ready?(f.side==='DOWN'?'↓':'↑'):'—');
      text('finalSide',f.ready?f.side+' FINAL':'PASS');
      text('finalAction',f.ready?'QUALIFIED':'UNLOCKED / PASS');
      text('finalConfidence','Model only: '+pct(f.confidence));
      text('finalActionSub',`UP ${pct(f.probability_up)} · DOWN ${pct(f.probability_down)} · independent model`);
      text('finalReason',f.ready?'Independent FINAL call qualified':'FINAL entry not qualified');
      text('finalBuyZone',m.origin&&f.early_origin_id===m.origin.origin_id?'Linked EARLY '+m.origin.side:'No linked EARLY origin');
      text('finalHoldZone',f.helper?.confirmed?'EARLY confirmed · '+f.helper.state:human(f.state));
      text('finalWatchZone',f.helper?human(f.helper.relation)+' · '+human(f.helper.probability_trend):'No position assumed');
      text('finalProtectZone',f.helper?.protect_latched?'PROTECT · support lost or opposed':'No new protection instruction');
      text('finalExitZone','No supported EARLY EXIT threshold · no automatic EXIT');
    }else{
      text('finalArrow','—');text('finalSide','WAIT');text('finalConfidence',retained('main','finalConfidence',ident));text('finalAction','WAIT');
      text('finalActionSub','WAIT — '+reasonText(m?.reason));text('finalReason','No current actionable FINAL guidance');
      for(const id of ['finalBuyZone','finalHoldZone','finalWatchZone','finalProtectZone','finalExitZone'])text(id,'WAIT · current authority refresh pending');
    }
    if(!qualified){
      waiting('early',m?.reason,ident);
      text('earlyAfterEntry','WAIT — '+reasonText(m?.reason));text('earlyEdge',retained('main','earlyEdge',ident));
      text('flipRisk',retained('main','flipRisk',ident,false));text('flipRiskSub','LAST QUALIFIED / REFRESHING · no action authority');
      text('contextBanner','WAIT — '+reasonText(m?.reason));
    }else{
      const e=m.early,o=m.origin,h=f?.helper,ctx=m.context;
      const prices=m.presentation_revalidation?.prices;
      const quotePrices=q&&q.status==='AVAILABLE'&&ident&&key(q.official_identity)===key(ident)?q:null;
      const ask=prices?prices[e.side.toLowerCase()+'_ask']:e.ask;
      const bid=prices&&o?prices[o.side.toLowerCase()+'_bid']:m.executable_current_bid;
      const pass=!o&&e.guidance==='PASS',passView=pass?earlyPass(e,prices||quotePrices):null;
      pill('earlyState',e.guidance);text('earlyTitle',o?'EARLY '+o.side:'EARLY · '+e.guidance);
      text('earlyEntry',o?'Origin ASK '+cents(o.original_ask):pass?passView.reason:'Current ASK '+cents(ask));
      text('earlyYourEntry',o?cents(o.original_ask)+' · signal ASK':'No accepted origin');
      text('earlyCurrentPrice',o?'BID '+cents(bid):pass?passView.quotes:'ASK '+cents(ask));
      text('earlyEdge',o?((bid-o.original_ask)*100).toFixed(1)+'¢ gross movement':pass?'No actionable edge while PASS':cents(e.edge)+' model edge');
      text('earlyAfterEntry',o?e.guidance+' · '+human(h?.relation):pass?passView.reason:'PASS · '+e.pass_reasons.map(reasonText).join(' · '));
      text('earlyLadderEntry','≤45¢ · fair ≥75% · 2–10m · |gap| ≥$25');
      text('earlyLadderHold',h?.confirmed?'FINAL confirms · '+e.guidance:o?e.guidance:'No position assumed');
      text('earlyLadderWatch',pass?passView.reason:ctx?human(ctx.phase)+' · '+ctx.reasons.map(human).join('; '):'Await qualified entry');
      text('earlyLadderProtect',h?.protect_latched?'PROTECT · review exposure at current bid':o?'Monitor FINAL support and bid':'No origin to protect');
      text('earlyLadderExit','No supported EARLY EXIT rule · PROTECT is risk guidance');
      text('earlyFlow',`${m.contract} · ${o?'If manually entered: '+e.guidance:'PASS'} · SIGNAL ONLY / NO ORDERS`);
      text('flipRisk',m.flip_risk_pct.toFixed(1)+'%');text('flipRiskSub','Model context only · no exit authority');
      text('contextBanner',human(m.phase)+' · '+(ctx?ctx.reasons.map(human).join('; '):'No active EARLY origin'));
    }
    text('oppositeArrow','—');text('oppositeTitle','SERIAL REVERSAL / RE-ENTRY');
    if(!aligned){
      waiting('scalp',s?.reason,ident);
      text('scalpTargetStrip',retained('scalp','scalpTargetStrip',ident));text('oppositeEntry','Fresh same-contract setup required');text('oppositeState','WAIT');
    }else{
      const o=s.origin;
      pill('scalpState',s.guidance);text('scalpTitle','SCALP '+(o?.side||'PASS'));text('scalpArrow',o?(o.side==='DOWN'?'↓':'↑'):'—');
      text('scalpEntry',o?'Origin ASK '+cents(o.original_ask):scalpPass(s));
      text('scalpYourEntry',o?cents(o.original_ask)+' · signal ASK':'No accepted origin');
      text('scalpCurrentPrice',o?'BID '+cents(s.executable_current_bid):'No active origin');
      text('scalpTargetStrip',o?s.movement_cents.toFixed(1)+'¢ gross':scalpPass(s));
      text('scalpLadderEntry',o?human(o.lane)+' · #'+o.serial_index:'30–45¢ · ideal overlap 30–35¢');
      text('scalpLadderHold',o?s.guidance+' · maximum 180s signal horizon':'No position assumed');
      text('scalpLadderWatch',s.context?human(s.context.phase)+' · '+s.context.reasons.map(human).join('; '):'Fresh qualifying observations required');
      text('scalpLadderProtect',s.presentation?.protection_armed?'PROTECT · trail trigger '+cents(s.trailing_trigger_bid):'Arms at +5¢ executable gain');
      text('scalpLadderExit',s.guidance==='EXIT'?'EXIT · current BID '+cents(s.executable_current_bid)+' · trigger BID '+cents(s.terminal.executable_exit_bid):'4¢ peak giveback after arm, or 180s horizon');
      text('scalpFlow',`${o?'If manually entered: '+s.guidance+'. ':''}${s.terminal?human(s.terminal.reason)+'. ':''}No assumed fill; fees excluded. SIGNAL ONLY / NO ORDERS`);
      text('oppositeEntry',o?'Next origin requires a later qualified setup after EXIT':'Both sides evaluated');text('oppositeState',s.guidance==='EXIT'?'RECONFIRM':'WAIT');
    }
    if(qualified)remember('main',ident,m.published_ts);
    if(aligned)remember('scalp',ident,s.published_ts);
    const freshQuote=q&&q.status==='AVAILABLE'&&ident&&key(q.official_identity)===key(ident);
    text('upOdds',freshQuote?cents(q.up_ask):retained('quote','upOdds',ident,false));text('downOdds',freshQuote?cents(q.down_ask):retained('quote','downOdds',ident,false));
    text('upCondition',freshQuote?'ASK · BID '+cents(q.up_bid):(history.quote&&(!ident||history.quote.identity===key(ident))?'LAST QUALIFIED / REFRESHING · ':'WAIT — ')+'timestamped quote refresh pending');
    text('downCondition',freshQuote?'ASK · BID '+cents(q.down_bid):(history.quote&&(!ident||history.quote.identity===key(ident))?'LAST QUALIFIED / REFRESHING · ':'WAIT — ')+'timestamped quote refresh pending');
    text('v2QuoteClock',freshQuote?`Source ${new Date(q.exchange_ts*1000).toISOString()} · seq ${q.sequence} · presentation only`:'WAIT — '+reasonText(q?.reason||'TIMESTAMPED_QUOTES_UNAVAILABLE'));
    for(const id of ['upOdds','downOdds']){
      const n=node(id);if(n){const value=freshQuote?[q.epoch,q.sid,q.sequence,q.exchange_ts].join('|'):'';if(n.dataset.quoteIdentity!==value)n.dataset.quoteIdentity=value;if(!freshQuote)n.dataset.quoteEvidence='';}
    }
    if(freshQuote){
      remember('quote',ident,q.exchange_ts);
      const tuple=[key(ident),q.epoch,q.sid,q.sequence].join('|');
      if(tuple!==quoteHistory){
        quoteHistory=tuple;
        receipts.push(Object.freeze({tuple,exchange_ts:q.exchange_ts,accepted_ts:q.accepted_ts,published_ts:q.published_ts,
          received_monotonic:caches.quote.received,rendered_monotonic:now,
          source_age_upper_ms:(q.served_ts-q.exchange_ts)*1000+caches.quote.rtt+(now-caches.quote.received),
          accepted_to_published_ms:(q.published_ts-q.accepted_ts)*1000,
          published_to_render_lower_ms:Math.max(0,(q.served_ts-q.published_ts)*1000+(now-caches.quote.received)),
          published_to_render_upper_ms:Math.max(0,(q.served_ts-q.published_ts)*1000+caches.quote.rtt+(now-caches.quote.received)),
          up_ask:q.up_ask,down_ask:q.down_ask,signal_only:true,orders:false}));
        if(receipts.length>120)receipts.shift();
        for(const id of ['upOdds','downOdds']){const n=node(id);if(n)n.dataset.quoteEvidence=JSON.stringify(receipts[receipts.length-1]);}
      }
    }
  }
  function accept(lane,data,sent,received){
    if(!data||data.signal_only!==true||data.orders!==false||!finite(data.served_ts))throw Error('SAFETY_SCHEMA');
    if(lane==='quote'){
      if(data.schema!=='BTC15_EXECUTABLE_QUOTE_R1'||data.revision!==REVISION||data.authority!=='PRICE_PRESENTATION_ONLY')throw Error('QUOTE_SCHEMA');
    }else if(data.schema!=='BTC15_V2_PRODUCT_ENVELOPE_R1'||data.product_revision!==REVISION||data.candidate!==STRATEGY||data.lane!==(lane==='scalp'?'v81':'main'))throw Error('PRODUCT_SCHEMA');
    const rtt=received-sent,priorClock=clocks[lane];
    const serverNow=Math.max(data.served_ts,priorClock?priorClock.server+(received-priorClock.received)/1000:-Infinity);
    clocks[lane]={server:serverNow,received};
    const i=data.official_identity;
    if((lane==='main'||lane==='quote')&&official(i,serverNow)){
      if(identity&&identity.value.official_open>i.official_open)throw Error('IDENTITY_ROLLBACK');
      if(identity&&identity.value.contract===i.contract&&key(identity.value)!==key(i))throw Error('FIXED_IDENTITY_CONFLICT');
      identity={value:i,deadline:received+(i.official_close-serverNow)*1000-rtt};
    }
    if(data.status==='UNAVAILABLE')return {data,deadline:received+2000,received,rtt}; // Reason only; never an action lease.
    if(!['AVAILABLE','PASS'].includes(data.status)||!finite(data.published_ts)||!finite(data.expires_at)||data.published_ts>data.served_ts||!official(i,data.served_ts))throw Error('CLOCK_OR_IDENTITY');
    if(lane!=='quote'){
      if(data.contract!==i.contract||data.target!==i.target||data.official_open!==i.official_open||data.official_close!==i.official_close||data.expires_at>i.official_close)throw Error('ACTION_IDENTITY');
      if(data.origin&&(!['UP','DOWN'].includes(data.origin.side)||data.origin.contract!==i.contract||!finite(data.origin.original_ask)||!finite(data.movement_cents)||!finite(data.executable_current_bid)))throw Error('ACTION_ORIGIN');
      if(data.context&&(!Array.isArray(data.context.reasons)||typeof data.context.phase!=='string'))throw Error('CONTEXT');
      if(lane==='main'){
        const f=data.final,e=data.early;
        if(!f||!e||typeof f.ready!=='boolean'||!['UP','DOWN'].includes(f.side)||!['confidence','probability_up','probability_down'].every(k=>finite(f[k])&&f[k]>=0&&f[k]<=1)||typeof e.guidance!=='string'||!Array.isArray(e.pass_reasons)||!finite(data.flip_risk_pct)||typeof data.phase!=='string')throw Error('MAIN_PAYLOAD');
        const p=data.presentation_revalidation;
        if(p){
          const s=p.source;
          if(p.schema!=='BTC15_READ_ONLY_REVALIDATION_R1'||p.status!=='CONFIRMED'||p.authority!=='PRESENTATION_CONFIRMATION_ONLY'||p.signal_only!==true||p.orders!==false||p.native_epoch!==data.native_epoch||p.native_sequence!==data.native_sequence||key(p.official_identity)!==key(i)||!s||!s.brti_epoch||!s.quote_epoch||!Number.isInteger(s.sid)||!Number.isInteger(s.sequence)||!['brti','brti_received','btc','btc_received','quote','quote_accepted','cut'].every(k=>finite(s[k]))||!(s.brti<=s.brti_received&&s.brti_received<=s.cut&&s.btc<=s.btc_received&&s.btc_received<=s.cut&&s.quote<=s.quote_accepted&&s.quote_accepted<=s.cut&&s.cut<=p.checked_ts&&p.checked_ts<=data.served_ts)||data.expires_at!==p.expires_at||data.expires_at>Math.min(i.official_close,s.brti+5,s.btc+10,s.quote+6)||!p.prices||!['up_bid','up_ask','down_bid','down_ask'].every(k=>finite(p.prices[k])&&p.prices[k]>=0&&p.prices[k]<=1)||p.prices.up_bid>p.prices.up_ask||p.prices.down_bid>p.prices.down_ask)throw Error('REVALIDATION_PROOF');
        }
      }else if(!['PASS','ENTER','HOLD','CAUTION','PROTECT','EXIT'].includes(data.guidance)||(data.guidance==='EXIT'&&(!data.terminal||!finite(data.terminal.executable_exit_bid))))throw Error('SCALP_PAYLOAD');
    }
    if(lane==='quote'){
      if(!data.epoch||!Number.isInteger(data.sid)||!Number.isInteger(data.sequence)||!finite(data.exchange_ts)||!finite(data.accepted_ts)||!(i.official_open<=data.exchange_ts&&data.exchange_ts<=data.accepted_ts&&data.accepted_ts<=data.published_ts)||data.expires_at>Math.min(i.official_close,data.exchange_ts+6))throw Error('QUOTE_PROVENANCE');
      if(!['up_ask','up_bid','down_ask','down_bid'].every(k=>finite(data[k])&&data[k]>=0&&data[k]<=1)||data.up_bid>data.up_ask||data.down_bid>data.down_ask)throw Error('QUOTE_VALUES');
      const old=caches.quote?.data;
      if(old?.status==='AVAILABLE'&&key(old.official_identity)===key(i)&&data.exchange_ts<old.exchange_ts)throw Error('QUOTE_ROLLBACK');
      if(old?.epoch===data.epoch&&(old.sid!==data.sid||old.sequence>data.sequence))throw Error('QUOTE_SEQUENCE_ROLLBACK');
    }
    const old=caches[lane]?.data;
    if(old?.published_ts>data.published_ts)throw Error('PUBLICATION_ROLLBACK');
    return {data,deadline:received+Math.max(0,(data.expires_at-serverNow)*1000)-rtt,received,rtt};
  }
  async function poll(lane,url){
    if(requests[lane]||document.visibilityState==='hidden')return;
    const controller=new AbortController(),generation=epoch,token={controller,generation};requests[lane]=token;
    const timeout=setTimeout(()=>controller.abort(),3000),sent=performance.now();
    try{
      let response;try{response=await fetch(url,{cache:'no-store',signal:controller.signal});}catch{throw Error('QUOTE_TRANSPORT');}
      if(!response.ok)throw Error('HTTP');
      const data=await response.json(),received=performance.now();
      if(generation!==epoch||document.visibilityState==='hidden')return;
      caches[lane]=accept(lane,data,sent,received);
    }catch(error){if(generation===epoch){
      // Keep only a transport-interrupted quote, on its ORIGINAL monotonic lease.
      // Malformed/revoked observations, action failures and lifecycle changes clear.
      if(lane!=='quote'||!['HTTP','QUOTE_TRANSPORT'].includes(error.message))caches[lane]=null;
    }}
    finally{clearTimeout(timeout);if(requests[lane]===token)requests[lane]=null;}
    render();
  }
  function refresh(){if(document.visibilityState!=='hidden'){poll('main','/ladders');poll('scalp',__V81_LADDERS_URL__);}}
  function refreshQuotes(){poll('quote','/ladders/quotes');}
  async function refreshIndicators(){
    if(indicatorRequest||document.visibilityState==='hidden')return;
    const controller=new AbortController(),generation=epoch,sent=performance.now();indicatorRequest=controller;
    const timeout=setTimeout(()=>controller.abort(),3000);
    try{
      const response=await fetch('/ladders/indicators',{cache:'no-store',signal:controller.signal});
      if(!response.ok)throw Error('INDICATOR_HTTP');
      const d=await response.json(),received=performance.now();
      if(generation!==epoch)return;
      if(d.schema!=='BTC15_DISPLAY_INDICATORS_R1'||d.authority!=='DISPLAY_ONLY'||d.signal_only!==true||d.orders!==false||!finite(d.served_ts))throw Error('INDICATOR_SCHEMA');
      const server=Math.max(d.served_ts,indicatorClock?indicatorClock.server+(received-indicatorClock.received)/1000:-Infinity);
      indicatorClock={server,received};
      if(d.status==='UNAVAILABLE'){indicators=null;return;}
      if(d.status!=='AVAILABLE'||d.provider!=='COINBASE_EXCHANGE'||d.product!=='BTC-USD'||d.granularity!==60||d.volume_unit!=='BTC'||!Number.isInteger(d.completed_count)||d.completed_count<1||d.completed_count>300||!['candle_open','candle_close','request_cutoff','received_ts','expires_at','volume'].every(k=>finite(d[k]))||d.candle_open%60||d.candle_close-d.candle_open!==60||!(d.candle_close<=d.request_cutoff&&d.request_cutoff<=d.received_ts&&d.received_ts<=d.served_ts)||d.expires_at!==d.candle_close+75||d.volume<0)throw Error('INDICATOR_PROVENANCE');
      if(d.completed_count>=15?(!finite(d.rsi)||d.rsi<0||d.rsi>100):d.rsi!==null)throw Error('RSI_HISTORY');
      if(d.completed_count>=34?(!['macd','signal','histogram'].every(k=>finite(d[k]))||Math.abs(d.macd-d.signal-d.histogram)>1e-8):[d.macd,d.signal,d.histogram].some(v=>v!==null))throw Error('MACD_HISTORY');
      if(indicators&&d.candle_close<indicators.data.candle_close)throw Error('INDICATOR_ROLLBACK');
      indicators={data:d,deadline:received+Math.max(0,(d.expires_at-server)*1000)-(received-sent)};
    }catch{if(generation===epoch)indicators=null;}
    finally{clearTimeout(timeout);if(indicatorRequest===controller)indicatorRequest=null;render();}
  }
  function invalidate(){epoch++;identity=null;quoteHistory=null;indicators=null;indicatorRequest?.abort();indicatorRequest=null;for(const lane of Object.keys(caches)){requests[lane]?.controller.abort();requests[lane]=null;caches[lane]=null;}render();}
  document.addEventListener('visibilitychange',()=>{invalidate();if(document.visibilityState!=='hidden'){refresh();refreshQuotes();refreshIndicators();}});
  window.addEventListener('pagehide',invalidate);
  window.addEventListener('pageshow',()=>{invalidate();refresh();refreshQuotes();refreshIndicators();});
  window.btc15RenderLadders=render;
  // Read-only bounded render receipts for paired acceptance measurements. No automatic external telemetry.
  window.btc15QuoteRenderReceipts=()=>receipts.map(r=>({...r}));
  setInterval(refresh,1000);setInterval(()=>poll('main','/ladders'),250);setInterval(refreshQuotes,500);setInterval(render,100);
  setInterval(refreshIndicators,1000);
  render();refresh();refreshQuotes();refreshIndicators();
})();
