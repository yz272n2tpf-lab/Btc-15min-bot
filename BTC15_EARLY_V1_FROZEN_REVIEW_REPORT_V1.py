#!/usr/bin/env python3
"""BTC15 EARLY V1 frozen review report.

PURE / OFFLINE / READ ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

EARLY is the affordable opportunity/entry lane. Settlement same-side rate is
secondary directional context and is never FINAL accuracy.
"""
from __future__ import annotations
import math
from typing import Any, Mapping

VERSION="BTC15_EARLY_V1_FROZEN_REVIEW_REPORT_V1"
EXPECTED_VERSION="BTC15_EARLY_FORWARD_SCORECARD_V1"
EXPECTED_COVERAGE="FIRST_SEEN_BEFORE_EARLY_10M_ELIGIBILITY_WINDOW"
EXPECTED_WINDOW=600.0
MIN_ELIGIBLE=30
MIN_SETTLED=12
EPS=1e-9

def _m(v): return v if isinstance(v,Mapping) else {}
def _i(v):
    try:return int(v)
    except (TypeError,ValueError):return 0
def _f(v):
    if v is None or isinstance(v,bool):return None
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError):return None
def _rate(n,d): return None if d<=0 else n/d
def _close(a,b):
    x,y=_f(a),_f(b)
    return (x is None and y is None) if (x is None or y is None) else abs(x-y)<=EPS
def _live(p):
    q=p.get("live") if isinstance(p,Mapping) else None
    return q if isinstance(q,Mapping) else _m(p)

def build_report(payload:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(payload,Mapping): raise TypeError("EARLY payload must be a mapping")
    s=_live(payload); errors=[]
    version=str(payload.get("version") or s.get("version") or "")
    if version!=EXPECTED_VERSION: errors.append(f"collector_version:{version or 'MISSING'}")
    if str(s.get("coverage_universe_semantics") or "")!=EXPECTED_COVERAGE: errors.append("coverage_semantics")
    if not _close(s.get("early_eligibility_open_seconds_left"),EXPECTED_WINDOW): errors.append("eligibility_window")
    if s.get("fresh_start_semantics")!="FIRST_POST_START_ROLLOVER": errors.append("fresh_start_semantics")
    if s.get("protected_early_thresholds_changed") is not False: errors.append("protected_thresholds_changed")
    if s.get("price_filter_added") is not False: errors.append("price_filter_added")
    if s.get("production_behavior_changed") is not False: errors.append("production_behavior_changed")
    if s.get("numeric_flip_risk_validated") is not False: errors.append("numeric_flip_risk_unexpected")
    if s.get("manual_execution_only") is not True: errors.append("manual_execution_only_not_true")
    if s.get("orders") is not False or payload.get("orders") is True: errors.append("orders_not_false")
    if s.get("settlement_accuracy_is_secondary_not_final_authority") is not True: errors.append("settlement_semantics")

    eligible=_i(s.get("eligibility_complete_contracts")); calls=_i(s.get("early_calls")); settled=_i(s.get("settled_early_calls")); same=_i(s.get("settlement_same_side_n")); le50=_i(s.get("ask_le_50c_n")); ideal=_i(s.get("ask_25_35c_n"))
    if any(x<0 for x in (eligible,calls,settled,same,le50,ideal)): errors.append("negative_counts")
    if calls>eligible: errors.append("calls_gt_eligible")
    if settled>calls: errors.append("settled_gt_calls")
    if same>settled: errors.append("same_side_gt_settled")
    if le50>calls or ideal>calls or ideal>le50: errors.append("entry_band_counts")
    if not _close(s.get("early_only_coverage"),_rate(calls,eligible)): errors.append("coverage_math")
    if not _close(s.get("settlement_same_side_rate_secondary"),_rate(same,settled)): errors.append("settlement_rate_math")
    if not _close(s.get("ask_le_50c_rate"),_rate(le50,calls)): errors.append("le50_rate_math")
    if not _close(s.get("ask_25_35c_rate"),_rate(ideal,calls)): errors.append("ideal_rate_math")

    integrity=not errors; counts_ready=eligible>=MIN_ELIGIBLE and settled>=MIN_SETTLED; collector_ready=bool(s.get("sample_ready")); ready=integrity and counts_ready and collector_ready
    status="INVALID_SNAPSHOT_FAIL_CLOSED" if not integrity else ("EARLY_V1_MANUAL_REVIEW_READY" if ready else "WAITING_FOR_FROZEN_GATE")
    return {
      "version":VERSION,"status":status,
      "integrity":{"pass":integrity,"errors":errors},
      "frozen_gate":{"eligible_contracts":eligible,"minimum_eligible_contracts":MIN_ELIGIBLE,"settled_early_calls":settled,"minimum_settled_early_calls":MIN_SETTLED,"remaining_eligible":max(0,MIN_ELIGIBLE-eligible),"remaining_settled":max(0,MIN_SETTLED-settled),"counts_ready":counts_ready,"collector_sample_ready":collector_ready,"manual_review_ready":ready},
      "entry_economics":{"early_calls":calls,"early_only_coverage":_f(s.get("early_only_coverage")),"avg_ask":_f(s.get("avg_ask")),"median_ask":_f(s.get("median_ask")),"ask_le_50c_n":le50,"ask_le_50c_rate":_f(s.get("ask_le_50c_rate")),"ideal_25_35c_n":ideal,"ideal_25_35c_rate":_f(s.get("ask_25_35c_rate"))},
      "timing_model_context":{"avg_minutes_left":_f(s.get("avg_minutes_left")),"median_minutes_left":_f(s.get("median_minutes_left")),"avg_fair":_f(s.get("avg_fair")),"avg_edge":_f(s.get("avg_edge"))},
      "secondary_direction":{"settled_early_calls":settled,"same_side_n":same,"settlement_same_side_rate":_f(s.get("settlement_same_side_rate_secondary")),"is_final_accuracy":False},
      "coverage":{"eligible_contracts":eligible,"excluded_late":_i(s.get("coverage_excluded_late_n")),"union_coverage_claimed":False},
      "decision_controls":{"auto_promote_allowed":False,"threshold_retune_allowed_from_confirmation_sample":False,"price_filter_added":False,"numeric_flip_risk_validated":False,"manual_review_required":True,"orders":False},
    }

def _pct(v):
    x=_f(v); return "—" if x is None else f"{100*x:.1f}%"
def _c(v):
    x=_f(v); return "—" if x is None else f"{100*x:.1f}¢"
def _min(v):
    x=_f(v); return "—" if x is None else f"{x:.2f}m"
def render_text(r):
    g=_m(r.get("frozen_gate")); e=_m(r.get("entry_economics")); t=_m(r.get("timing_model_context")); d=_m(r.get("secondary_direction")); i=_m(r.get("integrity"))
    lines=["=== BTC15 EARLY V1 FROZEN REVIEW ===",f"Status: {r.get('status')}",f"Integrity: {'PASS' if i.get('pass') else 'FAIL'}",f"Gate: eligible {g.get('eligible_contracts',0)}/{g.get('minimum_eligible_contracts',30)} · settled EARLY {g.get('settled_early_calls',0)}/{g.get('minimum_settled_early_calls',12)}",f"Remaining: eligible {g.get('remaining_eligible',0)} · settled {g.get('remaining_settled',0)}",f"EARLY-only coverage: {_pct(e.get('early_only_coverage'))} ({e.get('early_calls',0)} calls)",f"Entry ask: avg {_c(e.get('avg_ask'))} · median {_c(e.get('median_ask'))}",f"<=50¢: {e.get('ask_le_50c_n',0)} ({_pct(e.get('ask_le_50c_rate'))}) · ideal 25–35¢: {e.get('ideal_25_35c_n',0)} ({_pct(e.get('ideal_25_35c_rate'))})",f"Timing: avg {_min(t.get('avg_minutes_left'))} · median {_min(t.get('median_minutes_left'))}",f"Model context: avg fair {_pct(t.get('avg_fair'))} · avg edge {_pct(t.get('avg_edge'))}",f"Settlement same-side: {_pct(d.get('settlement_same_side_rate'))} ({d.get('same_side_n',0)}/{d.get('settled_early_calls',0)}) · SECONDARY, NOT FINAL ACCURACY","Controls: manual review only · no retune · no price filter · no auto-promotion · no orders"]
    if i.get("errors"): lines.append("Integrity errors: "+", ".join(map(str,i.get("errors") or [])))
    return "\n".join(lines)+"\n"

__all__=["VERSION","EXPECTED_VERSION","MIN_ELIGIBLE","MIN_SETTLED","build_report","render_text"]
