/* Real renderer + unchanged native adapter. Test display writes, not a second strategy. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const adapter=require('./adapter.js'),trade=require('./trade_records.js'),nodes=new Map();
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
for(const prefix of ['early','scalp']){
  const ol=node(prefix+'-ladder');ol.tagName='OL';
  for(const rung of (prefix==='early'?['entry','watch','exit']:['entry','hold','watch','protect','exit'])){const li=new Element();li.dataset.rung=rung;ol.append(li);}
  if(prefix!=='early')sides.UP.append(ol);
}
const document={getElementById:node,createElement:()=>new Element(),querySelector:s=>sides[s.includes('"UP"')?'UP':'DOWN']};
let resolved,market,info,receiveMarket,receiveInfo;
const window={BTC15SnapshotAdapter:adapter,BTC15TradeRecords:trade,
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
  for(const name of ['main','scalp','quote']){
    const p=sample[name],eligible=!!p&&['AVAILABLE','PASS'].includes(p.status);
    resolved.lanes[name]={eligible,current_payload:p,retained_payload:eligible?p:null,
      payload:p,selection:eligible?'current':'none'};
  }
}
const render=()=>window.BTC15Cockpit.renderResolved(resolved);
const clearWrites=()=>{for(const e of nodes.values())e.writes=[];};
const noCurrentBuy=name=>{
  assert.doesNotMatch(node(name+'-action').textContent,/CURRENT ACTIONABLE SIGNAL|BUY ISSUED|EARLY CALL · BUY/);
  assert.doesNotMatch(node(name+'-price').textContent,/current same-side BID/);
};
const noRungs=()=>{for(const p of ['early','scalp'])
  assert.ok(node(p+'-ladder').children.every(e=>!e.attributes['aria-current']),p+' must not show active rung');};
// Current issued record is stable across 100 renders.
setSample(samples[3]);render();
const fields=['final-reason','early-reason','scalp-reason','early-action','scalp-action',
  'scalp-up-status','scalp-down-status'];
clearWrites();for(let i=0;i<100;i++)render();
for(const id of fields)assert.equal(node(id).writes.length,0,id+' flicker');
// Lease expires: preserve immutable original ASK, never current executable BID,
// action authority, or active rungs. FINAL retains historical explanation.
const originalFinal=node('final-reason').textContent;
for(const lane of Object.values(resolved.lanes)){
  lane.eligible=false;lane.current_payload=null;lane.selection='retained';lane.reason_code='SOURCE_EXPIRED';
}
render();
assert.equal(node('final-reason').textContent,originalFinal);
assert.equal(node('final-reason').dataset.displayState,'retained');
assert.match(node('final-freshness').textContent,/no current call authority/);
for(const name of ['early','scalp']){
  noCurrentBuy(name);
  assert.match(node(name+'-freshness').textContent,/no current action or executable price|no executable price/);
  assert.match(node(name+'-price').textContent,/original ASK/);
}
noRungs();
// Recovery cannot create a second entry or cause repeated explanation writes.
const qualified=structuredClone(resolved);
setSample(samples[3]);render();clearWrites();
for(let i=0;i<30;i++)render();
for(const id of fields)assert.equal(node(id).writes.length,0,id+' recovery flicker');
// Conflicting current origin/helper must fail closed and be explicitly explained.
setSample(samples[4]);render();
resolved.lanes.main.current_payload=structuredClone(resolved.lanes.main.current_payload);
resolved.lanes.main.current_payload.final.helper.origin_id='WRONG';render();
assert.match(node('early-reason').textContent,/Conflicting origin binding; current action unavailable/);
noCurrentBuy('early');
assert.match(node('early-freshness').textContent,/no executable price/);
assert.ok(node('early-ladder').children.every(e=>!e.attributes['aria-current']));
// Contract rollover cannot retain action authority or same-contract explanations.
setSample(samples[3]);render();
for(const lane of Object.values(resolved.lanes)){
  lane.eligible=false;lane.current_payload=null;lane.selection='retained';
}
resolved.identity={...resolved.identity,contract:'NEXT'};render();
assert.notEqual(node('final-reason').dataset.displayState,'retained');
noCurrentBuy('early');noCurrentBuy('scalp');noRungs();
// Every reference fixture must render safely through the real DOM and issued
// record projection. No invented active rung when the lane is unavailable.
for(const sample of samples){
  setSample(sample);render();
  for(const [name,laneName] of [['early','main'],['scalp','scalp']]){
    const lane=resolved.lanes[laneName];
    const t=window.BTC15TradeRecords.project(lane,resolved.identity,name);
    if(t.entry)assert.equal(node(name+'-action').textContent,'BUY ISSUED',sample.label);
    else if(t.current)assert.match(node(name+'-action').textContent,name==='early'?/^WATCH(?: · COULD FLIP)?$/:/^(HOLD|WATCH|PROTECT|CAUTION)(?: · CAUTION)?$/,sample.label);
    else if(t.newExit)assert.match(node(name+'-action').textContent,/^EXIT — /,sample.label);
    else if(name==='early'&&t.completed)assert.equal(node(name+'-action').textContent,'NO ACTIVE EARLY TRADE — PREVIOUS SIGNAL EXITED',sample.label);
    else assert.doesNotMatch(node(name+'-action').textContent,/BUY ISSUED|^WATCH|^HOLD|^PROTECT|^EXIT — /,sample.label);
    if(!t.current){
      assert.doesNotMatch(node(name+'-price').textContent,/current same-side BID/);
      if(!t.completed)assert.doesNotMatch(node(name+'-action').textContent,/CURRENT ACTIONABLE SIGNAL/);
    }
  }
}
console.log('PASS: 100 stable renders, real issued records, expiry, immutable ASK, invalid binding, no stale BUY, rollover, '+samples.length+' fixtures');
