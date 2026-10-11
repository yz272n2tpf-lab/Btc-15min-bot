/* Explicitly read-only smoke test: local isolated cockpit relays existing GETs.
 * Start cockpit_candidate/server.py on 127.0.0.1:8765. No production writes.
 */
const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
const {spawn}=require('node:child_process');
const out=process.env.BTC15_BROWSER_OUT||'/tmp/btc15-live-browser';fs.mkdirSync(out,{recursive:true});
(async()=>{
 const proxyTransport=process.env.BTC15_TEST_PROXY_TRANSPORT==='1';
 const command=proxyTransport?[path.join(__dirname,'proxy_aware_smoke_host.py')]:[path.resolve(__dirname,'../../cockpit_candidate/server.py'),'--port','8765'];
 const server=spawn('python',command,{stdio:['ignore','pipe','pipe']});
 const log=[];server.stderr.on('data',x=>log.push(x.toString()));
 await new Promise((resolve,reject)=>{server.stdout.on('data',x=>{log.push(x.toString());if(x.toString().includes('BTC15 isolated candidate:'))resolve();});server.on('error',reject);server.on('exit',code=>reject(Error('Local server exit '+code)));});
 const b=await chromium.launch({executablePath:process.env.BTC15_CHROMIUM_PATH,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 const p=await b.newPage({viewport:{width:820,height:1180}}),errors=[],methods=[],responses=[];
 p.on('pageerror',e=>errors.push(e.message));
 p.on('request',r=>methods.push({method:r.method(),url:r.url()}));
 p.on('response',r=>{if(/ladders|information|dashboard_state/.test(r.url()))responses.push({path:new URL(r.url()).pathname,status:r.status()});});
 try{
 await p.goto('http://127.0.0.1:8765/?mode=live');
 await p.waitForFunction(()=>window.BTC15LadderOwner?.getResolvedView(),{timeout:15000});
 const observations=[];
 for(let n=0;n<40;n++){
  observations.push(await p.evaluate(()=>{
   const v=window.BTC15LadderOwner.getResolvedView(),m=window.BTC15MarketViewOwner.getResolvedView();
   const ids=['final-probability','final-freshness','quote-status','up-buy','down-buy','spot-price','spot-age','brti-latest','early-action','scalp-action','chart-note','context-status'];
   return {at:new Date().toISOString(),texts:Object.fromEntries(ids.map(id=>[id,document.getElementById(id)?.textContent])),
    identity:v.identity,eligibility:Object.fromEntries(Object.entries(v.lanes).map(([k,l])=>[k,{eligible:l.eligible,reason:l.reason_code}])),
    market:m?{contract:m.contract,target:m.source?.target,closeMs:m.clock?.closeMs,source:m.source?.source_timestamp_utc,network:m.network_healthy,qualified:m.lower?.qualified}:null};
  }));await p.waitForTimeout(500);
 }
 await p.screenshot({path:path.join(out,'isolated-live-ipad.png'),fullPage:true});
 const result={browser:b.version(),transport:proxyTransport?'LOCAL TEST urllib proxy transport; exact candidate assets':'original candidate direct HTTPS host',scope:'20-second local candidate read-only GET relay, not a full market session',errors,nonGET:methods.filter(x=>x.method!=='GET'),responses,observations};
 fs.writeFileSync(path.join(out,'live-results.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify({browser:result.browser,errors,nonGET:result.nonGET.length,samples:observations.length,
  eligibleSamples:Object.fromEntries(['main','scalp','quote'].map(k=>[k,observations.filter(x=>x.eligibility[k].eligible).length])),
  first:observations[0],last:observations.at(-1)},null,2));
 }finally{await b.close();server.kill('SIGINT');fs.writeFileSync(path.join(out,'local-server.log'),log.join(''));}
})().catch(e=>{console.error(e);process.exitCode=1;});
