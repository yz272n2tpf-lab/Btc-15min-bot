#!/usr/bin/env python3
"""BTC15 EARLY excursion V1 frozen review report.

PURE / OFFLINE / READ ONLY | MANUAL EXECUTION | NO ORDERS
Move checkpoints are tradable-utility metrics, never FINAL accuracy or new gates.
"""
from __future__ import annotations
import math
from typing import Any,Mapping
VERSION="BTC15_EARLY_EXCURSION_V1_FROZEN_REVIEW_REPORT_V1";EXPECTED_VERSION="BTC15_EARLY_EXCURSION_FORWARD_V1";EXPECTED_COVERAGE="FIRST_SEEN_BEFORE_EARLY_10M_WINDOW";MIN_ELIGIBLE=30;MIN_COMPLETED=10;EPS=1e-9

def _m(v):return v if isinstance(v,Mapping) else {}
def _i(v):
    try:return int(v)
    except(TypeError,ValueError):return 0
def _f(v):
    if v is None or isinstance(v,bool):return None
    try:
        x=float(v);return x if math.isfinite(x) else None
    except(TypeError,ValueError):return None
def _rate(n,d):return None if d<=0 else n/d
def _close(a,b):
    x,y=_f(a),_f(b);return (x is None and y is None) if (x is None or y is None) else abs(x-y)<=EPS
def _live(p):
    q=p.get("live") if isinstance(p,Mapping) else None;return q if isinstance(q,Mapping) else _m(p)
def build_report(payload:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(payload,Mapping):raise TypeError("excursion payload must be mapping")
    s=_live(payload);err=[];version=str(payload.get("version") or s.get("version") or "")
    if version!=EXPECTED_VERSION:err.append(f"collector_version:{version or 'MISSING'}")
    if str(s.get("coverage_universe_semantics") or "")!=EXPECTED_COVERAGE:err.append("coverage_semantics")
    if s.get("fresh_start_semantics")!="FIRST_POST_START_ROLLOVER":err.append("fresh_start_semantics")
    if s.get("production_behavior_changed") is not False:err.append("production_behavior_changed")
    if s.get("early_thresholds_changed") is not False:err.append("early_thresholds_changed")
    if s.get("orders") is not False or payload.get("orders") is True:err.append("orders_not_false")
    if s.get("manual_execution_only") is not True:err.append("manual_execution_only_not_true")
    eligible=_i(s.get("eligible_contracts"));calls=_i(s.get("early_calls"));complete=_i(s.get("completed_early_excursions"));ideal=_i(s.get("ideal_25_35c_n"));hits=[_i(s.get(f"hit_{n}c_n")) for n in (5,10,15,20)]
    if any(x<0 for x in (eligible,calls,complete,ideal,*hits)):err.append("negative_counts")
    if calls>eligible or complete>calls or ideal>calls:err.append("count_bounds")
    if not(hits[3]<=hits[2]<=hits[1]<=hits[0]<=complete):err.append("nested_target_counts")
    if not _close(s.get("early_coverage"),_rate(calls,eligible)):err.append("coverage_math")
    if not _close(s.get("ideal_25_35c_rate"),_rate(ideal,calls)):err.append("ideal_rate_math")
    for n,count in zip((5,10,15,20),hits):
        if not _close(s.get(f"hit_{n}c_rate"),_rate(count,complete)):err.append(f"hit_{n}c_rate_math")
    for key in ("final_agreement_rate","settlement_same_side_rate_secondary"):
        x=_f(s.get(key))
        if x is not None and not 0<=x<=1:err.append(f"{key}_bounds")
    integrity=not err;counts_ready=eligible>=MIN_ELIGIBLE and complete>=MIN_COMPLETED;collector_ready=bool(s.get("sample_ready"));ready=integrity and counts_ready and collector_ready;status="INVALID_SNAPSHOT_FAIL_CLOSED" if not integrity else ("EARLY_EXCURSION_V1_MANUAL_REVIEW_READY" if ready else "WAITING_FOR_FROZEN_GATE")
    return {"version":VERSION,"status":status,"integrity":{"pass":integrity,"errors":err},"frozen_gate":{"eligible_contracts":eligible,"completed_excursions":complete,"minimum_eligible":MIN_ELIGIBLE,"minimum_completed":MIN_COMPLETED,"remaining_eligible":max(0,MIN_ELIGIBLE-eligible),"remaining_completed":max(0,MIN_COMPLETED-complete),"counts_ready":counts_ready,"collector_sample_ready":collector_ready,"manual_review_ready":ready},"entry":{"early_calls":calls,"coverage":_f(s.get("early_coverage")),"avg_ask":_f(s.get("avg_entry_ask")),"median_ask":_f(s.get("median_entry_ask")),"ideal_25_35c_n":ideal,"ideal_25_35c_rate":_f(s.get("ideal_25_35c_rate")),"avg_minutes_left":_f(s.get("avg_entry_minutes_left")),"median_minutes_left":_f(s.get("median_entry_minutes_left"))},"excursion":{"avg_mfe":_f(s.get("avg_mfe")),"median_mfe":_f(s.get("median_mfe")),"avg_mae":_f(s.get("avg_mae")),"median_mae":_f(s.get("median_mae")),**{f"hit_{n}c_n":c for n,c in zip((5,10,15,20),hits)},**{f"hit_{n}c_rate":_f(s.get(f"hit_{n}c_rate")) for n in (5,10,15,20)},"metric_is_final_accuracy":False,"checkpoints_are_qualification_rules":False},"downstream_context":{"final_seen_after_early_n":_i(s.get("final_seen_after_early_n")),"final_agreement_rate":_f(s.get("final_agreement_rate")),"settled_early_n":_i(s.get("settled_early_n")),"settlement_same_side_rate_secondary":_f(s.get("settlement_same_side_rate_secondary")),"settlement_is_success_definition":False},"decision_controls":{"auto_promote_allowed":False,"threshold_retune_allowed":False,"manual_review_required":True,"orders":False}}
def _pct(v):
    x=_f(v);return "—" if x is None else f"{100*x:.1f}%"
def _c(v):
    x=_f(v);return "—" if x is None else f"{100*x:.1f}¢"
def render_text(r):
    g=_m(r.get("frozen_gate"));e=_m(r.get("entry"));x=_m(r.get("excursion"));d=_m(r.get("downstream_context"));i=_m(r.get("integrity"));lines=["=== BTC15 EARLY EXCURSION V1 FROZEN REVIEW ===",f"Status: {r.get('status')}",f"Integrity: {'PASS' if i.get('pass') else 'FAIL'}",f"Gate: eligible {g.get('eligible_contracts',0)}/30 · completed {g.get('completed_excursions',0)}/10",f"Entry coverage: {_pct(e.get('coverage'))} · avg ask {_c(e.get('avg_ask'))}",f"MFE avg {_c(x.get('avg_mfe'))} · MAE avg {_c(x.get('avg_mae'))}",f"+5/+10/+15/+20: {_pct(x.get('hit_5c_rate'))} / {_pct(x.get('hit_10c_rate'))} / {_pct(x.get('hit_15c_rate'))} / {_pct(x.get('hit_20c_rate'))}",f"FINAL-after-EARLY agreement: {_pct(d.get('final_agreement_rate'))}",f"Settlement-side context: {_pct(d.get('settlement_same_side_rate_secondary'))} · SECONDARY ONLY","Controls: movement utility, not FINAL accuracy · checkpoints not qualification rules · no auto-promotion · no orders"]
    if i.get("errors"):lines.append("Integrity errors: "+", ".join(map(str,i.get("errors") or [])))
    return "\n".join(lines)+"\n"
__all__=["VERSION","build_report","render_text"]
