'use strict';
const assert=require('assert');
const {recoveredV11View}=require('./btc15_recovered_v11_adapter_v1');
const base={signal_only:true,orders:false,ticker:'T',seconds_left:600,final_status:'PASS',final_side:'NONE'};
const info={authority:'INFORMATIONAL_READ_ONLY',status:'AVAILABLE',signal_only:true,orders:false,ticker:'T',
 probability_up:.99,probability_down:.01,flip_risk_pct:1,up_bid:.98,up_ask:.99,down_bid:.01,down_ask:.02,target:100,brti_agrees:true,
 protection_phase:'NORMAL',five_minute_caution:false,three_minute_guard:false};
let v=recoveredV11View(base,info);
assert.equal(v.final.state,'PASS'); assert.equal(v.final.display_side,'UP'); assert.equal(v.final.display_probability,.99);
assert.equal(v.early.qualified,false); assert.equal(v.scalp.state,'PASS'); // 99% informational cannot manufacture action.
v=recoveredV11View({...base,final_status:'FINAL CALL',final_side:'DOWN',final_confidence:.94,final_call_source:'TOURNAMENT WINNER'},info);
assert.equal(v.final.state,'DOWN'); assert.equal(v.final.confidence,.94);
v=recoveredV11View({...base,early:{qualified:true,side:'UP',entry_ask:.31}},info);
assert.equal(v.early.qualified,true); assert.equal(v.early.entry_quality,'IDEAL');
v=recoveredV11View({...base,early:{qualified:true,side:'UP',entry_ask:.44}},info);assert.equal(v.early.entry_quality,'GOOD');
v=recoveredV11View({...base,early:{qualified:true,side:'UP',entry_ask:.61}},info);assert.equal(v.early.entry_quality,'CAUTION');
v=recoveredV11View({...base,scalp:{qualified:true,side:'DOWN',state:'PROTECT',entry:.33,current_sell:.51,profit:.18,expected_minutes:3,protection_state:'ARMED'}},info);
assert.equal(v.scalp.state,'PROTECT');assert.equal(v.scalp.action,'PROTECT');assert.equal(v.scalp.expected_minutes,3);
v=recoveredV11View(base,{...info,ticker:'OTHER'});assert.equal(v.final.probability_up,null);assert.equal(v.risk.flip_risk_pct,null);
v=recoveredV11View(base,{...info,status:'WAIT'});assert.equal(v.final.probability_up,null);
v=recoveredV11View(base,{...info,probability_up:.08,probability_down:.92});assert.equal(v.final.display_side,'DOWN');assert.equal(v.final.display_probability,.92);
v=recoveredV11View({...base,seconds_left:170},{...info,three_minute_guard:true,protection_phase:'3M_GUARD'});assert.equal(v.risk.phase,'3M_GUARD');
console.log('RECOVERED V11 ADAPTER V1 PASS | AUTHORITY SEPARATED | UP/DOWN SYMMETRIC | FAIL-CLOSED');
