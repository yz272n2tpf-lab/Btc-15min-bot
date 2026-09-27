'use strict';const assert=require('assert');const {dashboardView}=require('./btc15_dashboard_adapter_v1');
const base={signal_only:true,orders:false,ticker:'T',seconds_left:420,final_status:'PASS',five_minute_caution:false,three_minute_guard:false,early:{provisional_candidate:false}};
let v=dashboardView(base,{authority:'INFORMATIONAL_READ_ONLY',status:'AVAILABLE',signal_only:true,orders:false,ticker:'T',probability_up:.99,probability_down:.01,flip_risk_pct:1,up_bid:.98,up_ask:.99,down_bid:.01,down_ask:.02,target:100,brti_agrees:true});
assert.equal(v.final.state,'PASS');assert.equal(v.final.probability_up,.99); // probability cannot manufacture FINAL
assert.equal(dashboardView({...base,orders:true},null).status,'DATA_STALE');
assert.equal(dashboardView(base,{authority:'INFORMATIONAL_READ_ONLY',status:'AVAILABLE',signal_only:true,orders:false,ticker:'WRONG',probability_up:.99}).final.probability_up,null);
v=dashboardView({...base,final_status:'FINAL CALL',final_side:'UP'},null);assert.equal(v.final.state,'UP');
v=dashboardView({...base,seconds_left:170,three_minute_guard:true},null);assert.equal(v.risk.phase,'3M_GUARD');
console.log('dashboard adapter tests: OK');
