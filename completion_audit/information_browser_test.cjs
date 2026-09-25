// Actual Chromium loads the assembled PR36 dashboard and both information assets.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const root=path.resolve(__dirname,'..'), temp=fs.mkdtempSync(path.join(os.tmpdir(),'btc15-browser-'));
const python=process.env.PYTHON || 'python';
execFileSync(python,['btc15_information_install_v1.py','--assemble-only','--directory',temp],{cwd:root});
const server=spawn(python,['-u',path.join(temp,'BTC15_DASHBOARD_LIVE_SERVER_V1.py')],{
  cwd:root,env:{...process.env,PORT:'18888',PYTHONPATH:root,BTC15_ISOLATED_CANARY_LOCAL_DATA:'1'},stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  let browser;const passed=[];
  try {
    for(let i=0;i<100;i++){try{if((await fetch('http://127.0.0.1:18888/health')).ok)break;}catch(_){}await sleep(100);}
    browser=await chromium.launch({headless:true});
    const page=await browser.newPage();
    let mode='fresh',calls=0,rawOld=null;
    const nativeSnapshot=()=>page.evaluate(()=>Object.fromEntries(
      [...document.querySelectorAll('[id]')].filter(e=>/^(final|early|scalp)/.test(e.id)).map(e=>[e.id,e.textContent])));
    await page.route('https://**/*',route=>route.abort()); // V8.1 stays separate; no external feed.
    await page.route('**/information',async route=>{
      calls++;const nonce=route.request().headers()['x-btc15-information-nonce'];
      if(mode==='disconnect'){await route.abort();return;}
      const checked=Date.now()/1000;
      const p={schema:'BTC15_INFORMATION_V1',authority:'INFORMATIONAL_READ_ONLY',status:'AVAILABLE',
        orders:false,signal_only:true,checked_ts:checked,display_until:checked+1,expires_at:checked+2,
        brti_source_ts:checked-2.486,ticker:'SYNTHETIC',probability_up:.81,probability_down:.19,brti_agrees:true};
      if(mode==='wait')p.status='WAIT';
      if(mode==='expired')p.display_until=checked-.01;
      if(mode==='future')p.brti_source_ts=checked+1;
      if(mode==='slow')await sleep(1100);
      let headers={'Content-Type':'application/json','X-BTC15-Information-Nonce':nonce};
      let body=JSON.stringify(p);
      if(mode==='replay'){body=rawOld.body;headers=rawOld.headers;}
      else rawOld={body,headers};
      try{await route.fulfill({status:200,headers,body});}catch(_){}
    });
    await page.goto('http://127.0.0.1:18888/');
    const panel=page.locator('#btc15-information-assessment');
    await panel.waitFor();await page.waitForFunction(()=>document.querySelector('#btc15-information-assessment').textContent.includes('81.0%'));
    const native=await nativeSnapshot();passed.push('assembled dashboard/assets, separate information panel');
    mode='disconnect';await page.waitForFunction(()=>document.querySelector('#btc15-information-assessment').textContent==='');
    assert.deepEqual(await nativeSnapshot(),native);passed.push('disconnect clears information, native cards unchanged');
    for(const next of ['wait','expired','future','slow']){
      mode=next;await sleep(1300);assert.equal(await panel.textContent(),'');
      assert.deepEqual(await nativeSnapshot(),native);passed.push(next+' fails closed');
    }
    mode='fresh';await page.waitForFunction(()=>document.querySelector('#btc15-information-assessment').textContent.includes('81.0%'));
    mode='replay';await sleep(1400);assert.equal(await panel.textContent(),'');passed.push('old HTTP body/nonce cannot revive on reconnect');
    mode='fresh';await page.waitForFunction(()=>document.querySelector('#btc15-information-assessment').textContent.includes('81.0%'));
    await page.evaluate(()=>dispatchEvent(new Event('pagehide')));assert.equal(await panel.textContent(),'');
    mode='disconnect';await page.evaluate(()=>dispatchEvent(new Event('pageshow')));await sleep(1000);
    assert.equal(await panel.textContent(),'');passed.push('page lifecycle/bfcache invalidates token');
    const tokens=await page.evaluate(()=>{
      const p={schema:'BTC15_INFORMATION_V1',authority:'INFORMATIONAL_READ_ONLY',status:'AVAILABLE',orders:false,
        signal_only:true,checked_ts:100,display_until:101,expires_at:102,brti_source_ts:98};
      const token=captureInformation(p,100,110);
      return [informationView(token,120).status,informationView(JSON.parse(JSON.stringify(token)),120).status,
              informationView(token,1200).status];
    });
    assert.deepEqual(tokens,['AVAILABLE','WAIT','WAIT']);passed.push('serialized token and browser timer expiry');
    assert.deepEqual(await nativeSnapshot(),native);
    console.log(JSON.stringify({schema:'BTC15_INFORMATION_BROWSER_V1',browser:await browser.version(),
      tests:passed.length,passed,information_requests:calls,native_cards_unchanged:true,external_network_blocked:true},null,2));
  } finally {if(browser)await browser.close();server.kill('SIGTERM');fs.rmSync(temp,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
