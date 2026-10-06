const { chromium } = require('playwright');
const fs = require('fs');

const URL = 'https://btc-15min-bot-production.up.railway.app/';
const IDS = [
  'currentContract','liveStatus',
  'finalSide','finalConfidence','finalAction','finalActionSub','finalReason','finalBuyZone','finalHoldZone','finalWatchZone','finalProtectZone','finalExitZone',
  'earlyState','earlyTitle','earlyEntry','earlyYourEntry','earlyCurrentPrice','earlyEdge','earlyAfterEntry','earlyLadderEntry','earlyLadderHold','earlyLadderWatch','earlyLadderProtect','earlyLadderExit','earlyFlow',
  'flipRisk','flipRiskSub','signalStrength','contextBanner',
  'scalpState','scalpTitle','scalpEntry','scalpYourEntry','scalpCurrentPrice','scalpTargetStrip','scalpLadderEntry','scalpLadderHold','scalpLadderWatch','scalpLadderProtect','scalpLadderExit','scalpFlow',
  'evidenceScore','momentumBadge','momentumSub','contextTrend','contextRange','contextBrti','contextLevels'
];

(async()=>{
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:390,height:844}});
  const consoleErrors=[],pageErrors=[],network=[];
  page.on('console',m=>{ if(m.type()==='error') consoleErrors.push({t:Date.now(),text:m.text()}); });
  page.on('pageerror',e=>pageErrors.push({t:Date.now(),text:String(e)}));
  page.on('response',async r=>{
    const u=r.url();
    if(!u.includes('/ladders') && !u.endsWith('/information') && !u.endsWith('/dashboard_state.json')) return;
    const item={t:Date.now(),url:u,status:r.status()};
    try{
      const ct=r.headers()['content-type']||'';
      if(ct.includes('json')){
        const j=await r.json();
        item.body={
          status:j.status,reason:j.reason,contract:j.contract||j.ticker,
          served_ts:j.served_ts,published_ts:j.published_ts,expires_at:j.expires_at,
          early:j.early&&{guidance:j.early.guidance,side:j.early.side,pass_reasons:j.early.pass_reasons},
          final:j.final&&{ready:j.final.ready,side:j.final.side,confidence:j.final.confidence,probability_up:j.final.probability_up,probability_down:j.final.probability_down},
          guidance:j.guidance,diagnostics:j.diagnostics,presentation_information:j.presentation_information
        };
      }
    }catch{}
    network.push(item);
  });
  await page.goto(URL,{waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForTimeout(2500);
  const started=Date.now(),duration=90000,interval=100;
  const transitions=[],counts={},last={};
  while(Date.now()-started<duration){
    const snap=await page.evaluate(ids=>Object.fromEntries(ids.map(id=>[id,document.getElementById(id)?.textContent??null])),IDS);
    const rel=Date.now()-started;
    for(const [id,value] of Object.entries(snap)){
      const key=id+'\u0000'+value;
      counts[key]=(counts[key]||0)+1;
      if(last[id]!==value){ transitions.push({ms:rel,id,from:last[id]??null,to:value}); last[id]=value; }
    }
    await page.waitForTimeout(interval);
  }
  const grouped={};
  for(const [k,n] of Object.entries(counts)){
    const [id,value]=k.split('\u0000'); (grouped[id]??=[]).push({value,count:n});
  }
  for(const arr of Object.values(grouped)) arr.sort((a,b)=>b.count-a.count);
  const out={url:URL,userAgent:await page.evaluate(()=>navigator.userAgent),started_at:new Date(started).toISOString(),duration_ms:Date.now()-started,
    final:last,transitions,counts:grouped,network,consoleErrors,pageErrors};
  fs.writeFileSync('live-dom-probe.json',JSON.stringify(out,null,2));
  console.log(JSON.stringify({
    transitionCount:transitions.length,
    networkCount:network.length,
    consoleErrors:consoleErrors.length,pageErrors:pageErrors.length,
    top:Object.fromEntries(Object.entries(grouped).map(([id,arr])=>[id,arr.slice(0,5)]))
  },null,2));
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});

// rerun-after-early50-stability

// rerun-after-isolated-freshness-553a
