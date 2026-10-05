/* Real assembled page, routes and isolated confirmation worker on loopback. */
const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:820,height:1180}}),errors=[],responses=[];
  page.on('response',async response=>{if(response.url().endsWith('/ladders'))try{responses.push(await response.json());}catch{}});
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://fixture-v81.test/ladders',async route=>{
   const r=await fetch(process.argv[2]+'/fixture-v81');await route.fulfill({contentType:'application/json',body:await r.text()});
  });
  await page.addInitScript(()=>{const original=window.fetch;window.fetch=async(...args)=>{const response=await original(...args);if(args[0]==='/ladders'){const d=await response.clone().json();window.__confirmed=d.presentation_revalidation?.status==='CONFIRMED';}return response;};});
  await page.goto(process.argv[2]);
  await page.waitForFunction(()=>window.__confirmed===true&&document.getElementById('finalAction').textContent==='UNLOCKED / PASS',null,{timeout:20000});
  // Warm the browser at the first confirmed native key, then cross TWO native
  // commits while BRTI is 4.9 seconds old at each native decision.
  const result=await page.evaluate(()=>new Promise(resolve=>{
   const samples=[];const start=performance.now();
   const timer=setInterval(()=>{
    samples.push({at:performance.now()-start,main:document.getElementById('finalAction').textContent,
     reason:document.getElementById('finalActionSub').textContent,early:document.getElementById('earlyState').textContent,quote:document.getElementById('upOdds').textContent,
     scalp:document.getElementById('scalpState').textContent});
    if(performance.now()-start>=11000){clearInterval(timer);resolve(samples);}
   },25);
  }));
  const holes=result.filter(s=>s.main==='UNAVAILABLE'||s.early==='UNAVAILABLE'||s.quote==='Unavailable'||s.scalp==='UNAVAILABLE');
  fs.writeFileSync(process.argv[3],JSON.stringify({status:holes.length?'FAIL':'PASS',scope:'REAL_LOOPBACK_ASSEMBLED_PRODUCT_SYNTHETIC_OWNER_SOURCES',
   responses,native_cadence_seconds:5,brti_age_at_native_cut:4.9,samples:result.length,holes,errors,signal_only:true,orders:false},null,2)+'\n');
  assert.deepEqual(holes,[]);assert.deepEqual(errors,[]);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
