const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),cp=require('node:child_process');
const adapter=require('./adapter.js'),trade=require('./trade_records.js'),nodes=new Map();
class Element{
 constructor(){this.children=[];this.dataset={};this.attributes={};this.writes=[];this.value='';this.open=false;}
 get textContent(){return this.value;}set textContent(v){this.value=String(v);this.writes.push(this.value);}
 append(...items){for(const e of items){e.remove();e.parentElement=this;this.children.push(e);}}
 remove(){if(this.parentElement){this.parentElement.children=this.parentElement.children.filter(e=>e!==this);this.parentElement=null;}}
 after(e){e.remove();e.parentElement=this.parentElement;this.parentElement.children.splice(this.parentElement.children.indexOf(this)+1,0,e);}
 get previousElementSibling(){return this.parentElement?.children[this.parentElement.children.indexOf(this)-1];}
 get lastElementChild(){return this.children.at(-1);}
 setAttribute(k,v){this.attributes[k]=v;}removeAttribute(k){delete this.attributes[k];}
}
const node=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
const panel=new Element();panel.append(node('scalp-heading'),node('scalp-guidance'));
for(const prefix of ['early','scalp'])for(const rung of ['entry','hold','watch','protect','exit']){const e=new Element();e.dataset.rung=rung;node(prefix+'-ladder').append(e);}
const document={getElementById:node,createElement:()=>new Element()};let resolved;
const window={BTC15SnapshotAdapter:adapter,BTC15TradeRecords:trade,BTC15LadderOwner:{getResolvedView:()=>resolved},BTC15CockpitLive:{connect:()=>()=>{}},BTC15MarketViewOwner:{getResolvedView:()=>null,subscribe:()=>()=>{}},BTC15InformationOwner:{getResolvedView:()=>null,subscribe:()=>()=>{}}};
vm.runInNewContext(fs.readFileSync(__dirname+'/cockpit.js','utf8'),{window,document,console,performance:{now:()=>1000}});
window.BTC15Cockpit.connectResolved();
const data=JSON.parse(cp.execFileSync('python',['-c',`
import json
from btc15_v2_product.directional import Directional
from test_btc15_supported_early import value_frame,step
from test_btc15_trade_clarity import scalp_origin
from test_btc15_scalp_journal_v1 import state,ENTRY
from test_btc15_scalp_entry_restore import frame
from btc15_v2_product.scalp import Scalp
from btc15_v2_product import ENVELOPE,REVISION
out={};e=Directional();e.restore({})
for name,f in [('entry',value_frame()),('hold',value_frame(2)),('exit',value_frame(3,side='DOWN',p=.6))]:
 _,_,v=step(e,f);v.update(signal_only=True,orders=False,official_identity={k:v[k]for k in ('contract','target','official_open','official_close')});out[name]=v
s,o=scalp_origin();_,_,v=s.process(state(ENTRY+1,.7,2),ENTRY+1.001);v['official_identity']={k:v[k] for k in ('contract','target','official_open','official_close')};out['scalp']=v
s=Scalp();s.restore({});_,_,v=s.process(frame(),ENTRY+.001);v['official_identity']={k:v[k] for k in ('contract','target','official_open','official_close')};out['scalpentry']=v
print(json.dumps(out))
`],{cwd:__dirname+'/..',encoding:'utf8'}));
function show(m,s=null){resolved={identity:m.official_identity,lanes:{main:{eligible:true,current_payload:m,retained_payload:m,issued_records:m.trade_clarity},scalp:{eligible:!!s,current_payload:s,retained_payload:s,issued_records:s?.trade_clarity},quote:{eligible:false}}};return window.BTC15Cockpit.renderResolved(resolved);}
show(data.entry);assert.match(node('early-action').textContent,/BUY ISSUED/);assert.match(node('early-price').textContent,/53¢/);
show(data.hold);assert.match(node('early-action').textContent,/HOLD|WATCH|PROTECT/);assert.match(node('early-price').textContent,/original ASK 53¢/);
const originalReason=node('early-reason').textContent;
resolved.lanes.main.eligible=false;resolved.lanes.main.current_payload=null;window.BTC15Cockpit.renderResolved(resolved);
assert.match(node('early-action').textContent,/SOURCE REFRESHING/);assert.match(node('early-price').textContent,/original ASK 53¢/);assert.match(node('early-reason').textContent,/Current action unavailable/);assert.match(node('early-freshness').textContent,/no executable price/);
for(const e of nodes.values())e.writes=[];
for(let i=0;i<100;i++)window.BTC15Cockpit.renderResolved(resolved);
for(const id of ['early-action','early-price','early-reason','early-direction','scalp-action','scalp-price'])assert.equal(node(id).writes.length,0,id+' flickers');
show(data.exit);assert.match(node('early-action').textContent,/COMPLETED EXIT/);assert.equal(node('early-direction').textContent,'UP');assert.match(node('early-exit-record').textContent,/observed trigger BID/);
assert.doesNotMatch(node('early-reason').textContent,/close at an available/);
assert.match(node('early-management').textContent,/Recorded trigger scenario/);
assert.doesNotMatch(fs.readFileSync(__dirname+'/index.html','utf8'),/id="scalp-(up|down)-ladder"/);
assert.ok(node('early-ladder').children.every(x=>!x.attributes['aria-current']));
const rolled={...data.hold,official_identity:{...data.hold.official_identity,contract:'NEXT',official_open:data.hold.official_close,official_close:data.hold.official_close+900},origin:null};
show(rolled);assert.match(node('early-action').textContent,/HISTORICAL/);assert.match(node('early-direction').textContent,/historical/);
show(data.hold,data.scalp);assert.match(node('scalp-action').textContent,/HOLD|WATCH|PROTECT/);assert.match(node('scalp-economics').textContent,/net liquidation/);
show({...data.hold,official_identity:data.scalpentry.official_identity},data.scalpentry);
assert.match(node('scalp-action').textContent,/BUY ISSUED/);
assert.match(node('scalp-price').textContent,/original ASK 60¢/);
assert.match(node('scalp-entry-risk').children.map(r=>r.children[1].textContent).join(' '),/UNESTABLISHED/);
assert.doesNotMatch(node('scalp-economics').textContent,/supported exit-value evidence/);
const broken=structuredClone(data.hold);broken.final.helper.origin_id='wrong';show(broken);assert.doesNotMatch(node('early-action').textContent,/BUY ISSUED|HOLD|WATCH|PROTECT/);
const legacy=structuredClone(data.hold);delete legacy.trade_clarity;show(legacy);assert.match(node('early-price').textContent,/original ASK 53¢/);
const example=structuredClone(data.hold);
example.final={...example.final,side:'DOWN',confidence:.844,ready:false,lock_state:'UNLOCKED',state:'PASS'};
const c=example.opportunity_analysis.candidates.find(c=>c.side==='DOWN');
c.ask=.92;c.bid=.91;c.fair=.844;c.economics={...c.economics,valid_book:true,series_fee_verified:true,net_model_ev_scenario:-.086,stress_net_model_ev_scenario:-.096};
show(example);assert.equal(node('final-probability').textContent,'84.4%');assert.match(node('final-summary').textContent,/PASS.*below 90%/);assert.match(node('final-value').textContent,/PASS.*92¢/);assert.match(node('final-market').textContent,/DOWN.*92¢/);
assert.match(node('early-entry').textContent,/BUY UP.*53¢/);
assert.ok(node('early-ladder').children.some(x=>x.attributes['aria-current']==='step'));
const html=fs.readFileSync(__dirname+'/index.html','utf8');
for(const name of ['early','scalp']){assert.match(html,new RegExp('id="'+name+'-ladder"'));assert.match(html,new RegExp('<details class="trade-details" id="'+name+'-trade-details">'));}
assert.doesNotMatch(html,/<details[^>]*\sopen(?:[\s=>])/);
console.log('PASS: native BUY/HOLD/gap/EXIT/rollover, legacy compatibility, origin binding, net scenario, and 100 stable repeated DOM renders');
