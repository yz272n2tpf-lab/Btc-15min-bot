/* Offline DOM regressions for the October 11 production incident.
 * npm install --prefix /tmp/btc15-test-env --no-audit --no-fund linkedom@0.18.12
 * NODE_PATH=/tmp/btc15-test-env/node_modules node cockpit_candidate/test_live_refresh_audit.cjs
 * AUDIT_BASELINE_DIR may point at unchanged release JS to reproduce failures.
 */
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),{parseHTML}=require('linkedom');
const file=name=>fs.readFileSync((process.env.AUDIT_BASELINE_DIR||__dirname)+'/'+name,'utf8');
function harness(){
  const {document}=parseHTML(fs.readFileSync(__dirname+'/index.html','utf8'));
  let resolved,market=null,info=null,receiveInfo,receiveMarket;
  const window={document,scrollBy(){},BTC15LadderOwner:{getResolvedView:()=>resolved},
    BTC15MarketViewOwner:{getResolvedView:()=>market,subscribe:f=>(receiveMarket=f,()=>{})},
    BTC15InformationOwner:{getResolvedView:()=>info,subscribe:f=>(receiveInfo=f,()=>{})},
    BTC15CockpitLive:{connect:()=>()=>{}}};
  const c=vm.createContext({window,document,performance:{now:()=>1000},console});
  for(const f of ['adapter.js','fixtures.js'])vm.runInContext(fs.readFileSync(__dirname+'/'+f,'utf8'),c);
  for(const f of ['trade_records.js','cockpit.js'])vm.runInContext(file(f),c);
  window.BTC15Cockpit.connectResolved();
  const sample=window.BTC15_REVIEW_SAMPLES[3];
  resolved={identity:sample.main.official_identity,lanes:{}};
  for(const name of ['main','scalp','quote']){
    const p=sample[name];resolved.lanes[name]={eligible:!!p,current_payload:p,retained_payload:p,payload:p,selection:p?'current':'none'};
  }
  return {document,window,resolved,render:()=>window.BTC15Cockpit.renderResolved(resolved),
    text:id=>document.getElementById(id).textContent,
    information:x=>{info=x;receiveInfo(x);},market:x=>{market=x;receiveMarket(x);}};
}
test('FINAL probability and quotes survive source expiry as timestamped history, without authority',()=>{
  const h=harness();h.render();const ids=['final-direction','final-probability','up-buy','down-buy'];
  const before=ids.map(h.text);
  for(const l of Object.values(h.resolved.lanes)){l.eligible=false;l.current_payload=null;l.reason_code='SOURCE_EXPIRED';l.selection='retained';}
  h.render();assert.deepEqual(ids.map(h.text),before);
  assert.match(h.text('final-freshness'),/STALE.*original publication/);
  assert.match(h.text('quote-status'),/STALE.*source.*no executable/);
  assert.doesNotMatch(h.text('final-lock'),/^QUALIFIED LOCK$/);
  assert.ok([...h.document.querySelectorAll('[aria-current]')].length===0);
  for(let i=0;i<100;i++)h.render();assert.deepEqual(ids.map(h.text),before);
  h.resolved.lanes.main.reason_code='BRTI_SOURCE_UNAVAILABLE';h.render();
  assert.match(h.text('final-freshness'),/UNAVAILABLE.*BRTI SOURCE UNAVAILABLE/);
  assert.deepEqual(ids.map(h.text),before);
  h.resolved.display_identity=h.resolved.identity;h.resolved.identity=null;h.render();
  assert.deepEqual(ids.map(h.text),before);assert.match(h.text('contract-window'),/LAST VERIFIED/);
  assert.ok([...h.document.querySelectorAll('[aria-current]')].length===0);
  h.resolved.identity=h.resolved.display_identity;
  h.resolved.identity={...h.resolved.identity,contract:'NEXT'};h.render();
  assert.ok(ids.map(h.text).every(v=>!before.includes(v)),'confirmed new identity clears contract-specific display');
});
test('BTC spot and BRTI retain timestamped history and cannot regress on older responses',()=>{
  const h=harness(),id=h.resolved.identity;
  const payload={ticker:id.contract,target:id.target,probability_up:.6,probability_down:.4,
    checked_ts:100,published_ts:99,btc_source_ts:98,brti_source_ts:99,btc_price:80020,brti_value:80021};
  const empty={labels:{status:'WAIT',assessment:'Unavailable'},current:{assessment:null}};
  h.information({...empty,current:{assessment:payload},delivery:{payload,requestStartedMs:1000}});
  const before=h.text('spot-price'),brtiBefore=h.text('brti-latest');h.information({...empty,retained_source:{payload}});
  assert.equal(h.text('spot-price'),before);assert.match(h.text('spot-age'),/STALE.*source.*1970/);
  assert.equal(h.text('brti-latest'),brtiBefore);assert.match(h.text('brti-latest-age'),/STALE.*source.*1970/);
  const older={...payload,btc_price:79000,btc_source_ts:97,brti_value:79001,brti_source_ts:98};
  h.information({...empty,current:{assessment:older},delivery:{payload:older,requestStartedMs:1000}});
  assert.equal(h.text('spot-price'),before);assert.doesNotMatch(h.text('spot-age'),/^CURRENT/);
  assert.equal(h.text('brti-latest'),brtiBefore);assert.doesNotMatch(h.text('brti-latest-age'),/^CURRENT/);
  h.information({...empty,labels:{...empty.labels,status:'UNAVAILABLE · SOURCE_OUTAGE'}});
  assert.match(h.text('brti-latest-age'),/UNAVAILABLE.*SOURCE_OUTAGE/);
  h.resolved.identity={...id,contract:'NEXT'};h.information(empty);
  assert.equal(h.text('spot-price'),'Unavailable');assert.equal(h.text('brti-latest'),'Unavailable');
});
test('SVG root and existing path survive a changed chart sample',()=>{
  const h=harness(),i=h.resolved.identity;
  const m={contract:i.contract,source:{target:i.target},clock:{closeMs:i.official_close*1000},
    brti:{price_state:'stale',label:'STALE'},values:{},lower:{history:{}},chart:{contract:i.contract,
      svg:'<svg viewBox="0 0 100 50"><path d="M0 0L10 10"/></svg>'}};
  h.market(m);const root=h.document.querySelector('#chart-surface svg'),path=root.firstElementChild;
  h.market({...m,chart:{...m.chart,svg:'<svg viewBox="0 0 100 50"><path d="M0 0L11 12"/></svg>'}});
  assert.ok(h.document.querySelector('#chart-surface svg')===root,'stable SVG root');
  assert.ok(root.firstElementChild===path,'stable path');assert.equal(path.getAttribute('d'),'M0 0L11 12');
});
test('expired record is historical during same-contract identity retention',()=>{
  const trade=require(process.env.AUDIT_BASELINE_DIR?process.env.AUDIT_BASELINE_DIR+'/trade_records.js':'./trade_records.js');
  const id={contract:'KXBTC15M-CURRENT',target:80000,official_open:0,official_close:900};
  const r={issued_buy:true,origin_id:'a'.repeat(64),side:'UP',original_ask:.05,signal_ts:870,open_ts:0,close_ts:900,target:80000,contract:id.contract,status:'EXPIRED'};
  const p=trade.project({eligible:false,issued_records:{schema:'BTC15_ISSUED_SIGNALS_V1',records:[r]}},id,'early');
  assert.equal(p.historical,true);assert.equal(p.entry,false);assert.equal(p.current,false);
  const mixed=trade.project({eligible:true,issued_records:{schema:'BTC15_ISSUED_SIGNALS_V1',records:[r],entry_authority_current:true},
    current_payload:{origin:r,early:{guidance:'ENTER'},final:{helper:{origin_id:r.origin_id},early_origin_id:r.origin_id}}},id,'early');
  assert.equal(mixed.historical,true);assert.equal(mixed.entry,false);assert.equal(mixed.current,false);
});
