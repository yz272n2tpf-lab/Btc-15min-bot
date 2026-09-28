'use strict';const assert=require('assert');const {dashboardView}=require('./btc15_dashboard_adapter_v1');
const base={signal_only:true,orders:false,ticker:'T',seconds_left:420,final_status:'PASS',five_minute_caution:false,three_minute_guard:false,early:{provisional_candidate:false}};
let v=dashboardView(base,{authority:'INFORMATIONAL_READ_ONLY',status:'AVAILABLE',signal_only:true,orders:false,ticker:'T',probability_up:.99,probability_down:.01,flip_risk_pct:1,up_bid:.98,up_ask:.99,down_bid:.01,down_ask:.02,target:100,brti_agrees:true});
assert.equal(v.final.state,'PASS');assert.equal(v.final.probability_up,.99); // probability cannot manufacture FINAL
assert.equal(dashboardView({...base,orders:true},null).status,'DATA_STALE');
assert.equal(dashboardView(base,{authority:'INFORMATIONAL_READ_ONLY',status:'AVAILABLE',signal_only:true,orders:false,ticker:'WRONG',probability_up:.99}).final.probability_up,null);
v=dashboardView({...base,final_status:'FINAL CALL',final_side:'UP'},null);assert.equal(v.final.state,'UP');
v=dashboardView({...base,seconds_left:170,three_minute_guard:true},null);assert.equal(v.risk.phase,'3M_GUARD');
// Missing/incomplete authority must fail closed.
for(const bad of [null,{}, {...base,ticker:''},{...base,seconds_left:NaN},{...base,signal_only:false}]){
  assert.equal(dashboardView(bad,null).status,'DATA_STALE');
}
// Rollover: old informational ticker must never decorate the new authoritative contract.
v=dashboardView({...base,ticker:'NEW'},{authority:'INFORMATIONAL_READ_ONLY',status:'AVAILABLE',signal_only:true,orders:false,ticker:'OLD',probability_up:.99,probability_down:.01});
assert.equal(v.ticker,'NEW');assert.equal(v.final.probability_up,null);assert.equal(v.final.state,'PASS');
// Explicit stale information cannot renew a previous display.
v=dashboardView(base,{authority:'INFORMATIONAL_READ_ONLY',status:'WAIT',signal_only:true,orders:false,ticker:'T',probability_up:.99});
assert.equal(v.final.probability_up,null);
// Entry display bands do not create qualification; only already-qualified EARLY is classified.
assert.equal(dashboardView({...base,early:{provisional_candidate:false,entry_ask:.30}},null).entry.state,'WAIT');
assert.equal(dashboardView({...base,early:{provisional_candidate:true,entry_ask:.30}},null).entry.state,'IDEAL');
assert.equal(dashboardView({...base,early:{provisional_candidate:true,entry_ask:.44}},null).entry.state,'GOOD');
assert.equal(dashboardView({...base,early:{provisional_candidate:true,entry_ask:.70}},null).entry.state,'CAUTION');
// Scalp/reversal likewise require authoritative qualification.
assert.equal(dashboardView({...base,true_scalp:{qualified:false,side:'UP',entry:.30}},null).scalp.state,'PASS');
assert.equal(dashboardView({...base,true_scalp:{qualified:true,side:'UP',entry:.30,exit:.45}},null).scalp.state,'SCALP');
assert.equal(dashboardView({...base,true_scalp:{qualified:true,reversal:true,side:'DOWN',entry:.35,exit:.50}},null).scalp.state,'REVERSAL');
console.log('dashboard adapter tests: OK');
