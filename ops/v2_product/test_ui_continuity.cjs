/* Bounded, offline, full-dashboard fault qualification. No live fetches. */
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),out=path.resolve(process.argv[2]||path.join(root,'../qualification'));
const tape=JSON.parse(fs.readFileSync(path.join(out,'candidate/tape.json')));
const html=fs.readFileSync(path.join(out,'dashboard/BTC_Kalshi_App_Live_v13.html'),'utf8');
const ids=['finalAction','finalSide','finalConfidence','earlyState','earlyCurrentPrice','earlyEdge','scalpState','scalpEntry','scalpTargetStrip','upOdds','downOdds','signalStrength','flipRisk','momentumBadge','momentumSub','contextTrend','contextRange','contextBrti','contextLevels','btc15-information-status','btc15-information-assessment'];
(async()=>{const browser=await chromium.launch({headless:true});let samples=0;const cases=[];
try{for(const width of [390,820]){
 let row=tape[0],fault={},at=row.at,requestCount=0;
 const page=await browser.newPage({viewport:{width,height:932}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(({at,ids})=>{
  let clock=at*1000,next=1;const Original=Date,timers=[],timeouts=new Map();
  window.Date=class extends Original{constructor(...args){super(...(args.length?args:[clock]));}static now(){return clock;}};
  Object.defineProperty(performance,'now',{value:()=>clock});
  window.setInterval=fn=>{timers.push(fn);return timers.length;};
  window.setTimeout=(fn,delay)=>{const id=next++;timeouts.set(id,{fn,due:clock+delay});return id;};window.clearTimeout=id=>timeouts.delete(id);
  window.__tick=async at=>{clock=at*1000;for(const [id,t] of [...timeouts])if(t.due<=clock || t.fn.name==='refresh'){timeouts.delete(id);t.fn();}for(const fn of timers)fn();};
  window.__violations=[];window.__watch=false;
  new MutationObserver(()=>{if(!window.__watch)return;const body=document.body?.innerText||'';
   if(/unavailable|not connected/i.test(body))window.__violations.push('VISIBLE_UNAVAILABLE');
   for(const id of ids){const n=document.getElementById(id);if(n&&!n.textContent.trim())window.__violations.push('BLANK:'+id);}
  }).observe(document,{childList:true,subtree:true,characterData:true});
 },{at,ids});
 await page.route('**/*',async route=>{
  const u=new URL(route.request().url());let body,type='application/json',headers={};
  if(u.pathname==='/'){body=html;type='text/html';}
  else if(u.pathname==='/ladders/panel.js'){body=fs.readFileSync(path.join(root,'btc15_v2_product/panel.js'),'utf8').replace('__V81_LADDERS_URL__','"https://offline.test/scalp-fixture"');type='application/javascript';}
  else if(['/information/panel.js','/information/view.js'].includes(u.pathname)){body=fs.readFileSync(path.join(root,u.pathname.includes('view')?'btc15_information_view_v1.js':'btc15_information_panel_v1.js'),'utf8');type='application/javascript';}
  else {
   const k={'/ladders':'main','/ladders/quotes':'quote','/ladders/indicators':'indicators','/scalp-fixture':'scalp','/dashboard_state.json':'legacy','/information':'information'}[u.pathname];
   let d=row[k];
   if(k==='legacy'){const m=row.main,i=m.official_identity,iso=v=>new Date(v*1000).toISOString();d={contract:i.contract,generated_utc:iso(at),source_timestamp_utc:iso(at),timer:{close_utc:iso(i.official_close)},safety:{read_only:true,orders_enabled:false},health:{paired_quotes:true},parity:{contract:i.contract,api_contract:i.contract,status:'PASS',timestamp_utc:iso(at)},market:{target:i.target,btc_price:i.target+80,brti_value:i.target+80,brti_age_seconds:.1,brti_ready:true,brti_side:'UP',preferred_side:'UP',range5:20},final:{side:'UP',confidence:.6,ready:false,conditions:{}},early:{ready:false},scalp:{ready:false},chart:{points:[0,1,2].map(n=>({t:iso(at-2+n),brti:i.target+80+n,brti_age_sec:.1}))}};}
   if(k==='information'){headers['X-BTC15-Information-Nonce']=route.request().headers()['x-btc15-information-nonce'];d={schema:'BTC15_INFORMATION_V1',authority:'INFORMATIONAL_READ_ONLY',status:'AVAILABLE',signal_only:true,orders:false,checked_ts:at,display_until:at+2,expires_at:at+2,brti_source_ts:at-.1,ticker:row.main.contract,probability_up:.6,probability_down:.4,flip_risk_pct:40,protection_phase:'NORMAL',profit_protection_status:'OBSERVE_ONLY_NO_POSITION_CONTEXT',brti_agrees:true};}
   if(fault[k]==='abort'){requestCount++;return route.abort();}
   if(fault[k])d={...d,...fault[k]};
   requestCount++;body=JSON.stringify(d||{status:'WAIT'});
  }
  await route.fulfill({contentType:type,body,headers});
 });
 await page.goto('https://offline.test/');
 const text=id=>page.locator('#'+id).textContent();
 async function tick(){const before=requestCount;await page.evaluate(at=>window.__tick(at),at);await page.waitForTimeout(35);assert.ok(requestCount>before);}
 async function check(name){await page.waitForTimeout(20);const d=await page.evaluate(ids=>({body:document.body.innerText,values:Object.fromEntries(ids.map(id=>[id,document.getElementById(id)?.textContent])),violations:window.__violations,overflow:document.documentElement.scrollWidth>innerWidth+1}),ids);
  fs.writeFileSync(path.join(out,'last-body.txt'),d.body);assert.doesNotMatch(d.body,/unavailable|not connected/i,name);for(const [id,v] of Object.entries(d.values))assert.ok(v?.trim(),name+':'+id);assert.deepEqual(d.violations,[],name);assert.equal(d.overflow,false,name+' overflow');samples++;cases.push(width+':'+name);return d;}
 await page.waitForFunction(()=>document.getElementById('finalAction').textContent==='UNLOCKED / PASS');await check('startup');await page.evaluate(()=>window.__watch=true);
 for(let n=0;n<tape.length;n++){
  row=tape[n];at=row.at;fault={};await tick();await check('native-'+n);
  assert.equal(await text('earlyState'),row.main.early.guidance);assert.equal(await text('scalpState'),row.scalp.guidance);
  if(n===2){
   for(const [name,change] of [
    ['revalidation-disagreement',{main:row.disagreement}],
    ['BRTI-expiry',{main:row.expired}],
    ['identity-clock',{main:{status:'UNAVAILABLE',reason:'REVALIDATION_IDENTITY_OR_CLOCK'}}],
    ['noncausal',{main:{status:'UNAVAILABLE',reason:'REVALIDATION_EXPIRED_OR_NONCAUSAL'}}],
    ['timestamped-quotes',{scalp:{status:'UNAVAILABLE',reason:'TIMESTAMPED_QUOTES_UNAVAILABLE'},quote:{status:'UNAVAILABLE'}}],
    ['official-market',{scalp:{status:'UNAVAILABLE',reason:'OFFICIAL_MARKET_UNQUALIFIED'}}],
    ['indicators',{indicators:{status:'UNAVAILABLE'}}],
    ['lower-interruption',{legacy:'abort',information:'abort'}],
    ['transport',{main:'abort',scalp:'abort',quote:'abort',indicators:'abort'}]
   ]){
    fault=change;at+=.1;await tick();const d=await check(name);
    if(change.main){assert.equal(d.values.finalAction,'WAIT');assert.equal(d.values.earlyState,'WAIT');assert.match(d.values.finalConfidence,/LAST QUALIFIED/);}
    if(change.scalp){assert.equal(d.values.scalpState,'WAIT');assert.match(d.values.scalpCurrentPrice||await text('scalpCurrentPrice'),/LAST QUALIFIED/);}
    if(name==='lower-interruption'){assert.match(d.values.contextLevels,/LAST QUALIFIED/);assert.match(d.values['btc15-information-status'],/LAST QUALIFIED/);}
    if(name==='timestamped-quotes')assert.match(d.values.scalpEntry,/WAIT — timestamped quote refresh pending/);
    if(change.indicators)assert.match(await page.locator('.indicator-unavailable').first().textContent(),/LAST QUALIFIED/);
    fault={};at+=.05;await tick();await check(name+'-recovery');
   }
   // Empty chart updates keep observed same-contract history with an explicit label.
   fault={legacy:{chart:{points:[]}}};at+=.1;await tick();await check('chart-interruption');assert.ok(await page.locator('.chart-card svg path').count());
   fault={};
  }
 }
 // Exact existing diagnostic codes are shown with PASS; no synthetic entry.
 row=tape.at(-1);for(const [code,label] of [['PRICE_OUTSIDE_30_45C','price outside 30–45¢'],['BASE_NOT_READY','base not ready'],['EVIDENCE_BELOW_CORE_SURGE','evidence below CORE/SURGE']]){
  fault={scalp:{diagnostics:[{side:'UP',reason:code}]}};at+=.1;await tick();await check(code);assert.equal(await text('scalpState'),'PASS');assert.equal(await text('scalpEntry'),'PASS — '+label);
 }
 // EARLY PASS never re-anchors its presentation to a changing model-selected side.
 // Both executable asks remain visible; PASS reason and edge semantics stay non-actionable.
 row=tape.at(-1);const baseEarly={...row.main.early,guidance:'PASS',pass_reasons:['remaining_2_to10']};
 for(const [side,upAsk,downAsk,edge] of [['DOWN',.016,.985,-.307],['UP',.011,.990,.508]]){
  fault={main:{early:{...baseEarly,side,ask:side==='UP'?upAsk:downAsk,edge}},quote:{up_ask:upAsk,up_bid:Math.max(0,upAsk-.001),down_ask:downAsk,down_bid:Math.max(0,downAsk-.001)}};
  at+=.1;await tick();const d=await check('EARLY_PASS_SIDE_'+side);
  assert.equal(d.values.earlyState,'PASS');
  assert.match(d.values.earlyEntry,/PASS — outside EARLY entry window \(requires 2–10m remaining\)/);
  assert.match(d.values.earlyCurrentPrice,/^UP ASK [0-9.]+¢ · DOWN ASK [0-9.]+¢$/);
  assert.equal(d.values.earlyEdge,'No actionable edge while PASS');
 }
 fault={};at+=90;await page.evaluate(at=>window.__tick(at),at);await page.waitForTimeout(80);await check('expired-replayed-payloads');assert.equal(await text('earlyState'),'WAIT');assert.equal(await text('finalAction'),'WAIT');assert.equal(await text('scalpState'),'WAIT');assert.equal(await page.locator('#upOdds').getAttribute('data-quote-identity'),'');
 assert.deepEqual(errors,[]);await page.screenshot({path:path.join(out,'refreshing-'+width+'.png'),fullPage:true});await page.close();
}
fs.writeFileSync(path.join(out,'browser-results.json'),JSON.stringify({status:'PASS',samples,cases,visible_unavailable:0,blank_transitions:0,stale_actions:0,widths:[390,820],physical_device:'NOT_TESTED'},null,2));console.log(JSON.stringify({status:'PASS',samples}));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
