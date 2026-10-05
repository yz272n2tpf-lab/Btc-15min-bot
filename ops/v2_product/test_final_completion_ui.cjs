/* Whole-page rollback comparison: exact HTML, full visible DOM, geometry and pixels. */
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),base=path.resolve(root,'../btc15');
const out=path.join(root,'qualification/final_completion_20261005');fs.mkdirSync(out,{recursive:true});
const htmls=[fs.readFileSync(path.resolve(base,'qualification/v2_product_20261004/dashboard/BTC_Kalshi_App_Live_v13.html'),'utf8'),fs.readFileSync(path.join(root,'qualification/visible_completion_20261005/dashboard/BTC_Kalshi_App_Live_v13.html'),'utf8')];
const markup=h=>h.replace(/<script[^>]*>[\s\S]*?<\/script>/g,'');
assert.equal(markup(htmls[0]),markup(htmls[1]),'Entire HTML/CSS outside functional scripts remains byte-identical');
const fixture=JSON.parse(fs.readFileSync(path.join(base,'qualification/v2_product_20261004/ui_fixture.json')));
const revalidated=JSON.parse(fs.readFileSync(path.join(base,'qualification/v2_product_20261004/ui_revalidated_fixture.json')));
const iso=t=>new Date(t*1000).toISOString();const m=fixture.main,i=m.official_identity,t=m.served_ts;
const legacy={contract:i.contract,generated_utc:iso(t),source_timestamp_utc:iso(t-.1),timer:{close_utc:iso(i.official_close)},
 safety:{read_only:true,orders_enabled:false},health:{paired_quotes:true},parity:{contract:i.contract,api_contract:i.contract,status:'PASS',timestamp_utc:iso(t)},
 market:{target:i.target,btc_price:80080,brti_value:80080,brti_age_seconds:.3,brti_ready:true,brti_side:'UP',up_ask:.99,down_ask:.01,preferred_side:'UP'},
 final:{side:'UP',confidence:.999,ready:true,conditions:{}},early:{ready:true,side:'UP',ask:.99},scalp:{ready:true,side:'UP',ask:.99,bid:.98},
 chart:{points:Array.from({length:61},(_,n)=>({t:iso(t-300+n*5),brti:80010+n+5*Math.sin(n),brti_age_sec:.3}))}};
(async()=>{const browser=await chromium.launch({headless:true}),results=[];
try{for(const width of [390,430,820,1180])for(const state of ['fresh','revalidated','unavailable']){
 const observations=[];
 for(const [index,folder] of [base,root].entries()){
  const context=await browser.newContext({viewport:{width,height:932},deviceScaleFactor:1,isMobile:width<500,hasTouch:width<1101});
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(({at})=>{const Original=Date;window.Date=class extends Original{constructor(...args){super(...(args.length?args:[at]));}static now(){return at;}};Object.defineProperty(performance,'now',{value:()=>100});window.setInterval=()=>1;}, {at:t*1000});
  await page.route('**/*',async route=>{
   const u=new URL(route.request().url());let body,type='application/json';
   if(u.pathname==='/'){body=htmls[index];type='text/html';}
   else if(u.pathname==='/ladders/panel.js'){body=fs.readFileSync(path.join(folder,'btc15_v2_product/panel.js'),'utf8').replace('__V81_LADDERS_URL__','"https://offline.test/fixture-v81"');type='application/javascript';}
   else if(['/information/panel.js','/information/view.js'].includes(u.pathname)){body=fs.readFileSync(path.join(folder,u.pathname.includes('view')?'btc15_information_view_v1.js':'btc15_information_panel_v1.js'),'utf8');type='application/javascript';}
   else if(u.pathname==='/ladders/indicators'){
    const close=Math.floor(t/60)*60;
    body=JSON.stringify(state==='unavailable'?{schema:'BTC15_DISPLAY_INDICATORS_R1',status:'UNAVAILABLE',authority:'DISPLAY_ONLY',served_ts:t,signal_only:true,orders:false}:{schema:'BTC15_DISPLAY_INDICATORS_R1',status:'AVAILABLE',authority:'DISPLAY_ONLY',provider:'COINBASE_EXCHANGE',product:'BTC-USD',granularity:60,volume_unit:'BTC',completed_count:300,candle_open:close-60,candle_close:close,request_cutoff:close,received_ts:close+.2,served_ts:t,expires_at:close+75,rsi:52.31,macd:12.34,signal:10.23,histogram:2.11,volume:3.99,signal_only:true,orders:false});
   }else {
    const lane=u.pathname==='/ladders'?'main':u.pathname==='/ladders/quotes'?'quote':u.pathname==='/fixture-v81'?'scalp':null;
    let data=lane?structuredClone(state==='revalidated'&&index===1?revalidated[lane]:fixture[lane]):u.pathname==='/dashboard_state.json'?structuredClone(legacy):{status:'WAIT'};
    if(lane&&state==='unavailable'){data.status='UNAVAILABLE';data.reason='SOURCE_EXPIRED';delete data.expires_at;delete data.final;}
    body=JSON.stringify(data);
   }
   await route.fulfill({contentType:type,body});
  });
  await page.goto('https://offline.test/');
  await page.waitForFunction(state=>document.getElementById('finalAction').textContent===(state!=='unavailable'?'UNLOCKED / PASS':'UNAVAILABLE')&&document.getElementById('scalpState').textContent===(state!=='unavailable'?'EXIT':'UNAVAILABLE')&&document.getElementById('timerRemaining').textContent!=='—',state);
  await page.evaluate(()=>document.fonts.ready);
  const dom=await page.evaluate(()=>{
    const rect=e=>{let r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height];};
    const structure=[...document.body.querySelectorAll('*')].filter(e=>!['SCRIPT','STYLE'].includes(e.tagName)).map(e=>({tag:e.tagName,id:e.id,cls:e.getAttribute('class'),parent:e.parentElement.id||e.parentElement.tagName,
      directText:(e.id==='signalStrength'||e.classList.contains('indicator-unavailable'))?'REQUESTED_LIVE_VALUE':[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(''),rect:rect(e),display:getComputedStyle(e).display,
      points:e.tagName.toLowerCase()==='polyline'?e.getAttribute('points'):undefined}));
    return {structure,text:structure.map(x=>x.directText).join('\n'),scrollWidth:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,
       timer:document.getElementById('timerRemaining').textContent,chart:document.querySelector('.chart-card svg').outerHTML,cards:[...document.querySelectorAll('article.card')].map(e=>({id:e.id,cls:e.className,rect:rect(e)}))};
  });
  assert.deepEqual(errors,[]);assert.ok(dom.height>932);assert.ok(dom.scrollWidth<=width+1);assert.ok(dom.chart.includes('<path')&&dom.chart.includes('Sampled BRTI'));
  const name=`${index?'candidate':'rollback'}-${width}-${state}`;
  fs.writeFileSync(path.join(out,name+'-dom.json'),JSON.stringify(dom,null,2));
  await page.screenshot({path:path.join(out,name+'.png'),fullPage:true,animations:'disabled'});
  const masked=await page.screenshot({fullPage:true,animations:'disabled',mask:[page.locator('#signalStrength'),page.locator('.indicator-row .indicator-unavailable')]});
  dom.maskedScreenshotSha=require('node:crypto').createHash('sha256').update(masked).digest('hex');
  const label=await page.locator('#signalStrength').innerText();
  if(index===1){assert.deepEqual(await page.locator('.indicator-row .indicator-unavailable').allTextContents(),state==='unavailable'?Array(3).fill('NOT CONNECTED — no live indicator feed'):['52.31','12.34 / 10.23 / 2.11','3.99 BTC']);}
  if(index===1)assert.equal(label,state==='unavailable'?'NOT CONNECTED':(m.final.confidence>=.90?'STRONG':m.final.confidence>=.75?'GOOD':m.final.confidence>=.60?'MODERATE':'WEAK'));
  observations.push(dom);await context.close();
 }
 assert.deepEqual(observations[0],observations[1],`Full DOM/text/layout regression ${width}/${state}`);
 results.push({width,state,status:'PASS',static_html_css_bytes_identical:true,requested_dynamic_indicator_and_signal_strength_values_only:true,other_pixels_identical:true,dom_geometry_identical:true,height:observations[1].height,elements:observations[1].structure.length,timer:observations[1].timer});
}
fs.writeFileSync(path.join(out,'ui_invariance.json'),JSON.stringify({status:'PASS',engine:'Chromium',physical_devices:'NOT_TESTED',results},null,2));console.log(JSON.stringify(results));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
