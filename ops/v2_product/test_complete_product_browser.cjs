/* Full existing page, 960 one-second observations plus rollover; no network. */
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'qualification/final_completion_20261005');
const tape=JSON.parse(fs.readFileSync(path.join(out,'product-tape.json')));
const html=fs.readFileSync(path.join(out,'dashboard/BTC_Kalshi_App_Live_v13.html'),'utf8');
(async()=>{const browser=await chromium.launch({headless:true});let row=tape[0],override=null;
try{
 const page=await browser.newPage({viewport:{width:820,height:932}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(({at})=>{
  let clock=at*1000,next=1;const Original=Date,timers=[],timeouts=new Map();
  window.Date=class extends Original{constructor(...args){super(...(args.length?args:[clock]));}static now(){return clock;}};
  Object.defineProperty(performance,'now',{value:()=>clock});
  window.setInterval=(fn,delay)=>{timers.push(fn);return timers.length;};
  window.setTimeout=(fn,delay)=>{const id=next++;timeouts.set(id,{fn,due:clock+delay});return id;};
  window.clearTimeout=id=>timeouts.delete(id);
  window.__tick=async at=>{clock=at*1000;const due=[...timeouts].filter(([id,t])=>t.due<=clock);for(const [id] of due)timeouts.delete(id);await Promise.all(due.map(([id,t])=>t.fn()));for(const fn of timers)fn();};
 },{at:row.at});
 await page.route('**/*',async route=>{
  const u=new URL(route.request().url());let body,type='application/json';
  if(u.pathname==='/'){body=html;type='text/html';}
  else if(u.pathname==='/ladders/panel.js'){body=fs.readFileSync(path.join(root,'btc15_v2_product/panel.js'),'utf8').replace('__V81_LADDERS_URL__','"https://offline.test/scalp-fixture"');type='application/javascript';}
  else if(['/information/panel.js','/information/view.js'].includes(u.pathname)){body=fs.readFileSync(path.join(root,u.pathname.includes('view')?'btc15_information_view_v1.js':'btc15_information_panel_v1.js'),'utf8');type='application/javascript';}
  else {const key={'/ladders':'main','/ladders/quotes':'quote','/ladders/indicators':'indicators','/scalp-fixture':'scalp','/dashboard_state.json':'legacy'}[u.pathname];body=JSON.stringify((override&&override[key])||row[key]||{status:'WAIT'});}
  await route.fulfill({contentType:type,body});
 });
 await page.goto('https://offline.test/');
 const charts=new Set(),timers=new Set(),contracts=new Set();
 for(let index=0;index<tape.length;index++){
  row=tape[index];await page.evaluate(at=>window.__tick(at),row.at);
  await page.waitForFunction(({seq,contract})=>document.getElementById('upOdds').dataset.quoteIdentity.split('|').at(-2)===String(seq)&&document.getElementById('currentContract').textContent.includes(contract),{seq:row.quote.sequence,contract:row.main.contract});
  const d=await page.evaluate(()=>({final:document.getElementById('finalAction').textContent,scalp:document.getElementById('scalpState').textContent,
   strength:document.getElementById('signalStrength').textContent,flip:document.getElementById('flipRisk').textContent,
   timer:document.getElementById('timerRemaining').textContent,chart:document.querySelector('.chart-card svg').outerHTML,
   indicators:[...document.querySelectorAll('.indicator-row .indicator-unavailable')].map(n=>n.textContent),
   elements:[...document.body.querySelectorAll('*')].filter(e=>!['SCRIPT','STYLE'].includes(e.tagName)).length}));
  assert.equal(d.final,'UNLOCKED / PASS');assert.equal(d.scalp,'PASS');assert.equal(d.strength,'MODERATE');assert.equal(d.flip,'40.0%');
  assert.equal(d.elements,289);assert.ok(d.indicators.every(v=>v&&!v.includes('NOT CONNECTED')));
  // The frozen dashboard's mmss() rounds remaining seconds to the nearest second.
  const left=Math.round(row.main.official_close-row.at),expectedTimer=String(Math.floor(left/60)).padStart(2,'0')+':'+String(left%60).padStart(2,'0');
  assert.equal(d.timer,expectedTimer);charts.add(d.chart);timers.add(d.timer);contracts.add(row.main.contract);
 }
 console.log(JSON.stringify({chart_frames:charts.size,timer_values:timers.size,contracts:contracts.size}));
 assert.equal(contracts.size,2);assert.ok(charts.size>100);assert.ok(timers.size>100);assert.deepEqual(errors,[]);
 const injections=[];
 for(const lane of ['main','scalp','quote','indicators']){
  override={[lane]:{...row[lane],status:'UNAVAILABLE',reason:'INJECTED_MISSING_SOURCE',served_ts:row.at}};
  await page.evaluate(at=>window.__tick(at),row.at);
  const id={main:'finalAction',scalp:'scalpState',quote:'upOdds'}[lane];
  if(id)await page.waitForFunction(id=>document.getElementById(id).textContent.toUpperCase()==='UNAVAILABLE',id);
  else await page.waitForFunction(()=>[...document.querySelectorAll('.indicator-row .indicator-unavailable')].every(n=>n.textContent.startsWith('NOT CONNECTED')));
  injections.push(lane);override=null;
  await page.evaluate(at=>window.__tick(at),row.at);
  await page.waitForFunction(()=>document.getElementById('finalAction').textContent==='UNLOCKED / PASS'&&document.getElementById('scalpState').textContent==='PASS'&&document.getElementById('upOdds').textContent!=='Unavailable'&&!document.querySelector('.indicator-unavailable').textContent.startsWith('NOT CONNECTED'));
 }
 // No poll response can keep indicators/action/quotes live past their own lease.
 row={...row,at:row.at+90};override={main:row.main,scalp:row.scalp,quote:row.quote,indicators:row.indicators};
 await page.evaluate(at=>window.__tick(at),row.at);
 await page.waitForFunction(()=>document.getElementById('finalAction').textContent==='UNAVAILABLE'&&document.getElementById('scalpState').textContent==='UNAVAILABLE'&&document.getElementById('upOdds').textContent==='Unavailable'&&document.querySelector('.indicator-unavailable').textContent.startsWith('NOT CONNECTED'));
 const result={status:'PASS',samples:tape.length,elapsed_seconds:960,clock:'accelerated 1-second production cadence',contracts:[...contracts],distinct_chart_frames:charts.size,distinct_timer_values:timers.size,
  main_false_holes:0,scalp_false_holes:0,indicator_false_holes:0,source_injections:injections,replayed_expired_payloads_fail_closed:true,elements:289,physical_devices:'NOT_TESTED'};
 fs.writeFileSync(path.join(out,'product-browser-contract.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
