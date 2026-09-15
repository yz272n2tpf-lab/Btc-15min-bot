#!/usr/bin/env python3
"""
BTC15 direct-BRTI Flip Risk forward V2.

READ ONLY | SHADOW ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

Frozen in BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2_FREEZE_20260915.md before any
V2 future outcome is scored. V2 keeps the frozen 12-feature/base-model design
and changes only probability calibration to monotonic isotonic regression.

The startup contract is excluded. Future scoring arms on first rollover.
Production is read only from dashboard_state.json.
"""
from __future__ import annotations

import json
import math
import statistics
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

import BTC15_DIRECT_BRTI_FLIP_RISK_MODEL_V1 as v1

VERSION = "BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2"
MAIN_STATE_URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"
PORT = 8080
POLL_SEC = 5.0
SUPERVISOR_SEC = 5.0
STALE_SEC = 30.0
HEARTBEAT_LOG_SEC = 60.0
FIRST_SEEN_MIN_SECONDS = 840.0
TARGET_MINUTES = tuple(v1.TARGET_REMAINING_MINUTES)
SNAP_TOL_SEC = v1.SNAP_TOL_SEC
MIN_PREDICTIONS_PER_COMPLETE_CONTRACT = 6
MIN_COMPLETE_CONTRACTS = 30
MAX_WAIT_COMPLETE_CONTRACTS = 50
MIN_SETTLED_SNAPSHOTS = 240
MIN_HIGH_STAY_SNAPSHOTS = 30
MIN_HIGH_STAY_CONTRACTS = 8
SETTLEMENT_INITIAL_DELAY_SEC = 30.0
SETTLEMENT_RETRY_SEC = 60.0
BINS = list(v1.BINS)

LOCK = threading.RLock()
MODEL_LOCK = threading.RLock()
MODEL: dict[str, Any] = {
    "ready": False,
    "base": None,
    "isotonic": None,
    "historical_training_prior": None,
    "historical_train_contracts": [],
    "historical_cal_contracts": [],
    "historical_train_snapshots": 0,
    "historical_cal_snapshots": 0,
    "last_error": None,
}
STATE: dict[str, Any] = {
    "started_at_utc": None,
    "startup_contract": None,
    "current_contract": None,
    "live_scoring_armed": False,
    "live_scoring_armed_at_utc": None,
    "first_seen_seconds_left": {},
    "eligible_contracts": [],
    "excluded_late": {},
    "predictions": {},
    "settlements": {},
    "pending_settlement": {},
    "ended_contracts": [],
    "last_poll_utc": None,
    "last_error": None,
}
RUNTIME_LOCK = threading.RLock()
RUNTIME: dict[str, Any] = {
    "generation": 0,
    "worker_alive": False,
    "restarts": 0,
    "iterations": 0,
    "successes": 0,
    "last_iteration_utc": None,
    "last_success_utc": None,
    "last_exception": None,
    "last_heartbeat_monotonic": 0.0,
}
CURRENT_WORKER: threading.Thread | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime | None = None) -> str:
    return (d or _now()).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _dt(v: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def _f(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "BTC15FlipRiskForwardV2/1.0", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _seconds_left(d: Mapping[str, Any]) -> float | None:
    timer = d.get("timer") if isinstance(d.get("timer"), Mapping) else {}
    return _f(timer.get("seconds_left"))


def _contract(d: Mapping[str, Any]) -> str:
    return str(d.get("contract") or "").strip()


def _market(d: Mapping[str, Any]) -> Mapping[str, Any]:
    return d.get("market") if isinstance(d.get("market"), Mapping) else {}


def _current_age(d: Mapping[str, Any], chart_rows: pd.DataFrame) -> float | None:
    market = _market(d)
    parity = d.get("parity") if isinstance(d.get("parity"), Mapping) else {}
    for v in (
        market.get("brti_age_sec"), market.get("brti_age_seconds"),
        parity.get("brti_age_sec"), parity.get("brti_age_seconds"),
    ):
        x = _f(v)
        if x is not None:
            return x
    if len(chart_rows) and "brti_age_sec" in chart_rows.columns:
        x = _f(chart_rows.iloc[-1].get("brti_age_sec"))
        if x is not None:
            return x
    return None


def chart_frame(d: Mapping[str, Any]) -> pd.DataFrame:
    chart = d.get("chart") if isinstance(d.get("chart"), Mapping) else {}
    points = chart.get("points") if isinstance(chart.get("points"), list) else []
    rows = []
    for p in points:
        if not isinstance(p, Mapping):
            continue
        t = _dt(p.get("t"))
        b = _f(p.get("brti"))
        if t is None or b is None or b <= 0:
            continue
        rows.append({
            "timestamp_utc": pd.Timestamp(t),
            "direct_brti": b,
            "brti_age_sec": _f(p.get("brti_age_sec")),
        })
    if not rows:
        return pd.DataFrame(columns=["timestamp_utc", "direct_brti", "brti_age_sec"])
    out = pd.DataFrame(rows).drop_duplicates("timestamp_utc", keep="last")
    return out.sort_values("timestamp_utc").reset_index(drop=True)


def _lag_from_chart(hist: pd.DataFrame, now_ts: pd.Timestamp, lag_sec: float) -> float | None:
    requested = now_ts - pd.Timedelta(seconds=lag_sec)
    q = hist[hist["timestamp_utc"] <= requested]
    if q.empty:
        return None
    r = q.iloc[-1]
    stale = (requested - r["timestamp_utc"]).total_seconds()
    if stale < -1e-9 or stale > v1.LAG_TOL_SEC + 1e-9:
        return None
    x = _f(r["direct_brti"])
    return x if x is not None and x > 0 else None


def live_features(d: Mapping[str, Any], target_minute: int) -> dict[str, float] | None:
    left = _seconds_left(d)
    if left is None or abs(left - target_minute * 60.0) > SNAP_TOL_SEC + 1e-12:
        return None
    market = _market(d)
    cur = _f(market.get("brti_value"))
    target = _f(market.get("target"))
    if cur is None or target is None or cur <= 0 or target <= 0 or abs(cur-target) <= 1e-12:
        return None
    generated = _dt(d.get("generated_utc")) or _now()
    now_ts = pd.Timestamp(generated)
    hist = chart_frame(d)
    if hist.empty:
        return None
    age = _current_age(d, hist)
    if age is not None and age > 5.0 + 1e-12:
        return None
    # Append the authoritative current direct BRTI at the state generation time.
    hist = pd.concat([
        hist,
        pd.DataFrame([{"timestamp_utc": now_ts, "direct_brti": cur, "brti_age_sec": age}]),
    ], ignore_index=True).drop_duplicates("timestamp_utc", keep="last").sort_values("timestamp_utc")
    win = hist[(hist.timestamp_utc >= now_ts - pd.Timedelta(seconds=300)) & (hist.timestamp_utc <= now_ts)].copy()
    if len(win) < 50:
        return None
    gaps = win.timestamp_utc.diff().dt.total_seconds().dropna()
    if len(gaps) and float(gaps.max()) > 8.0 + 1e-12:
        return None
    prices = win.direct_brti.to_numpy(dtype=float)
    if not np.isfinite(prices).all() or np.any(prices <= 0):
        return None
    lag = {}
    for m in (1,2,3,5):
        p = _lag_from_chart(hist, now_ts, m * 60.0)
        if p is None:
            return None
        lag[m] = p
    side_sign = 1.0 if cur > target else -1.0
    signed_dist = (cur-target)/target
    abs_dist = abs(signed_dist)
    remaining = left/60.0
    if remaining <= 0:
        return None
    returns = pd.Series(prices).pct_change().dropna().to_numpy(dtype=float)
    if len(returns) < 2:
        return None
    range_d = float(np.max(prices)-np.min(prices))
    out = {
        "remaining_min": remaining,
        "current_side_sign": side_sign,
        "signed_dist_target_pct": signed_dist,
        "abs_dist_target_pct": abs_dist,
        "dist_per_min_remaining_pct": abs_dist/remaining,
        "aligned_move_1m_pct": ((cur/lag[1])-1.0)*side_sign,
        "aligned_move_2m_pct": ((cur/lag[2])-1.0)*side_sign,
        "aligned_move_3m_pct": ((cur/lag[3])-1.0)*side_sign,
        "aligned_move_5m_pct": ((cur/lag[5])-1.0)*side_sign,
        "brti_range_5m_pct": range_d/cur,
        "brti_vol_5m": float(np.std(returns, ddof=1)),
        "dist_over_range_5m": abs(cur-target)/max(range_d,1e-6),
    }
    if not all(math.isfinite(float(out[k])) for k in v1.FEATURES):
        return None
    out["current_side"] = "UP" if side_sign > 0 else "DOWN"
    out["current_brti"] = cur
    out["target"] = target
    out["generated_utc"] = _iso(generated)
    return out


def train_historical_model() -> None:
    print("FLIP V2 TRAINING | loading frozen direct-BRTI tape | NO ORDERS", flush=True)
    df = v1.load_tape()
    inv = v1.contract_inventory(df)
    usable = inv[inv.usable].copy().sort_values("first_ts")
    ordered = usable.contract.astype(str).tolist()
    if len(ordered) != 94:
        raise RuntimeError(f"frozen usable contract drift: {len(ordered)} != 94")
    truth = v1.fetch_official_truth(ordered)
    ds, excluded = v1.build_dataset(df, ordered, truth)
    train_contracts = ordered[:70]
    cal_contracts = ordered[70:94]
    train = ds[ds.contract.isin(train_contracts)].copy()
    cal = ds[ds.contract.isin(cal_contracts)].copy()
    if len(train) == 0 or len(cal) == 0 or train.flip.nunique() < 2 or cal.flip.nunique() < 2:
        raise RuntimeError("historical V2 train/cal split invalid")
    base = v1._base_model()
    base.fit(train[v1.FEATURES], train.flip)
    raw_cal = base.predict_proba(cal[v1.FEATURES])[:,1]
    iso = IsotonicRegression(out_of_bounds="clip", increasing=True)
    iso.fit(raw_cal, cal.flip.to_numpy(dtype=float))
    with MODEL_LOCK:
        MODEL.update({
            "ready": True,
            "base": base,
            "isotonic": iso,
            "historical_training_prior": float(train.flip.mean()),
            "historical_train_contracts": list(train_contracts),
            "historical_cal_contracts": list(cal_contracts),
            "historical_train_snapshots": len(train),
            "historical_cal_snapshots": len(cal),
            "last_error": None,
        })
    print(
        "FLIP V2 TRAINED | "
        f"train_contracts=70 train_snapshots={len(train)} | "
        f"cal_contracts=24 cal_snapshots={len(cal)} | "
        f"prior={float(train.flip.mean()):.4f} | excluded_grid={excluded['no_snapshot']} | "
        "ISOTONIC ONLY | FUTURE SCORE CLAIMS ONLY | NO ORDERS",
        flush=True,
    )


def predict_from_features(features: Mapping[str, Any]) -> tuple[float,float]:
    with MODEL_LOCK:
        if not MODEL.get("ready"):
            raise RuntimeError("V2 model not ready")
        base = MODEL["base"]
        iso = MODEL["isotonic"]
    x = pd.DataFrame([{k: float(features[k]) for k in v1.FEATURES}])
    raw = float(base.predict_proba(x)[:,1][0])
    calibrated = float(iso.predict([raw])[0])
    calibrated = min(1.0, max(0.0, calibrated))
    return raw, calibrated


def reset_state_for_tests() -> None:
    global CURRENT_WORKER
    with LOCK:
        STATE.update({
            "started_at_utc": None, "startup_contract": None, "current_contract": None,
            "live_scoring_armed": False, "live_scoring_armed_at_utc": None,
            "first_seen_seconds_left": {}, "eligible_contracts": [], "excluded_late": {},
            "predictions": {}, "settlements": {}, "pending_settlement": {},
            "ended_contracts": [], "last_poll_utc": None, "last_error": None,
        })
    with RUNTIME_LOCK:
        RUNTIME.update({
            "generation": 0, "worker_alive": False, "restarts": 0,
            "iterations": 0, "successes": 0, "last_iteration_utc": None,
            "last_success_utc": None, "last_exception": None,
            "last_heartbeat_monotonic": 0.0,
        })
    CURRENT_WORKER = None


def observer_cycle(d: Mapping[str, Any], observed_at: datetime | None = None) -> None:
    now = (observed_at or _now()).astimezone(timezone.utc)
    contract = _contract(d)
    left = _seconds_left(d)
    if not contract or left is None:
        raise ValueError("production state missing contract/timer")
    with LOCK:
        STATE["last_poll_utc"] = _iso(now)
        prior = STATE.get("current_contract")
        if not prior:
            STATE["current_contract"] = contract
            STATE["startup_contract"] = contract
            STATE["first_seen_seconds_left"][contract] = left
            return
        if prior != contract:
            if prior not in STATE["ended_contracts"]:
                STATE["ended_contracts"].append(prior)
            if STATE.get("predictions", {}).get(prior):
                STATE["pending_settlement"].setdefault(
                    prior, _iso(now + timedelta(seconds=SETTLEMENT_INITIAL_DELAY_SEC))
                )
            STATE["current_contract"] = contract
            if not STATE.get("live_scoring_armed"):
                STATE["live_scoring_armed"] = True
                STATE["live_scoring_armed_at_utc"] = _iso(now)
                print(
                    f"FLIP V2 FORWARD ARMED | rollover={prior}->{contract} | at={_iso(now)} | "
                    "STARTUP CONTRACT EXCLUDED | NO ORDERS",
                    flush=True,
                )
        if contract not in STATE["first_seen_seconds_left"]:
            STATE["first_seen_seconds_left"][contract] = left
        if not STATE.get("live_scoring_armed"):
            return
        if contract not in STATE["eligible_contracts"] and contract not in STATE["excluded_late"]:
            first_left = STATE["first_seen_seconds_left"][contract]
            if first_left >= FIRST_SEEN_MIN_SECONDS - 1e-12:
                STATE["eligible_contracts"].append(contract)
                print(
                    f"FLIP V2 ELIGIBLE | {contract} | first_seen_left={first_left:.2f}s | "
                    ">=840s | NO ORDERS",
                    flush=True,
                )
            else:
                STATE["excluded_late"][contract] = first_left
                print(
                    f"FLIP V2 EXCLUDED LATE | {contract} | first_seen_left={first_left:.2f}s | "
                    "NO BACKFILL | NO ORDERS",
                    flush=True,
                )
        eligible = contract in STATE["eligible_contracts"]
        existing = set(int(x) for x in STATE["predictions"].get(contract, {}).keys())
    if not eligible:
        return
    for minute in TARGET_MINUTES:
        if minute in existing or abs(left-minute*60.0) > SNAP_TOL_SEC + 1e-12:
            continue
        feat = live_features(d, minute)
        if feat is None:
            continue
        raw, cal = predict_from_features(feat)
        rec = {
            "contract": contract,
            "target_remaining_min": minute,
            "captured_at_utc": _iso(now),
            "state_generated_utc": feat["generated_utc"],
            "current_side": feat["current_side"],
            "current_brti": feat["current_brti"],
            "target": feat["target"],
            "raw_flip_prob": raw,
            "flip_prob": cal,
            "stay_prob": 1.0-cal,
            "features": {k: float(feat[k]) for k in v1.FEATURES},
        }
        with LOCK:
            bucket = STATE["predictions"].setdefault(contract, {})
            if minute in bucket or str(minute) in bucket:
                continue
            bucket[minute] = rec
        print(
            "FLIP V2 PREDICTION | "
            f"{contract} | {minute}m | side={rec['current_side']} | "
            f"raw={raw:.3f} | flip={cal:.3f} | stay={1-cal:.3f} | "
            "SHADOW ONLY | NO ORDERS",
            flush=True,
        )
        existing.add(minute)
        log_summary()


def _official_settlement(contract: str) -> str | None:
    for base in (v1.LIVE, v1.HIST):
        try:
            p = v1._public_json(base+contract)
            m = p.get("market", p) if isinstance(p, Mapping) else None
            if not isinstance(m, Mapping):
                continue
            result = str(m.get("result") or "").lower().strip()
            status = str(m.get("status") or "").lower().strip()
            if status != "finalized":
                continue
            return "UP" if result == "yes" else ("DOWN" if result == "no" else None)
        except Exception:
            continue
    return None


def maybe_settle(now: datetime | None = None) -> None:
    now = (now or _now()).astimezone(timezone.utc)
    with LOCK:
        pending = dict(STATE["pending_settlement"])
    for contract, raw_due in pending.items():
        due = _dt(raw_due)
        if due is not None and now < due:
            continue
        side = _official_settlement(contract)
        with LOCK:
            if side in {"UP","DOWN"}:
                STATE["settlements"][contract] = side
                STATE["pending_settlement"].pop(contract, None)
                print(f"FLIP V2 SETTLED | {contract} | official={side} | NO ORDERS", flush=True)
                log_summary()
            else:
                STATE["pending_settlement"][contract] = _iso(
                    now + timedelta(seconds=SETTLEMENT_RETRY_SEC)
                )


def _flatten_settled() -> pd.DataFrame:
    rows=[]
    with LOCK:
        preds={c:dict(v) for c,v in STATE["predictions"].items()}
        settlements=dict(STATE["settlements"])
        eligible=set(STATE["eligible_contracts"])
        ended=set(STATE["ended_contracts"])
    for c,bucket in preds.items():
        if c not in settlements:
            continue
        official=settlements[c]
        for key,r in bucket.items():
            x=dict(r)
            x["minute"]=int(key)
            x["official_side"]=official
            x["flip"]=int(x["current_side"] != official)
            rows.append(x)
    return pd.DataFrame(rows)


def summarize_state() -> dict[str, Any]:
    with LOCK:
        eligible=set(STATE["eligible_contracts"])
        ended=set(STATE["ended_contracts"])
        preds={c:dict(v) for c,v in STATE["predictions"].items()}
        settlements=dict(STATE["settlements"])
        excluded=dict(STATE["excluded_late"])
        armed=bool(STATE["live_scoring_armed"])
        startup=STATE["startup_contract"]
    complete=[c for c in eligible & ended if len(preds.get(c,{})) >= MIN_PREDICTIONS_PER_COMPLETE_CONTRACT]
    settled_complete=[c for c in complete if c in settlements]
    df=_flatten_settled()
    if len(df):
        # Keep only prediction-complete contracts in the review sample.
        review=df[df.contract.isin(settled_complete)].copy()
    else:
        review=pd.DataFrame()
    with MODEL_LOCK:
        prior=_f(MODEL.get("historical_training_prior"))
        model_ready=bool(MODEL.get("ready"))
        train_n=int(MODEL.get("historical_train_snapshots") or 0)
        cal_n=int(MODEL.get("historical_cal_snapshots") or 0)
    out={
        "version":VERSION,
        "status":"COLLECTING_FUTURE_V2",
        "model_ready":model_ready,
        "historical_train_snapshots":train_n,
        "historical_cal_snapshots":cal_n,
        "historical_training_prior":prior,
        "startup_contract_excluded":startup,
        "live_scoring_armed":armed,
        "eligible_contracts":len(eligible),
        "excluded_late_contracts":len(excluded),
        "ended_eligible_contracts":len(eligible & ended),
        "prediction_complete_contracts":len(complete),
        "settled_prediction_complete_contracts":len(settled_complete),
        "all_captured_predictions":sum(len(x) for x in preds.values()),
        "settled_review_predictions":len(review),
        "sample_ready":False,
        "gate_pass":False,
        "decision_ready":False,
        "orders":False,
        "manual_execution_only":True,
        "production_changed":False,
        "numeric_flip_risk_user_facing_allowed":False,
    }
    if review.empty or prior is None:
        return out
    raw=float(brier_score_loss(review.flip,review.raw_flip_prob))
    cal=float(brier_score_loss(review.flip,review.flip_prob))
    null=float(brier_score_loss(review.flip,np.full(len(review),prior)))
    skill=1-cal/null if null>0 else None
    rel=[]
    for lo,hi in BINS:
        q=review[(review.flip_prob>=lo)&(review.flip_prob<hi)]
        if len(q)>=20:
            stated=float(q.flip_prob.mean());actual=float(q.flip.mean())
            rel.append({"lo":lo,"hi":min(hi,1.0),"n":len(q),"stated":stated,"actual":actual,"error":abs(stated-actual)})
    ece=(sum(r["n"]*r["error"] for r in rel)/sum(r["n"] for r in rel)) if rel else None
    n30=[r["error"] for r in rel if r["n"]>=30]
    max30=max(n30) if n30 else None
    rho=None
    if len(rel)>=3:
        rho=float(spearmanr([r["stated"] for r in rel],[r["actual"] for r in rel]).statistic)
    high=review[(1-review.flip_prob)>=.90]
    high_actual=float((1-high.flip).mean()) if len(high) else None
    time_rows=[];time_ok=True
    for minute in TARGET_MINUTES:
        q=review[review.minute==minute]
        if len(q)>=20:
            stated=float(q.flip_prob.mean());actual=float(q.flip.mean());err=abs(stated-actual)
            time_rows.append({"minute":minute,"n":len(q),"stated":stated,"actual":actual,"error":err})
            time_ok &= err<=.15+1e-12
    base_ready=(len(settled_complete)>=MIN_COMPLETE_CONTRACTS and len(review)>=MIN_SETTLED_SNAPSHOTS)
    high_ready=len(high)>=MIN_HIGH_STAY_SNAPSHOTS
    forced_high_fail=(len(settled_complete)>=MAX_WAIT_COMPLETE_CONTRACTS and not high_ready)
    decision_ready=bool(base_ready and (high_ready or forced_high_fail))
    brier_ok=cal<=raw+1e-12 and skill is not None and skill>=.05-1e-12
    rel_ok=bool(rel) and ece is not None and ece<=.05+1e-12 and max30 is not None and max30<=.10+1e-12 and len(rel)>=3 and rho is not None and math.isfinite(rho) and rho>=.80-1e-12
    high_ok=bool(high_ready and high.contract.nunique()>=MIN_HIGH_STAY_CONTRACTS and high_actual is not None and high_actual>=.90-1e-12)
    passed=bool(decision_ready and not forced_high_fail and brier_ok and rel_ok and high_ok and time_ok)
    if decision_ready:
        out["status"]="READY_FOR_NUMERIC_FLIP_RISK_MANUAL_REVIEW" if passed else "FUTURE_V2_REVIEW_SAMPLE_FAILED"
    elif base_ready and not high_ready:
        out["status"]="COLLECTING_HIGH_STAY_COHORT"
    out.update({
        "raw_brier":raw,"v2_brier":cal,"null_brier":null,"brier_skill":skill,
        "reliability":rel,"weighted_abs_calibration_error":ece,
        "max_bin_error_n30":max30,"reliability_spearman":rho,
        "stay90_snapshots":len(high),"stay90_contracts":high.contract.nunique() if len(high) else 0,
        "stay90_actual_stay":high_actual,"time_buckets":time_rows,"time_ok":bool(time_ok),
        "sample_ready":bool(base_ready),"high_stay_ready":bool(high_ready),
        "forced_high_stay_fail":bool(forced_high_fail),"decision_ready":decision_ready,
        "brier_gate_ok":bool(brier_ok),"reliability_gate_ok":bool(rel_ok),
        "high_stay_gate_ok":bool(high_ok),"gate_pass":passed,
    })
    return out


def runtime_health(now: datetime | None = None) -> dict[str, Any]:
    now=(now or _now()).astimezone(timezone.utc)
    with RUNTIME_LOCK:
        last=_dt(RUNTIME.get("last_iteration_utc"));out=dict(RUNTIME)
    age=None if last is None else max(0.0,(now-last).total_seconds())
    healthy=bool(out.get("worker_alive") and age is not None and age<=STALE_SEC)
    return {
        "healthy":healthy,"age_sec":age,"stale_sec":STALE_SEC,
        "worker_alive":bool(out.get("worker_alive")),"restarts":int(out.get("restarts") or 0),
        "iterations":int(out.get("iterations") or 0),"successes":int(out.get("successes") or 0),
        "last_success_utc":out.get("last_success_utc"),"last_exception":out.get("last_exception"),
    }


def _one_iteration(now: datetime) -> None:
    d=_fetch_json(MAIN_STATE_URL)
    observer_cycle(d,observed_at=now)
    maybe_settle(now)
    with LOCK:
        STATE["last_error"]=None


def _worker_loop(generation: int) -> None:
    with RUNTIME_LOCK:
        RUNTIME["worker_alive"]=True
    try:
        while True:
            with RUNTIME_LOCK:
                if generation!=int(RUNTIME.get("generation") or 0):return
                RUNTIME["iterations"]=int(RUNTIME.get("iterations") or 0)+1
                RUNTIME["last_iteration_utc"]=_iso()
            now=_now()
            try:
                _one_iteration(now)
                with RUNTIME_LOCK:
                    RUNTIME["successes"]=int(RUNTIME.get("successes") or 0)+1
                    RUNTIME["last_success_utc"]=_iso(now);RUNTIME["last_exception"]=None
            except Exception as exc:
                msg=f"{type(exc).__name__}:{exc}"
                with RUNTIME_LOCK:RUNTIME["last_exception"]=msg
                with LOCK:STATE["last_error"]=msg
                print(f"FLIP V2 WARNING | {msg} | FAIL CLOSED | NO ORDERS",flush=True)
            time.sleep(POLL_SEC)
    finally:
        with RUNTIME_LOCK:
            if generation==int(RUNTIME.get("generation") or 0):RUNTIME["worker_alive"]=False


def _start_worker(replacement: bool) -> None:
    global CURRENT_WORKER
    with RUNTIME_LOCK:
        RUNTIME["generation"]=int(RUNTIME.get("generation") or 0)+1
        gen=int(RUNTIME["generation"])
        if replacement:RUNTIME["restarts"]=int(RUNTIME.get("restarts") or 0)+1
        RUNTIME["worker_alive"]=True;RUNTIME["last_iteration_utc"]=_iso()
    CURRENT_WORKER=threading.Thread(target=_worker_loop,args=(gen,),name=f"flip-v2-worker-{gen}",daemon=True)
    CURRENT_WORKER.start()


def supervisor_loop() -> None:
    _start_worker(False)
    while True:
        h=runtime_health();alive=bool(CURRENT_WORKER and CURRENT_WORKER.is_alive())
        if not alive or not h["healthy"]:
            print(f"FLIP V2 SUPERVISOR | replace worker | alive={alive} age={h['age_sec']} | NO ORDERS",flush=True)
            _start_worker(True)
        mono=time.monotonic()
        with RUNTIME_LOCK:
            due=mono-float(RUNTIME.get("last_heartbeat_monotonic") or 0)>=HEARTBEAT_LOG_SEC
            if due:RUNTIME["last_heartbeat_monotonic"]=mono
        if due:
            s=summarize_state();h=runtime_health()
            print(
                "FLIP V2 HEARTBEAT | "
                f"healthy={h['healthy']} restarts={h['restarts']} | eligible={s['eligible_contracts']} | "
                f"complete={s['prediction_complete_contracts']} settled_complete={s['settled_prediction_complete_contracts']} | "
                f"settled_preds={s['settled_review_predictions']} status={s['status']} | NO ORDERS",
                flush=True,
            )
        time.sleep(SUPERVISOR_SEC)


def log_summary() -> None:
    s=summarize_state()
    def fmt(x,d=3):return "NA" if x is None else f"{float(x):.{d}f}"
    print(
        "FLIP V2 FORWARD | "
        f"status={s['status']} | eligible={s['eligible_contracts']} | complete={s['prediction_complete_contracts']} | "
        f"settled_complete={s['settled_prediction_complete_contracts']} | preds={s['settled_review_predictions']} | "
        f"brier={fmt(s.get('v2_brier'))} raw={fmt(s.get('raw_brier'))} skill={fmt(s.get('brier_skill'))} | "
        f"ece={fmt(s.get('weighted_abs_calibration_error'))} | stay90={s.get('stay90_snapshots',0)} actual={fmt(s.get('stay90_actual_stay'))} | "
        f"ready={s['decision_ready']} pass={s['gate_pass']} | SHADOW ONLY | NO ORDERS",
        flush=True,
    )


class Handler(BaseHTTPRequestHandler):
    server_version="BTC15FlipRiskForwardV2/1.0"
    def log_message(self,fmt,*args):return
    def _json(self,status,obj):
        raw=json.dumps(obj,sort_keys=True,separators=(",",":")).encode()
        self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/health":
            h=runtime_health();return self._json(200 if h["healthy"] else 503,{"ok":h["healthy"],"version":VERSION,"watchdog":h,"model_ready":bool(MODEL.get('ready')),"orders":False})
        if path=="/state":
            return self._json(200,{"ok":True,"version":VERSION,"live":summarize_state(),"watchdog":runtime_health(),"orders":False,"manual_execution_only":True})
        return self._json(404,{"ok":False,"error":"not_found"})


def main() -> int:
    print(
        f"{VERSION} PREP | frozen 70/24 historical train/cal | ISOTONIC ONLY | "
        ">=840s future eligibility | STARTUP EXCLUDED | SHADOW ONLY | NO ORDERS",
        flush=True,
    )
    train_historical_model()
    with LOCK:STATE["started_at_utc"]=_iso()
    print(f"{VERSION} START | FUTURE OUTCOMES ONLY FROM FIRST POST-START ROLLOVER | NO ORDERS",flush=True)
    threading.Thread(target=supervisor_loop,name="flip-v2-supervisor",daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
