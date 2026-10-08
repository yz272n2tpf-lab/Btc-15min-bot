/* P3 candidate-only read-only market presentation. No native action output. */
(() => {
  'use strict';
  if(window.BTC15MarketViewOwner||window.BTC15Sync131)throw Error('BTC15_MARKET_OWNER_ALREADY_LOADED');
  const hostDocument=window.document,privateNodes=new Map();
  // Initial text and SVG copied from the pinned assembled HTML, never attached.
  const initialText={"btc15-render-fix-v4":"\n#btcPrice { color:#f3f5f7 !important; opacity:1 !important; text-shadow:none !important; }\n.chart-card > svg { opacity:1 !important; visibility:visible !important; transition:none !important; animation:none !important; }\n#finalReason {\n  min-height:4.2em !important;\n  height:4.2em !important;\n  line-height:1.4em !important;\n  overflow:hidden !important;\n  display:-webkit-box !important;\n  -webkit-line-clamp:3 !important;\n  -webkit-box-orient:vertical !important;\n}\n#finalActionSub { min-height:2.8em !important; }\n/* UI LOCK: never allow the temporary V8.1 overlay to alter the frozen layout. */\n#v81ScalpCard { display:none !important; }\n","v2-product-layout":"\n      #finalSide{font-size:clamp(1.25rem,5vw,2rem);overflow-wrap:anywhere}\n      #finalConfidence{font-size:1rem;color:var(--muted,#aab4c8)}\n      #finalAction{font-size:clamp(1.3rem,5vw,2rem);font-weight:850;overflow-wrap:anywhere}\n      .wait-mode #finalSide,.wait-mode #finalArrow{color:var(--muted,#aab4c8)}\n      .ladder-row strong,.pos strong,.flow-status{min-width:0;overflow-wrap:anywhere}\n      #v2QuoteClock{font-size:.8rem;overflow-wrap:anywhere;color:var(--muted,#aab4c8)}\n      #upOdds,#downOdds{font-size:clamp(1.1rem,4vw,2rem);overflow-wrap:anywhere}\n      #flipRisk{color:var(--muted,#aab4c8);font-size:clamp(1.1rem,4vw,2rem);overflow-wrap:anywhere}\n      /* The frozen desktop columns need >1000px; phone reflow ends at 700px. */\n      .odds{grid-template-columns:auto minmax(0,1fr)}\n      .odds .kalshi-condition{grid-column:1/-1;white-space:normal;overflow-wrap:anywhere}\n      @media (min-width:701px) and (max-width:1100px){\n        .primary-grid{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:auto auto auto}\n        .primary-grid>*{min-width:0}\n        .right-stack{grid-column:1/-1;grid-row:2;grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:auto;align-items:start}\n        .right-stack>*{min-width:0}\n        .chart-card{grid-row:3}\n        .odds-grid{grid-template-columns:1fr}\n        .secondary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}\n        .market-card{grid-column:1/-1}\n      }\n    ","liveDate":"—","liveTime":"—","liveStatus":"WAIT / REFRESHING","nextContract":"Next contract: —","currentContract":"WAIT / REFRESHING","finalCard":"\n        ","finalArrow":"—","finalSide":"WAIT / REFRESHING","finalConfidence":"WAIT / REFRESHING","finalAction":"WAIT / REFRESHING","finalActionSub":"WAIT / REFRESHING","finalReason":"WAIT / REFRESHING","finalBuyZone":"WAIT / REFRESHING","finalHoldZone":"WAIT / REFRESHING","finalWatchZone":"WAIT / REFRESHING","finalProtectZone":"WAIT / REFRESHING","finalExitZone":"WAIT / REFRESHING","upOdds":"WAIT / REFRESHING","upCondition":"WAIT / REFRESHING","downOdds":"WAIT / REFRESHING","downCondition":"WAIT / REFRESHING","earlyTitle":"WAIT / REFRESHING","earlyState":"WAIT / REFRESHING","earlyEntry":"WAIT / REFRESHING","earlyAfterEntry":"WAIT / REFRESHING","earlyYourEntry":"WAIT / REFRESHING","earlyCurrentPrice":"WAIT / REFRESHING","earlyEdge":"WAIT / REFRESHING","earlyLadderEntry":"WAIT / REFRESHING","earlyLadderHold":"WAIT / REFRESHING","earlyLadderWatch":"WAIT / REFRESHING","earlyLadderProtect":"WAIT / REFRESHING","earlyLadderExit":"WAIT / REFRESHING","earlyFlow":"WAIT / REFRESHING","btcPrice":"—","btcGap":"—","chartBtcPath":"\n        ","chartTargetPath":"\n      ","timerRemaining":"—","timerEnd":"—","scalpCard":"\n        ","scalpActive":"\n          ","scalpArrow":"—","scalpTitle":"WAIT / REFRESHING","scalpEntry":"WAIT / REFRESHING","scalpState":"WAIT / REFRESHING","scalpYourEntry":"WAIT / REFRESHING","scalpCurrentPrice":"WAIT / REFRESHING","scalpTargetStrip":"WAIT / REFRESHING","scalpLadderEntry":"WAIT / REFRESHING","scalpLadderHold":"WAIT / REFRESHING","scalpLadderWatch":"WAIT / REFRESHING","scalpLadderProtect":"WAIT / REFRESHING","scalpLadderExit":"WAIT / REFRESHING","scalpFlow":"WAIT / REFRESHING","oppositeArrow":"—","oppositeTitle":"WAIT / REFRESHING","oppositeEntry":"WAIT / REFRESHING","oppositeState":"WAIT / REFRESHING","signalStrength":"—","evidenceSub":"FINAL gate checks","evidenceScore":"— / 7","flipRisk":"WAIT / REFRESHING","flipRiskSub":"WAIT / REFRESHING","momentumBadge":"—","momentumSub":"Live directional pressure","contextTrend":"—","contextRange":"—","contextBrti":"—","contextLevels":"—","contextBanner":"WAIT / REFRESHING","parityFooter":"PARITY: —","btc15-information-panel":"\n  ","btc15-information-status":"WAIT — information refresh pending","btc15-information-assessment":"WAIT — information refresh pending","v2QuoteClock":"WAIT — timestamped quote refresh pending"};
  const template=hostDocument.createElement('template');template.innerHTML="<svg viewBox=\"0 0 900 340\" class=\"static-chart\" preserveAspectRatio=\"none\">\n        <g>\n          <line x1=\"112.5\" y1=\"0\" x2=\"112.5\" y2=\"340\" class=\"gridline\"/><line x1=\"225\" y1=\"0\" x2=\"225\" y2=\"340\" class=\"gridline\"/><line x1=\"337.5\" y1=\"0\" x2=\"337.5\" y2=\"340\" class=\"gridline\"/><line x1=\"450\" y1=\"0\" x2=\"450\" y2=\"340\" class=\"gridline\"/><line x1=\"562.5\" y1=\"0\" x2=\"562.5\" y2=\"340\" class=\"gridline\"/><line x1=\"675\" y1=\"0\" x2=\"675\" y2=\"340\" class=\"gridline\"/><line x1=\"787.5\" y1=\"0\" x2=\"787.5\" y2=\"340\" class=\"gridline\"/>\n          <line x1=\"0\" y1=\"68\" x2=\"900\" y2=\"68\" class=\"gridline\"/><line x1=\"0\" y1=\"136\" x2=\"900\" y2=\"136\" class=\"gridline\"/><line x1=\"0\" y1=\"204\" x2=\"900\" y2=\"204\" class=\"gridline\"/><line x1=\"0\" y1=\"272\" x2=\"900\" y2=\"272\" class=\"gridline\"/>\n        </g>\n        <polyline id=\"chartBtcPath\" points=\"\" fill=\"none\" stroke=\"#2e78ff\" stroke-width=\"2.2\"/>\n        <polyline id=\"chartTargetPath\" points=\"\" fill=\"none\" stroke=\"#f6a63d\" stroke-width=\"1.8\"/>\n      </svg>";
  const chart=template.content.firstElementChild;
  const note=hostDocument.createElement('span');note.textContent='(sampled reference · 15m contract)';
  const ring=hostDocument.createElement('div'),fill=hostDocument.createElement('div');
  const bars=Array.from({length:6},()=>hostDocument.createElement('i'));
  const surface=()=>hostDocument.getElementById('chart-surface')||hostDocument.querySelector('.chart-card > svg');
  Object.defineProperties(chart,{clientWidth:{get:()=>surface()?.clientWidth||0},clientHeight:{get:()=>surface()?.clientHeight||0}});
  chart.getBoundingClientRect=()=>surface()?.getBoundingClientRect()||{left:0,top:0,width:900,height:150};
  function privateNode(id){if(!privateNodes.has(id)){const n=hostDocument.createElement('span');n.textContent=initialText[id]||'';privateNodes.set(id,n);}return privateNodes.get(id);}
  const document=Object.freeze({
    get visibilityState(){return hostDocument.visibilityState;},
    getElementById:privateNode,
    querySelector:selector=>({'.chart-card > svg':chart,'.chart-head > div:first-child span':note,'.timer-ring':ring,'.evidence-fill':fill})[selector]||null,
    querySelectorAll:selector=>selector==='.signal-bars i'?bars:[],
    createElementNS:hostDocument.createElementNS.bind(hostDocument),
    addEventListener:hostDocument.addEventListener.bind(hostDocument)
  });
  const listeners=new Set();let resolved=null;
  function freeze(value){if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;}
  function publish(value){resolved=freeze(structuredClone(value));for(const fn of listeners){try{fn(resolved);}catch(error){console.error('BTC15 market display subscriber failed',error);}}}
  Object.defineProperty(window,'BTC15MarketViewOwner',{value:Object.freeze({
    getResolvedView:()=>resolved,
    // New resolutions only: an inspection snapshot is not a renewed source.
    subscribe(fn){if(typeof fn!=='function')throw TypeError('Display listener required');listeners.add(fn);return ()=>listeners.delete(fn);}
  })});
// P3_SOURCE_BEGIN

/* Display-only synchronization. No trading or order logic. */
(function(root) {
  'use strict';
  function finite(v) {
    if ((typeof v !== 'number' && typeof v !== 'string') || (typeof v === 'string' && !v.trim())) return NaN;
    const n = Number(v);
    return Number.isFinite(n) ? n : NaN;
  }
  function timestamp(v) {
    if (typeof v !== 'string' || !v.trim()) return NaN;
    return Date.parse(v);
  }
  class SnapshotClock {
    constructor() {
      this.contract = null; this.sourceMs = -Infinity; this.closeMs = NaN;
      this.generatedMs = -Infinity; this.serverBaseMs = NaN; this.monoBaseMs = NaN;
      this.rejectReason = ''; this.uncertaintyMs = NaN;
    }
    accept(d, sentMono, receivedMono) {
      const gen = timestamp(d.generated_utc);
      const source = timestamp(d.source_timestamp_utc);
      const close = timestamp(d.timer && d.timer.close_utc);
      const contract = typeof d.contract === 'string' ? d.contract : '';
      const rtt = receivedMono - sentMono;
      this.rejectReason = '';
      if (!contract || ![gen, source, close, rtt].every(Number.isFinite) || rtt < 0 || rtt > 10000) {
        this.rejectReason = 'Missing or invalid timing data'; return false;
      }
      if (source > gen + 1000 || close < source || close - source > 901000) {
        this.rejectReason = 'Inconsistent source clock'; return false;
      }
      if (gen === this.generatedMs && (source !== this.sourceMs || contract !== this.contract)) {
        this.rejectReason = 'Inconsistent cached snapshot'; return false;
      }
      if (gen < this.generatedMs || source < this.sourceMs) {
        this.rejectReason = 'Older snapshot rejected'; return false;
      }
      if (this.contract && contract !== this.contract && (close <= this.closeMs || source <= this.sourceMs)) {
        this.rejectReason = 'Old contract rejected'; return false;
      }
      if (contract === this.contract && Math.abs(close - this.closeMs) > 1000) {
        this.rejectReason = 'Contract deadline changed unexpectedly'; return false;
      }
      if (contract !== this.contract) this.closeMs = Math.round(close / 1000) * 1000;
      this.contract = contract; this.sourceMs = source;
      if (gen === this.generatedMs) return true; // Cached JSON must not restart the clock.
      this.generatedMs = gen;
      // Server wall time plus an estimated one-way network transit time. The
      // estimate can be imperfect; it does not accumulate per refresh.
      this.serverBaseMs = gen + rtt / 2;
      this.monoBaseMs = receivedMono; this.uncertaintyMs = rtt / 2;
      return true;
    }
    now(mono) { return this.serverBaseMs + Math.max(0, mono - this.monoBaseMs); }
    left(mono) { return Math.max(0, (this.closeMs - this.now(mono)) / 1000); }
    age(mono) { return (this.now(mono) - this.sourceMs) / 1000; }
    fresh(mono) { const a = this.age(mono); return Number.isFinite(a) && a >= 0 && a <= 15 && this.left(mono) > 0; }
  }
  root.BTC15Sync131 = {finite, timestamp, SnapshotClock};
})(typeof globalThis !== 'undefined' ? globalThis : this);


(() => {
  const N = BTC15Sync131.finite;
  const clock = new BTC15Sync131.SnapshotClock();
  let latestState = null, networkHealthy = false, timerHandle = null, pollActive = false;
  let viewEpoch=0, activeAbort=null, requireNewGeneration=false, clockTrusted=false;
  const retiredActionIds=new Set(["contextBanner", "currentContract", "downCondition", "downOdds", "earlyAfterEntry", "earlyCurrentPrice", "earlyEdge", "earlyEntry", "earlyFlow", "earlyLadderEntry", "earlyLadderExit", "earlyLadderHold", "earlyLadderProtect", "earlyLadderWatch", "earlyState", "earlyTitle", "earlyYourEntry", "finalAction", "finalActionSub", "finalArrow", "finalBuyZone", "finalCard", "finalConfidence", "finalExitZone", "finalHoldZone", "finalProtectZone", "finalReason", "finalSide", "finalWatchZone", "flipRisk", "flipRiskSub", "liveStatus", "oppositeArrow", "oppositeEntry", "oppositeState", "oppositeTitle", "scalpActive", "scalpArrow", "scalpCard", "scalpCurrentPrice", "scalpEntry", "scalpFlow", "scalpLadderEntry", "scalpLadderExit", "scalpLadderHold", "scalpLadderProtect", "scalpLadderWatch", "scalpState", "scalpTargetStrip", "scalpTitle", "scalpYourEntry", "signalStrength", "upCondition", "upOdds"]);
  const retiredNodes=new Map();
  const $ = (id) => { if(!retiredActionIds.has(id))return document.getElementById(id); if(!retiredNodes.has(id)){const n=document.getElementById(id);retiredNodes.set(id,n?n.cloneNode(true):null);}return retiredNodes.get(id); };
  const fmtPct = (v, d=0) => Number.isFinite(v) ? `${(v*100).toFixed(d)}%` : '—';
  const fmtC = (v, d=1) => Number.isFinite(v) ? `${(v*100).toFixed(d)}¢` : '—';
  const fmtDollar = (v, d=2) => Number.isFinite(v) ? `$${N(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d})}` : '—';
  const fmtSignedDollar = (v) => Number.isFinite(v) ? `${v>=0?'+':'−'}$${Math.abs(v).toFixed(2)}` : '—';
  const safe = (v, fallback='—') => (v === null || v === undefined || v === '') ? fallback : String(v);
  const etDate = (d) => new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',month:'short',day:'numeric',year:'numeric'}).format(d);
  const etTime = (d) => new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true}).format(d) + ' ET';
  const mmss = (seconds) => {
    if (!Number.isFinite(seconds)) return '—';
    seconds=Math.max(0,Math.round(seconds));
    const m=Math.floor(seconds/60), s=seconds%60;
    return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  };
  const lowerIds=new Set(['evidenceScore','momentumBadge','momentumSub','contextTrend','contextRange','contextBrti','contextLevels']);
  const lowerFallback=new Map([
    ['evidenceScore','Evidence score pending first qualified sample'],
    ['momentumBadge','Momentum sample pending'],
    ['momentumSub','BRTI momentum sample pending'],
    ['contextTrend','Trend sample pending'],
    ['contextRange','Range sample pending'],
    ['contextBrti','BRTI context sample pending'],
    ['contextLevels','Target / BTC levels pending']
  ]);
  const lowerHistory=new Map(); let lowerQualified=false,lowerContract=null;
  const setText = (id, value) => {
    if(lowerIds.has(id)){
      const valid=lowerQualified && !/unavailable|not connected|fresh brti required|refreshing|stale|^—(?: \/ 7)?$/i.test(String(value));
      if(valid)lowerHistory.set(id,{value,contract:lowerContract});
      else {
        const prior=lowerHistory.get(id);
        value=prior&&(!lowerContract||prior.contract===lowerContract)?prior.value:lowerFallback.get(id);
      }
    }
    const el=$(id); if(el && el.textContent!==value) el.textContent=value;
  };
  const setStatePill = (id, text, kind='watch') => {
    const el=$(id); if(!el) return; el.textContent=text; el.classList.remove('state-good','state-watch');
    if(kind==='good') el.classList.add('state-good'); else el.classList.add('state-watch');
  };
  const setFlow = (id, text, kind='warn') => {
    const el=$(id); if(!el) return; el.textContent=text; el.classList.remove('good','warn','exit'); el.classList.add(kind);
  };
  const setCond = (id, text, kind='watch') => {
    const el=$(id); if(!el) return; el.textContent=text; el.classList.remove('cond-good','cond-watch','cond-bad'); el.classList.add(`cond-${kind}`);
  };

  // Display-only history: never fed back into a price, timing, or signal gate.
  let lastBrtiDisplay=null;
  let lastChartSignature=null,lastChartContract=null,chartRefreshing=false;
  function retainBrtiDisplay(d){
    // Previous-contract BRTI may remain explicitly historical information.
    const m=d.market||{}, value=N(m.brti_value), rawAge=N(m.brti_age_seconds);
    const source=Date.parse(d.source_timestamp_utc), target=N(m.target);
    if(d.safety?.read_only!==true || d.safety?.orders_enabled!==false || d.health?.paired_quotes!==true)return;
    if(m.brti_ready!==true || !Number.isFinite(value) || value<=0 || !Number.isFinite(rawAge) || rawAge<0 || !Number.isFinite(source))return;
    const observed=source-rawAge*1000;
    // Duplicate/older samples cannot refresh the age or replace newer history.
    if(lastBrtiDisplay && observed<=lastBrtiDisplay.observed)return;
    lastBrtiDisplay={contract:d.contract,value,target,observed};
  }
  function renderBrtiDisplay(d,forcedUnavailable=false){
    const price=$('btcPrice'), gap=$('btcGap');
    const note=document.querySelector('.chart-head > div:first-child span');
    const chart=document.querySelector('.chart-card > svg');
    const record=lastBrtiDisplay;
    const m=d?.market||{};
    const observed=Date.parse(d?.source_timestamp_utc)-N(m.brti_age_seconds)*1000;
    const sameSample=record && record.contract===d?.contract && Number.isFinite(observed) && Math.abs(observed-record.observed)<0.001 && N(m.brti_value)===record.value;
    const sourceFresh=networkHealthy && clockTrusted && clock.fresh(performance.now()) && d?.health?.paired_quotes===true;
    const current=Boolean(!forcedUnavailable && sourceFresh && sameSample && freshBrti(d));
    const age=record && clockTrusted?(clock.now(performance.now())-record.observed)/1000:NaN;
    const ageLabel=Number.isFinite(age)&&age>=0?`${age.toFixed(1)}s old`:'age pending resync';
    setText('btcPrice',record?fmtDollar(record.value):'REFRESHING');
    setText('btcGap',record && Number.isFinite(record.target)?fmtSignedDollar(record.value-record.target):'REFRESHING');
    if(price){
      price.dataset.priceState=record?(current?'fresh':'last-received'):'unavailable';
      price.style.color=record&&!current?'var(--yellow)':'';
      price.title=record?`Last received BRTI · ${etTime(new Date(record.observed))}. ${current?'Fresh sample, not a native-app parity guarantee.':'Historical display only; not current signal input.'}`:'BRTI refresh pending; Coinbase is not substituted.';
    }
    if(gap){gap.style.color=record&&!current?'var(--yellow)':'';gap.title=record?'Gap at last received BRTI sample':'BRTI refresh pending';}
    let label='WAIT — BRTI refresh pending';
    if(record){
      const ended=clockTrusted && clock.left(performance.now())===0;
      label=current?`BRTI · ${ageLabel}`:!clockTrusted?`LAST QUALIFIED BRTI / REFRESHING · resyncing`:ended?`ENDED · LAST QUALIFIED BRTI / REFRESHING · ${ageLabel}`:!networkHealthy?`OFFLINE · LAST QUALIFIED BRTI / REFRESHING · ${ageLabel}`:`STALE · LAST QUALIFIED BRTI / REFRESHING · ${ageLabel}`;
    }
    if(record && record.contract!==d?.contract)label+=' · '+record.contract;
    if(chartRefreshing)label+=' · Chart LAST QUALIFIED / REFRESHING';
    if(note && note.textContent!==label)note.textContent=label;
    if(chart){chart.style.opacity='1';chart.dataset.stale=current?'false':'true';}
   if(gap){const _gt=(gap.textContent||'').trim();const _neg=/[-\u2212]/.test(_gt);const _hasNum=/\d/.test(_gt);gap.style.setProperty('color',_neg?'#ff4d67':(_hasNum?'#35d07f':'#f3f5f7'),'important');}}

  // P3_BEGIN_MARKET_INTERFACE
  function publishMarket(){
    const ids=['liveDate','liveTime','timerRemaining','timerEnd','nextContract','btcPrice','btcGap','evidenceScore','momentumBadge','momentumSub','contextTrend','contextRange','contextBrti','contextLevels','parityFooter'];
    publish({
      schema:'BTC15_COCKPIT_MARKET_DISPLAY_R1',authority:'DISPLAY_ONLY',signal_only:true,orders:false,
      resolved_monotonic:performance.now(),view_epoch:viewEpoch,visibility:document.visibilityState,
      contract:latestState?.contract??null,
      source:latestState?{contract:latestState.contract,generated_utc:latestState.generated_utc,source_timestamp_utc:latestState.source_timestamp_utc,timer:latestState.timer,target:latestState.market?.target}:null,
      clock:{...clock},network_healthy:networkHealthy,clock_trusted:clockTrusted,require_new_generation:requireNewGeneration,poll_active:pollActive,
      reason:$('liveStatus')?.textContent??null,
      values:Object.fromEntries(ids.map(id=>[id,$(id)?.textContent??null])),
      brti:{record:lastBrtiDisplay,unit:'USD',observed_unit:'epoch_milliseconds',price_state:$('btcPrice')?.dataset.priceState??null,title:$('btcPrice')?.title??'',label:note.textContent},
      chart:{contract:lastChartContract,refreshing:chartRefreshing,signature:lastChartSignature,stale:chart.dataset.stale??null,svg:chart.outerHTML,timeframe_minutes:15},
      lower:{qualified:lowerQualified,contract:lowerContract,history:Object.fromEntries(lowerHistory),evidence_fill:fill.style.width}
    });
  }
  // P3_END_MARKET_INTERFACE
  function currentBrtiAge(d) {
    return N(d.market?.brti_age_seconds) + clock.age(performance.now());
  }
  function freshBrti(d) {
    const age=currentBrtiAge(d);
    return d.market?.brti_ready===true && Number.isFinite(N(d.market?.brti_value)) && Number.isFinite(age) && age>=0 && age<=5;
  }
  function usableFrame(d) {
    const parityAge = (clock.now(performance.now()) - Date.parse(d.parity?.timestamp_utc || ''))/1000;
    return networkHealthy && clockTrusted && clock.fresh(performance.now()) && d.health?.paired_quotes === true
      && d.safety?.read_only===true && d.safety?.orders_enabled===false
      && d.parity?.contract===d.contract && d.parity?.api_contract===d.contract
      && d.parity?.status === 'PASS' && Number.isFinite(parityAge) && parityAge >= 0 && parityAge <= 45;
  }
  function markUnavailable(reason) {
    lowerQualified=false;
    const el=$('liveStatus');
    if(el){el.textContent=reason;el.classList.remove('live-ok','live-warn');el.classList.add('live-stale');}
    const action=$('finalAction');
    if(action){action.textContent='WAIT';action.classList.remove('action-hold','action-protect','action-exit');action.classList.add('action-watch');}
    setText('finalSide','WAIT');setText('finalArrow','·');
    setText('finalActionSub','Diagnostic display · fresh data required');setText('finalReason',reason);
    for(const id of ['upOdds','downOdds','earlyCurrentPrice','earlyEdge','scalpCurrentPrice','finalConfidence','scalpTargetStrip','contextRange','contextLevels','flipRisk'])setText(id,'—');
    setCond('upCondition','WAIT');setCond('downCondition','WAIT');
    setStatePill('earlyState','WAIT');setStatePill('scalpState','WAIT');
    setText('earlyTitle','Waiting for fresh data');setText('scalpEntry','Waiting for fresh data');
    setText('earlyAfterEntry','Position not linked');setText('earlyEntry','Unavailable until source is fresh');
    setText('earlyLadderEntry','Unavailable until source is fresh');setText('earlyLadderHold','No live guidance while unavailable');
    setText('scalpLadderEntry','Unavailable until source is fresh');setText('scalpLadderHold','No live guidance while unavailable');
    for(const id of ['finalBuyZone','finalHoldZone','finalWatchZone','earlyLadderWatch','scalpLadderWatch'])setText(id,'Unavailable');
    setText('signalStrength','NOT CONNECTED');setText('evidenceScore','— / 7');
    setText('momentumBadge','UNAVAILABLE');setText('momentumSub','Fresh BRTI required');
    setText('contextTrend','Unavailable');setText('contextBrti','Unavailable');
    setText('contextBanner','Live market context unavailable.');setText('flipRiskSub','Probability not connected');
    setText('parityFooter','PARITY: NOT CURRENTLY VERIFIED');
    setText('oppositeState','NOT CONNECTED');
    setFlow('earlyFlow',reason,'warn');setFlow('scalpFlow',reason,'warn');
    // Retain the labeled last-qualified informational bar during refresh.
    const chart=document.querySelector('.chart-card > svg');if(chart){chart.style.opacity='1';chart.dataset.stale='true';}
    renderBrtiDisplay(latestState,true);
  }
  function liveCountdown(){
    const serverNow=clock.now(performance.now());
    const now=Number.isFinite(serverNow)?new Date(serverNow):new Date();
    setText('liveDate', etDate(now)); setText('liveTime', etTime(now));
    const left=clockTrusted?clock.left(performance.now()):NaN;
    setText('timerRemaining', mmss(left));
    setText('nextContract',Number.isFinite(left)?(left>0?`Contract ends in ${mmss(left)}`:'Awaiting next contract'):'Clock not synchronized');
    setText('timerEnd',clockTrusted && Number.isFinite(clock.closeMs)?etTime(new Date(clock.closeMs)):'Resynchronizing');
    const ring=document.querySelector('.timer-ring');
    if(ring && Number.isFinite(left)){
      const angle=Math.max(0,Math.min(360,left/900*360));
      ring.style.background=`radial-gradient(circle at center,#071522 52%,transparent 53%),conic-gradient(var(--green) 0deg ${angle}deg,#1b2d41 ${angle}deg 360deg)`;
    }
    if(latestState){
      if(!networkHealthy) markUnavailable('● RESYNCING / OFFLINE');
      else if(!clockTrusted) markUnavailable('● CLOCK NOT SYNCHRONIZED');
      else if(!clock.fresh(performance.now())) markUnavailable(left===0?'● CONTRACT ENDED · WAIT':'● STALE SOURCE · WAIT');
      else applyState(latestState,false);
    }
    /* P3_HOOK */publishMarket();/* P3_END_HOOK */
  }

  function renderMainChart(d){
    const svg=document.querySelector('.chart-card > svg'); if(!svg)return;
    const pts=(d.chart?.points||[]).map(p=>({t:Date.parse(p.t),v:N(p.brti),age:N(p.brti_age_sec)}))
      .filter(p=>Number.isFinite(p.t)&&Number.isFinite(p.v)&&Number.isFinite(p.age)&&p.age>=0&&p.age<=5)
      .sort((a,b)=>a.t-b.t);
    const w=Math.max(320,svg.clientWidth||900), h=Math.max(120,svg.clientHeight||150);
    const signature=JSON.stringify([d.contract,w,h,N(d.market?.target),pts]);
    chartRefreshing=!pts.length;
    if(chartRefreshing && lastChartContract===d.contract && svg.querySelector('path'))return;
    lastChartContract=d.contract;
    if(signature===lastChartSignature)return; // Do not rebuild identical history.
    lastChartSignature=signature;
    const oldChartNodes=Array.from(svg.childNodes);svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
    svg.setAttribute('aria-label','Sampled BRTI reference history with actual timestamps and contract target. Not a candle or forecast chart.');
    const ns='http://www.w3.org/2000/svg';
    function add(tag,attrs,text){const el=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));if(text!==undefined)el.textContent=text;svg.appendChild(el);return el;}
    if(!pts.length){add('text',{x:12,y:28,fill:'#9eafbf','font-size':12},'WAIT — BRTI history refresh pending');oldChartNodes.forEach(n=>n.remove());return;}
    const left=10,right=w-89,top=12,bottom=h-25;
    const target=N(d.market?.target), vals=pts.map(p=>p.v);
    if(Number.isFinite(target))vals.push(target);
    let low=Math.min(...vals),high=Math.max(...vals),span=Math.max(high-low,1);low-=span*.12;high+=span*.12;
    const end=clock.closeMs,begin=end-900000;
    const x=t=>left+(right-left)*(t-begin)/(end-begin);
    const y=v=>bottom-(bottom-top)*(v-low)/(high-low);
    for(let i=0;i<4;i++){
      const value=low+(high-low)*i/3,py=y(value);
      add('line',{x1:left,x2:right,y1:py,y2:py,stroke:'#173043','stroke-width':1});
      add('text',{x:right+5,y:py+4,fill:'#9eafbf','font-size':10,'font-family':'system-ui'},value.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}));
    }
    for(let i=0;i<4;i++){
      const t=begin+i*300000,px=x(t);
      add('line',{x1:px,x2:px,y1:top,y2:bottom,stroke:'#173043','stroke-width':1});
      const time=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(t));
      add('text',{x:px,y:h-7,fill:'#9eafbf','font-size':10,'text-anchor':i===0?'start':i===3?'end':'middle'},time);
    }
    if(Number.isFinite(target)){
      const py=y(target);add('line',{x1:left,x2:right,y1:py,y2:py,stroke:'#f6a63d','stroke-width':1,'stroke-dasharray':'4 4'});
      add('text',{x:left+5,y:Math.max(top+10,py-4),fill:'#f6a63d','font-size':10},`TARGET ${target.toFixed(2)}`);
    }
    let path='',previous=null;
    for(const p of pts){if(p.t<begin||p.t>end)continue;
      path+=`${!previous||p.t-previous.t>15000?'M':'L'}${x(p.t).toFixed(2)},${y(p.v).toFixed(2)} `;previous=p;}
    add('path',{d:path,fill:'none',stroke:'#4b91ff','stroke-width':1.7,'stroke-linejoin':'round','stroke-linecap':'round','vector-effect':'non-scaling-stroke'});
    if(previous)add('circle',{cx:x(previous.t),cy:y(previous.v),r:2.5,fill:'#4b91ff'});
    const cross=add('line',{x1:0,x2:0,y1:top,y2:bottom,stroke:'#7e93a7','stroke-width':1,'stroke-dasharray':'3 3',visibility:'hidden'});
    const tip=add('text',{x:left+4,y:top+10,fill:'#edf5ff','font-size':11,visibility:'hidden'});
    oldChartNodes.forEach(n=>n.remove());svg.onpointermove=event=>{const rect=svg.getBoundingClientRect();const px=(event.clientX-rect.left)/rect.width*w;const t=begin+(px-left)/(right-left)*(end-begin);
      let best=pts[0];for(const p of pts){if(Math.abs(p.t-t)<Math.abs(best.t-t))best=p;}
      cross.setAttribute('x1',x(best.t));cross.setAttribute('x2',x(best.t));cross.setAttribute('visibility','visible');
      tip.textContent=`BRTI ${fmtDollar(best.v)} · ${etTime(new Date(best.t))} · sampled`;
      tip.setAttribute('visibility','visible');};
    svg.onpointerleave=()=>{cross.setAttribute('visibility','hidden');tip.setAttribute('visibility','hidden');};
  }

  function applyState(d,drawChart=true){
    const usable=usableFrame(d);
    lowerQualified=usable && freshBrti(d);lowerContract=d.contract;
    // Keep raw qualification diagnostics but never present stale data as action.
    d={...d,final:{...d.final,ready:usable && freshBrti(d) && d.final?.ready===true},
      early:{...d.early,ready:usable && d.early?.ready===true},
      scalp:{...d.scalp,ready:usable && d.scalp?.ready===true}};
    const status=$('liveStatus');
    if(status){
      status.classList.remove('live-ok','live-warn','live-stale');
      status.textContent=usable?(freshBrti(d)?'● DATA FRESH · DIAGNOSTIC':'● BRTI STALE · WAIT'):'● PARITY / DATA CHECK';
      status.classList.add(usable && freshBrti(d)?'live-ok':'live-warn');
    }
    setText('currentContract',d.contract?`BTC 15-MINUTE · ${d.contract} · V2`:'WAITING FOR CONTRACT');

    const m=d.market||{}, f=d.final||{}, e=d.early||{}, sc=d.scalp||{};
    if(drawChart)renderMainChart(d);
    // The readout below labels BRTI age separately from quote/source age.
    const pref=(f.side||m.preferred_side||'').toUpperCase();
    const conf=N(f.confidence);
    const finalCard=$('finalCard');
    if(finalCard){
      finalCard.classList.remove('down-mode','wait-mode');
      if(pref==='DOWN') finalCard.classList.add('down-mode');
      if(!pref) finalCard.classList.add('wait-mode');
    }
    setText('finalArrow',pref==='DOWN'?'↓':pref==='UP'?'↑':'·');
    setText('finalSide',pref||'WAIT');
    setText('finalConfidence',fmtPct(conf,1));
    const finalAction=$('finalAction');
    if(finalAction){
      finalAction.classList.remove('action-hold','action-watch','action-protect','action-exit');
      if(f.ready){finalAction.textContent='QUALIFIED';finalAction.classList.add('action-hold');}
      else{finalAction.textContent=usable && freshBrti(d)?'WATCH':'WAIT';finalAction.classList.add('action-watch');}
    }
    setText('finalActionSub',f.ready?`${pref} FINAL qualified · ${fmtPct(conf,1)}`:(Number.isFinite(conf)&&conf>=0.90?`${pref} probability ${fmtPct(conf,1)} · FINAL gate still pending`:`Continuous ${pref||'direction'} probability · FINAL not qualified`));
    const unmet=[];
    if(!usable)unmet.push('current same-contract parity');
    if(!freshBrti(d))unmet.push('fresh BRTI');
    const c=f.conditions||{};
    if(!c.minutes_left_lte_8) unmet.push('time'); if(!c.fair_gte_90) unmet.push('90% fair'); if(!c.gap_ok) unmet.push('gap');
    if(!c.dist_over_range5_gte_1) unmet.push('distance/range'); if(!c.preferred_matches_target) unmet.push('target match'); if(!c.direct_brti_authority_ready) unmet.push('direct BRTI'); if(!c.preferred_matches_brti) unmet.push('BRTI agreement');
    setText('finalReason',f.ready?'Reason: Frozen FINAL gate is qualified. Protection remains shadow-only.':`Reason: Waiting on ${unmet.join(' · ')||'FINAL gate'}.`);
    setText('finalBuyZone', e.ready ? `EARLY active · ${fmtC(e.ask)}` : sc.ready ? `SCALP active · ${fmtC(sc.ask)}` : 'No entry signal');
    setText('finalHoldZone', f.ready ? `${pref} FINAL qualified · not a position` : 'Waiting for FINAL gate');
    setText('finalWatchZone',`Reversal: ${safe(m.reversal_state,'WARMING')}`);
    setText('finalProtectZone','Shadow validation in progress');
    setText('finalExitZone','No validated FINAL exit rule yet');

    const upAsk=N(m.up_ask), downAsk=N(m.down_ask);
    setText('upOdds',fmtPct(upAsk,1)); setText('downOdds',fmtPct(downAsk,1));
    setCond('upCondition','ASK','watch');
    setCond('downCondition','ASK','watch');

    const earlySide=(e.side||pref||'').toUpperCase();
    setText('earlyTitle',e.ready?`Potential ${earlySide} Entry`:`Watching ${earlySide||'market'} Entry`);
    setStatePill('earlyState',e.ready?'GOOD':'WATCHING',e.ready?'good':'watch');
    setText('earlyEntry',e.ready?`≤45¢ · now ${fmtC(N(e.ask))}`:`Wait · now ${fmtC(N(e.ask))}`);
    setText('earlyAfterEntry','Position not linked · signal only');
    setText('earlyCurrentPrice',fmtC(N(e.ask)));
    setText('earlyEdge',Number.isFinite(N(e.edge))?`${(N(e.edge)*100).toFixed(1)}¢`:'—');
    setText('earlyLadderEntry',`≤45¢ · now ${fmtC(N(e.ask))}`);
    setText('earlyLadderHold',e.ready?'Frozen Tier-1 remains qualified':'No Tier-1 entry yet');
    setText('earlyLadderWatch',`Reversal: ${safe(m.reversal_state,'WARMING')}`);
    setText('earlyLadderProtect','Protection policy pending validation');
    setText('earlyLadderExit','No validated Tier-1 exit rule yet');
    setFlow('earlyFlow',e.ready?`${earlySide} Tier-1 gate QUALIFIES · position not linked`:'Watching frozen Tier-1 gate',e.ready?'good':'warn');

    const brtiAge=currentBrtiAge(d);
    renderBrtiDisplay(d);

    const scalpSide=(sc.side||pref||'').toUpperCase();
    const scalpOpp=scalpSide==='UP'?'DOWN':scalpSide==='DOWN'?'UP':'DOWN';
    setText('scalpArrow',scalpSide==='DOWN'?'↓':'↑');
    setText('scalpTitle',`SCALP ${scalpSide||'—'}`);
    setText('scalpEntry',sc.ready?`Now ${fmtC(N(sc.ask))} · max 70¢`:'Waiting for frozen gate');
    setStatePill('scalpState',sc.ready?'QUALIFIES':'WATCHING',sc.ready?'good':'watch');
    setText('scalpCurrentPrice',fmtC(N(sc.bid)));
    setText('scalpTargetStrip','—');
    setText('scalpLadderEntry',`Ask ≤70¢ · now ${fmtC(N(sc.ask))}`);
    setText('scalpLadderHold',`Up to ${safe(sc.horizon_minutes,5)}m horizon`);
    setText('scalpLadderWatch',`Reversal: ${safe(m.reversal_state,'WARMING')}`);
    setText('scalpLadderProtect','Position not linked');
    setText('scalpLadderExit','Position not linked');
    setFlow('scalpFlow',sc.ready?`${scalpSide} strong-scalp gate QUALIFIES · diagnostic only`:'Watching frozen strong-scalp gate',sc.ready?'good':'warn'); if(typeof renderV81ScalpInline==='function')renderV81ScalpInline(d);
    setText('oppositeArrow',scalpOpp==='DOWN'?'↓':'↑');
    setText('oppositeTitle',`SCALP ${scalpOpp}`);
    setText('oppositeEntry','Separate opposite-side setup');
    setText('oppositeState','NOT CONNECTED');

    const q=[c.minutes_left_lte_8,c.fair_gte_90,c.gap_ok,c.dist_over_range5_gte_1,c.preferred_matches_target,c.direct_brti_authority_ready,c.preferred_matches_brti].filter(Boolean).length;
    const p=N(m.preferred_side?conf:e.fair);
    let strength='WARMING';
    if(Number.isFinite(p)){ strength=p>=.90?'STRONG':p>=.75?'GOOD':p>=.60?'MODERATE':'WEAK'; }
    setText('signalStrength','NOT CONNECTED');
    setText('evidenceScore',`${q} / 7`);
    const fill=document.querySelector('.evidence-fill'); if(fill)fill.style.width=`${q/7*100}%`;
    document.querySelectorAll('.signal-bars i').forEach(el=>el.style.opacity='.12');
    const rev=safe(m.reversal_state,'WARMING').toUpperCase();
    setText('flipRisk','—');
    setText('flipRiskSub',`Probability not connected · reversal ${rev}`);
    setText('momentumBadge',`${pref||'—'} · ${rev}`);
    setText('momentumSub',freshBrti(d)?`BRTI ${safe(m.brti_side,'—')} · ${brtiAge.toFixed(1)}s`:'BRTI stale / unavailable');

    setText('contextTrend',pref||'—');
    setText('contextRange',Number.isFinite(N(m.range5))?fmtDollar(N(m.range5)):'—');
    setText('contextBrti',freshBrti(d)?`${safe(m.brti_side,'—')} · ${brtiAge.toFixed(1)}s`:'STALE / UNAVAILABLE');
    setText('contextLevels',`${fmtDollar(N(m.target))} / ${fmtDollar(N(m.btc_price))} Coinbase`);
    const align=freshBrti(d) && m.brti_side===pref;
    setText('contextBanner',`${align?'BRTI aligned':'BRTI not aligned'} · ${pref||'—'} preferred · reversal ${rev}.`);
    
    setText('parityFooter',`PARITY: ${safe(d.parity?.status,'WAIT')}${d.parity?.shadow_only?' · SHADOW':''}`);
  }

  function invalidateView(){
    viewEpoch++;networkHealthy=false;clockTrusted=false;
    requireNewGeneration=Number.isFinite(clock.generatedMs);
    clearTimeout(timerHandle);if(activeAbort)activeAbort.abort();
    markUnavailable('● RESYNCING');setText('timerRemaining','—');setText('timerEnd','Resynchronizing');
    /* P3_HOOK */publishMarket();/* P3_END_HOOK */
  }
  async function refresh(){
    if(pollActive || document.visibilityState==='hidden')return;
    pollActive=true;clearTimeout(timerHandle);
    const epoch=viewEpoch, controller=new AbortController();activeAbort=controller;
    const deadline=setTimeout(()=>controller.abort(),8000);
    const sent=performance.now();
    try{
      const response=await fetch('/dashboard_state.json',{cache:'no-store',signal:controller.signal});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const d=await response.json(),received=performance.now();
      if(epoch!==viewEpoch || document.visibilityState==='hidden')throw new Error('Response from previous app view rejected');
      if(requireNewGeneration && Date.parse(d.generated_utc)<=clock.generatedMs)throw new Error('Awaiting fresh server clock');
      if(!clock.accept(d,sent,received))throw new Error(clock.rejectReason);
      requireNewGeneration=false;clockTrusted=true;networkHealthy=true;latestState=d;
      retainBrtiDisplay(d);applyState(d);liveCountdown();
    }catch(error){
      networkHealthy=false;
      if(document.visibilityState!=='hidden')markUnavailable(`● RESYNCING · ${error.name==='AbortError'?'request timeout':error.message}`);
    }finally{
      clearTimeout(deadline);pollActive=false;activeAbort=null;
      if(document.visibilityState!=='hidden')timerHandle=setTimeout(refresh,epoch!==viewEpoch?0:Math.max(1000,5000-(performance.now()-sent)));
      /* P3_HOOK */publishMarket();/* P3_END_HOOK */
    }
  }
  document.addEventListener('visibilitychange',()=>{invalidateView();if(document.visibilityState==='visible')refresh();});
  window.addEventListener('pagehide',invalidateView);
  window.addEventListener('pageshow',()=>{invalidateView();refresh();});
  window.addEventListener('resize',()=>{if(latestState && clockTrusted && Number.isFinite(clock.closeMs))renderMainChart(latestState);/* P3_HOOK */publishMarket();/* P3_END_HOOK */});
  liveCountdown();setInterval(liveCountdown,1000);refresh();

})();
// P3_SOURCE_END
})();
