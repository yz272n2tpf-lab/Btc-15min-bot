/* Issued-record projection only. Authority remains with the native lease owner. */
(function(root){
  'use strict';
  const finite=Number.isFinite,valid=r=>r&&r.issued_buy===true&&/^[0-9a-f]{64}$/.test(r.origin_id)&&['UP','DOWN'].includes(r.side)&&typeof r.contract==='string'&&[r.original_ask,r.signal_ts,r.open_ts,r.close_ts,r.target].every(finite)&&r.original_ask>0&&r.original_ask<=1&&r.open_ts<=r.signal_ts&&r.signal_ts<r.close_ts;
  function legacy(p,name){
    const o=p?.origin;if(!o)return null;
    const early=name==='early',t=p.terminal;
    const r={origin_id:o.origin_id,issued_buy:true,contract:o.contract,side:o.side,original_ask:o.original_ask,
      signal_ts:early?Date.parse(o.signal_timestamp_utc)/1000:o.signal_ts,open_ts:early?o.official_open:o.open_ts,
      close_ts:early?o.official_close:o.close_ts,target:o.target,serial_index:o.serial_index,
      entry_policy:o.entry_policy||o.route,entry_reason:o.qualification?.reason||'Recorded native qualification; no fill assumed',
      entry_qualification:o.qualification?.conditions||o.entry_features,management_state:early?p.early?.guidance:p.guidance,
      terminal:t?{state:t.state,trigger_ts:t.decision_ts??t.ts,observed_bid:t.executable_exit_bid,reason:t.reason}:null};
    if(!valid(r))return null;
    // Legacy origins must still agree with the native terminal/helper binding.
    if(early&&p.final?.helper?.origin_id!==o.origin_id)return null;
    if(t&&(early?t.origin_id!==o.origin_id:t.origin?.origin_id!==o.origin_id))return null;
    return r;
  }
  function project(lane,identity,name){
    const p=lane?.current_payload,retained=lane?.retained_payload;
    const c=lane?.issued_records||p?.trade_clarity||retained?.trade_clarity;
    let records=c?.schema==='BTC15_ISSUED_SIGNALS_V1'&&Array.isArray(c.records)?c.records.filter(valid).slice(-8):[];
    if(!records.length){const old=legacy(p,name)||legacy(retained,name);if(old)records=[old];}
    const r=records.find(x=>x.origin_id===c?.selected_origin_id)||records.at(-1)||null;
    const same=!!r&&!!identity&&r.contract===identity.contract&&r.target===identity.target&&r.open_ts===identity.official_open&&r.close_ts===identity.official_close;
    const binding=name==='early'?p?.final?.helper?.origin_id===r?.origin_id&&p?.final?.early_origin_id===r?.origin_id:(!p?.terminal||p.terminal.origin?.origin_id===r?.origin_id);
    const fresh=!!lane?.eligible&&!!p&&same&&p.origin?.origin_id===r?.origin_id&&binding;
    const terminal=r?.terminal;
    const historical=!!r&&(!same||['ENDED_UNARMED','UNAVAILABLE'].includes(terminal?.state));
    const completed=terminal?.state==='EXIT';
    const management=fresh&&!terminal?(name==='early'?p.early?.guidance:p.guidance):null;
    // Native ENTER is one event publication. An old record can never renew it.
    const entry=fresh&&!terminal&&management==='ENTER'&&(c?c.entry_authority_current===true:true);
    const current=fresh&&binding&&!terminal&&!historical;
    const state=completed?'COMPLETED EXIT — NO NEW ENTRY':historical?'LAST ISSUED SIGNAL — HISTORICAL':!fresh&&r?'SOURCE REFRESHING / UNAVAILABLE':entry?'CURRENT ACTIONABLE SIGNAL':current?'EXISTING SIGNAL UNDER MANAGEMENT':'NO ISSUED BUY';
    return {record:r,records,state,entry,current,completed,historical,management,
      bid:current?p.executable_current_bid:null,
      economics:current?(name==='early'?p.management?.economics:p.economics):null,
      reason:completed?terminal.reason:fresh&&!binding?'Conflicting origin binding; current action unavailable':r?(r.management_reason||(name==='early'?(p?.origin?.origin_id===r.origin_id?p:retained)?.management?.reason:(p?.origin?.origin_id===r.origin_id?p:retained)?.presentation?.message)||r.entry_reason):'Potential setups are separate; no BUY has been issued',
      sourceAvailable:!!lane?.eligible};
  }
  const api={project};if(typeof module!=='undefined')module.exports=api;root.BTC15TradeRecords=api;
})(typeof window!=='undefined'?window:globalThis);
