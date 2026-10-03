/* Small DOM contract check against real generated card IDs and production JS. */
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
(async()=>{
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const html=fs.readFileSync(process.argv[3],'utf8');
const ids=[...html.matchAll(/id="([^"]+)"/g)].map(x=>x[1]);
const nodes=Object.fromEntries(ids.map(id=>[id,{textContent:'',className:''}]));
const listeners={},intervals=[];let now=0;
const document={visibilityState:'visible',getElementById:id=>nodes[id]||null,addEventListener:(n,f)=>{listeners[n]=f;}};
const window={addEventListener:(n,f)=>{listeners[n]=f;}};
const script=fs.readFileSync('btc15_ladder_panel_v1.js','utf8').replace('__V81_LADDERS_URL__','"https://v81.test/ladders"');
const sandbox={document,window,performance:{now:()=>now},AbortSignal:{timeout:()=>({})},setInterval:f=>intervals.push(f),
  fetch:async url=>({ok:true,json:async()=>JSON.parse(JSON.stringify(url.includes('v81.test')?fixture.scalp:fixture.main))})};
vm.runInNewContext(script,sandbox);
await new Promise(r=>setImmediate(r));
assert.equal(nodes.earlyState.textContent,'HOLD');assert.equal(nodes.scalpState.textContent,'EXIT');
assert.match(nodes.scalpLadderExit.textContent,/current BID 68.0¢ · trigger BID 68.0¢/);
assert.match(nodes.scalpYourEntry.textContent,/35.0¢/);assert.match(nodes.finalActionSub.textContent,/UP 85.0% · DOWN 15.0%/);
assert.match(nodes.scalpFlow.textContent,/NO ORDERS/);
// Monotonic expiry, independently of local wall-clock settings or page polls.
now=6000;window.btc15RenderLadders();assert.equal(nodes.scalpState.textContent,'UNAVAILABLE');
assert.equal(nodes.scalpCurrentPrice.textContent,'Unavailable');
// Different candidate identity cannot render actionable guidance.
fixture.scalp.candidate='WRONG';intervals[0]();await new Promise(r=>setImmediate(r));
assert.equal(nodes.scalpState.textContent,'UNAVAILABLE');
document.visibilityState='hidden';listeners.visibilitychange();assert.equal(nodes.earlyState.textContent,'UNAVAILABLE');
console.log('PASS: existing cards, independent probabilities, linked HOLD, latched EXIT/current bid, identity and monotonic expiry');
})().catch(e=>{console.error(e);process.exit(1);});
