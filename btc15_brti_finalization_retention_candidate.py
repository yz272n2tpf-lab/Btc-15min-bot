#!/usr/bin/env python3
"""
Development-only helper for BRTI settlement-finalization retention.

Problem modeled:
Production currently attempts to finalize the just-ended contract, then replaces
its retained metadata as soon as the next active contract appears. If the 60/60
BRTI window is still delayed at that exact handoff, the old contract can stop
being retried and its FINALIZED telemetry can be lost.

This helper keeps an unfinished previous contract in a separate pending slot
until finalization succeeds. It does not touch trading logic, thresholds,
credentials, orders, or production runtime.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple


@dataclass(frozen=True)
class ContractMeta:
    ticker: str
    close_dt: datetime
    target: float


def rollover_retention_step(
    active: Optional[ContractMeta],
    pending: Optional[ContractMeta],
    observed: ContractMeta,
    pending_finalize_succeeded: bool = False,
    active_finalize_succeeded: bool = False,
) -> Tuple[ContractMeta, Optional[ContractMeta], str]:
    """Pure state transition for delayed settlement finalization.

    Rules:
    - Same active contract: keep state unchanged.
    - If an older pending contract exists, clear it only after success.
    - When the active contract changes, a failed finalization attempt moves the
      old active contract into pending instead of discarding it.
    - A successful attempt does not create pending state.
    """
    if active is None:
        return observed, pending, "INITIALIZE_ACTIVE"

    if pending is not None and pending_finalize_succeeded:
        pending = None

    if observed.ticker == active.ticker:
        return active, pending, "SAME_CONTRACT"

    if active_finalize_succeeded:
        return observed, pending, "ROLLOVER_FINALIZED"

    if pending is None:
        pending = active
        return observed, pending, "ROLLOVER_RETAIN_PREVIOUS"

    # Never overwrite an older unfinished settlement silently. The caller can
    # continue retrying pending and surface this condition for operator review.
    return observed, pending, "ROLLOVER_PENDING_ALREADY_OCCUPIED"


if __name__ == "__main__":
    print("BRTI finalization retention candidate — development only")
    print("Production unchanged; no orders; no strategy changes")
