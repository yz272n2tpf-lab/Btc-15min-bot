#!/usr/bin/env python3
"""BTC15 scalp opportunity-quality frontier V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

This scorer asks one narrow question: which information that existed BEFORE a
scalp move helps identify later executable +10c/+20c opportunities?  It never
modifies the collector, FINAL, EARLY, production dashboard, or order behavior.

Validation discipline:
- reproduce the frozen serial scalp lifecycle first;
- candidate-time features only (future path fields are labels, never inputs);
- chronological DEVELOPMENT -> VALIDATION -> untouched HOLDOUT by contract;
- model family and probability threshold chosen on VALIDATION only;
- actual ASK at entry -> future executable BID for every move label;
- 15/30/45/60s verify study re-enters at the THEN-current ASK;
- price bands are diagnostics, not an automatic production gate;
- no promotion from this script; no orders.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
except Exception:  # pragma: no cover
    ExtraTreesClassifier = RandomForestClassifier = None
    SimpleImputer = LogisticRegression = Pipeline = StandardScaler = None

VERSION = "BTC15_SCALP_OPPORTUNITY_QUALITY_FRONTIER_V1"
MIN_SECONDS_LEFT = 120.0
MIN_BTC30 = 15.0
ARM_GAIN = 0.05
GIVEBACK = 0.04

# Causal candidate-time features only. Do not add outcome/path-future columns.
FEATURES = [
    "entry_ask", "spread", "max_possible_upside", "seconds_left",
    "btc_move5_side", "btc_move15_side", "btc_move30_side",
    "brti_move5_side", "brti_move15_side", "ask_move5", "ask_move15",
    "acceleration", "confirm_count", "recent_range60",
    "btc_move5_norm", "btc_move15_norm", "brti_latency_sec", "brti_attempts",
    "structure_ok", "btc_against_side", "brti_against_side",
    "dual_reversal_evidence", "brti_primary_ok",
    "btc_brti_agree5", "btc_brti_agree15", "momentum_floor15",
    "market_response_abs15", "price_extreme", "affordable_le50", "minutes_left",
]
FORBIDDEN = (
    "peak", "adverse", "giveback", "hit5", "hit10", "hit15", "hit20", "hit30",
    "horizon", "result", "settle", "outcome", "future", "protect_armed",
    "profit_floor", "exec_gain", "current_bid", "current_ask",
)


def f(v: Any) -> float | None:
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def b(v: Any) -> int:
    if isinstance(v, bool):
        return int(v)
    return int(str(v or "").strip().lower() in {"1", "true", "yes", "y", "t"})


def dt(v: Any) -> datetime:
    s = str(v or "").strip()
    if not s:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        x = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if x.tzinfo is None:
            x = x.replace(tzinfo=timezone.utc)
        return x.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def typ(r: Mapping[str, Any]) -> str:
    return str(r.get("record_type") or "").strip().upper()


def cid(r: Mapping[str, Any]) -> str:
    return str(r.get("candidate_id") or "").strip()


def contract(r: Mapping[str, Any]) -> str:
    return str(r.get("contract") or "").strip()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def btc30(r: Mapping[str, Any]) -> float | None:
    x = f(r.get("btc30"))
    return x if x is not None else f(r.get("btc_move30_side"))


def baseline_qualified(r: Mapping[str, Any]) -> bool:
    side = str(r.get("side") or "").strip().upper()
    left = f(r.get("seconds_left")); m30 = btc30(r)
    return bool(side in {"UP", "DOWN"} and left is not None and left >= MIN_SECONDS_LEFT
                and m30 is not None and m30 >= MIN_BTC30)


def elapsed(r: Mapping[str, Any], t0: datetime) -> float | None:
    e = f(r.get("elapsed_sec"))
    if e is not None:
        return max(0.0, e)
    tr = dt(r.get("timestamp_utc"))
    if tr == datetime.min.replace(tzinfo=timezone.utc):
        return None
    return max(0.0, (tr - t0).total_seconds())


@dataclass
class PathOutcome:
    peak_gain: float | None = None
    adverse_gain: float | None = None
    exit_gain: float | None = None
    exit_time_utc: str | None = None
    t5_sec: float | None = None
    t10_sec: float | None = None
    t20_sec: float | None = None


def measure_path(candidate: Mapping[str, Any], rows: Iterable[Mapping[str, Any]]) -> PathOutcome:
    t0 = dt(candidate.get("timestamp_utc"))
    z = []
    for r in rows:
        e = elapsed(r, t0); g = f(r.get("exec_gain"))
        if e is not None and g is not None:
            z.append((e, g, r))
    z.sort(key=lambda x: x[0])
    out = PathOutcome()
    if not z:
        return out
    gains = [g for _, g, _ in z]
    out.peak_gain = max(gains); out.adverse_gain = min(gains)
    for target, attr in ((.05, "t5_sec"), (.10, "t10_sec"), (.20, "t20_sec")):
        setattr(out, attr, next((e for e, g, _ in z if g >= target), None))
    peak = -float("inf"); armed = False
    for e, g, r in z:
        peak = max(peak, g)
        armed = armed or peak >= ARM_GAIN
        if armed and peak - g >= GIVEBACK - 1e-12:
            out.exit_gain = g
            tr = dt(r.get("timestamp_utc"))
            if tr == datetime.min.replace(tzinfo=timezone.utc):
                tr = t0 + timedelta(seconds=e)
            out.exit_time_utc = tr.isoformat()
            break
    return out


def n(r: Mapping[str, Any], name: str) -> float:
    x = f(r.get(name)); return np.nan if x is None else float(x)


def candidate_features(r: Mapping[str, Any]) -> dict[str, float]:
    ask = n(r, "entry_ask"); left = n(r, "seconds_left")
    m5 = n(r, "btc_move5_side"); m15 = n(r, "btc_move15_side")
    bm5 = n(r, "brti_move5_side"); bm15 = n(r, "brti_move15_side")
    a15 = n(r, "ask_move15"); m30 = btc30(r)
    out = {
        "entry_ask": ask, "spread": n(r, "spread"),
        "max_possible_upside": n(r, "max_possible_upside"), "seconds_left": left,
        "btc_move5_side": m5, "btc_move15_side": m15,
        "btc_move30_side": np.nan if m30 is None else m30,
        "brti_move5_side": bm5, "brti_move15_side": bm15,
        "ask_move5": n(r, "ask_move5"), "ask_move15": a15,
        "acceleration": n(r, "acceleration"), "confirm_count": n(r, "confirm_count"),
        "recent_range60": n(r, "recent_range60"),
        "btc_move5_norm": n(r, "btc_move5_norm"), "btc_move15_norm": n(r, "btc_move15_norm"),
        "brti_latency_sec": n(r, "brti_latency_sec"), "brti_attempts": n(r, "brti_attempts"),
        "structure_ok": float(b(r.get("structure_ok"))),
        "btc_against_side": float(b(r.get("btc_against_side"))),
        "brti_against_side": float(b(r.get("brti_against_side"))),
        "dual_reversal_evidence": float(b(r.get("dual_reversal_evidence"))),
        "brti_primary_ok": float(str(r.get("brti_status") or "").strip().upper() == "PRIMARY_OK"),
    }
    out["btc_brti_agree5"] = float(math.isfinite(m5) and math.isfinite(bm5) and m5 > 0 and bm5 > 0)
    out["btc_brti_agree15"] = float(math.isfinite(m15) and math.isfinite(bm15) and m15 > 0 and bm15 > 0)
    out["momentum_floor15"] = min(m15, bm15) if math.isfinite(m15) and math.isfinite(bm15) else np.nan
    out["market_response_abs15"] = abs(a15) if math.isfinite(a15) else np.nan
    out["price_extreme"] = float(math.isfinite(ask) and (ask < .10 or ask >= .80))
    out["affordable_le50"] = float(math.isfinite(ask) and ask <= .50)
    out["minutes_left"] = left / 60.0 if math.isfinite(left) else np.nan
    return out


def assert_integrity() -> None:
    bad = [x for x in FEATURES if any(tok in x.lower() for tok in FORBIDDEN)]
    if bad:
        raise RuntimeError(f"future/outcome leakage in feature list: {bad}")


def build_serial_opportunities(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    done = {cid(r) for r in rows if typ(r) == "RESULT" and cid(r)}
    paths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    byc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r0 in rows:
        r = dict(r0)
        if typ(r) == "PATH" and cid(r): paths[cid(r)].append(r)
        if typ(r) == "CANDIDATE" and cid(r) and contract(r): byc[contract(r)].append(r)
    out = []
    for c, raw in byc.items():
        qualified = [r for r in sorted(raw, key=lambda x: dt(x.get("timestamp_utc"))) if baseline_qualified(r)]
        earliest = datetime.min.replace(tzinfo=timezone.utc); used = set(); idx = 1
        while True:
            cand = next((r for r in qualified if cid(r) not in used and dt(r.get("timestamp_utc")) > earliest), None)
            if cand is None: break
            used.add(cid(cand))
            if cid(cand) not in done: break
            pr = sorted(paths.get(cid(cand), []), key=lambda x: elapsed(x, dt(cand.get("timestamp_utc"))) or 0.0)
            pm = measure_path(cand, pr)
            rec = {
                "contract": c, "candidate_id": cid(cand), "timestamp": dt(cand.get("timestamp_utc")),
                "opportunity_index": idx, "side": str(cand.get("side") or "").strip().upper(),
                "plus5": int(pm.peak_gain is not None and pm.peak_gain >= .05),
                "plus10": int(pm.peak_gain is not None and pm.peak_gain >= .10),
                "plus20": int(pm.peak_gain is not None and pm.peak_gain >= .20),
                "peak_gain": pm.peak_gain, "adverse_gain": pm.adverse_gain,
                "protected_exit_gain": pm.exit_gain, "t10_sec": pm.t10_sec, "t20_sec": pm.t20_sec,
                "_candidate": cand, "_paths": pr,
            }
            rec.update(candidate_features(cand)); out.append(rec)
            if not pm.exit_time_utc: break
            earliest = dt(pm.exit_time_utc); idx += 1
    return out


def chronological_split(opps: list[dict[str, Any]]) -> dict[str, str]:
    first: dict[str, datetime] = {}
    for r in opps:
        c = r["contract"]; first[c] = min(first.get(c, r["timestamp"]), r["timestamp"])
    ordered = sorted(first, key=lambda c: first[c]); total = len(ordered)
    if total < 10: return {c: "DEVELOPMENT" for c in ordered}
    i60 = max(1, int(total * .60)); i80 = max(i60 + 1, int(total * .80))
    return {c: ("DEVELOPMENT" if i < i60 else "VALIDATION" if i < i80 else "HOLDOUT")
            for i, c in enumerate(ordered)}


def price_band(v: Any) -> str:
    x = f(v)
    if x is None: return "unknown"
    if x < .10: return "<10c"
    if x < .20: return "10-20c"
    if x < .30: return "20-30c"
    if x < .45: return "30-45c"
    if x < .60: return "45-60c"
    if x < .80: return "60-80c"
    return "80c+"


def label_value(r: Mapping[str, Any], key: str, target: float) -> int:
    if key in r: return int(bool(r.get(key)))
    peak = f(r.get("peak_gain")); return int(peak is not None and peak >= target)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows: return {"n": 0}
    asks = [x for x in (f(r.get("entry_ask")) for r in rows) if x is not None]
    left = [x for x in (f(r.get("seconds_left")) for r in rows) if x is not None]
    peaks = [x for x in (f(r.get("peak_gain")) for r in rows) if x is not None]
    adverse = [x for x in (f(r.get("adverse_gain")) for r in rows) if x is not None]
    exits = [x for x in (f(r.get("protected_exit_gain")) for r in rows) if x is not None]
    t10 = [x for x in (f(r.get("t10_sec")) for r in rows) if x is not None]
    return {
        "n": len(rows), "contracts": len({str(r.get("contract") or "") for r in rows}),
        "plus5_rate": sum(label_value(r, "plus5", .05) for r in rows) / len(rows),
        "plus10_rate": sum(label_value(r, "plus10", .10) for r in rows) / len(rows),
        "plus20_rate": sum(label_value(r, "plus20", .20) for r in rows) / len(rows),
        "avg_entry_ask_c": None if not asks else 100 * statistics.fmean(asks),
        "median_entry_ask_c": None if not asks else 100 * statistics.median(asks),
        "pct_entry_le50": None if not asks else sum(x <= .50 for x in asks) / len(asks),
        "avg_minutes_left": None if not left else statistics.fmean(left) / 60.0,
        "median_peak_c": None if not peaks else 100 * statistics.median(peaks),
        "median_adverse_c": None if not adverse else 100 * statistics.median(adverse),
        "median_protected_exit_c": None if not exits else 100 * statistics.median(exits),
        "median_t10_sec": None if not t10 else statistics.median(t10),
    }


def score_bands(opps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for band in ("<10c", "10-20c", "20-30c", "30-45c", "45-60c", "60-80c", "80c+"):
        z = [r for r in opps if price_band(r.get("entry_ask")) == band]
        if z:
            s = summarize(z); s["price_band"] = band; s["price_is_diagnostic_only"] = True; out.append(s)
    return out


def to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    d = pd.DataFrame([{k: r.get(k, np.nan) for k in FEATURES + ["plus10", "plus20"]} for r in rows])
    for c in FEATURES + ["plus10", "plus20"]: d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


def models():
    if LogisticRegression is None: return []
    return [
        ("LOGISTIC", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                               ("model", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42))])),
        ("RANDOM_FOREST", Pipeline([("impute", SimpleImputer(strategy="median")),
                                    ("model", RandomForestClassifier(n_estimators=600, max_depth=5,
                                      min_samples_leaf=5, class_weight="balanced", random_state=42, n_jobs=-1))])),
        ("EXTRA_TREES", Pipeline([("impute", SimpleImputer(strategy="median")),
                                  ("model", ExtraTreesClassifier(n_estimators=600, max_depth=5,
                                    min_samples_leaf=4, class_weight="balanced", random_state=42, n_jobs=-1))])),
    ]


def fit_frontier(opps: list[dict[str, Any]], split: Mapping[str, str]):
    dev = [r for r in opps if split.get(r["contract"]) == "DEVELOPMENT"]
    val = [r for r in opps if split.get(r["contract"]) == "VALIDATION"]
    hold = [r for r in opps if split.get(r["contract"]) == "HOLDOUT"]
    if min(len(dev), len(val), len(hold)) < 5 or not models(): return [], None, None
    xd = to_frame(dev); xv = to_frame(val); xh = to_frame(hold)
    frontier = []; fitted = {}
    val_contracts = len({r["contract"] for r in val})
    for name, model in models():
        try:
            model.fit(xd[FEATURES], xd["plus10"].astype(int)); p = model.predict_proba(xv[FEATURES])[:, 1]
            fitted[name] = model
            for th in np.arange(.50, .951, .025):
                z = [r for r, pr in zip(val, p) if pr >= th]
                if not z: continue
                s = summarize(z); s.update({"model": name, "threshold": round(float(th), 3),
                    "opportunity_coverage": len(z)/len(val),
                    "contract_coverage": len({r['contract'] for r in z})/val_contracts if val_contracts else None})
                frontier.append(s)
        except Exception as exc:
            frontier.append({"model": name, "error": f"{type(exc).__name__}:{exc}"})
    valid = [r for r in frontier if "error" not in r]
    min_n = max(12, int(math.ceil(len(val) * .20)))
    eligible = [r for r in valid if r.get("n",0) >= min_n and r.get("contracts",0) >= min(8,val_contracts)]
    if not eligible: return frontier, None, None
    passing = [r for r in eligible if (r.get("plus10_rate") or 0) >= .93]
    winner = max(passing if passing else eligible,
                 key=lambda r: (r.get("plus10_rate") or 0, r.get("contract_coverage") or 0,
                                r.get("pct_entry_le50") or 0, r.get("opportunity_coverage") or 0))
    ph = fitted[winner["model"]].predict_proba(xh[FEATURES])[:,1]
    zh = [r for r, pr in zip(hold, ph) if pr >= winner["threshold"]]
    hs = summarize(zh); hs.update({"model": winner["model"],
        "threshold_frozen_from_validation": winner["threshold"],
        "opportunity_coverage": len(zh)/len(hold) if hold else None,
        "contract_coverage": len({r['contract'] for r in zh})/len({r['contract'] for r in hold}) if hold else None,
        "holdout_is_report_only": True})
    return frontier, winner, hs


def verify_entry(candidate: Mapping[str, Any], paths: list[Mapping[str, Any]], delay: float) -> dict[str, Any] | None:
    """At delay, enter at then-current ASK and score only subsequent executable BID."""
    t0 = dt(candidate.get("timestamp_utc")); timeline = []
    for r in paths:
        e = elapsed(r, t0)
        if e is not None: timeline.append((e,r))
    timeline.sort(key=lambda x:x[0])
    vr = next(((e,r) for e,r in timeline if e >= delay and f(r.get("current_ask")) is not None), None)
    if vr is None: return None
    ve, row = vr; ask = f(row.get("current_ask")); assert ask is not None
    future = [(e, f(r.get("current_bid")) - ask) for e,r in timeline if e >= ve and f(r.get("current_bid")) is not None]
    if not future: return None
    peak = max(g for _,g in future); adverse = min(g for _,g in future)
    return {"entry_ask": ask, "peak_gain": peak, "adverse_gain": adverse,
            "plus5": int(peak >= .05), "plus10": int(peak >= .10), "plus20": int(peak >= .20),
            "t10_sec": next((e-ve for e,g in future if g >= .10), None)}


def verify_frontier(opps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for delay in (15.0,30.0,45.0,60.0):
        z = []
        for o in opps:
            x = verify_entry(o["_candidate"], o["_paths"], delay)
            if x:
                x.update({"contract":o["contract"], "seconds_left":max(0.0,(f(o.get("seconds_left")) or 0)-delay)})
                z.append(x)
        s = summarize(z); s["verify_delay_sec"] = delay
        s["note"] = "then-current ASK -> subsequent BID; diagnostic only"
        out.append(s)
    return out


def clean(v: Any):
    if isinstance(v, dict): return {k:clean(x) for k,x in v.items()}
    if isinstance(v, list): return [clean(x) for x in v]
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating,float)):
        return None if not math.isfinite(float(v)) else float(v)
    if isinstance(v, datetime): return v.isoformat()
    return v


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows: path.write_text("",encoding="utf-8"); return
    fields = sorted({k for r in rows for k in r if not k.startswith("_")})
    with path.open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=fields,extrasaction="ignore"); w.writeheader()
        w.writerows([{k:clean(v) for k,v in r.items() if not k.startswith("_")} for r in rows])


def main() -> int:
    assert_integrity()
    ap=argparse.ArgumentParser(); ap.add_argument("csv",nargs="?",default="/data/scalp_move_shadow_v1_events.csv")
    ap.add_argument("--outdir",default="shadow_quality_out"); args=ap.parse_args()
    outdir=Path(args.outdir); outdir.mkdir(parents=True,exist_ok=True)
    opps=build_serial_opportunities(read_rows(Path(args.csv))); split=chronological_split(opps)
    for o in opps: o["split"]=split.get(o["contract"],"")
    bands=score_bands(opps); frontier,winner,hold=fit_frontier(opps,split); verify=verify_frontier(opps)
    report={"version":VERSION,"orders":False,"manual_execution_only":True,"production_logic_changed":False,
      "feature_integrity":"PASS","baseline_serial_blueprint":summarize(opps),"price_band_diagnostics":bands,
      "split_contracts":{s:sum(x==s for x in split.values()) for s in ("DEVELOPMENT","VALIDATION","HOLDOUT")},
      "validation_selected_candidate":winner,"untouched_holdout_result":hold,"candidate_verify_diagnostics":verify,
      "acceptance_markers":{"target_plus10_rate":.93,"stretch_plus10_rate":.95,
        "must_preserve_useful_coverage":True,"must_preserve_entry_economics":True,
        "holdout_never_selects_threshold":True,"promotion":False}}
    write_csv(outdir/"scalp_quality_opportunities_v1.csv",opps)
    write_csv(outdir/"scalp_quality_price_bands_v1.csv",bands)
    write_csv(outdir/"scalp_quality_validation_frontier_v1.csv",frontier)
    write_csv(outdir/"scalp_quality_verify_frontier_v1.csv",verify)
    (outdir/"scalp_quality_report_v1.json").write_text(json.dumps(clean(report),indent=2,sort_keys=True),encoding="utf-8")
    print("="*84); print(VERSION); print("RESEARCH ONLY | SIGNAL ONLY | NO ORDERS"); print("="*84)
    print("Baseline:",json.dumps(clean(report["baseline_serial_blueprint"]),sort_keys=True))
    print("Validation winner:",json.dumps(clean(winner),sort_keys=True))
    print("Untouched holdout:",json.dumps(clean(hold),sort_keys=True)); print("Outputs:",outdir)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
