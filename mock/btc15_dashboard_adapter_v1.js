'use strict';
// Presentation-only adapter. It may hide authority; it may never manufacture it.
function staleView(){
  return {authority:'UI_PRESENTATION_ONLY',status:'DATA_STALE',signal_only:true,orders:false,
    ticker:null,seconds_left:null,
    final:{state:'PASS',probability_up:null,probability_down:null,confidence:'NONE',locked:false},
    market:{up_bid:null,up_ask:null,down_bid:null,down_ask:null,target:null,aligned:false},
    risk:{flip_risk_pct:null,phase:'DATA_STALE',five_minute_caution:false,three_minute_guard:false},
    entry:{state:'UNAVAILABLE',target_max:.50,ideal_min:.25,ideal_max:.35},
    scalp:{state:'UNAVAILABLE',side:null,entry:null,exit:null,expected_minutes:null},
    evidence:{signal_strength:'UNAVAILABLE',score:null}};
}
function dashboardView(authoritative,information){
  const out=staleView();
  if(!authoritative||authoritative.signal_only!==true||authoritative.orders!==false||
     !authoritative.ticker||!Number.isFinite(authoritative.seconds_left)) return out;
  // Authoritative actions come ONLY from the frozen native/action stream.
  const fs=authoritative.final_status==='FINAL CALL' ? String(authoritative.final_side||'') : 'PASS';
  if(!['UP','DOWN','PASS'].includes(fs)) return out;
  out.status='AVAILABLE';out.ticker=authoritative.ticker;out.seconds_left=authoritative.seconds_left;
  out.final.state=fs;out.final.locked=authoritative.locked===true;
  const phase=authoritative.three_minute_guard===true?'3M_GUARD':authoritative.five_minute_caution===true?'5M_CAUTION':'NORMAL';
  out.risk.phase=phase;out.risk.five_minute_caution=phase==='5M_CAUTION';out.risk.three_minute_guard=phase==='3M_GUARD';
  if(authoritative.early&&authoritative.early.provisional_candidate===true){
    const ask=Number(authoritative.early.entry_ask??authoritative.early.ask??authoritative.early.preferred_ask);
    out.entry.state=Number.isFinite(ask)?(ask>=.25&&ask<=.35?'IDEAL':ask<=.50?'GOOD':'CAUTION'):'WAIT';
  } else out.entry.state='WAIT';
  if(authoritative.true_scalp&&authoritative.true_scalp.qualified===true){
    out.scalp={state:authoritative.true_scalp.reversal===true?'REVERSAL':'SCALP',
      side:authoritative.true_scalp.side??null,entry:authoritative.true_scalp.entry??null,
      exit:authoritative.true_scalp.exit??null,expected_minutes:authoritative.true_scalp.expected_minutes??null};
  } else out.scalp.state='PASS';
  // Informational probability can decorate the display only when same-ticker and AVAILABLE.
  if(information&&information.status==='AVAILABLE'&&information.authority==='INFORMATIONAL_READ_ONLY'&&
     information.ticker===out.ticker&&information.signal_only===true&&information.orders===false){
    out.final.probability_up=information.probability_up??null;out.final.probability_down=information.probability_down??null;
    out.risk.flip_risk_pct=information.flip_risk_pct??null;
    out.market={up_bid:information.up_bid??null,up_ask:information.up_ask??null,down_bid:information.down_bid??null,
      down_ask:information.down_ask??null,target:information.target??null,aligned:information.brti_agrees===true};
  }
  return out;
}
if(typeof module!=='undefined')module.exports={staleView,dashboardView};
