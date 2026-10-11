/* Real Chromium acceptance of unmodified cockpit assets. All HTTP is intercepted.
 * Schema-valid synthetic publications are NOT an incident/price replay.
 * NODE_PATH=<playwright module root> BTC15_CHROMIUM_PATH=<binary> node this-file
 */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const browserKind=process.env.BTC15_TEST_BROWSER||'chromium';
const root=path.resolve(__dirname,'../../cockpit_candidate'),out=path.resolve(process.env.BTC15_BROWSER_OUT||'/tmp/btc15-browser-acceptance');
fs.mkdirSync(out,{recursive:true});
const box={window:{}};vm.runInNewContext(fs.readFileSync(path.join(root,'fixtures.js'),'utf8'),box);
const seed=box.window.BTC15_REVIEW_SAMPLES[4],clone=x=>JSON.parse(JSON.stringify(x));
const start=Date.now(),base=seed.at;let mode='normal',roll=0,serial=100,frozen=null,lastQuote=null,delayNext=false,pending=null;
const counts={},requests=[],errors=[],checks=[];
const iso=x=>new Date(x*1000).toISOString();
function data(){
 const now=base+(Date.now()-start)/1000+roll*900,elapsed=now-base-roll*900;
 const id={...seed.main.official_identity};
 if(roll){id.official_open+=900;id.official_close+=900;id.contract='KXBTC15M-26OCT031630-30';id.target+=50;}
 const main=clone(seed.main),scalp=clone(seed.scalp),quote=clone(seed.quote),seq=serial++;
 for(const p of [main,scalp])Object.assign(p,{official_identity:id,contract:id.contract,target:id.target,
   official_open:id.official_open,official_close:id.official_close,published_ts:now,served_ts:now,expires_at:Math.min(now+3.5,id.official_close)});
 Object.assign(quote,{official_identity:id,published_ts:now,served_ts:now,exchange_ts:now-.1,accepted_ts:now-.02,
  expires_at:Math.min(now+5.9,id.official_close),epoch:'browser-'+roll,sequence:seq,
  up_bid:.60+Math.floor(elapsed)%3/100,up_ask:.61+Math.floor(elapsed)%3/100,
  down_bid:.38-Math.floor(elapsed)%3/100,down_ask:.39-Math.floor(elapsed)%3/100});
 main.final.confidence=roll?.61:.95;main.final.probability_up=main.final.confidence;main.final.probability_down=1-main.final.confidence;
 if(roll){
  for(const p of [main,scalp]){p.origin=null;p.terminal=null;p.executable_current_bid=null;p.movement_cents=null;p.status='PASS';}
  main.early.guidance='PASS';main.final.early_origin_id=null;main.final.helper.origin_id=null;scalp.guidance='PASS';
 }
 const historical={issued_buy:true,origin_id:'a'.repeat(64),side:'UP',original_ask:.05,signal_ts:id.official_open-29.086,
  contract:'KXBTC15M-26OCT031600-00',target:79995,open_ts:id.official_open-900,close_ts:id.official_open,
  status:'EXPIRED',management_state:'WATCH',entry_reason:'SYNTHETIC historical record; no fill',realized_profit:null};
 // The rollover test deliberately carries historical identities, never active authority.
 if(roll)main.trade_clarity={schema:'BTC15_ISSUED_SIGNALS_V1',records:[historical],selected_origin_id:historical.origin_id,entry_authority_current:false};
 const market={generated_utc:iso(now),source_timestamp_utc:iso(now-.05),contract:id.contract,
  safety:{read_only:true,orders_enabled:false},health:{source_fresh:true,paired_quotes:true,market_open:true,brti_fresh:true},
  timer:{close_utc:iso(id.official_close),seconds_left:id.official_close-now},
  market:{target:id.target,btc_price:id.target+35+elapsed/10,brti_value:id.target+30+elapsed/10,
   brti_age_seconds:.25,brti_ready:true,brti_gap:30+elapsed/10,brti_side:'UP',preferred_side:'UP',
   up_bid:quote.up_bid,up_ask:quote.up_ask,down_bid:quote.down_bid,down_ask:quote.down_ask,
   direct_brti_authority_ready:true,direct_brti_agrees:true,dist_over_range5:1.2,range5:25,vol5:.0002},
  final:main.final,early:main.early,scalp:{ready:false},
  chart:{points:Array.from({length:30},(_,i)=>({t:iso(now-90+i*3),brti:id.target+15+i/2+elapsed/10,
    brti_age_sec:.25,target:id.target,btc:id.target+20+i/2+elapsed/10}))}};
 const info={schema:'BTC15_INFORMATION_V1',authority:'INFORMATIONAL_READ_ONLY',status:'AVAILABLE',orders:false,signal_only:true,
  checked_ts:now,published_ts:now,display_until:now+3,expires_at:now+4,brti_source_ts:now-.3,btc_source_ts:now-.3,
  ticker:id.contract,target:id.target,btc_price:market.market.btc_price,brti_value:market.market.brti_value,
  probability_up:main.final.probability_up,probability_down:main.final.probability_down,brti_agrees:true,protection_phase:'NORMAL',flip_risk_pct:5};
 return {main,scalp,quote,market,info};
}
(async()=>{
 const browser=await (browserKind==='webkit'?webkit.launch({headless:true}):chromium.launch({executablePath:process.env.BTC15_CHROMIUM_PATH,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']}));
 const page=await browser.newPage({viewport:{width:820,height:1180},deviceScaleFactor:1});
 page.on('pageerror',e=>errors.push(e.message));
 try{
 await page.route('**/*',async route=>{
  const u=new URL(route.request().url()),p=u.pathname;requests.push({path:p,method:route.request().method()});counts[p]=(counts[p]||0)+1;
  assert.equal(u.hostname,'btc15-audit.test');assert.equal(route.request().method(),'GET');
  const assets={'/':'index.html','/index.html':'index.html','/styles.css':'styles.css','/adapter.js':'adapter.js','/trade_records.js':'trade_records.js','/cockpit.js':'cockpit.js','/live.js':'live.js',
   '/owners/market_view_owner.js':'owners/market_view_owner.js','/owners/information_owner.js':'owners/information_owner.js','/owners/ladder_owner.js':'owners/ladder_owner.js'};
  if(assets[p])return route.fulfill({contentType:p.endsWith('.css')?'text/css':p==='/'||p.endsWith('.html')?'text/html':'application/javascript',body:fs.readFileSync(path.join(root,assets[p]),'utf8')});
  const key={'/ladders':'main','/scalp/ladders':'scalp','/ladders/quotes':'quote','/dashboard_state.json':'market','/information':'info'}[p];
  if(!key)return route.fulfill({json:{status:'UNAVAILABLE',reason:'NO_SYNTHETIC_INDICATOR',signal_only:true,orders:false}});
  let row=data(),body=row[key];
  if(mode==='partial'){body={status:'AVAILABLE'};}
  if(mode==='stale')body=frozen[key];
  if(mode==='outage')body={...body,status:key==='info'?'WAIT':'UNAVAILABLE',reason:'AUDIT_SOURCE_OUTAGE'};
  if(mode==='older'&&key==='quote')body={...lastQuote,published_ts:lastQuote.published_ts-1,exchange_ts:lastQuote.exchange_ts-1,accepted_ts:lastQuote.accepted_ts-1,sequence:lastQuote.sequence-1,served_ts:row.quote.served_ts};
  if(key==='quote'&&mode==='normal')lastQuote=clone(body);
  if(key==='quote'&&delayNext){delayNext=false;pending={route,body};return;}
  if(mode==='outage'&&key==='market')return route.fulfill({status:503,json:{reason:'AUDIT_SOURCE_OUTAGE'}});
  const headers=key==='info'?{'X-BTC15-Information-Nonce':route.request().headers()['x-btc15-information-nonce']||''}:{};
  return route.fulfill({headers,json:body});
 });
 await page.goto('https://btc15-audit.test/?mode=live');
 await page.waitForFunction(()=>window.BTC15LadderOwner?.getResolvedView()?.lanes.quote.eligible&&window.BTC15LadderOwner?.getResolvedView()?.lanes.main.eligible);
 await page.waitForFunction(()=>document.querySelector('#chart-surface svg')&&/\$/.test(document.getElementById('spot-price').textContent));
 await page.evaluate(()=>{
  window.auditFrames={samples:0,blank:[],rootChanges:0,pathChanges:0,seenPrices:new Set()};
  const root=document.querySelector('#chart-surface svg'),path=root.querySelector('path');window.auditRoot=root;
  const ids=['final-probability','up-buy','down-buy','spot-price','brti-latest','target-price'];
  function frame(){const a=window.auditFrames;a.samples++;for(const id of ids){const n=document.getElementById(id),s=getComputedStyle(n);if(!/\d/.test(n.textContent)||s.display==='none'||s.visibility==='hidden'||s.opacity==='0')a.blank.push({id,text:n.textContent});}
   a.seenPrices.add(document.getElementById('up-buy').textContent);if(document.querySelector('#chart-surface svg')!==root)a.rootChanges++;
   if(root.querySelector('path')!==path)a.pathChanges++;window.auditRAF=requestAnimationFrame(frame);}
  window.auditRAF=requestAnimationFrame(frame);
 });
 await page.waitForTimeout(6500);
 const normal=await page.evaluate(()=>{cancelAnimationFrame(window.auditRAF);return {...window.auditFrames,seenPrices:[...window.auditFrames.seenPrices]};});
 assert.equal(normal.blank.length,0,JSON.stringify(normal.blank.slice(0,5)));assert.equal(normal.rootChanges,0);assert.equal(normal.pathChanges,0);assert.ok(normal.seenPrices.length>=2);
 checks.push({name:'normal refresh',...normal});await page.screenshot({path:path.join(out,'normal-ipad.png'),fullPage:true});
 const fields=['final-probability','up-buy','down-buy','spot-price','brti-latest'];
 const before=await page.evaluate(ids=>Object.fromEntries(ids.map(id=>[id,document.getElementById(id).textContent])),fields);
 for(const width of [1440,820,390]){
 await page.setViewportSize({width,height:1180});
 const layout=await page.evaluate(()=>Array.from(document.querySelectorAll('[data-section]')).map(e=>({name:e.dataset.section,y:e.getBoundingClientRect().top,x:e.getBoundingClientRect().left})));
 assert.deepEqual(layout.map(x=>x.name),['header','final','early','scalp','chart','health','context','details']);
 const reading=['final','early','scalp','chart'].map(n=>layout.find(x=>x.name===n));
 assert.ok(reading.every((r,i)=>i===0||r.y>reading[i-1].y+1||Math.abs(r.y-reading[i-1].y)<=1&&r.x>reading[i-1].x));
 const screen=await page.evaluate(()=>({w:innerWidth,doc:document.documentElement.scrollWidth}));assert.ok(screen.doc<=screen.w+1);
 assert.equal(await page.locator('#early-ladder li').count(),3);assert.equal(await page.locator('#scalp-ladder li').count(),5);
 assert.equal(await page.locator('[data-section=health]').count(),1);assert.equal(await page.locator('[data-section=context]').count(),1);
 checks.push({name:'approved independent ladder order',width,order:layout.map(x=>x.name),pass:true});
}
await page.setViewportSize({width:820,height:1180});
mode='partial';await page.waitForTimeout(1400);
 const partial=await page.evaluate(ids=>({values:Object.fromEntries(ids.map(id=>[id,document.getElementById(id).textContent])),view:window.BTC15LadderOwner.getResolvedView(),active:document.querySelectorAll('[aria-current]').length}),fields);
 // A response already in flight may finish before the injected failure. Compare
 // with the final accepted observation, not a racy pre-injection screenshot.
 assert.equal(partial.values['up-buy'],(partial.view.lanes.quote.retained_payload.up_ask*100).toFixed(2)+'¢');
 assert.equal(partial.values['down-buy'],(partial.view.lanes.quote.retained_payload.down_ask*100).toFixed(2)+'¢');
 assert.ok(Object.values(partial.values).every(v=>/\d/.test(v)));assert.equal(partial.active,0);assert.equal(partial.view.lanes.quote.eligible,false);assert.equal(partial.view.lanes.quote.reason_code,'SAFETY_SCHEMA');checks.push({name:'partial reply',pass:true});
 mode='normal';await page.waitForFunction(()=>window.BTC15LadderOwner.getResolvedView().lanes.quote.eligible);
 frozen=data();mode='stale';await page.waitForTimeout(7200);
 const stale=await page.evaluate(()=>({eligible:window.BTC15LadderOwner.getResolvedView().lanes.quote.eligible,quote:document.getElementById('quote-status').textContent,final:document.getElementById('final-freshness').textContent,active:document.querySelectorAll('[aria-current]').length}));
 assert.equal(stale.eligible,false);assert.equal(stale.active,0);assert.match(stale.quote,/STALE.*historical.*no executable/);checks.push({name:'expired unchanged replies',...stale});
 mode='outage';await page.waitForTimeout(1300);assert.match(await page.locator('#quote-status').textContent(),/UNAVAILABLE.*AUDIT SOURCE OUTAGE/);
 await page.screenshot({path:path.join(out,'outage-ipad.png'),fullPage:true});checks.push({name:'outage remains visible',pass:true});
 const retained=await page.evaluate(()=>window.BTC15LadderOwner.getResolvedView().lanes.quote.retained_payload.sequence);
 mode='older';await page.waitForTimeout(1000);
 assert.equal(await page.evaluate(()=>window.BTC15LadderOwner.getResolvedView().lanes.quote.retained_payload.sequence),retained);checks.push({name:'older response after outage rejected',pass:true});
 mode='normal';await page.waitForFunction(()=>window.BTC15LadderOwner.getResolvedView().lanes.quote.eligible);
 delayNext=true;while(!pending)await page.waitForTimeout(50);
 const delayed=pending;pending=null;
 await page.evaluate(()=>{window.dispatchEvent(new Event('pagehide'));window.dispatchEvent(new Event('pageshow'));});
 await page.waitForFunction(()=>window.BTC15LadderOwner.getResolvedView().lanes.quote.eligible);
 const newest=await page.evaluate(()=>window.BTC15LadderOwner.getResolvedView().lanes.quote.retained_payload.sequence);
 await delayed.route.fulfill({json:delayed.body}).catch(()=>{});await page.waitForTimeout(150);
 assert.ok(await page.evaluate(()=>window.BTC15LadderOwner.getResolvedView().lanes.quote.retained_payload.sequence)>=newest);checks.push({name:'delayed pre-resume response cannot overwrite',pass:true});
 roll=1;await page.waitForFunction(()=>window.BTC15LadderOwner.getResolvedView().identity?.contract.endsWith('1630-30'));
 await page.waitForFunction(()=>document.getElementById('early-action').textContent.includes('HISTORICAL'));
 assert.equal(await page.locator('#early-ladder [aria-current]').count(),0);assert.match(await page.locator('#early-price').textContent(),/5¢/);checks.push({name:'confirmed rollover retains historical BUY without action',pass:true});
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(300);
 const width=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));assert.ok(width.document<=width.viewport+1,JSON.stringify(width));
 await page.screenshot({path:path.join(out,'history-phone.png'),fullPage:true});checks.push({name:'phone layout',...width});
 assert.deepEqual(errors,[]);
 const result={status:'PASS',browser:browser.version(),production_contact:false,source:'unmodified candidate assets; synthetic schema-valid HTTP stream',checks,requests:counts,pageErrors:errors,physical_iPadSafari:'NOT_TESTED'};
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
 }catch(e){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:e.stack,errors,checks,requests:counts,view:await page.evaluate(()=>window.BTC15LadderOwner?.getResolvedView()),texts:await page.locator('body').innerText()},null,2));throw e;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
