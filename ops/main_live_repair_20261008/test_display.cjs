/* Presentation transitions using the existing real owner/capture harness.
   VM DOM assertions are NOT browser or visual validation. No network. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../cockpit_candidate');
process.env.BTC15_TEST_ROOT=root;
process.env.BTC15_OWNER_TEST_OUTPUT=process.env.BTC15_OWNER_TEST_OUTPUT||path.resolve(__dirname,'../../../display-validation');
process.env.BTC15_DIAGNOSTIC_DIR=process.env.BTC15_DIAGNOSTIC_DIR||path.join(__dirname,'fixtures');
const code=fs.readFileSync(path.join(root,'test_surgical.cjs'),'utf8');
const context=vm.createContext({require,process,console,Buffer,URL,AbortController,structuredClone,setImmediate,
  __dirname:root,module:{exports:{}}});
vm.runInContext(code.slice(0,code.indexOf('async function main(){'))+
  '\nmodule.exports={harness,capture,deliver,advance,fields,rungs,slot,assertProjection,plain};',context);
const {harness,capture,deliver,advance,fields,rungs,slot,plain}=context.module.exports;
function assertProjection(h){
  const v=h.last,l=v.lanes,expected=require(path.join(root,'adapter.js')).project({
    main:l.main.eligible?l.main.current_payload:{status:'UNAVAILABLE',official_identity:v.identity,reason:l.main.reason_code},
    scalp:l.scalp.eligible?l.scalp.current_payload:null,quote:l.quote.eligible?l.quote.current_payload:null});
  for(const id of ['final-action','early-action','early-price','scalp-action','scalp-price','up-buy','down-buy'])assert.equal(fields(h)[id],expected.fields[id]);
  assert.deepEqual(JSON.parse(JSON.stringify(rungs(h))),expected.activeRungs);
}
const results={mode:'OFFLINE_REAL_OWNER_AND_VM_DOM',browser_visual:'BLOCKED; NOT A VISUAL PASS',checks:[],network_requests:0};
async function run(){
  const h=harness('candidate');h.now=40;
  await deliver(h,'main',capture('relay-main'));await deliver(h,'scalp',capture('direct-scalp'));await deliver(h,'quote',capture('relay-quotes'));
  const current=plain(h.last),identityNode=h.nodes.get('identity-details').children[0];
  assertProjection(h);assert.equal(fields(h)['final-action'],'PASS');
  assert.match(fields(h)['final-freshness'],/^CURRENT/);assert.match(fields(h)['health-main'],/^CURRENT · PASS/);
  assert.match(fields(h)['health-status'],/reported diagnostics/);
  assert.equal(h.nodes.get('explanation-details').children[0].children[1].textContent,
    require(path.join(root,'adapter.js')).project({main:current.lanes.main.current_payload,scalp:current.lanes.scalp.current_payload,quote:current.lanes.quote.current_payload}).fields['final-reason']);
  results.checks.push('CURRENT/PASS separated from service uptime; full source explanation retained in Details');
  await advance(h,Math.max(current.lanes.main.lease.deadline,current.lanes.scalp.lease.deadline,current.lanes.quote.lease.deadline)-h.now);
  assertProjection(h);assert.equal(fields(h)['final-action'],'Action unavailable');
  assert.match(fields(h)['final-freshness'],/^REFRESHING/);assert.match(fields(h)['final-retained'],/^LAST QUALIFIED/);
  const expired=require(path.join(root,'adapter.js')).project({main:{status:'UNAVAILABLE',official_identity:h.last.identity}});
  for(const id of ['final-direction','final-probability','final-lock'])assert.equal(fields(h)[id],expired.fields[id]);
  assert.equal(slot(h),'UP');assert.equal(rungs(h)['scalp-up'],null);
  results.checks.push('Expired FINAL outcome/lock cleared from current fields; same-contract history separate; SCALP placement retained without active rungs');
  // Pure renderer recovery fixture: restore an accepted current owner state.
  // The original capture clocks are untouched; this does not claim new receipt.
  h.context.BTC15Cockpit.renderResolved(current);
  assert.equal(fields(h)['final-action'],'PASS');assert.match(fields(h)['final-freshness'],/^CURRENT/);
  assert.equal(h.nodes.get('final-retained').hidden,true);assert.equal(h.nodes.get('identity-details').children[0],identityNode);
  results.checks.push('Renderer recovery restores native action only and preserves disclosure nodes');
  const failure=plain(current);failure.lanes.main.eligible=false;failure.lanes.main.reason_code='JOURNAL_FAILURE:OSError';failure.lanes.main.selection='retained';
  h.context.BTC15Cockpit.renderResolved(failure);
  assert.match(fields(h)['final-freshness'],/^UNAVAILABLE/);assert.match(fields(h)['early-freshness'],/^UNAVAILABLE/);
  assert.equal(fields(h)['final-action'],'Action unavailable');assert.equal(fields(h)['early-action'],'Action unavailable');
  results.checks.push('Explicit producer failure is UNAVAILABLE, not an asserted healthy refresh');
  const rollover=plain(failure);rollover.identity={...rollover.identity,contract:'NEW_CONTRACT',official_open:rollover.identity.official_open+900,official_close:rollover.identity.official_close+900};
  for(const lane of Object.values(rollover.lanes)){lane.eligible=false;lane.current_payload=null;lane.selection='none';}
  h.context.BTC15Cockpit.renderResolved(rollover);
  for(const id of ['final-retained','early-retained','scalp-retained','quote-retained'])assert.equal(h.nodes.get(id).hidden,true);
  assert.equal(slot(h),'neutral');assert.deepEqual(JSON.parse(JSON.stringify(rungs(h))),{early:null,'scalp-up':null,'scalp-down':null});
  assert.equal(fields(h)['early-exit'],'Unsupported');
  results.checks.push('Rollover excludes every prior-contract history/action; five-rung order and unsupported EARLY exit preserved');
  results.passed=true;
  fs.writeFileSync(path.join(__dirname,'display_results.json'),JSON.stringify(results,null,2)+'\n');console.log(JSON.stringify(results,null,2));
}
run().catch(e=>{results.passed=false;results.failure=e.stack;fs.writeFileSync(path.join(__dirname,'display_results.json'),JSON.stringify(results,null,2));console.error(e);process.exitCode=1;});
