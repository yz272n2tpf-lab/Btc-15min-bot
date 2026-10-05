/* Full generated HTML + ALL delivered scripts/timers. DOM integration, not physical Safari. */
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),vm=require('vm');
const {JSDOM,VirtualConsole}=require('jsdom');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'qualification/v2_product_20261004');
const fixture=JSON.parse(fs.readFileSync(path.join(out,'ui_fixture.json')));
const html=fs.readFileSync(path.join(out,'dashboard/BTC_Kalshi_App_Live_v13.html'),'utf8');
const manifest=JSON.parse(fs.readFileSync(path.join(out,'dashboard/manifest.json')));
  const clone=v=>JSON.parse(JSON.stringify(v));
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};

(async()=>{
  const errors=[],writes=[],requests=[],checks=[];
  const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));
  const dom=new JSDOM(html,{url:'https://offline.test/',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
  const w=dom.window,d=w.document;let now=0,visible=true,id=0,offline=false,pending=false;
  const deferred=[],timers=new Map(),payload=clone(fixture),owned=new Set(manifest.owned_action_ids);
  Object.defineProperty(w.performance,'now',{value:()=>now});
  Object.defineProperty(d,'visibilityState',{get:()=>visible?'visible':'hidden'});Object.defineProperty(d,'hidden',{get:()=>!visible});
  w.AbortSignal.timeout=undefined; // Supported fallback must work without this API.
  function watch(proto,key){const desc=Object.getOwnPropertyDescriptor(proto,key);if(!desc?.set)return;
    Object.defineProperty(proto,key,{...desc,set(value){if(this.isConnected&&owned.has(this.id))writes.push({id:this.id,property:key,value:String(value),stack:new Error().stack});return desc.set.call(this,value);}});}
  watch(w.Node.prototype,'textContent');watch(w.Element.prototype,'className');
  const attribute=w.Element.prototype.setAttribute;
  w.Element.prototype.setAttribute=function(k,v){if(this.isConnected&&owned.has(this.id))writes.push({id:this.id,property:k,value:String(v),stack:new Error().stack});return attribute.call(this,k,v);};
  w.setTimeout=(fn,ms=0)=>{timers.set(++id,{fn,at:now+ms,repeat:0});return id;};w.clearTimeout=n=>timers.delete(n);
  w.setInterval=(fn,ms)=>{timers.set(++id,{fn,at:now+ms,repeat:ms});return id;};w.clearInterval=w.clearTimeout;
  const iso=t=>new Date(t*1000).toISOString();
  function legacy(){const m=payload.main,i=m.official_identity||fixture.main.official_identity,t=m.served_ts;
    return {contract:i.contract,generated_utc:iso(t),source_timestamp_utc:iso(t-.1),timer:{close_utc:iso(i.official_close)},
      safety:{read_only:true,orders_enabled:false},health:{paired_quotes:true},parity:{contract:i.contract,api_contract:i.contract,status:'PASS',timestamp_utc:iso(t)},
      market:{target:i.target,btc_price:80080,brti_value:80080,brti_age_seconds:.3,brti_ready:true,brti_side:'UP',up_ask:.99,down_ask:.01,preferred_side:'UP'},
      final:{side:'UP',confidence:.999,ready:true,conditions:{}},early:{ready:true,side:'UP',ask:.99},scalp:{ready:true,side:'UP',ask:.99,bid:.98}};}
  w.fetch=async(url,opts={})=>{
    requests.push({url:String(url),signal:opts.signal});
    if(offline)throw Error('Offline fixture');
    const lane=String(url).includes('v81.test')?'scalp':url==='/ladders'?'main':url==='/ladders/quotes'?'quote':null;
    const data=lane?clone(payload[lane]):url==='/dashboard_state.json'?legacy():{status:'WAIT'};
    const result={ok:true,headers:{get:()=>null},json:async()=>data};
    if(pending&&lane)return new Promise(resolve=>deferred.push(()=>resolve(result)));
    return result;
  };
  const sources=[];
  for(const script of d.querySelectorAll('script')){
    let code,name;
    if(!script.src){code=script.textContent;name='legacy-inline.js';}
    else if(script.src.endsWith('/ladders/panel.js')){code=fs.readFileSync(path.join(root,'btc15_v2_product/panel.js'),'utf8').replace('__V81_LADDERS_URL__','"https://v81.test/ladders"');name='product-panel.js';}
    else {const file=script.src.endsWith('/information/view.js')?'btc15_information_view_v1.js':'btc15_information_panel_v1.js';code=fs.readFileSync(path.join(root,file),'utf8');name=file;}
    sources.push(name);vm.runInContext(code,dom.getInternalVMContext(),{filename:name});
  }
  await flush();
  async function advance(ms){now+=ms;const due=[...timers.entries()].filter(([,t])=>t.at<=now);for(const [n,t] of due){if(!timers.has(n))continue;if(t.repeat)t.at=now+t.repeat;else timers.delete(n);t.fn();}await flush();}
  function fresh(){for(const lane of ['main','scalp','quote']){payload[lane]=clone(fixture[lane]);for(const k of ['published_ts','served_ts','expires_at','exchange_ts','accepted_ts'])if(Number.isFinite(payload[lane][k]))payload[lane][k]+=now/1000;}}
  const txt=id=>d.getElementById(id).textContent;
  assert.equal(txt('finalAction'),'UNLOCKED / PASS');assert.equal(txt('finalSide'),'PASS');assert.match(txt('finalConfidence'),/95.0%/);
  assert.equal(txt('scalpState'),'EXIT');assert.match(txt('scalpLadderExit'),/current BID 68.0¢ · trigger BID 68.0¢/);
  assert.equal(txt('upOdds'),'35.0¢');assert.equal(txt('downOdds'),'66.0¢');checks.push('Initial real-processor fixture; unqualified 95% FINAL remains dominant PASS; actual later-bid EXIT');
  await advance(1100);assert.equal(txt('upOdds'),'35.0¢');assert.equal(txt('finalAction'),'UNLOCKED / PASS');
  assert.equal(writes.filter(x=>!x.stack.includes('product-panel.js')).length,0,'Legacy code mutated owned live DOM');checks.push('All assembled scripts, legacy success/timer callbacks and detached ownership');
  payload.main={...clone(fixture.main),status:'UNAVAILABLE',reason:'SOURCE_EXPIRED',historical_only:true};delete payload.main.expires_at;delete payload.main.final;
  await advance(1000);assert.equal(txt('earlyState'),'WAIT');assert.equal(txt('scalpState'),'EXIT');assert.equal(txt('finalArrow'),'—');assert.equal(txt('finalSide'),'FINAL · WAIT');assert.equal(txt('finalAction'),'WAIT / REFRESHING');checks.push('Typed MAIN source loss retains informational reference only; independent fresh SCALP remains visible');
  payload.scalp.target++;payload.scalp.official_identity.target++;await advance(1000);assert.equal(txt('scalpState'),'WAIT');assert.match(txt('scalpFlow'),/NO CURRENT ACTION AUTHORITY/);checks.push('Target mismatch rejected for action while display remains informative');
  payload.scalp=clone(fixture.scalp);payload.scalp.guidance='EXIT';delete payload.scalp.terminal;await advance(1000);assert.equal(txt('scalpState'),'WAIT');checks.push('Malformed action payload rejected for action and shown as WAIT');
  payload.main=clone(fixture.main);payload.scalp=clone(fixture.scalp);offline=true;await advance(5000);
  assert.equal(txt('upOdds'),'35.0¢ LAST');assert.equal(txt('earlyState'),'WAIT');assert.equal(txt('scalpState'),'WAIT');assert.equal(txt('finalAction'),'WAIT / REFRESHING');for(const id of owned)assert.doesNotMatch(txt(id),/UNAVAILABLE/i);checks.push('Network loss and source expiry suppress action authority while retaining clearly labelled last-qualified information');
  offline=false;pending=true;await advance(1100);assert.ok(deferred.length>=3);
  visible=false;d.dispatchEvent(new w.Event('visibilitychange'));assert.equal(txt('finalAction'),'WAIT / REFRESHING');
  assert.ok(requests.filter(r=>r.url==='/ladders').at(-1).signal.aborted);
  pending=false;fresh();visible=true;d.dispatchEvent(new w.Event('visibilitychange'));await flush();
  const current=txt('finalAction');for(const resolve of deferred.splice(0))resolve();await flush();assert.equal(txt('finalAction'),current);checks.push('AbortController timeout fallback, hide/resume cancellation and late previous-generation replies');
  w.dispatchEvent(new w.Event('pagehide'));assert.equal(txt('earlyState'),'WAIT');
  w.dispatchEvent(new w.Event('pageshow'));await flush();assert.equal(txt('finalAction'),'UNLOCKED / PASS');checks.push('bfcache lifecycle requires refetch');
  await advance(6000);assert.equal(txt('finalAction'),'WAIT / REFRESHING');assert.equal(txt('upOdds'),'35.0¢ LAST');checks.push('Repeated cached served timestamps cannot renew action leases; last-qualified display remains explicitly non-authoritative');
  // Same accepted provider advances by 3 cents; display receipt and latest comparable book share the exact tuple.
  fresh();payload.quote.sequence++;payload.quote.up_bid+=.03;payload.quote.up_ask+=.03;payload.quote.down_bid-=.03;payload.quote.down_ask-=.03;
  await advance(500);assert.equal(txt('upOdds'),'38.0¢');assert.equal(txt('downOdds'),'63.0¢');
  const measured=w.btc15QuoteRenderReceipts().at(-1);
  assert.equal(measured.up_ask,payload.quote.up_ask);assert.equal(measured.down_ask,payload.quote.down_ask);
  assert.equal(measured.accepted_to_published_ms,(payload.quote.published_ts-payload.quote.accepted_ts)*1000);
  checks.push('Comparable accepted tuple → DOM: injected 3¢ move reflected; measured delta zero after render');
  offline=true;await advance(500);assert.equal(txt('upOdds'),'38.0¢');assert.equal(txt('downOdds'),'63.0¢');offline=false;
  checks.push('500ms transient browser transport failure preserves the original accepted quote lease');
  const old=clone(payload.quote);payload.quote.sequence--;await advance(500);assert.equal(txt('upOdds'),'38.0¢ LAST');checks.push('Out-of-order accepted sequence fails closed for current quote while last-qualified presentation remains labelled');
  payload.quote=old;payload.main=clone(fixture.main);payload.scalp=clone(fixture.scalp);
  payload.scalp.status='PASS';payload.scalp.guidance='PASS';payload.scalp.origin=null;payload.scalp.terminal=null;
  payload.scalp.diagnostics=[
    {side:'UP',ask:.98,in_30_45_band:false,reason:'PRICE_OUTSIDE_30_45C'},
    {side:'DOWN',ask:.02,in_30_45_band:false,reason:'PRICE_OUTSIDE_30_45C'}
  ];
  fresh();visible=false;d.dispatchEvent(new w.Event('visibilitychange'));visible=true;d.dispatchEvent(new w.Event('visibilitychange'));await flush();
  assert.equal(txt('scalpState'),'PASS');
  assert.match(txt('scalpEntry'),/PASS · no side in 30–45¢ entry band · UP 98\.0¢ · DOWN 2\.0¢/);
  checks.push('Healthy SCALP PASS exposes exact non-entry reason instead of looking dead');
  payload.quote=old;payload.main=clone(fixture.main);payload.scalp=clone(fixture.scalp);
  for(const lane of ['main','scalp','quote']){
    const x=payload[lane],i=x.official_identity;i.official_open+=900;i.official_close+=900;i.contract='KXBTC15M-26OCT031630-30';
    for(const k of ['published_ts','served_ts','expires_at','exchange_ts','accepted_ts'])if(Number.isFinite(x[k]))x[k]+=900;
    if(lane!=='quote'){x.contract=i.contract;x.target=i.target;x.official_open=i.official_open;x.official_close=i.official_close;x.origin=null;}
  }
  payload.main.status='PASS';payload.main.early.guidance='PASS';payload.scalp.status='PASS';payload.scalp.guidance='PASS';payload.scalp.terminal=null;
  visible=false;d.dispatchEvent(new w.Event('visibilitychange'));await advance(901000);
  for(const lane of ['main','scalp','quote']){const x=payload[lane],delta=fixture[lane].served_ts+now/1000-x.served_ts;for(const k of ['published_ts','served_ts','expires_at','exchange_ts','accepted_ts'])if(Number.isFinite(x[k]))x[k]+=delta;}
  visible=true;d.dispatchEvent(new w.Event('visibilitychange'));await flush();
  assert.match(txt('currentContract'),/1630-30/);assert.doesNotMatch(txt('earlyYourEntry'),/35.0¢/);assert.equal(txt('scalpState'),'PASS');checks.push('Hidden across rollover: exact new identity, old origins discarded');
  assert.equal(writes.filter(x=>!x.stack.includes('product-panel.js')).length,0,'Legacy failure/resume mutated live cards');
  assert.equal(errors.length,0,errors.join('\n'));assert.doesNotMatch(html,/DIAGNOSTIC V13\.2-P1/);
  const report={schema:'BTC15_ASSEMBLED_UI_TEST_R1',status:'PASS',evidence_class:'OFFLINE_DOM_INTEGRATION',
    scripts:sources,checks,owned_writes:writes.length,legacy_owned_writes:0,errors,
    quote_measurement:{scope:'SYNTHETIC_SAME_CLOCK',injected_change_cents:3,post_render_up_delta_cents:0,post_render_down_delta_cents:0,receipt:measured},
    physical_safari:'NOT_TESTED_REQUIRES_USER_DEVICE_ACCEPTANCE',visual_layout:'REQUIRES_RENDERED_BROWSER_CHECK',signal_only:true,orders:false};
  fs.writeFileSync(path.join(out,'assembled_ui_results.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));dom.window.close();
})().catch(e=>{console.error(e);process.exit(1);});
