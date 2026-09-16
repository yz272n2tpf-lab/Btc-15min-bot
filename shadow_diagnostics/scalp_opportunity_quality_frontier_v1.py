#!/usr/bin/env python3
"""BTC15 scalp opportunity-quality frontier V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Purpose
-------
Use the generalized scalp CANDIDATE/PATH/RESULT tape to learn which *causal*
information available at signal time is associated with a later executable
+10c / +20c move.  This script never changes the collector or production bot.

Integrity rules
---------------
* Outcome/path fields are labels only, never model features.
* Actual entry ask and future executable bid are used for move labels.
* Contracts are split chronologically into DEVELOPMENT / VALIDATION / HOLDOUT.
* Model family + probability threshold are selected on VALIDATION only.
* HOLDOUT is revealed once, report-only.
* The currently validated serial scalp lifecycle is reproduced: >=120s left,
  side-aligned 30s BTC move >=15, +5c arm, protected exit after 4c giveback.
* Entry price is analyzed as an explanatory/economic feature, never silently
  turned into a production eligibility rule.
* No orders. Manual execution only.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, asdict
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

# Exact protected baseline lifecycle currently under forward review.
MIN_SECONDS_LEFT = 120.0
MIN_BTC30 = 15.0
ARM_GAIN = 0.05
GIVEBACK = 0.04

# Candidate-time only.  Never add outcome/path-future fields here.
NUMERIC_FEATURES = [
    "entry_ask",
    "spread",
    "max_possible_upside",
    "seconds_left",
    "btc_move5_side",
    "btc_move15_side",
    "btc_move30_side",
    "brti_move5_side",
    "brti_move15_side",
    "ask_move5",
    "ask_move15",
    "acceleration",
    "confirm_count",
    "recent_range60",
    "btc_move5_norm",
    "btc_move15_norm",
    "brti_latency_sec",
    "brti_attempts",
    # engineered, causal
    "btc_brti_agree5",
    "btc_brti_agree15",
    "momentum_floor15",
    "market_response_abs15",
    "price_extreme",
    "affordable_le50",
    "minutes_left",
]
BINARY_FEATURES = [
    "structure_ok",
    "btc_against_side",
    "brti_against_side",
    "dual_reversal_evidence",
    "brti_primary_ok",
]
FEATURES = NUMERIC_FEATURES + BINARY_FEATURES

FORBIDDEN_FEATURE_TOKENS = (
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
    # The forward validator branch uses btc30; older preserved tapes used the
    # explicit btc_move30_side name.  Support both without changing semantics.
    return f(r.get("btc30")) if f(r.get("btc30")) is not None else f(r.get("btc_move30_side"))


def baseline_qualified(r: Mapping[str, Any]) -> bool:
    side = str(r.get("side") or "").strip().upper()
    left = f(r.get("seconds_left"))
    m30 = btc30(r)
    return bool(
        side in {"UP", "DOWN"}
        and left is not None and left >= MIN_SECONDS_LEFT
        and m30 is not None and m30 >= MIN_BTC30
    )


def path_elapsed(r: Mapping[str, Any], t0: datetime) -> float | None:
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
    armed: bool = False
    exit_gain: float | None = None
    exit_elapsed_sec: float | None = None
    exit_time_utc: str | None = None
    t5_sec: float | None = None
    t10_sec: float | None = None
    t20_sec: float | None = None


def measure_original_entry(candidate: Mapping[str, Any], rows: Iterable[Mapping[str, Any]]) -> PathOutcome:
    t0 = dt(candidate.get("timestamp_utc"))
    timeline: list[tuple[float, float, Mapping[str, Any]]] = []
    for r in rows:
        e = path_elapsed(r, t0)
        g = f(r.get("exec_gain"))
        if e is not None and g is not None:
            timeline.append((e, g, r))
    timeline.sort(key=lambda x: x[0])
    out = PathOutcome()
    if not timeline:
        return out

    gains = [x[1] for x in timeline]
    out.peak_gain = max(gains)
    out.adverse_gain = min(gains)
    for target, attr in ((.05, "t5_sec"), (.10, "t10_sec"), (.20, "t20_sec")):
        hit = next((e for e, g, _ in timeline if g >= target), None)
        setattr(out, attr, hit)

    peak = -float("inf")
    armed = False
    for e, g, r in timeline:
        peak = max(peak, g)
        if peak >= ARM_GAIN:
            armed = True
        if armed and peak - g >= GIVEBACK - 1e-12:
            out.exit_gain = g
            out.exit_elapsed_sec = e
            tr = dt(r.get("timestamp_utc"))
            if tr == datetime.min.replace(tzinfo=timezone.utc):
                tr = t0 + timedelta(seconds=e)
            out.exit_time_utc = tr.isoformat()
            break
    out.armed = bool(out.peak_gain is not None and out.peak_gain >= ARM_GAIN)
    return out


def candidate_features(r: Mapping[str, Any]) -> dict[str, float]:
    def n(name: str) -> float:
        x = f(r.get(name))
        return np.nan if x is None else float(x)

    a = n("entry_ask")
    m5 = n("btc_move5_side")
    m15 = n("btc_move15_side")
    m30 = btc30(r)
    bm5 = n("brti_move5_side")
    bm15 = n("brti_move15_side")
    ask15 = n("ask_move15")
    left = n("seconds_left")

    out = {
        "entry_ask": a,
        "spread": n("spread"),
        "max_possible_upside": n("max_possible_upside"),
        "seconds_left": left,
        "btc_move5_side": m5,
        "btc_move15_side": m15,
        "btc_move30_side": np.nan if m30 is None else float(m30),
        "brti_move5_side": bm5,
        "brti_move15_side": bm15,
        "ask_move5": n("ask_move5"),
        "ask_move15": ask15,
        "acceleration": n("acceleration"),
        "confirm_count": n("confirm_count"),
        "recent_range60": n("recent_range60"),
        "btc_move5_norm": n("btc_move5_norm"),
        "btc_move15_norm": n("btc_move15_norm"),
        "brti_latency_sec": n("brti_latency_sec"),
        "brti_attempts": n("brti_attempts"),
        "structure_ok": float(b(r.get("structure_ok"))),
        "btc_against_side": float(b(r.get("btc_against_side"))),
        "brti_against_side": float(b(r.get("brti_against_side"))),
        "dual_reversal_evidence": float(b(r.get("dual_reversal_evidence"))),
        "brti_primary_ok": float(str(r.get("brti_status") or "").strip().upper() == "PRIMARY_OK"),
    }
    out["btc_brti_agree5"] = float(
        math.isfinite(m5) and math.isfinite(bm5) and m5 > 0 and bm5 > 0
    )
    out["btc_brti_agree15"] = float(
        math.isfinite(m15) and math.isfinite(bm15) and m15 > 0 and bm15 > 0
    )
    vals = [x for x in (m15, bm15) if math.isfinite(x)]
    out["momentum_floor15"] = min(vals) if len(vals) == 2 else np.nan
    out["market_response_abs15"] = abs(ask15) if math.isfinite(ask15) else np.nan
    out["price_extreme"] = float(math.isfinite(a) and (a < .10 or a >= .80))
    out["affordable_le50"] = float(math.isfinite(a) and a <= .50)
    out["minutes_left"] = left / 60.0 if math.isfinite(left) else np.nan
    return out


def assert_feature_integrity() -> None:
    bad = [x for x in FEATURES if any(tok in x.lower() for tok in FORBIDDEN_FEATURE_TOKENS)]
    if bad:
        raise RuntimeError(f"future/outcome leakage in feature list: {bad}")


def build_serial_opportunities(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    results = {cid(r) for r in rows if typ(r) == "RESULT" and cid(r)}
    paths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r0 in rows:
        r = dict(r0)
        if typ(r) == "PATH" and cid(r):
            paths[cid(r)].append(r)
        elif typ(r) == "CANDIDATE" and cid(r) and contract(r):
            candidates[contract(r)].append(r)

    out: list[dict[str, Any]] = []
    for c, raw in candidates.items():
        qualified = [x for x in sorted(raw, key=lambda z: dt(z.get("timestamp_utc"))) if baseline_qualified(x)]
        earliest = datetime.min.replace(tzinfo=timezone.utc)
        used: set[str] = set()
        idx = 1
        while True:
            cand = next((x for x in qualified if cid(x) not in used and dt(x.get("timestamp_utc")) > earliest), None)
            if cand is None:
                break
            used.add(cid(cand))
            if cid(cand) not in results:
                break
            pr = sorted(paths.get(cid(cand), []), key=lambda x: path_elapsed(x, dt(cand.get("timestamp_utc"))) or 0.0)
            pm = measure_original_entry(cand, pr)
            rec: dict[str, Any] = {
                "contract": c,
                "candidate_id": cid(cand),
                "timestamp": dt(cand.get("timestamp_utc")),
                "opportunity_index": idx,
                "side": str(cand.get("side") or "").strip().upper(),
                "plus5": int(pm.peak_gain is not None and pm.peak_gain >= .05),
                "plus10": int(pm.peak_gain is not None and pm.peak_gain >= .10),
                "plus20": int(pm.peak_gain is not None and pm.peak_gain >= .20),
                "peak_gain": pm.peak_gain,
                "adverse_gain": pm.adverse_gain,
                "protected_exit_gain": pm.exit_gain,
                "t10_sec": pm.t10_sec,
                "t20_sec": pm.t20_sec,
                "_candidate": cand,
                "_paths": pr,
            }
            rec.update(candidate_features(cand))
            out.append(rec)
            if not pm.exit_time_utc:
                break
            earliest = dt(pm.exit_time_utc)
            idx += 1
    return out


def chronological_split(opps: list[dict[str, Any]]) -> dict[str, str]:
    first: dict[str, datetime] = {}
    for r in opps:
        c = r["contract"]
        first[c] = min(first.get(c, r["timestamp"]), r["timestamp"])
    ordered = sorted(first, key=lambda c: first[c])
    n = len(ordered)
    if n < 10:
        return {c: "DEVELOPMENT" for c in ordered}
    i60 = max(1, int(n * .60))
    i80 = max(i60 + 1, int(n * .80))
    return {
        c: ("DEVELOPMENT" if i < i60 else "VALIDATION" if i < i80 else "HOLDOUT")
        for i, c in enumerate(ordered)
    }


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


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    asks = [f(r.get("entry_ask")) for r in rows]
    asks = [x for x in asks if x is not None]
    left = [f(r.get("seconds_left")) for r in rows]
    left = [x for x in left if x is not None]
    peaks = [f(r.get("peak_gain")) for r in rows]
    peaks = [x for x in peaks if x is not None]
    adv = [f(r.get("adverse_gain")) for r in rows]
    adv = [x for x in adv if x is not None]
    exits = [f(r.get("protected_exit_gain")) for r in rows]
    exits = [x for x in exits if x is not None]
    t10 = [f(r.get("t10_sec")) for r in rows if f(r.get("t10_sec")) is not None]
    return {
        "n": len(rows),
        "contracts": len({r["contract"] for r in rows}),
        "plus5_rate": sum(int(r["plus5"]) for r in rows) / len(rows),
        "plus10_rate": sum(int(r["plus10"]) for r in rows) / len(rows),
        "plus20_rate": sum(int(r["plus20"]) for r in rows) / len(rows),
        "avg_entry_ask_c": None if not asks else 100 * statistics.fmean(asks),
        "median_entry_ask_c": None if not asks else 100 * statistics.median(asks),
        "pct_entry_le50": None if not asks else sum(x <= .50 for x in asks) / len(asks),
        "avg_minutes_left": None if not left else statistics.fmean(left) / 60.0,
        "median_peak_c": None if not peaks else 100 * statistics.median(peaks),
        "median_adverse_c": None if not adv else 100 * statistics.median(adv),
        "median_protected_exit_c": None if not exits else 100 * statistics.median(exits),
        "median_t10_sec": None if not t10 else statistics.median(t10),
    }


def score_price_bands(opps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for band in ("<10c", "10-20c", "20-30c", "30-45c", "45-60c", "60-80c", "80c+"):
        x = [r for r in opps if price_band(r.get("entry_ask")) == band]
        if x:
            s = summarize(x); s["price_band"] = band; out.append(s)
    return out


def model_candidates():
    if LogisticRegression is None:
        return []
    return [
        (
            "LOGISTIC",
            Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)),
            ]),
        ),
        (
            "RANDOM_FOREST",
            Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("model", RandomForestClassifier(
                    n_estimators=600, max_depth=5, min_samples_leaf=5,
                    class_weight="balanced", random_state=42, n_jobs=-1,
                )),
            ]),
        ),
        (
            "EXTRA_TREES",
            Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("model", ExtraTreesClassifier(
                    n_estimators=600, max_depth=5, min_samples_leaf=4,
                    class_weight="balanced", random_state=42, n_jobs=-1,
                )),
            ]),
        ),
    ]


def to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    d = pd.DataFrame([{k: r.get(k, np.nan) for k in FEATURES + ["plus10", "plus20", "contract"]} for r in rows])
    for c in FEATURES + ["plus10", "plus20"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


def threshold_frontier(
    name: str, model, validation_rows: list[dict[str, Any]], probs: np.ndarray,
    baseline_contracts: int,
) -> list[dict[str, Any]]:
    out = []
    for th in np.arange(.50, .951, .025):
        selected = [r for r, p in zip(validation_rows, probs) if p >= th]
        s = summarize(selected)
        if not selected:
            continue
        s.update({
            "model": name,
            "threshold": round(float(th), 3),
            "opportunity_coverage": len(selected) / len(validation_rows),
            "contract_coverage": len({r["contract"] for r in selected}) / baseline_contracts if baseline_contracts else None,
        })
        out.append(s)
    return out


def select_validation_winner(frontier: list[dict[str, Any]], val_n: int, val_contracts: int) -> dict[str, Any] | None:
    # Prevent tiny-sample fake accuracy.  Require >=12 signals, >=8 contracts,
    # and at least 20% of validation opportunities.  Prefer >=93% if real;
    # otherwise select the strongest honest fallback for holdout diagnosis.
    min_n = max(12, int(math.ceil(val_n * .20)))
    eligible = [
        r for r in frontier
        if r.get("n", 0) >= min_n and r.get("contracts", 0) >= min(8, val_contracts)
    ]
    if not eligible:
        return None
    passing = [r for r in eligible if (r.get("plus10_rate") or 0) >= .93]
    pool = passing if passing else eligible
    return max(
        pool,
        key=lambda r: (
            r.get("plus10_rate") or 0,
            r.get("contract_coverage") or 0,
            r.get("pct_entry_le50") or 0,
            r.get("opportunity_coverage") or 0,
        ),
    )


def fit_quality_frontier(opps: list[dict[str, Any]], split_map: Mapping[str, str]):
    dev = [r for r in opps if split_map.get(r["contract"]) == "DEVELOPMENT"]
    val = [r for r in opps if split_map.get(r["contract"]) == "VALIDATION"]
    hold = [r for r in opps if split_map.get(r["contract"]) == "HOLDOUT"]
    if min(len(dev), len(val), len(hold)) < 5 or not model_candidates():
        return [], None, None

    xdev = to_frame(dev); xval = to_frame(val); xhold = to_frame(hold)
    frontier: list[dict[str, Any]] = []
    fitted: dict[str, Any] = {}
    for name, model in model_candidates():
        try:
            model.fit(xdev[FEATURES], xdev["plus10"].astype(int))
            pv = model.predict_proba(xval[FEATURES])[:, 1]
            frontier.extend(threshold_frontier(name, model, val, pv, len({r["contract"] for r in val})))
            fitted[name] = model
        except Exception as exc:
            frontier.append({"model": name, "error": f"{type(exc).__name__}:{exc}"})

    winner = select_validation_winner(
        [r for r in frontier if "error" not in r], len(val), len({r["contract"] for r in val})
    )
    if not winner:
        return frontier, None, None
    model = fitted[winner["model"]]
    ph = model.predict_proba(xhold[FEATURES])[:, 1]
    selected_hold = [r for r, p in zip(hold, ph) if p >= winner["threshold"]]
    hold_score = summarize(selected_hold)
    hold_score.update({
        "model": winner["model"],
        "threshold_frozen_from_validation": winner["threshold"],
        "opportunity_coverage": len(selected_hold) / len(hold) if hold else None,
        "contract_coverage": len({r["contract"] for r in selected_hold}) / len({r["contract"] for r in hold}) if hold else None,
        "holdout_is_report_only": True,
    })
    return frontier, winner, hold_score


def verify_reentry(candidate: Mapping[str, Any], paths: list[Mapping[str, Any]], delay: float) -> dict[str, Any] | None:
    """Enter only after delay using then-current ASK; score future executable BID."""
    t0 = dt(candidate.get("timestamp_utc"))
    timeline = []
    for r in paths:
        e = path_elapsed(r, t0)
        if e is not None:
            timeline.append((e, r))
    timeline.sort(key=lambda x: x[0])
    hit = next(((e, r) for e, r in timeline if e >= delay), None)
    if hit is None:
        return None
    ve, vr = hit
    ask = f(vr.get("current_ask"))
    if ask is None:
        return None
    future = []
    for e, r in timeline:
        if e < ve:
            continue
        bid = f(r.get("current_bid"))
        if bid is not None:
            future.append((e, bid - ask))
    if not future:
        return None
    peak = max(g for _, g in future)
    adverse = min(g for _, g in future)
    t10 = next((e - ve for e, g in future if g >= .10), None)
    return {
        "delay_sec": delay,
        "verify_entry_ask": ask,
        "plus10": int(peak >= .10),
        "plus20": int(peak >= .20),
        "peak_gain": peak,
        "adverse_gain": adverse,
        "t10_sec": t10,
        "verify_btc5": f(vr.get("btc_move5_side")),
        "verify_btc15": f(vr.get("btc_move15_side")),
        "verify_brti5": f(vr.get("brti_move5_side")),
        "verify_brti15": f(vr.get("brti_move15_side")),
        "verify_ask_move15": f(vr.get("ask_move15")),
        "verify_dual_reversal": b(vr.get("dual_reversal_evidence")),
    }


def verify_frontier(opps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for delay in (15.0, 30.0, 45.0, 60.0):
        rows = []
        for o in opps:
            x = verify_reentry(o["_candidate"], o["_paths"], delay)
            if x:
                x.update({"contract": o["contract"], "entry_ask": x["verify_entry_ask"], "seconds_left": max(0.0, (o.get("seconds_left") or 0) - delay)})
                rows.append(x)
        s = summarize(rows)
        s["verify_delay_sec"] = delay
        s["note"] = "later ASK -> future BID; diagnostic only, not serial-lifecycle promotion"
        out.append(s)
    return out


def clean_for_json(v: Any):
    if isinstance(v, dict): return {k: clean_for_json(x) for k, x in v.items()}
    if isinstance(v, list): return [clean_for_json(x) for x in v]
    if isinstance(v, (np.floating, float)):
        return None if not math.isfinite(float(v)) else float(v)
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, datetime): return v.isoformat()
    return v


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8"); return
    fields = sorted({k for r in rows for k in r.keys() if not k.startswith("_")})
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows([{k: clean_for_json(v) for k, v in r.items() if not k.startswith("_")} for r in rows])


def main() -> int:
    assert_feature_integrity()
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="/data/scalp_move_shadow_v1_events.csv")
    ap.add_argument("--outdir", default="shadow_quality_out")
    args = ap.parse_args()
    src = Path(args.csv)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    rows = read_rows(src)
    opps = build_serial_opportunities(rows)
    split_map = chronological_split(opps)
    for o in opps:
        o["split"] = split_map.get(o["contract"], "")

    baseline = summarize(opps)
    bands = score_price_bands(opps)
    frontier, winner, holdout = fit_quality_frontier(opps, split_map)
    verify = verify_frontier(opps)

    report = {
        "version": VERSION,
        "source": str(src),
        "orders": False,
        "manual_execution_only": True,
        "production_logic_changed": False,
        "feature_integrity": "PASS",
        "baseline_serial_blueprint": baseline,
        "price_band_diagnostics": bands,
        "chronological_split_contracts": {
            s: sum(v == s for v in split_map.values()) for s in ("DEVELOPMENT", "VALIDATION", "HOLDOUT")
        },
        "validation_selected_candidate": winner,
        "untouched_holdout_result": holdout,
        "candidate_verify_diagnostics": verify,
        "acceptance_markers": {
            "target_plus10_rate": .93,
            "stretch_plus10_rate": .95,
            "must_preserve_useful_coverage": True,
            "must_preserve_entry_economics": True,
            "holdout_never_selects_threshold": True,
            "promotion": False,
        },
    }

    write_csv(outdir / "scalp_quality_opportunities_v1.csv", opps)
    write_csv(outdir / "scalp_quality_price_bands_v1.csv", bands)
    write_csv(outdir / "scalp_quality_validation_frontier_v1.csv", frontier)
    write_csv(outdir / "scalp_quality_verify_frontier_v1.csv", verify)
    (outdir / "scalp_quality_report_v1.json").write_text(
        json.dumps(clean_for_json(report), indent=2, sort_keys=True), encoding="utf-8"
    )

    print("=" * 84)
    print(VERSION)
    print("RESEARCH ONLY | SIGNAL ONLY | NO ORDERS")
    print("=" * 84)
    print("Baseline:", json.dumps(clean_for_json(baseline), sort_keys=True))
    print("Split contracts:", report["chronological_split_contracts"])
    print("Validation winner:", json.dumps(clean_for_json(winner), sort_keys=True))
    print("Untouched holdout:", json.dumps(clean_for_json(holdout), sort_keys=True))
    print("Outputs:", outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
