/* Actual assembled scripts and layout. Synthetic transport; not physical Safari. */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'qualification/v2_product_20261004');
const manifest=JSON.parse(fs.readFileSync(path.join(out,'dashboard/manifest.json')));
const widths=[390,430,820,1180,700,701,1100,1101];

(async()=>{
  const browser=await chromium.launch({headless:true}),results=[];
  let negativeControl=null;
  try{
    for(const width of widths){
      const context=await browser.newContext({viewport:{width,height:932},isMobile:width<500,hasTouch:width<1101,deviceScaleFactor:1});
      const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
      try{
        for(const state of ['fresh','revalidated','pending','unavailable']){
          await page.goto(pathToFileURL(path.join(out,'browser_fixture.html')).href+(state==='fresh'?'':'#'+state));
          const qualified=['fresh','revalidated'].includes(state);
          const expected=qualified?'UNLOCKED / PASS':'UNAVAILABLE';
          await page.waitForFunction(text=>document.getElementById('finalAction').textContent===text,expected);
          await page.waitForFunction(state=>document.getElementById('scalpState').textContent===(state==='unavailable'?'UNAVAILABLE':'EXIT')&&document.getElementById('upOdds').textContent===(state==='unavailable'?'Unavailable':'35.0¢'),state);
          if(state==='revalidated')await page.waitForFunction(()=>document.getElementById('finalReason').textContent.includes('fresh evidence confirms'));
          const measured=await page.evaluate(owned=>{
            const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};};
            const text=id=>document.getElementById(id).textContent;
            return {fullText:document.body.innerText,height:document.documentElement.scrollHeight,scripts:[...document.scripts].map(s=>s.src).filter(Boolean),width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
              final:text('finalAction'),early:text('earlyState'),scalp:text('scalpState'),up:text('upOdds'),down:text('downOdds'),
              scalpBounds:rect(document.getElementById('scalpCard')),
              quotes:[...document.querySelectorAll('.odds')].map(e=>({box:rect(e),children:[...e.children].map(c=>({...rect(c),scrollWidth:c.scrollWidth,clientWidth:c.clientWidth}))})),
              cards:[...document.querySelectorAll('article.card')].map((e,i)=>({id:e.id||e.className+'-'+i,...rect(e)})).filter(r=>r.width&&r.height),
              actions:owned.map(id=>{const elements=document.querySelectorAll('#'+CSS.escape(id));const e=elements[0];
                return {id,count:elements.length,...rect(e),fontSize:parseFloat(getComputedStyle(e).fontSize)};})};
          },manifest.owned_action_ids);
          assert.doesNotMatch(measured.fullText,/NOT CONNECTED|not connected|RSI|MACD|SMA|SIGNAL STRENGTH|EVIDENCE SCORE|MARKET MOMENTUM/i);
          assert.equal(manifest.legacy_scripts,0);assert.equal(Object.keys(manifest.visible_widget_sources).length,5);
          assert.ok(measured.scrollWidth<=width+1,`Document overflow at ${width}`);
          for(const card of measured.cards){
            assert.ok(card.x>=-1&&card.x+card.width<=width+1,`Clipped card at ${width}: ${JSON.stringify(card)}`);
          }
          for(const quote of measured.quotes)for(const child of quote.children){
            assert.ok(child.x>=quote.box.x&&child.x+child.width<=quote.box.x+quote.box.width,`Clipped quote content at ${width}`);
            assert.ok(child.scrollWidth<=child.clientWidth+1,`Clipped quote text at ${width}`);
          }
          for(let i=0;i<measured.cards.length;i++)for(let j=i+1;j<measured.cards.length;j++){
            const a=measured.cards[i],b=measured.cards[j];
            const dx=Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x);
            const dy=Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y);
            assert.ok(dx<=1||dy<=1,`Overlapping cards at ${width}: ${a.id}, ${b.id}`);
          }
          for(const a of measured.actions){
            assert.equal(a.count,1,`Duplicate owner ${a.id}`);
            if(a.width&&a.height)assert.ok(a.x>=-1&&a.x+a.width<=width+1,`Clipped action ${a.id} at ${width}`);
          }
          // Explicit regression for the original 820px offscreen SCALP failure.
          if(width===820){
            assert.ok(measured.scalpBounds.x>=0);
            assert.ok(measured.scalpBounds.x+measured.scalpBounds.width<=820);
            for(const id of ['finalAction','earlyState','scalpState','upOdds','downOdds','flipRisk']){
              assert.ok(measured.actions.find(a=>a.id===id).fontSize>=12,`Unreadable tablet text: ${id}`);
            }

          }
          assert.equal(measured.scalp,state!=='unavailable'?'EXIT':'UNAVAILABLE');
          assert.equal(measured.up,state!=='unavailable'?'35.0¢':'Unavailable');
          assert.equal(measured.down,state!=='unavailable'?'66.0¢':'Unavailable');
          if(qualified){
            await page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));
            assert.equal(await page.locator('#earlyState').textContent(),'UNAVAILABLE');
            await page.evaluate(()=>window.dispatchEvent(new Event('pageshow')));
            await page.waitForFunction(()=>document.getElementById('finalAction').textContent==='UNLOCKED / PASS');
            assert.equal(await page.locator('#scalpState').textContent(),'EXIT');
          }
          assert.deepEqual(errors,[]);
          const vertical=[];for(let y=0;y<measured.height;y+=700){await page.evaluate(y=>scrollTo(0,y),y);vertical.push(await page.evaluate(()=>({top:scrollY,bottom:scrollY+innerHeight})));}
          assert.ok(vertical.at(-1).bottom>=measured.height);await page.evaluate(()=>scrollTo(0,0));
          measured.vertical_coverage=vertical;
          await page.screenshot({path:path.join(out,`render-${width}-${state}.png`),fullPage:true});
          results.push({viewport:width,state,status:'PASS',...measured,lifecycle:'PASS',errors});
        }
      }finally{await context.close();}
    }
    const report={status:'PASS',evidence_class:'SYNTHETIC_RENDERED_BROWSER',engine:'Chromium',
      physical_safari:'NOT_TESTED_REQUIRES_LIVE_DEVICE_ACCEPTANCE',negative_control:negativeControl,results};
    fs.writeFileSync(path.join(out,'rendered_ui_results.json'),JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify({status:'PASS',viewports:widths,scenarios:results.length,negative_control:negativeControl}));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
