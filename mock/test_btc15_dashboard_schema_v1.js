'use strict';const fs=require('fs'),assert=require('assert');const s=JSON.parse(fs.readFileSync('mock/btc15_dashboard_view_model_v1.schema.json','utf8'));
assert.equal(s.properties.authority.const,'UI_PRESENTATION_ONLY');assert.equal(s.properties.signal_only.const,true);assert.equal(s.properties.orders.const,false);
assert.deepEqual(s.properties.entry.properties.target_max,{const:.5});assert.deepEqual(s.properties.entry.properties.ideal_min,{const:.25});assert.deepEqual(s.properties.entry.properties.ideal_max,{const:.35});
assert(s.properties.status.enum.includes('DATA_STALE'));assert(s.properties.final.properties.state.enum.includes('PASS'));
console.log('dashboard schema contract tests: OK');