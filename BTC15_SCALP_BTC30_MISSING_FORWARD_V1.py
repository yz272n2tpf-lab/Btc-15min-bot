#!/usr/bin/env python3
"""
BTC15 SCALP BTC30-missing recovery fresh-forward validator V1.

FRESH FORWARD SHADOW ONLY | SIGNAL ONLY | NO ORDERS

Frozen hypothesis
-----------------
The existing V5 adapter remains the baseline:
    side valid, seconds_left >= 120, btc30 exists and btc30 >= 15.

The ONE research projection changes only the adapter treatment of a raw frozen
collector CANDIDATE when btc30 is unavailable:
    if side is valid and seconds_left >= 120 and btc30 is missing, allow that
    already-emitted raw candidate into the same serial lifecycle projection.

If btc30 is present, the existing >=15 requirement remains unchanged. No price
eligibility filter is added. The +5c arm, first 4c giveback EXIT,
ENDED_UNARMED lifecycle reset, and armed/no-validated-exit blocking behavior are
unchanged.

Fresh acceptance gate (locked before future outcomes)
----------------------------------------------------
- cutoff: 2026-09-15T14:16:00Z; nothing before it counts;
- >=30 completed baseline serial opportunities across >=15 contracts;
- >=10 selected missing-btc30 opportunities across >=8 contracts;
- >=5 selected missing-btc30 opportunities with entry <=50c (telemetry only);
- preserve >=90% of baseline opportunity IDs;
- preserve >=95% of baseline +10c winner IDs;
- projected +10 precision may not fall >3 percentage points below baseline;
- selected missing-btc30 class must reach +5 on >=85%;
- selected missing-btc30 class must reach +10 on >=70%;
- >=50% of selected missing-btc30 entries must be <=50c;
- the <=50c selected missing-btc30 subset must reach +10 on >=70%.

A pass earns MANUAL REVIEW ONLY. It never changes V5, production, dashboard
qualification, or order behavior automatically.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_BTC30_MISSING_FORWARD_V1"
CUTOFF_RAW = "2026-09-15T14:16:00Z"
MIN_BASELINE_OPPS = 30
MIN_BASELINE_CONTRACTS = 15
MIN_RECOVERED_MISSING = 10
MIN_RECOVERED_CONTRACTS = 8
MIN_RECOVERED_LE50 = 5
MIN_BASELINE_ID_RETENTION = 0.90
MIN_BASELINE_WINNER_RETENTION = 0.95
MIN_PRECISION_DELTA = -0.03
MIN_RECOVERED_PLUS5 = 0.85
MIN_RECOVERED_PLUS10 = 0.70
MIN_RECOVERED_LE50_SHARE = 0.50
MIN_RECOVERED_LE50_PLUS10 = 0.70
POLL_SEC = max(30, int(os.environ.get("SCALP_BTC30_MISSING_POLL_SEC", "60")))


def cutoff_dt() -> datetime:
    return research.dt(CUTOFF_RAW)


def _valid_side_left(c: Mapping[str, Any]) -> bool:
    side = str(c.get("side") or "").strip().upper()
    left = research.f(c.get("seconds_left"))
    return bool(side in {"UP", "DOWN"} and left is not None and left >= research.SCALP_MIN_SECONDS_LEFT)


def baseline_eligible(c: Mapping[str, Any]) -> bool:
    return research.candidate_qualified(c)


def hypothesis_eligible(c: Mapping[str, Any]) -> bool:
    if not _valid_side_left(c):
        return False
    b30 = research.f(c.get("btc30"))
    return bool(b30 is None or b30 >= research.SCALP_MIN_BTC30)


def missing_btc30(c: Mapping[str, Any]) -> bool:
    return bool(_valid_side_left(c) and research.f(c.get("btc30")) is None)


def fresh_raw_candidates(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    cut = cutoff_dt()
    return [
        dict(r) for r in rows
        if research.typ(r) == "CANDIDATE"
        and research.cid(r)
        and research.contract(r)
        and research.dt(r.get("timestamp_utc")) >= cut
        and _valid_side_left(r)
    ]


def _result_times(rows: list[Mapping[str, Any]]) -> dict[str, datetime]:
    out: dict[str, datetime] = {}
    for r in rows:
        if research.typ(r) != "RESULT":
            continue
        cid = research.cid(r)
        if not cid:
            continue
        t = research.dt(r.get("timestamp_utc"))
        if t == datetime.min.replace(tzinfo=timezone.utc):
            continue
        prev = out.get(cid)
        if prev is None or t < prev:
            out[cid] = t
    return out


def _paths(rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            out[research.cid(r)].append(dict(r))
    return out


def build_serial(
    rows: list[Mapping[str, Any]],
    predicate: Callable[[Mapping[str, Any]], bool],
) -> list[dict[str, Any]]:
    rows = [dict(r) for r in rows]
    results = _result_times(rows)
    paths = _paths(rows)
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in fresh_raw_candidates(rows):
        by_contract[research.contract(c)].append(c)

    out: list[dict[str, Any]] = []
    for contract, candidates in by_contract.items():
        candidates.sort(key=lambda x: research.dt(x.get("timestamp_utc")))
        earliest = datetime.min.replace(tzinfo=timezone.utc)
        used: set[str] = set()
        index = 1
        while True:
            cand = next((
                c for c in candidates
                if research.cid(c) not in used
                and research.dt(c.get("timestamp_utc")) > earliest
                and predicate(c)
            ), None)
            if cand is None:
                break
            cid = research.cid(cand)
            used.add(cid)
            result_time = results.get(cid)
            if result_time is None:
                break

            pm = research.measure_path(cand, research.path_rows_for(cand, paths))
            if pm.exit_time_utc:
                terminal_kind = "PROTECTED_EXIT"
                terminal_time = research.dt(pm.exit_time_utc)
            elif not pm.armed:
                terminal_kind = "ENDED_UNARMED"
                terminal_time = result_time
            else:
                terminal_kind = "ARMED_NO_VALIDATED_EXIT"
                terminal_time = None

            peak = pm.peak_gain
            ask = research.f(cand.get("entry_ask"))
            out.append({
                "contract": contract,
                "candidate_id": cid,
                "opportunity_index": index,
                "timestamp_utc": str(cand.get("timestamp_utc") or ""),
                "side": str(cand.get("side") or "").strip().upper(),
                "entry_ask": ask,
                "entry_at_or_below_50c": bool(ask is not None and ask <= 0.50 + 1e-12),
                "btc30": research.f(cand.get("btc30")),
                "btc30_missing": research.f(cand.get("btc30")) is None,
                "peak_gain": peak,
                "adverse_gain": pm.adverse_gain,
                "plus5": bool(peak is not None and peak >= 0.05 - 1e-12),
                "plus10": bool(peak is not None and peak >= 0.10 - 1e-12),
                "plus20": bool(peak is not None and peak >= 0.20 - 1e-12),
                "terminal_kind": terminal_kind,
                "protected_exit_gain": pm.exit_gain,
                "entry_price_is_telemetry_only": True,
                "orders": False,
            })
            if terminal_time is None:
                break
            earliest = terminal_time
            index += 1

    out.sort(key=lambda r: (research.dt(r.get("timestamp_utc")), str(r.get("candidate_id") or "")))
    return out


def _rate(rows: list[Mapping[str, Any]], key: str) -> float | None:
    return None if not rows else sum(bool(r.get(key)) for r in rows) / len(rows)


def summarize(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    baseline = build_serial(rows, baseline_eligible)
    hypothesis = build_serial(rows, hypothesis_eligible)

    base_ids = {str(r.get("candidate_id") or "") for r in baseline}
    hyp_ids = {str(r.get("candidate_id") or "") for r in hypothesis}
    base_winners = {str(r.get("candidate_id") or "") for r in baseline if r.get("plus10")}
    hyp_winners = {str(r.get("candidate_id") or "") for r in hypothesis if r.get("plus10")}
    base_contracts = {str(r.get("contract") or "") for r in baseline}

    recovered = [r for r in hypothesis if r.get("btc30_missing")]
    recovered_contracts = {str(r.get("contract") or "") for r in recovered}
    recovered_le50 = [r for r in recovered if r.get("entry_at_or_below_50c")]

    base_plus10 = _rate(baseline, "plus10")
    hyp_plus10 = _rate(hypothesis, "plus10")
    id_ret = None if not base_ids else len(base_ids & hyp_ids) / len(base_ids)
    winner_ret = None if not base_winners else len(base_winners & hyp_winners) / len(base_winners)
    precision_delta = None if base_plus10 is None or hyp_plus10 is None else hyp_plus10 - base_plus10
    recovered_plus5 = _rate(recovered, "plus5")
    recovered_plus10 = _rate(recovered, "plus10")
    recovered_le50_share = None if not recovered else len(recovered_le50) / len(recovered)
    recovered_le50_plus10 = _rate(recovered_le50, "plus10")

    sample_ready = bool(
        len(baseline) >= MIN_BASELINE_OPPS
        and len(base_contracts) >= MIN_BASELINE_CONTRACTS
        and len(recovered) >= MIN_RECOVERED_MISSING
        and len(recovered_contracts) >= MIN_RECOVERED_CONTRACTS
        and len(recovered_le50) >= MIN_RECOVERED_LE50
    )
    acceptance_pass = bool(
        sample_ready
        and id_ret is not None and id_ret >= MIN_BASELINE_ID_RETENTION
        and winner_ret is not None and winner_ret >= MIN_BASELINE_WINNER_RETENTION
        and precision_delta is not None and precision_delta >= MIN_PRECISION_DELTA
        and recovered_plus5 is not None and recovered_plus5 >= MIN_RECOVERED_PLUS5
        and recovered_plus10 is not None and recovered_plus10 >= MIN_RECOVERED_PLUS10
        and recovered_le50_share is not None and recovered_le50_share >= MIN_RECOVERED_LE50_SHARE
        and recovered_le50_plus10 is not None and recovered_le50_plus10 >= MIN_RECOVERED_LE50_PLUS10
    )
    status = (
        "READY_FOR_MANUAL_REVIEW" if acceptance_pass
        else "REVIEW_SAMPLE_READY_REJECTED" if sample_ready
        else "COLLECTING_FRESH_FORWARD"
    )

    return {
        "version": VERSION,
        "status": status,
        "cutoff_utc": CUTOFF_RAW,
        "hypothesis": "allow raw candidate when btc30 missing; present btc30 still requires >=15",
        "baseline_n": len(baseline),
        "baseline_contracts": len(base_contracts),
        "baseline_plus10_n": sum(bool(r.get("plus10")) for r in baseline),
        "baseline_plus10_rate": base_plus10,
        "hypothesis_n": len(hypothesis),
        "hypothesis_plus10_n": sum(bool(r.get("plus10")) for r in hypothesis),
        "hypothesis_plus10_rate": hyp_plus10,
        "baseline_id_retention": id_ret,
        "baseline_winner_retention": winner_ret,
        "plus10_precision_delta": precision_delta,
        "recovered_missing_n": len(recovered),
        "recovered_missing_contracts": len(recovered_contracts),
        "recovered_plus5_rate": recovered_plus5,
        "recovered_plus10_rate": recovered_plus10,
        "recovered_plus20_rate": _rate(recovered, "plus20"),
        "recovered_le50_n": len(recovered_le50),
        "recovered_le50_share": recovered_le50_share,
        "recovered_le50_plus10_rate": recovered_le50_plus10,
        "sample_ready": sample_ready,
        "acceptance_pass": acceptance_pass,
        "minimum_baseline_opps": MIN_BASELINE_OPPS,
        "minimum_baseline_contracts": MIN_BASELINE_CONTRACTS,
        "minimum_recovered_missing": MIN_RECOVERED_MISSING,
        "minimum_recovered_contracts": MIN_RECOVERED_CONTRACTS,
        "minimum_recovered_le50": MIN_RECOVERED_LE50,
        "minimum_baseline_id_retention": MIN_BASELINE_ID_RETENTION,
        "minimum_baseline_winner_retention": MIN_BASELINE_WINNER_RETENTION,
        "minimum_precision_delta": MIN_PRECISION_DELTA,
        "minimum_recovered_plus5": MIN_RECOVERED_PLUS5,
        "minimum_recovered_plus10": MIN_RECOVERED_PLUS10,
        "minimum_recovered_le50_share": MIN_RECOVERED_LE50_SHARE,
        "minimum_recovered_le50_plus10": MIN_RECOVERED_LE50_PLUS10,
        "baseline_records": baseline,
        "hypothesis_records": hypothesis,
        "recovered_records": recovered,
        "research_only": True,
        "manual_execution_only": True,
        "orders": False,
        "entry_price_filter_applied": False,
        "price_is_evaluation_telemetry_only": True,
        "new_fixed_time_window_applied": False,
        "protected_thresholds_changed": False,
        "stop_loss_rule_selected": False,
        "auto_promote_allowed": False,
        "production_behavior_changed": False,
        "note": "Passing earns manual review only. V5, V6, V12 and production remain unchanged.",
    }


def _fmt(v: Any, digits: int = 3) -> str:
    if v is None:
        return "NA"
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return str(v)


def cycle() -> dict[str, Any]:
    rows, sha = forward.fetch_csv_rows()
    s = summarize(rows)
    print(
        "BTC30 MISSING FORWARD | "
        f"status={s['status']} | cutoff={s['cutoff_utc']} | "
        f"base={s['baseline_n']}/{s['baseline_contracts']} | base_+10={_fmt(s['baseline_plus10_rate'])} | "
        f"projection={s['hypothesis_n']} | proj_+10={_fmt(s['hypothesis_plus10_rate'])} | "
        f"delta={_fmt(s['plus10_precision_delta'])} | base_id_ret={_fmt(s['baseline_id_retention'])} | "
        f"winner_ret={_fmt(s['baseline_winner_retention'])} | recovered={s['recovered_missing_n']}/{s['recovered_missing_contracts']} | "
        f"rec_+5={_fmt(s['recovered_plus5_rate'])} | rec_+10={_fmt(s['recovered_plus10_rate'])} | "
        f"rec_le50={s['recovered_le50_n']} share={_fmt(s['recovered_le50_share'])} | "
        f"rec_le50_+10={_fmt(s['recovered_le50_plus10_rate'])} | ready={s['sample_ready']} | pass={s['acceptance_pass']} | "
        f"source_sha256={sha} | FRESH FORWARD | NO AUTO-PROMOTE | NO ORDERS",
        flush=True,
    )
    return s


def main() -> int:
    print(
        f"{VERSION} START | cutoff={CUTOFF_RAW} | "
        "ONE HYPOTHESIS: missing btc30 may enter serial projection | "
        "FRESH FORWARD SHADOW | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    while True:
        try:
            cycle()
        except Exception as exc:
            print(
                f"BTC30 MISSING FORWARD ERROR | {type(exc).__name__}: {exc} | RETRYING | NO ORDERS",
                flush=True,
            )
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
