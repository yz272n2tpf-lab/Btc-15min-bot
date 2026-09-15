#!/usr/bin/env python3
"""
BTC15 combined-system fresh-forward scorecard V2.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION ONLY | NO ORDERS

V2 fixes the V1 rollover-observation gap. It reads the frozen V5 combined-state
(main contract/timer authority) directly so EARLY/FINAL can be captured as soon
as the main contract rolls, while reading frozen V5 scalp-state separately and
waiting fail-closed for scalp contract alignment. No signal is recalculated.

Only contracts first seen within 5 seconds of their canonical 15-minute start
are eligible for the common-universe score. Late-seen contracts remain diagnostic
only and cannot inflate the 30-contract / 25-settled gate.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import BTC15_COMBINED_FORWARD_SCORECARD_V1 as v1
from btc15_combined_empirical_scorecard_v2 import score_records

VERSION = "BTC15_COMBINED_FORWARD_SCORECARD_V2"
COMBINED_URL = os.environ.get(
    "BTC15_COMBINED_V5_URL",
    "https://scalp-move-shadow-v1-production.up.railway.app/combined-state",
)
SCALP_URL = os.environ.get(
    "BTC15_SCALP_V5_URL",
    "https://scalp-move-shadow-v1-production.up.railway.app/state",
)
MAX_FIRST_SEEN_LAG_SEC = 5.0
CONTRACT_LENGTH_SEC = 900.0

STATE = v1.STATE
LOCK = v1.LOCK


def _combined_contract(combined: Mapping[str, Any]) -> str:
    if combined.get("version") != "BTC15_COMBINED_STATE_BRIDGE_V5":
        raise ValueError("expected frozen V5 combined-state")
    if combined.get("orders") is not False or combined.get("manual_execution_only") is not True:
        raise ValueError("combined safety envelope invalid")
    if combined.get("order_action") is not None:
        raise ValueError("combined order_action must remain null")
    if combined.get("numeric_flip_risk_validated") is not False:
        raise ValueError("numeric flip risk must remain unvalidated")
    if combined.get("scalp_lifecycle_metadata_only") is not True:
        raise ValueError("combined lifecycle metadata flag missing")
    if combined.get("scalp_ended_unarmed_is_actionable_exit") is not False:
        raise ValueError("ENDED_UNARMED cannot become actionable")
    if combined.get("scalp_armed_no_exit_reset_allowed") is not False:
        raise ValueError("armed/no-exit reset loophole detected")
    contract = str(combined.get("contract") or "").strip()
    if not contract:
        raise ValueError("combined contract missing")
    return contract


def _scalp_contract(scalp: Mapping[str, Any]) -> str:
    if scalp.get("version") != "GENERALIZED_SCALP_INTEGRATION_V5":
        raise ValueError("expected frozen V5 scalp-state")
    if scalp.get("orders") is not False or scalp.get("manual_execution_only") is not True:
        raise ValueError("scalp safety envelope invalid")
    if scalp.get("order_action") is not None:
        raise ValueError("scalp order_action must remain null")
    if scalp.get("lifecycle_ended_unarmed_is_actionable_exit") is not False:
        raise ValueError("ENDED_UNARMED cannot become actionable EXIT")
    if scalp.get("armed_no_exit_reset_allowed") is not False:
        raise ValueError("armed/no-exit reset loophole detected")
    return str(scalp.get("contract") or "").strip()


def _first_seen_meta(combined: Mapping[str, Any]) -> tuple[float | None, float | None, bool]:
    left = v1._f(combined.get("canonical_seconds_left"))
    if left is None:
        return None, None, False
    left = min(CONTRACT_LENGTH_SEC, max(0.0, left))
    lag = max(0.0, CONTRACT_LENGTH_SEC - left)
    return left, lag, bool(lag <= MAX_FIRST_SEEN_LAG_SEC + 1e-12)


def _new_record(contract: str, combined: Mapping[str, Any], observed_at: datetime) -> dict[str, Any]:
    r = v1._new_record(contract)
    left, lag, eligible = _first_seen_meta(combined)
    r.update({
        "first_seen_utc": v1._iso(observed_at),
        "first_seen_seconds_left": left,
        "first_seen_lag_sec": lag,
        "full_observation_eligible": eligible,
        "scalp_alignment_seen": False,
        "scalp_first_aligned_utc": None,
    })
    return r


def reset_state_for_tests() -> None:
    v1.reset_state_for_tests()
    with LOCK:
        STATE["excluded_late_start_contracts"] = []


def observer_cycle(
    combined: Mapping[str, Any],
    scalp: Mapping[str, Any],
    *,
    observed_at: datetime | None = None,
) -> None:
    now = observed_at or v1._now()
    contract = _combined_contract(combined)
    s_contract = _scalp_contract(scalp)
    cutoff = v1._dt(v1.LIVE_CUTOFF_RAW)

    with LOCK:
        STATE["last_poll_utc"] = v1._iso(now)
        prior = STATE.get("current_contract")

        if not prior:
            STATE["current_contract"] = contract
            STATE["startup_contract"] = contract
            return

        if prior != contract:
            if prior in STATE["records"]:
                STATE["pending_settlement"].setdefault(
                    prior,
                    v1._iso(now + timedelta(seconds=v1.SETTLEMENT_INITIAL_DELAY_SEC)),
                )
            STATE["current_contract"] = contract
            if now >= cutoff and STATE.get("live_scoring_armed") is not True:
                STATE["live_scoring_armed"] = True
                STATE["live_scoring_armed_at_utc"] = v1._iso(now)
                print(
                    f"COMBINED V2 ARMED | rollover={prior}->{contract} | at={v1._iso(now)} | "
                    "MAIN AUTHORITY FIRST | NO ORDERS",
                    flush=True,
                )

        if STATE.get("live_scoring_armed") is not True:
            return

        if contract not in STATE["records"]:
            record = _new_record(contract, combined, now)
            STATE["records"][contract] = record
            if record["full_observation_eligible"]:
                if not STATE.get("first_full_contract"):
                    STATE["first_full_contract"] = contract
                print(
                    f"COMBINED V2 FULL CONTRACT | {contract} | first_seen_lag={record['first_seen_lag_sec']:.2f}s | "
                    "ELIGIBLE | NO ORDERS",
                    flush=True,
                )
            else:
                STATE.setdefault("excluded_late_start_contracts", []).append(contract)
                print(
                    f"COMBINED V2 LATE START | {contract} | first_seen_lag={record['first_seen_lag_sec']}s | "
                    "EXCLUDED FROM GATE | NO ORDERS",
                    flush=True,
                )

        record = STATE["records"][contract]
        early_new, final_new = v1._capture_modules(record, combined)

        scalp_new = 0
        scalp_aligned = bool(
            s_contract == contract
            and scalp.get("source_fresh") is True
            and scalp.get("integration_ready") is True
        )
        if scalp_aligned:
            if not record.get("scalp_alignment_seen"):
                record["scalp_alignment_seen"] = True
                record["scalp_first_aligned_utc"] = v1._iso(now)
            scalp_new = v1._capture_scalps(record, scalp)

        if early_new:
            e = record["early"]
            print(
                f"COMBINED V2 EARLY | {contract} | {e['side']} | ask={e['ask']} | "
                f"left={e['seconds_left']}s | NO ORDERS",
                flush=True,
            )
        if final_new:
            f = record["final"]
            print(
                f"COMBINED V2 FINAL | {contract} | {f['side']} | ask={f['ask']} | "
                f"left={f['seconds_left']}s | NO ORDERS",
                flush=True,
            )
        if scalp_new:
            print(
                f"COMBINED V2 SCALP | {contract} | serial_opportunities={len(record['scalps'])} | "
                "ALIGNED | NO ORDERS",
                flush=True,
            )


def summarize_state() -> dict[str, Any]:
    with LOCK:
        all_rows = [dict(r) for r in STATE["records"].values()]
        armed = STATE.get("live_scoring_armed") is True
        first_full = STATE.get("first_full_contract")
        startup = STATE.get("startup_contract")
    eligible_rows = [r for r in all_rows if r.get("full_observation_eligible") is True]
    score = score_records(eligible_rows)
    settled = sum(v1._side(r.get("official_side")) is not None for r in eligible_rows)
    excluded = [r for r in all_rows if r.get("full_observation_eligible") is not True]
    ready = bool(len(eligible_rows) >= v1.MIN_FULL_CONTRACTS and settled >= v1.MIN_SETTLED_CONTRACTS)
    score.update({
        "observer_version": VERSION,
        "status": "COMBINED_SMOKE_SAMPLE_READY" if ready else "COLLECTING_COMBINED_FORWARD_V2",
        "live_cutoff_utc": v1.LIVE_CUTOFF_RAW,
        "live_scoring_armed": armed,
        "first_full_contract": first_full,
        "startup_contract_excluded": startup,
        "partial_start_contract_counted": False,
        "settled_contracts": settled,
        "min_full_contracts": v1.MIN_FULL_CONTRACTS,
        "min_settled_contracts": v1.MIN_SETTLED_CONTRACTS,
        "sample_ready": ready,
        "max_first_seen_lag_sec": MAX_FIRST_SEEN_LAG_SEC,
        "diagnostic_seen_contracts": len(all_rows),
        "excluded_late_start_contracts": [r.get("contract") for r in excluded],
        "excluded_late_start_n": len(excluded),
        "main_authority_captured_before_scalp_alignment": True,
        "scalp_mismatch_is_fail_closed_not_cycle_failure": True,
    })
    return score


def log_summary() -> None:
    s = summarize_state()
    def fmt(v: Any, d: int = 3) -> str:
        return "NA" if v is None else f"{float(v):.{d}f}"
    print(
        f"COMBINED FORWARD V2 | status={s['status']} | eligible={s['contracts']} | "
        f"seen={s['diagnostic_seen_contracts']} | excluded_late={s['excluded_late_start_n']} | settled={s['settled_contracts']} | "
        f"EARLY={s['early_contracts']} acc={fmt(s['early']['accuracy'])} | "
        f"SCALP contracts={s['scalp_contracts']} opps={s['scalp']['opportunities']} +10={fmt(s['scalp']['plus_10c_rate'])} | "
        f"FINAL={s['final_contracts']} acc={fmt(s['final']['accuracy'])} | "
        f"UNION={s['union_actionable_contracts']}/{s['contracts']} ({fmt(s['union_actionable_coverage'])}) | "
        f"ready={s['sample_ready']} | NO ORDERS",
        flush=True,
    )


def observer_loop() -> None:
    print(
        f"{VERSION} START | cutoff={v1.LIVE_CUTOFF_RAW} | V5 MAIN-AUTHORITY FIRST | "
        f"full_contract_lag<={MAX_FIRST_SEEN_LAG_SEC:.1f}s | protected EARLY + serial V5 SCALP + protected FINAL | "
        "UNION COUNTS CONTRACT ONCE | READ ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS",
        flush=True,
    )
    last_contract = None
    while True:
        now = v1._now()
        try:
            combined = v1._fetch_json(COMBINED_URL)
            scalp = v1._fetch_json(SCALP_URL)
            observer_cycle(combined, scalp, observed_at=now)
            v1._maybe_settle(now)
            after = str(STATE.get("current_contract") or "")
            if after and after != last_contract:
                log_summary()
                last_contract = after
            with LOCK:
                STATE["last_error"] = None
        except Exception as exc:
            with LOCK:
                STATE["last_error"] = f"{type(exc).__name__}:{exc}"
            print(
                f"COMBINED FORWARD V2 WARNING | {type(exc).__name__}: {exc} | FAIL CLOSED | NO ORDERS",
                flush=True,
            )
        time.sleep(v1.POLL_SEC)


def main() -> int:
    # Reuse V1's HTTP server and settlement resolver, but replace the runtime
    # observer and summary with V2's rollover-integrity semantics.
    v1.VERSION = VERSION
    v1.observer_loop = observer_loop
    v1.summarize_state = summarize_state
    reset_state_for_tests()
    return v1.main()


if __name__ == "__main__":
    raise SystemExit(main())
