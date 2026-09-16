#!/usr/bin/env python3
"""BTC15 EARLY->FINAL handoff V1 frozen review report.

PURE / OFFLINE / READ ONLY | MANUAL EXECUTION | NO ORDERS
Only this common-universe lane may review/certify union coverage.
"""
from __future__ import annotations
import math
from typing import Any,Mapping
VERSION="BTC15_HANDOFF_V1_FROZEN_REVIEW_REPORT_V1"
EXPECTED_VERSION="BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1"
EXPECTED_COVERAGE="FIRST_SEEN_BEFORE_EARLY_10M_ELIGIBILITY_WINDOW"
MIN_ELIGIBLE=30; MIN_HANDOFFS=10; MIN_SETTLED_FINAL=12; EPS=1e-9

def _m(v):return v if isinstance(v,Mapping) else {}
def _i(v):
    try:return int(v)
    except (TypeError,ValueError):return 0
def _f(v):
    if v is None or isinstance(v,bool):return None
    try:
        x=float(v);return x if math.isfinite(x) else None
    except (TypeError,ValueError):return None
def _rate(n,d):return None if d<=0 else n/d
def _close(a,b):
    x,y=_f(a),_f(b);return (x is None and y is None) if (x is None or y is None) else abs(x-y)<=EPS
def _live(p):
    q=p.get("live") if isinstance(p,Mapping) else None
    return q if isinstance(q,Mapping) else _m(p)

def build_report(payload:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(payload,Mapping):raise TypeError("handoff payload must be mapping")
    s=_live(payload);err=[];version=str(payload.get("version") or s.get("version") or "")
    if version!=EXPECTED_VERSION:err.append(f"collector_version:{version or 'MISSING'}")
    if s.get("fresh_start_semantics")!="FIRST_POST_START_ROLLOVER":err.append("fresh_start_semantics")
    if str(s.get("coverage_universe_semantics") or "")!=EXPECTED_COVERAGE:err.append("coverage_semantics")
    if s.get("protected_early_thresholds_changed") is not False:err.append("early_thresholds_changed")
    if s.get("protected_final_thresholds_changed") is not False:err.append("final_thresholds_changed")
    if s.get("auto_promotion") is not False:err.append("auto_promotion_not_false")
    if s.get("orders") is not False or payload.get("orders") is True:err.append("orders_not_false")
    if s.get("manual_execution_only") is not True:err.append("manual_execution_only_not_true")
    g=_m(s.get("review_gate"))
    if _i(g.get("min_eligible_contracts"))!=MIN_ELIGIBLE or _i(g.get("min_handoffs"))!=MIN_HANDOFFS or _i(g.get("min_settled_final"))!=MIN_SETTLED_FINAL:err.append("review_gate_drift")
    eligible=_i(s.get("eligibility_complete_contracts")); early=_i(s.get("early_calls")); final=_i(s.get("final_locks")); both=_i(s.get("handoffs")); eo=_i(s.get("early_only_contracts")); fo=_i(s.get("final_only_contracts")); none=_i(s.get("no_anchor_contracts")); settled=_i(s.get("settled_final_locks"))
    counts=(eligible,early,final,both,eo,fo,none,settled)
    if any(x<0 for x in counts):err.append("negative_counts")
    if early>eligible or final>eligible or both>min(early,final) or settled>final:err.append("count_bounds")
    union_n=early+final-both
    if union_n>eligible:err.append("union_gt_eligible")
    if eo!=early-both or fo!=final-both or none!=eligible-union_n:err.append("partition_math")
    if not _close(s.get("any_signal_coverage"),_rate(union_n,eligible)):err.append("union_coverage_math")
    if not _close(s.get("early_coverage"),_rate(early,eligible)):err.append("early_coverage_math")
    if not _close(s.get("final_coverage"),_rate(final,eligible)):err.append("final_coverage_math")
    if not _close(s.get("dual_anchor_coverage"),_rate(both,eligible)):err.append("dual_coverage_math")
    agree=_f(s.get("handoff_side_agreement_rate"));
    if both==0 and agree is not None:err.append("agreement_should_be_null")
    facc=_f(s.get("final_accuracy"));
    if facc is not None and not 0<=facc<=1:err.append("final_accuracy_bounds")
    integrity=not err; counts_ready=eligible>=MIN_ELIGIBLE and both>=MIN_HANDOFFS and settled>=MIN_SETTLED_FINAL; collector_ready=bool(s.get("sample_ready")); ready=integrity and counts_ready and collector_ready
    status="INVALID_SNAPSHOT_FAIL_CLOSED" if not integrity else ("HANDOFF_V1_MANUAL_REVIEW_READY" if ready else "WAITING_FOR_FROZEN_GATE")
    return {"version":VERSION,"status":status,"integrity":{"pass":integrity,"errors":err},"frozen_gate":{"eligible_contracts":eligible,"handoffs":both,"settled_final_locks":settled,"minimum_eligible":MIN_ELIGIBLE,"minimum_handoffs":MIN_HANDOFFS,"minimum_settled_final":MIN_SETTLED_FINAL,"remaining_eligible":max(0,MIN_ELIGIBLE-eligible),"remaining_handoffs":max(0,MIN_HANDOFFS-both),"remaining_settled_final":max(0,MIN_SETTLED_FINAL-settled),"counts_ready":counts_ready,"collector_sample_ready":collector_ready,"manual_review_ready":ready},"common_universe":{"early_calls":early,"final_locks":final,"handoffs":both,"early_only":eo,"final_only":fo,"no_anchor":none,"any_signal_count":union_n,"any_signal_coverage":_f(s.get("any_signal_coverage")),"dual_anchor_coverage":_f(s.get("dual_anchor_coverage")),"union_coverage_certified":bool(ready),"target_90pct_met_observed":bool(_f(s.get("any_signal_coverage")) is not None and _f(s.get("any_signal_coverage"))>=.90-EPS),"target_90pct_certified":bool(ready and _f(s.get("any_signal_coverage")) is not None and _f(s.get("any_signal_coverage"))>=.90-EPS)},"handoff_quality":{"side_agreement_rate":agree,"avg_gap_minutes":_f(s.get("avg_early_to_final_gap_minutes")),"median_gap_minutes":_f(s.get("median_early_to_final_gap_minutes")),"avg_same_side_ask_change":_f(s.get("avg_same_side_ask_change_early_to_final"))},"entry_economics":{"avg_early_ask":_f(s.get("avg_early_ask")),"median_early_ask":_f(s.get("median_early_ask")),"early_ideal_25_35c_n":_i(s.get("early_ideal_25_35c_n")),"early_le_50c_n":_i(s.get("early_le_50c_n")),"avg_final_ask":_f(s.get("avg_final_ask")),"median_final_ask":_f(s.get("median_final_ask")),"final_le_50c_n":_i(s.get("final_le_50c_n"))},"direction_context":{"final_accuracy":facc,"early_settlement_same_side_secondary":_f(s.get("early_same_side_as_settlement_rate_secondary")),"early_is_final_accuracy":False},"decision_controls":{"auto_promote_allowed":False,"threshold_retune_allowed":False,"manual_review_required":True,"orders":False}}

def _pct(v):
    x=_f(v);return "—" if x is None else f"{100*x:.1f}%"
def render_text(r):
    g=_m(r.get("frozen_gate"));u=_m(r.get("common_universe"));q=_m(r.get("handoff_quality"));d=_m(r.get("direction_context"));i=_m(r.get("integrity"))
    lines=["=== BTC15 EARLY → FINAL HANDOFF V1 FROZEN REVIEW ===",f"Status: {r.get('status')}",f"Integrity: {'PASS' if i.get('pass') else 'FAIL'}",f"Gate: eligible {g.get('eligible_contracts',0)}/30 · handoffs {g.get('handoffs',0)}/10 · settled FINAL {g.get('settled_final_locks',0)}/12",f"Remaining: eligible {g.get('remaining_eligible',0)} · handoffs {g.get('remaining_handoffs',0)} · settled FINAL {g.get('remaining_settled_final',0)}",f"Common-universe any-signal coverage: {_pct(u.get('any_signal_coverage'))} ({u.get('any_signal_count',0)}/{g.get('eligible_contracts',0)})",f"Dual-anchor coverage: {_pct(u.get('dual_anchor_coverage'))} · side agreement {_pct(q.get('side_agreement_rate'))}",f">=90% observed={u.get('target_90pct_met_observed')} · certified={u.get('target_90pct_certified')}",f"FINAL accuracy in this universe: {_pct(d.get('final_accuracy'))}",f"EARLY settlement-side context: {_pct(d.get('early_settlement_same_side_secondary'))} · SECONDARY, NOT FINAL ACCURACY","Controls: common universe only · no added coverages · no auto-promotion · no orders"]
    if i.get("errors"):lines.append("Integrity errors: "+", ".join(map(str,i.get("errors") or [])))
    return "\n".join(lines)+"\n"
__all__=["VERSION","build_report","render_text"]
