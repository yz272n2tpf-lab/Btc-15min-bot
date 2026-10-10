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
for(const prefix of ['early','scalp-up','scalp-down'])for(const rung of ['entry','hold','watch','protect','exit']){const e=new Element();e.dataset.rung=rung;node(prefix+'-ladder').append(e);}
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
from btc15_v2_product import ENVELOPE,REVISION
out={};e=Directional();e.restore({})
for name,f in [('entry',value_frame()),('hold',value_frame(2)),('exit',value_frame(3,side='DOWN',p=.6))]:
 _,_,v=step(e,f);v.update(signal_only=True,orders=False,official_identity={k:v[k]for k in ('contract','target','official_open','official_close')});out[name]=v
s,o=scalp_origin();_,_,v=s.process(state(ENTRY+1,.7,2),ENTRY+1.001);v['official_identity']={k:v[k] for k in ('contract','target','official_open','official_close')};out['scalp']=v
print(json.dumps(out))
`],{cwd:__dirname+'/..',encoding:'utf8'}));
function show(m,s=null){resolved={identity:m.official_identity,lanes:{main:{eligible:true,current_payload:m,retained_payload:m,issued_records:m.trade_clarity},scalp:{eligible:!!s,current_payload:s,retained_payload:s,issued_records:s?.trade_clarity},quote:{eligible:false}}};return window.BTC15Cockpit.renderResolved(resolved);}
show(data.entry);assert.match(node('early-action').textContent,/CURRENT ACTIONABLE SIGNAL.*BUY ISSUED/);assert.match(node('early-price').textContent,/53.00/);
show(data.hold);assert.match(node('early-action').textContent,/EXISTING SIGNAL UNDER MANAGEMENT/);assert.match(node('early-price').textContent,/original ASK 53.00/);
const originalReason=node('early-reason').textContent;
resolved.lanes.main.eligible=false;resolved.lanes.main.current_payload=null;window.BTC15Cockpit.renderResolved(resolved);
assert.match(node('early-action').textContent,/SOURCE REFRESHING/);assert.match(node('early-price').textContent,/original ASK 53.00.*unavailable/);assert.equal(node('early-reason').textContent,originalReason);
for(const e of nodes.values())e.writes=[];
for(let i=0;i<100;i++)window.BTC15Cockpit.renderResolved(resolved);
for(const id of ['early-action','early-price','early-reason','early-direction','scalp-action','scalp-price'])assert.equal(node(id).writes.length,0,id+' flickers');
show(data.exit);assert.match(node('early-action').textContent,/EXIT RECOMMENDED — AWAIT FRESH QUALIFIED BUY/);assert.equal(node('early-direction').textContent,'UP');assert.match(node('early-exit-record').textContent,/observed trigger BID/);
assert.ok(node('early-ladder').children.every(x=>!x.attributes['aria-current']));
const rolled={...data.hold,official_identity:{...data.hold.official_identity,contract:'NEXT',official_open:data.hold.official_close,official_close:data.hold.official_close+900},origin:null};
show(rolled);assert.match(node('early-action').textContent,/HISTORICAL/);assert.match(node('early-direction').textContent,/historical/);
show(data.hold,data.scalp);assert.match(node('scalp-action').textContent,/EXISTING SIGNAL UNDER MANAGEMENT/);assert.match(node('scalp-economics').textContent,/net liquidation/);
const broken=structuredClone(data.hold);broken.final.helper.origin_id='wrong';show(broken);assert.doesNotMatch(node('early-action').textContent,/CURRENT ACTIONABLE|EXISTING SIGNAL UNDER MANAGEMENT/);
const legacy=structuredClone(data.hold);delete legacy.trade_clarity;show(legacy);assert.match(node('early-price').textContent,/original ASK 53.00/);
console.log('PASS: native BUY/HOLD/gap/EXIT/rollover, legacy compatibility, origin binding, net scenario, and 100 stable repeated DOM renders');
