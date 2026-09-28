'use strict';
// Recovered V11 app presentation adapter.
// It may suppress/hide authority; it may NEVER manufacture FINAL/EARLY/SCALP/PROTECT/EXIT authority.
function unavailable(){
  return {authority:'UI_PRESENTATION_ONLY',status:'DATA_STALE',signal_only:true,orders:false,
    ticker:null,seconds_left:null,
    final:{state:'PASS',probability_up:null,probability_down:null,display_side:null,display_probability:null,
      confidence:null,source:null,locked:false},
    early:{qualified:false,side:null,ask:null,entry_quality:'UNAVAILABLE'},
    market:{up_bid:null,up_ask:null,down_bid:null,down_ask:null,target:null,brti_agrees:null},
    risk:{flip_risk_pct:null,phase:'DATA_STALE',five_minute_caution:false,three_minute_guard:false},
    scalp:{state:'UNAVAILABLE',side:null,entry:null,current_sell:null,profit:null,expected_minutes:null,
      protection_state:null,action:null},
    evidence:{signal_strength:'UNAVAILABLE',score:null}};
}
function num(v){return Number.isFinite(Number(v))?Number(v):null;}
function entryQuality(ask){
  ask=num(ask); if(ask===null)return 'WAIT';
  return ask>=.25&&ask<=.35?'IDEAL':ask<=.50?'GOOD':'CAUTION';
}
function recoveredV11View(action,info){
  const out=unavailable();
  if(!action||action.signal_only!==true||action.orders!==false||!action.ticker||!Number.isFinite(action.seconds_left))return out;
  out.status='AVAILABLE'; out.ticker=action.ticker; out.seconds_left=action.seconds_left;

  // FINAL authority: only an explicit native FINAL CALL may create a qualified final state.
  const finalReady=action.final_status==='FINAL CALL'&&['UP','DOWN'].includes(String(action.final_side||'').toUpperCase());
  out.final.state=finalReady?String(action.final_side).toUpperCase():'PASS';
  out.final.confidence=finalReady?num(action.final_confidence):null;
  out.final.source=finalReady?(action.final_call_source||null):null;
  out.final.locked=finalReady&&action.locked===true;

  // EARLY qualification must be explicit. Informational probability/quotes can never create it.
  const e=action.early;
  if(e&&e.qualified===true&&['UP','DOWN'].includes(String(e.side||'').toUpperCase())){
    out.early.qualified=true; out.early.side=String(e.side).toUpperCase();
    out.early.ask=num(e.entry_ask??e.ask??e.preferred_ask); out.early.entry_quality=entryQuality(out.early.ask);
  }

  // Existing scalp/protection lifecycle remains authoritative.
  const s=action.scalp;
  if(s&&s.qualified===true&&['UP','DOWN'].includes(String(s.side||'').toUpperCase())){
    const state=String(s.state||'ACTIVE').toUpperCase();
    if(['ACTIVE','PROTECT','EXIT','REVERSAL'].includes(state)){
      out.scalp.state=state; out.scalp.side=String(s.side).toUpperCase();
      out.scalp.entry=num(s.entry); out.scalp.current_sell=num(s.current_sell??s.bid);
      out.scalp.profit=num(s.profit??s.gain); out.scalp.expected_minutes=num(s.expected_minutes);
      out.scalp.protection_state=s.protection_state??null;
      out.scalp.action=state==='EXIT'?'EXIT':state==='PROTECT'?'PROTECT':'HOLD';
    }
  } else out.scalp.state='PASS';

  // INFORMATIONAL_READ_ONLY may decorate only same-ticker fresh/AVAILABLE frames.
  const infoOK=info&&info.status==='AVAILABLE'&&info.authority==='INFORMATIONAL_READ_ONLY'&&
    info.signal_only===true&&info.orders===false&&info.ticker===out.ticker;
  if(infoOK){
    const up=num(info.probability_up),down=num(info.probability_down);
    if(up!==null&&down!==null&&up>=0&&up<=1&&down>=0&&down<=1&&Math.abs((up+down)-1)<1e-6){
      out.final.probability_up=up; out.final.probability_down=down;
      out.final.display_side=up>=down?'UP':'DOWN'; out.final.display_probability=Math.max(up,down);
    }
    out.market.up_bid=num(info.up_bid);out.market.up_ask=num(info.up_ask);
    out.market.down_bid=num(info.down_bid);out.market.down_ask=num(info.down_ask);
    out.market.target=num(info.target);out.market.brti_agrees=typeof info.brti_agrees==='boolean'?info.brti_agrees:null;
    out.risk.flip_risk_pct=num(info.flip_risk_pct);
    const phase=info.three_minute_guard===true?'3M_GUARD':info.five_minute_caution===true?'5M_CAUTION':
      (['NORMAL','5M_CAUTION','3M_GUARD'].includes(info.protection_phase)?info.protection_phase:'NORMAL');
    out.risk.phase=phase;out.risk.five_minute_caution=phase==='5M_CAUTION';out.risk.three_minute_guard=phase==='3M_GUARD';
  }
  return out;
}
if(typeof module!=='undefined')module.exports={unavailable,entryQuality,recoveredV11View};
