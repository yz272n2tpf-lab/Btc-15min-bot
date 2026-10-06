/* Full assembled DOM and all scripts; synthetic clocks/data. No browser/device claims. */
const {JSDOM,VirtualConsole}=require('jsdom'),fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),out=path.resolve(process.argv[2]);
const tape=JSON.parse(fs.readFileSync(path.join(out,'tape.json'))),html=fs.readFileSync(path.join(out,'dashboard/BTC_Kalshi_App_Live_v13.html'),'utf8');
(async()=>{
 const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 const dom=new JSDOM(html,{url:'https://offline.test/',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
 const w=dom.window,d=w.document,timers=[],checks=[];w.structuredClone=structuredClone;
 let row=tape[0],at=row.at,abort=false,forceWait=false,infoHealthy=true;
 Object.defineProperty(w.performance,'now',{value:()=>at*1000});
 w.setInterval=fn=>{timers.push(fn);return timers.length;};w.setTimeout=()=>1;w.clearTimeout=()=>{};
 Object.defineProperty(d,'visibilityState',{get:()=> 'visible'});Object.defineProperty(d,'hidden',{get:()=>false});
 w.fetch=async(url,opts={})=>{
  const name=String(url),k=name==='/ladders'?'main':name==='/ladders/quotes'?'quote':name.includes('scalp-fixture')?'scalp':null;
  if(abort&&k)throw Error('fixture transport');
  let value=k?structuredClone(row[k]):{status:'WAIT'};
  if(k){value.served_ts=at;if(forceWait&&k==='main')value={...value,status:'UNAVAILABLE',reason:'SOURCE_EXPIRED'};}
  if(name==='/information')value=infoHealthy?{schema:'BTC15_INFORMATION_V1',authority:'INFORMATIONAL_READ_ONLY',status:'AVAILABLE',signal_only:true,orders:false,checked_ts:at,display_until:at+2,expires_at:at+2,brti_source_ts:at-.1,ticker:row.main.contract,probability_up:.66,probability_down:.34,flip_risk_pct:34,protection_phase:'NORMAL',profit_protection_status:'OBSERVE_ONLY_NO_POSITION_CONTEXT',brti_agrees:true}:{status:'WAIT'};
  return {ok:true,json:async()=>value,headers:{get:name=>opts.headers?.[name]||null}};
 };
 for(const script of d.querySelectorAll('script')){
  let code,name;
  if(!script.src){code=script.textContent;name='legacy-inline.js';}
  else if(script.src.endsWith('/ladders/panel.js')){name='product-panel.js';code=fs.readFileSync(path.join(root,'btc15_v2_product/panel.js'),'utf8').replace('__V81_LADDERS_URL__','"https://offline.test/scalp-fixture"');}
  else {name=script.src.endsWith('/information/view.js')?'btc15_information_view_v1.js':'btc15_information_panel_v1.js';code=fs.readFileSync(path.join(root,name),'utf8');}
  vm.runInContext(code,dom.getInternalVMContext(),{filename:name});
 }
 const text=id=>d.getElementById(id)?.textContent;
 async function tick(){for(const fn of timers)fn();for(let i=0;i<20;i++)await Promise.resolve();w.btc15RenderLadders();}
 function check(name){const visible=d.body.cloneNode(true);visible.querySelectorAll('script,style').forEach(n=>n.remove());assert.doesNotMatch(visible.textContent,/unavailable|not connected/i,name);assert.deepEqual(errors,[],name);checks.push(name);}
 await tick();check('startup');
 for(let n=0;n<tape.length;n++){
  row=tape[n];at=row.at;await tick();check('native-'+n);
  assert.equal(text('earlyState'),row.main.origin?row.main.early.guidance:row.main.early_opportunity.status,'early-'+n);
  assert.equal(text('scalpState'),row.scalp.guidance,'scalp-'+n);
  assert.match(text('finalActionSub'),/UP 66.0% · DOWN 34.0% · continuous probability/);
  assert.match(text('earlyLadderEntry'),/≤50¢/);assert.match(text('earlyLadderEntry'),/25–35¢/);assert.match(text('earlyLadderExit'),/not yet validated/);
  if(n<3){assert.match(text('earlyCurrentPrice'),/UP ASK .*DOWN ASK/);assert.match(text('earlyEdge'),/model edge/);assert.match(text('earlyTitle'),/EARLY (UP|DOWN) · WATCH/);}
  if(n===0){const action=text('scalpState');abort=true;at+=.2;await tick();check('transport-original-lease');assert.equal(text('scalpState'),action);abort=false;}
  if(row.scalp.guidance==='EXIT')assert.match(text('scalpLadderExit'),/EXIT · current BID/);
  if(n===4)assert.match(text('contextBanner'),/MIXED HORIZONS/);
  if(row.main.final.ready)assert.equal(text('finalAction'),'FINAL LOCK / QUALIFIED');
  if(row.scalp.lifecycle_state==='ENDED_UNARMED')assert.match(text('scalpLadderExit'),/ENDED_UNARMED · information only/);
 }
 const earlyBefore=text('earlyState'),scalpBefore=text('scalpState'),finalSideBefore=text('finalSide');
 forceWait=true;at+=.1;await tick();check('native-failure');
 assert.equal(text('earlyState'),earlyBefore);assert.equal(text('finalSide'),finalSideBefore);assert.match(text('finalActionSub'),/UP 66.0%/);
 assert.match(text('finalReason'),/REFRESHING/);assert.match(text('earlyFlow'),/NO NEW ACTION AUTHORITY/);
 assert.match(text('earlyLadderEntry'),/≤50¢/);assert.doesNotMatch(text('earlyLadderEntry'),/current authority refresh pending/);
 forceWait=false;at+=.1;await tick();
 abort=true;infoHealthy=false;at=Math.max(row.main.expires_at,row.scalp.expires_at,row.quote.expires_at)+1;await tick();check('expiry');
 assert.equal(text('earlyState'),earlyBefore);assert.equal(text('scalpState'),scalpBefore);assert.match(text('finalReason'),/REFRESHING/);assert.match(text('upCondition'),/LAST QUALIFIED/);
 assert.match(text('scalpFlow'),/NO NEW ACTION AUTHORITY/);assert.doesNotMatch(text('scalpLadderEntry'),/current authority refresh pending/);
 fs.writeFileSync(path.join(out,'ui-results.json'),JSON.stringify({status:'PASS',checks,mode:'FULL_ASSEMBLED_JSDOM',physical_device_acceptance:'PENDING',signal_only:true,orders:false},null,2));
 console.log(JSON.stringify({status:'PASS',checks:checks.length,physical_device_acceptance:'PENDING'}));dom.window.close();
})().catch(e=>{console.error(e);process.exit(1)});
