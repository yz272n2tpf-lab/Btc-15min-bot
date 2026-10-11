const {test}=require('node:test'),fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
function harness(){
  let now=1000;const window={addEventListener(){}},document={visibilityState:'visible',getElementById:()=>null,querySelectorAll:()=>[],addEventListener(){}};
  const context={window,document,performance:{now:()=>now},console,structuredClone,Intl,AbortController,
    fetch:()=>new Promise(()=>{}),setInterval(){},setTimeout(){},clearTimeout(){}};
  const path=process.env.AUDIT_BASELINE_DIR?process.env.AUDIT_BASELINE_DIR+'/ladder_owner.js':__dirname+'/owners/ladder_owner.js';
  vm.runInNewContext(fs.readFileSync(path,'utf8').replace(/\}\)\(\);\s*$/,
    'window.audit={accept:(lane,d)=>{caches[lane]=accept(lane,d,performance.now()-1,performance.now());render();},poll,invalidate,render};})();'),context);
  vm.runInNewContext(fs.readFileSync(__dirname+'/fixtures.js','utf8'),context);
  const d=structuredClone(window.BTC15_REVIEW_SAMPLES[3].quote);
  return {window,d,document,fetch:fn=>context.fetch=fn,now:x=>now=x,view:()=>window.BTC15LadderOwner.getResolvedView()};
}
test('older publication cannot replace newer unavailable response or retained quote',()=>{
  const h=harness(),a=h.window.audit,d=h.d;a.accept('quote',d);
  const gap={...d,status:'UNAVAILABLE',reason:'SOURCE_EXPIRED',served_ts:d.served_ts+1};delete gap.published_ts;
  a.accept('quote',gap);
  assert.throws(()=>a.accept('quote',{...d,published_ts:d.published_ts-.01,accepted_ts:d.accepted_ts-.01,
    exchange_ts:d.exchange_ts-.01,expires_at:d.expires_at-.01,served_ts:d.served_ts+2}),/ROLLBACK/);
  assert.equal(h.view().lanes.quote.eligible,false);
  assert.equal(h.view().lanes.quote.retained_payload.exchange_ts,d.exchange_ts);
});
test('quote sequence floor survives invalidate; malformed response cannot change identity',()=>{
  const h=harness(),a=h.window.audit,d=h.d;a.accept('quote',d);a.invalidate();
  assert.equal(h.view().identity,null);assert.deepEqual(h.view().display_identity,d.official_identity);
  assert.equal(h.view().lanes.quote.eligible,false);
  assert.throws(()=>a.accept('quote',{...d,published_ts:d.published_ts+1,served_ts:d.served_ts+1,sequence:d.sequence-1}),/ROLLBACK/);
  a.accept('quote',d);const old=h.view().identity;
  assert.throws(()=>a.accept('quote',{...d,official_identity:{...d.official_identity,target:d.official_identity.target+1},up_ask:NaN}),/CONFLICT|VALUES/);
  a.render();assert.deepEqual(h.view().identity,old);
});
test('partial response fails closed without erasing last quote; delayed pre-resume reply is ignored',async()=>{
  const h=harness(),a=h.window.audit,d=h.d;a.accept('quote',d);a.invalidate();
  const pending=[];h.fetch(()=>new Promise(resolve=>pending.push(resolve)));
  const first=a.poll('quote','/ladders/quotes');a.invalidate();
  const second=a.poll('quote','/ladders/quotes');
  const newer={...d,published_ts:d.published_ts+1,accepted_ts:d.accepted_ts+1,
    exchange_ts:d.exchange_ts+1,expires_at:d.expires_at+1,served_ts:d.served_ts+1,sequence:d.sequence+1};
  pending[1]({ok:true,json:async()=>newer});await second;
  pending[0]({ok:true,json:async()=>d});await first;
  assert.equal(h.view().lanes.quote.current_payload.sequence,newer.sequence);
  h.fetch(async()=>({ok:true,json:async()=>({status:'AVAILABLE'})}));await a.poll('quote','/ladders/quotes');
  assert.equal(h.view().lanes.quote.eligible,false);
  assert.equal(h.view().lanes.quote.reason_code,'SAFETY_SCHEMA');
  assert.equal(h.view().lanes.quote.retained_payload.sequence,newer.sequence);
  assert.equal(h.view().identity.contract,newer.official_identity.contract);
});
