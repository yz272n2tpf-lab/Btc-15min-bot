#!/usr/bin/env python3
"""
BTC15 protected FINAL forward scorecard V4.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION ONLY | NO ORDERS

V4 preserves the supervised V3 collector and the protected FINAL decision/model.
It fixes the live coverage-universe semantics after rollover research showed that
the production broad market discovery may identify a new contract ~30 seconds
after its canonical start.

For FINAL confirmation, observing second 0 is not required. The protected FINAL
path cannot become eligible until <=8 minutes remain. Therefore a contract is a
valid FINAL-coverage denominator when this observer first sees it BEFORE the
8:00-remaining eligibility window opens. A contract first seen after that point
is excluded fail-closed because an earlier FINAL lock could have been missed.

Fresh V4 cutoff: 2026-09-15T20:00:00Z.
No protected FINAL threshold is changed by this scorecard.

Import-isolation rule
---------------------
This module MUST NOT mutate V1/V2/V3 module globals at import time. Railway runs
V1+V2+V3+V4 unit tests inside one Python process before starting V4. Runtime
callback/version patches are therefore applied only inside main(), which starts
in a separate process after every regression suite has passed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import BTC15_FINAL_FORWARD_SCORECARD_V3 as v3

VERSION = "BTC15_FINAL_FORWARD_SCORECARD_V4"
LIVE_CUTOFF_RAW = "2026-09-15T20:00:00Z"
FINAL_ELIGIBILITY_OPEN_SECONDS_LEFT = 480.0

# Shared state is intentional: V3 owns the supervised worker and settlement
# machinery. Merely binding this reference has no behavior side effect.
STATE = v3.STATE
LOCK = v3.LOCK


def _seconds_left(main_state: Mapping[str, Any]) -> float | None:
    return v3.v2.v1.adapter.protected_main_summary(main_state).get("seconds_left")


def _ensure_v4_state_keys() -> None:
    """Initialize V4-only metadata without changing any protected model state."""
    with LOCK:
        STATE.setdefault("first_seen_seconds_left", {})
        STATE.setdefault("coverage_excluded_late", {})
        STATE.setdefault(
            "coverage_universe_semantics",
            "FIRST_SEEN_BEFORE_FINAL_ELIGIBILITY_WINDOW",
        )


def reset_state_for_tests() -> None:
    """Test helper only; runtime main() never calls this."""
    v3.reset_runtime_for_tests()
    with LOCK:
        STATE["first_seen_seconds_left"] = {}
        STATE["coverage_excluded_late"] = {}
        STATE["coverage_universe_semantics"] = (
            "FIRST_SEEN_BEFORE_FINAL_ELIGIBILITY_WINDOW"
        )


def observer_cycle(
    main_state: Mapping[str, Any],
    observed_at: datetime | None = None,
) -> None:
    _ensure_v4_state_keys()
    now = (observed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = v3.v2.v1._dt(LIVE_CUTOFF_RAW)
    contract = str(main_state.get("contract") or "").strip()
    if not contract:
        raise ValueError("production dashboard state missing contract")
    left = _seconds_left(main_state)

    with LOCK:
        STATE["last_poll_utc"] = v3.v2.v1._iso(now)
        prior = STATE.get("current_contract")
        STATE["current_contract"] = contract

        if contract not in STATE["first_seen_seconds_left"]:
            STATE["first_seen_seconds_left"][contract] = left

        if prior and prior != contract and prior in STATE.get("lock_records", {}):
            STATE["pending_settlement"].setdefault(
                prior,
                v3.v2.v1._iso(
                    now + __import__("datetime").timedelta(seconds=30)
                ),
            )

        if now < cutoff:
            return

        # Count the contract only if we first saw it before any protected FINAL
        # lock could have occurred. This makes coverage valid without falsely
        # claiming second-zero/full-contract observation.
        if (
            contract not in STATE["observed_contracts"]
            and contract not in STATE["coverage_excluded_late"]
        ):
            first_left = STATE["first_seen_seconds_left"].get(contract)
            if (
                first_left is not None
                and float(first_left)
                >= FINAL_ELIGIBILITY_OPEN_SECONDS_LEFT - 1e-12
            ):
                STATE["observed_contracts"].append(contract)
                print(
                    "FINAL V4 COVERAGE-ELIGIBLE CONTRACT | "
                    f"{contract} | first_seen_left={float(first_left):.2f}s | "
                    "SEEN BEFORE FINAL ELIGIBILITY WINDOW | NO ORDERS",
                    flush=True,
                )
            else:
                STATE["coverage_excluded_late"][contract] = first_left
                print(
                    "FINAL V4 COVERAGE EXCLUDED | "
                    f"{contract} | first_seen_left={first_left} | "
                    "FINAL ELIGIBILITY WINDOW MAY HAVE ALREADY OPENED | "
                    "NO ORDERS",
                    flush=True,
                )

        eligible = contract in STATE["observed_contracts"]

    if not eligible:
        return

    # This reads the already-protected production FINAL state. It does not
    # recompute, weaken, or qualify FINAL itself.
    rec = v3.v2.v1.extract_first_lock(main_state, observed_at=now)
    if rec is not None:
        with LOCK:
            if contract not in STATE["lock_records"]:
                STATE["lock_records"][contract] = rec
                print(
                    "FINAL V4 FIRST LOCK | "
                    f"{contract} | {rec['side']} | fair={rec['fair']:.3f} | "
                    f"left={rec['minutes_left']:.2f}m | "
                    f"ask={rec['preferred_ask']} | band={rec['price_band']} | "
                    f"<=50c={rec['ask_at_or_below_50c']} | NO ORDERS",
                    flush=True,
                )
                log_summary()


def summarize_live_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    out = v3.v2.v1.summarize_live_snapshot(state)
    out["version"] = VERSION
    out["live_cutoff_utc"] = LIVE_CUTOFF_RAW
    out["coverage_universe_semantics"] = (
        "FIRST_SEEN_BEFORE_FINAL_ELIGIBILITY_WINDOW"
    )
    out["final_eligibility_open_seconds_left"] = (
        FINAL_ELIGIBILITY_OPEN_SECONDS_LEFT
    )
    out["eligibility_complete_contracts"] = len(
        state.get("observed_contracts") or []
    )
    out["coverage_excluded_late_n"] = len(
        state.get("coverage_excluded_late") or {}
    )
    out["full_contract_from_second_zero_required"] = False
    out["full_contract_from_second_zero_claimed"] = False
    out["protected_final_thresholds_changed"] = False
    out["production_behavior_changed"] = False
    out["numeric_flip_risk_validated"] = False
    out["orders"] = False
    out["manual_execution_only"] = True
    return out


def log_summary() -> None:
    with LOCK:
        s = summarize_live_snapshot(STATE)

    def fmt(v: Any, d: int = 3) -> str:
        return "NA" if v is None else f"{float(v):.{d}f}"

    print(
        "FINAL FORWARD V4 | "
        f"status={s['status']} | cutoff={s['live_cutoff_utc']} | "
        f"eligible={s['eligibility_complete_contracts']} | "
        f"excluded_late={s['coverage_excluded_late_n']} | "
        f"locks={s['lock_calls']} | settled={s['settled_lock_calls']} | "
        f"accuracy={fmt(s['qualified_accuracy'])} | "
        f"coverage={fmt(s['final_only_coverage'])} | "
        f"avg_left={fmt(s['avg_minutes_left'],2)}m | "
        f"med_left={fmt(s['median_minutes_left'],2)}m | "
        f"avg_ask={fmt(s['avg_preferred_ask'])} | "
        f"med_ask={fmt(s['median_preferred_ask'])} | "
        f"ask<=50c={s['ask_le_50c_n']} "
        f"({fmt(s['ask_le_50c_rate'])}) | ready={s['sample_ready']} | "
        "READ ONLY | NO ORDERS",
        flush=True,
    )


class Handler(v3.Handler):
    server_version = "BTC15FinalScorecardV4/1.0"

    def do_GET(self):
        from urllib.parse import urlparse

        path = urlparse(self.path).path
        if path == "/state":
            with LOCK:
                live = summarize_live_snapshot(STATE)
                hist = STATE.get("historical")
                err = STATE.get("last_error")
                last_poll = STATE.get("last_poll_utc")
            return self._json(
                200,
                {
                    "ok": True,
                    "version": VERSION,
                    "historical": hist,
                    "live": live,
                    "watchdog": v3.runtime_health(),
                    "last_poll_utc": last_poll,
                    "last_error": err,
                    "orders": False,
                    "manual_execution_only": True,
                },
            )
        return super().do_GET()


def _apply_runtime_patches() -> None:
    """Patch only the dedicated runtime process, never unittest imports."""
    _ensure_v4_state_keys()

    # Identification/cutoff changes are scorecard-runtime metadata only.
    v3.VERSION = VERSION
    v3.v2.VERSION = VERSION
    v3.v2.LIVE_CUTOFF_RAW = LIVE_CUTOFF_RAW
    v3.v2.v1.LIVE_CUTOFF_RAW = LIVE_CUTOFF_RAW

    # V3 worker calls these callbacks. Replace only the read-only scorecard
    # callbacks after all legacy regression suites have already finished.
    v3.v2.observer_cycle = observer_cycle
    v3.v2.summarize_live_snapshot = summarize_live_snapshot
    v3.v2.log_summary = lambda prefix="FINAL FORWARD V4": log_summary()

    # V3 main resolves Handler from its own module global at runtime.
    v3.Handler = Handler


def main() -> int:
    print(
        f"{VERSION} PREP | cutoff={LIVE_CUTOFF_RAW} | "
        "coverage universe = seen before <=8m FINAL window | "
        "WATCHDOG PRESERVED | MODEL UNCHANGED | NO ORDERS",
        flush=True,
    )
    _apply_runtime_patches()
    return v3.main()


if __name__ == "__main__":
    raise SystemExit(main())
