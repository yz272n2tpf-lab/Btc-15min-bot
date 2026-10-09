/* Real renderer + unchanged native adapter. Test display writes, not a second strategy. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const adapter=require('./adapter.js'),nodes=new Map();
class Element {
  constructor(){this.children=[];this.dataset={};this.attributes={};this.writes=[];this.value='';this.open=false;}
  get textContent(){return this.value;}
  set textContent(v){this.value=String(v);this.writes.push(this.value);}
  append(...items){for(const e of items){e.remove();e.parentElement=this;this.children.push(e);}}
  remove(){if(this.parentElement){const p=this.parentElement;p.children=p.children.filter(e=>e!==this);this.parentElement=null;}}
  insertBefore(e,before){e.remove();e.parentElement=this;this.children.splice(this.children.indexOf(before),0,e);}
  after(e){this.parentElement.insertBefore(e,this.parentElement.children[this.parentElement.children.indexOf(this)+1]);}
  get previousElementSibling(){return this.parentElement?.children[this.parentElement.children.indexOf(this)-1];}
  get lastElementChild(){return this.children.at(-1);}
  setAttribute(k,v){this.attributes[k]=v;}
  removeAttribute(k){delete this.attributes[k];}
  querySelector(){return this.children.find(e=>e.tagName==='OL');}
}
const node=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
const sides={UP:new Element(),DOWN:new Element()},panel=new Element();
panel.append(node('scalp-heading'),node('scalp-guidance'),sides.UP,sides.DOWN);
for(const prefix of ['early','scalp-up','scalp-down']){
  const ol=node(prefix+'-ladder');ol.tagName='OL';
  for(const rung of ['entry','hold','watch','protect','exit']){const li=new Element();li.dataset.rung=rung;ol.append(li);}
  if(prefix!=='early')sides[prefix.endsWith('up')?'UP':'DOWN'].append(ol);
}
const document={getElementById:node,createElement:()=>new Element(),querySelector:s=>sides[s.includes('"UP"')?'UP':'DOWN']};
let resolved,market,info,receiveMarket,receiveInfo;
const window={BTC15SnapshotAdapter:adapter,
  BTC15LadderOwner:{getResolvedView:()=>resolved},
  BTC15MarketViewOwner:{getResolvedView:()=>market,subscribe:f=>(receiveMarket=f,()=>{})},
  BTC15InformationOwner:{getResolvedView:()=>info,subscribe:f=>(receiveInfo=f,()=>{})},
  BTC15CockpitLive:{connect:()=>()=>{}}};
const context={window,document,performance:{now:()=>1000},console};
vm.runInNewContext(fs.readFileSync(__dirname+'/fixtures.js','utf8'),context);
vm.runInNewContext(fs.readFileSync(__dirname+'/cockpit.js','utf8'),context);
window.BTC15Cockpit.connectResolved();
const samples=window.BTC15_REVIEW_SAMPLES;
function setSample(sample){
  resolved={identity:sample.main.official_identity,lanes:{}};
  for(const name of ['main','scalp','quote']){const p=sample[name],eligible=!!p&&['AVAILABLE','PASS'].includes(p.status);
    resolved.lanes[name]={eligible,current_payload:p,retained_payload:eligible?p:null,payload:p,selection:eligible?'current':'none'};}
}
const render=()=>window.BTC15Cockpit.renderResolved(resolved);
const clearWrites=()=>{for(const e of nodes.values())e.writes=[];};
setSample(samples[0]);render();
const explanatory=['final-reason','early-reason','scalp-reason','scalp-up-status','scalp-down-status','health-status','health-quotes','health-continuity','flip-risk'];
const original=Object.fromEntries(explanatory.map(id=>[id,node(id).textContent]));
clearWrites();for(let n=0;n<100;n++)render();
for(const id of explanatory)assert.equal(node(id).writes.length,0,id+' must not alternate between writers');
const qualified=structuredClone(resolved);
for(const lane of Object.values(resolved.lanes)){lane.eligible=false;lane.current_payload=null;lane.selection='retained';lane.reason_code='SOURCE_EXPIRED';}
render();
for(const name of ['final','early','scalp']){
  assert.equal(node(name+'-reason').textContent,original[name+'-reason']);
  assert.equal(node(name+'-reason').dataset.displayState,'retained');
  assert.match(node(name+'-freshness').textContent,/no current action authority\nLAST QUALIFIED.*historical/);
  assert.equal(node(name+'-action').textContent,'Action unavailable');
}
for(const p of ['early','scalp-up','scalp-down'])assert.ok(node(p+'-ladder').children.every(e=>!e.attributes['aria-current']));
for(const side of ['up','down']){
  assert.equal(node('scalp-'+side+'-status').textContent,original['scalp-'+side+'-status'],'side explanation remains stable through expiry');
  assert.match(node('scalp-'+side+'-freshness').textContent,/LAST QUALIFIED.*historical.*no current authority/);
}
assert.equal(node('early-price').textContent,'');assert.equal(node('scalp-price').textContent,'');
assert.equal(node('up-buy').textContent,'—');
clearWrites();resolved=qualified;render();
for(const name of ['final','early','scalp'])assert.equal(node(name+'-reason').writes.length,0,'same decision recovery must not rewrite explanation');
resolved.lanes.main.current_payload.final.reason='brti_side';render();
assert.match(node('final-reason').textContent,/BRTI does not meet/,'genuine new native reason appears immediately');
setSample(samples[4]);render();const prior=resolved.lanes.main.retained_payload;
resolved.lanes.main.current_payload=structuredClone(prior);resolved.lanes.main.current_payload.final.helper.origin_id='WRONG';render();
assert.match(node('early-reason').textContent,/conflicting origin/,'never conceal a current invalid binding with historical wording');
assert.equal(node('early-action').textContent,'Action unavailable');
setSample(samples[0]);render();
for(const lane of Object.values(resolved.lanes)){lane.eligible=false;lane.current_payload=null;lane.selection='retained';}
resolved.identity={...resolved.identity,contract:'NEXT'};render();
for(const name of ['final','early','scalp'])assert.notEqual(node(name+'-reason').dataset.displayState,'retained','no cross-contract explanation retention');
// Every existing protected scenario passes through the actual DOM renderer.
for(const sample of samples){setSample(sample);const view=render();
  for(const p of ['early','scalp-up','scalp-down']){
    const active=node(p+'-ladder').children.filter(e=>e.attributes['aria-current']).map(e=>e.dataset.rung);
    assert.deepEqual(active,view.activeRungs[p]?[view.activeRungs[p]]:[],sample.label+' '+p);
    for(const r of ['entry','hold','watch','protect','exit'])assert.equal(node(p+'-'+r).textContent,view.fields[p+'-'+r]);
  }
  for(const name of ['final','early','scalp']){
    assert.equal(node(name+'-action').textContent,view.fields[name+'-action']);
    assert.equal(node(name+'-reason').textContent,view.fields[name+'-reason'],sample.label+' immediate '+name+' reason');
  }
}
// Asynchronous descriptive owners must resolve the same field through one formatter.
setSample(samples[0]);const identity=resolved.identity;
market={contract:identity.contract,source:{target:identity.target},clock:{closeMs:identity.official_close*1000},
  values:{timerRemaining:'04:00',btcPrice:'$80,021',evidenceScore:'4',momentumBadge:'UP',momentumSub:'sample'},
  brti:{price_state:'fresh',label:'CURRENT market BRTI',record:{contract:identity.contract}},chart:{},lower:{history:{},qualified:true}};
const payload={ticker:identity.contract,target:identity.target,probability_up:.6,probability_down:.4,protection_phase:'NORMAL',checked_ts:100,published_ts:99,brti_source_ts:99,btc_source_ts:98,btc_price:80020,brti_value:80021};
info={labels:{},current:{assessment:payload},delivery:{payload,requestStartedMs:1000},retained_source:{payload}};
render();clearWrites();
for(let n=0;n<20;n++){receiveMarket(market);receiveInfo(info);render();}
for(const id of ['health-brti','btc-price','btc-timestamp','model-information','model-information-note','evidence-score','market-momentum'])assert.equal(node(id).writes.length,0,id+' must have one live formatter');
info={...info,current:{assessment:null}};receiveInfo(info);
assert.equal(node('model-information').writes.length,0,'assessment text is separate from delivery classification');
assert.match(node('model-information-note').textContent,/LAST QUALIFIED.*no current action authority/);
console.log('PASS: one writer, stable repeated rendering, historical explanation-only expiry, immediate recovery/reasons, invalid binding, rollover, '+samples.length+' protected scenarios, asynchronous descriptive owners');

// Exercise the real Python native value output through the live renderer.
const child=require('node:child_process');
const valueNative=JSON.parse(child.execFileSync('python',['-c',`
import json
from test_btc15_value_opportunities import ValueAnalysis
_,v=ValueAnalysis().view(ask=.53,p=.8,offset=540)
v['official_identity']={k:v[k] for k in ('contract','target','official_open','official_close')}
print(json.dumps(v))
`],{cwd:__dirname+'/..',encoding:'utf8'}));
setSample({main:valueNative,scalp:null,quote:null});render();
assert.equal(node('early-action').textContent,'WATCH / POTENTIAL');
assert.match(node('early-reason').textContent,/unvalidated/);
assert.match(node('early-context').textContent,/all prices evaluated/);
assert.doesNotMatch(node('early-context').textContent,/entry limit/);
assert.match(node('value-best').textContent,/WATCH.*UP/);
assert.match(node('value-costs').textContent,/unverified.*No fill assumed/);
assert.ok(node('early-ladder').children.every(e=>!e.attributes['aria-current']));
clearWrites();for(let n=0;n<30;n++)render();
for(const id of ['early-reason','value-best','value-risk','value-costs'])assert.equal(node(id).writes.length,0,id+' stable');
resolved.lanes.main.eligible=false;resolved.lanes.main.current_payload=null;resolved.lanes.main.selection='retained';render();
assert.equal(node('early-action').textContent,'Action unavailable');
assert.match(node('value-best').textContent,/HISTORICAL/);
assert.match(node('value-freshness').textContent,/no current action authority/);
resolved.identity={...resolved.identity,contract:'OTHER'};render();
assert.equal(node('value-best').textContent,'No current native value selection');
console.log('PASS: native 53-cent WATCH, costs, no new rung authority, stable value rendering, expiry and rollover');
