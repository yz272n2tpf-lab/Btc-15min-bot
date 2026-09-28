'use strict';
// Simulated transport lease. Presentation only; never evaluates strategy.
class DashboardLease {
  constructor(adapter, maxAgeMs=1500){this.adapter=adapter;this.maxAgeMs=maxAgeMs;this.generation=0;this.last=null;}
  disconnect(){this.generation++;this.last=null;}
  receive(authoritative,information,receivedMs){
    if(!Number.isFinite(receivedMs)) {this.disconnect();return;}
    this.last=Object.freeze({generation:this.generation,receivedMs,authoritative:structuredClone(authoritative),information:structuredClone(information)});
  }
  view(nowMs){
    if(!this.last||!Number.isFinite(nowMs)||nowMs<this.last.receivedMs||nowMs-this.last.receivedMs>=this.maxAgeMs) return this.adapter(null,null);
    if(this.last.generation!==this.generation)return this.adapter(null,null);
    return this.adapter(this.last.authoritative,this.last.information);
  }
}
if(typeof module!=='undefined')module.exports={DashboardLease};
