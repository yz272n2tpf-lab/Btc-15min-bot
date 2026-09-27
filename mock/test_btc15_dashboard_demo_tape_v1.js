'use strict';const assert=require('assert');const {DEMO,demoAt}=require('./btc15_dashboard_demo_tape_v1');
assert.equal(DEMO[0].state,'PASS');assert.equal(demoAt(8).state,'EARLY');assert.equal(demoAt(16).state,'SCALP');assert.equal(demoAt(24).state,'UP');assert.equal(demoAt(32).state,'5M_CAUTION');assert.equal(demoAt(40).state,'3M_GUARD');assert.equal(demoAt(48).state,'LOCK_PROFIT');assert.equal(demoAt(56).state,'DATA_STALE');assert.equal(demoAt(64).state,'PASS');
for(let i=1;i<DEMO.length;i++)assert(DEMO[i].t>DEMO[i-1].t);
console.log('dashboard demo tape tests: OK');