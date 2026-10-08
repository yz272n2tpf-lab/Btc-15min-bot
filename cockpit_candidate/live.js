/* P2 binding only. Explicit connect; index/fixture/live boot selection belongs to P4. */
(function(){
  'use strict';
  if(window.BTC15CockpitLive)throw Error('BTC15_COCKPIT_BINDING_ALREADY_LOADED');
  let disconnect=null;
  function connect(){
    if(disconnect)return disconnect;
    const owner=window.BTC15LadderOwner,renderer=window.BTC15Cockpit;
    if(!owner?.subscribe||!renderer?.render)throw Error('BTC15_COCKPIT_BINDING_DEPENDENCY');
    if(window.BTC15Review)throw Error('BTC15_FIXTURE_BOOT_IS_NOT_LIVE');
    renderer.render({}); // Wait for the owner's next resolution, never replay a cached view.
    const unsubscribe=owner.subscribe(view=>{
      const {main,scalp,quote}=view.lanes;
      // Identity belongs to the owner, including quote-established identity while
      // MAIN refreshes. The stub supplies no native state, timestamp or authority.
      const identityOnly={status:'UNAVAILABLE',official_identity:view.identity,reason:main.reason_code};
      renderer.render({
        main:main.eligible?main.current_payload:identityOnly,
        scalp:scalp.eligible?scalp.current_payload:null,
        quote:quote.eligible?quote.current_payload:null
      });
      // Retained payloads stay available through getResolvedView/subscribe.
      // Their labelled display entry is P4; never feed them to the snapshot
      // renderer as a current signal. No action cache, timer or fetch lives here.
    });
    let connected=true;
    disconnect=()=>{if(!connected)return;connected=false;unsubscribe();disconnect=null;renderer.render({});};
    return disconnect;
  }
  Object.defineProperty(window,'BTC15CockpitLive',{value:Object.freeze({connect})});
})();
