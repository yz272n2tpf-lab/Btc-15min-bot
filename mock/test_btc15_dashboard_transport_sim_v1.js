'use strict';const assert=require('assert');const {dashboardView}=require('./btc15_dashboard_adapter_v1');const {DashboardLease}=require('./btc15_dashboard_transport_sim_v1');
const a={signal_only:true,orders:false,ticker:'A',seconds_left:500,final_status:'FINAL CALL',final_side:'UP',early:{provisional_candidate:false}};
const info={authority:'INFORMATIONAL_READ_ONLY',status:'AVAILABLE',signal_only:true,orders:false,ticker:'A',probability_up:.8,probability_down:.2};
let l=new DashboardLease(dashboardView,1500);assert.equal(l.view(0).status,'DATA_STALE');
l.receive(a,info,1000);assert.equal(l.view(1000).final.state,'UP');assert.equal(l.view(2499).status,'AVAILABLE');assert.equal(l.view(2500).status,'DATA_STALE');
l.receive(a,info,3000);l.disconnect();assert.equal(l.view(3001).status,'DATA_STALE');
l.receive({...a,ticker:'NEW'}, {...info,ticker:'OLD',probability_up:.99},4000);let v=l.view(4001);assert.equal(v.ticker,'NEW');assert.equal(v.final.probability_up,null);
l.receive({...a,ticker:'NEW',final_status:'PASS',final_side:null},{...info,ticker:'NEW',probability_up:.99},5000);v=l.view(5001);assert.equal(v.final.state,'PASS');assert.equal(v.final.probability_up,.99);
assert.equal(l.view(4999).status,'DATA_STALE'); // future/clock regression fails closed
console.log('dashboard transport simulation: OK');