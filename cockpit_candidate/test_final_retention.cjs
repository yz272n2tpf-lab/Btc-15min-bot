/* Focused owner regression: actual native output, actual acceptance/expiry code. */
const fs=require('node:fs'),vm=require('node:vm'),cp=require('node:child_process'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/owners/ladder_owner.js','utf8');
let now=1000;
const window={addEventListener(){}},document={visibilityState:'visible',getElementById:()=>null,querySelectorAll:()=>[],addEventListener(){}};
const context={window,document,performance:{now:()=>now},console,structuredClone,Intl,AbortController,
  fetch:()=>new Promise(()=>{}),setInterval(){},setTimeout(){},clearTimeout(){}};
// Test-only closure access; production has no injection or alternate source.
vm.runInNewContext(source.replace(/\}\)\(\);\s*$/,
  'window.testReceive=(data)=>{const at=performance.now();caches.main=accept("main",data,at-1,at);render();};})();'),context);
const data=JSON.parse(cp.execFileSync('python',['-c',`
import json
from btc15_v2_product.directional import Directional
from test_btc15_supported_early import value_frame,step
from btc15_v2_product import ENVELOPE,REVISION
e=Directional();e.restore({});out={}
for name,f in [('call',value_frame(p=.96,ask=.8)),('pass',value_frame(3,p=.84,ask=.8))]:
 _,_,v=step(e,f)
 v.update(schema=ENVELOPE,product_revision=REVISION,lane='main',served_ts=v['published_ts']+.01,
   official_identity={k:v[k] for k in ('contract','target','official_open','official_close')})
 v['early_opportunity']['origin_authority']=False
 out[name]=v
print(json.dumps(out))
`],{cwd:__dirname+'/..',encoding:'utf8'}));
const view=()=>window.BTC15LadderOwner.getResolvedView();
window.testReceive(data.call);
assert.equal(view().lanes.main.eligible,true);
const call=view().lanes.main.verified_final_call;
assert.equal(call.publication_id,data.call.final.publication_id);
assert.equal(call.confidence,.96);assert.equal(call.action_authority,false);
const deadline=view().lanes.main.lease.deadline;
now=deadline+1;window.btc15RenderLadders();
assert.equal(view().lanes.main.eligible,false,'history cannot extend the original source lease');
assert.equal(view().lanes.main.current_payload,null);
assert.equal(view().lanes.main.verified_final_call.publication_id,call.publication_id);
const unavailable={...data.call,status:'UNAVAILABLE',served_ts:data.call.served_ts+6,reason:'BRTI_SOURCE_UNAVAILABLE'};
window.testReceive(unavailable);
assert.equal(view().lanes.main.eligible,false);
assert.equal(view().lanes.main.verified_final_call.publication_id,call.publication_id,'explicit source interruption preserves history only');
now+=4000;window.testReceive(data.pass);
assert.equal(view().lanes.main.eligible,true);
assert.equal(view().lanes.main.verified_final_decision.state,'PASS');
assert.equal(view().lanes.main.verified_final_call.publication_id,call.publication_id,'superseded call remains in details');
now=view().lanes.main.lease.deadline+1;window.btc15RenderLadders();
assert.equal(view().lanes.main.verified_final_decision.state,'PASS');
assert.equal(view().lanes.main.eligible,false);
now=view().identity_deadline+1;window.btc15RenderLadders();
assert.equal(view().identity,null);assert.equal(view().lanes.main.verified_final_call,null,'expired contract cannot supply headline history');
console.log('PASS: verified FINAL call survives expiry/outage without a lease; fresh PASS supersedes; rollover clears headline history');
