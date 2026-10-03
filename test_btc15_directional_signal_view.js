// Offline renderer controls; no DOM, network, orders or new timers.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync('btc15_directional_signal_publication_v1.py','utf8');
const render = source.match(/RENDER = '''([\s\S]*?)'''/)[1];
let now = Date.parse('2026-01-01T12:05:00Z'), usable = true, brti = true;
const fields = {};
const context = {setText:(k,v)=>fields[k]=v, usableFrame:()=>usable, freshBrti:()=>brti,
                 clock:{now:()=>now}, performance:{now:()=>0}};
vm.createContext(context); vm.runInContext(render,context);
const signal = {status:'AVAILABLE',guidance:'BUY',source_timestamp_utc:'2026-01-01T12:05:00Z',
  origin:{side:'UP',origin_id:'immutable-example',contract:{ticker:'CONTRACT'},
          original_ask:.32,signal_timestamp_utc:'2026-01-01T12:05:00Z'}};
function run(changes={}) { context.renderDirectionalSignal({directional_signal:{...signal,...changes}}); }
run();assert.equal(fields.directionalSignalAction,'BUY · UP');
assert(fields.directionalSignalOrigin.includes('32.00¢'));assert(fields.directionalSignalOrigin.includes('Not a fill'));
for (const guidance of ['HOLD','PROTECT']) {run({guidance});assert.equal(fields.directionalSignalAction,guidance+' · UP');}
brti=false;run({guidance:'HOLD'});assert.equal(fields.directionalSignalAction,'UNAVAILABLE');
run({guidance:'PROTECT'});assert.equal(fields.directionalSignalAction,'UNAVAILABLE');
run();assert.equal(fields.directionalSignalAction,'BUY · UP'); // EARLY has no new BRTI alpha gate.
brti=true;usable=false;run();assert.equal(fields.directionalSignalAction,'UNAVAILABLE');
usable=true;now+=15001;run();assert.equal(fields.directionalSignalAction,'UNAVAILABLE');
now-=15002;run();assert.equal(fields.directionalSignalAction,'UNAVAILABLE');
now+=1;run({status:'UNAVAILABLE'});assert.equal(fields.directionalSignalAction,'UNAVAILABLE');
run({status:'PASS'});assert.equal(fields.directionalSignalAction,'PASS');
assert(!/fetch\(|setInterval\(|setTimeout\(/.test(render));
console.log('14 renderer assertions PASS; no network or timer added');
