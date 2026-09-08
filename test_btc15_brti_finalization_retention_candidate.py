from datetime import datetime, timedelta, timezone

from btc15_brti_finalization_retention_candidate import (
    ContractMeta,
    rollover_retention_step,
)


def meta(name, minute):
    return ContractMeta(
        ticker=name,
        close_dt=datetime(2026, 9, 8, 23, minute, tzinfo=timezone.utc),
        target=78000.0 + minute,
    )


def test_same_contract_keeps_state():
    active = meta("A", 15)
    got_active, pending, reason = rollover_retention_step(active, None, active)
    assert got_active == active
    assert pending is None
    assert reason == "SAME_CONTRACT"


def test_failed_finalize_is_retained_across_rollover():
    old = meta("A", 15)
    new = meta("B", 30)
    got_active, pending, reason = rollover_retention_step(
        old,
        None,
        new,
        active_finalize_succeeded=False,
    )
    assert got_active == new
    assert pending == old
    assert reason == "ROLLOVER_RETAIN_PREVIOUS"


def test_pending_clears_only_after_late_success():
    old = meta("A", 15)
    new = meta("B", 30)
    newer_snapshot = meta("B", 30)

    active, pending, _ = rollover_retention_step(
        old,
        None,
        new,
        active_finalize_succeeded=False,
    )
    assert pending == old

    active, pending, reason = rollover_retention_step(
        active,
        pending,
        newer_snapshot,
        pending_finalize_succeeded=True,
    )
    assert active == new
    assert pending is None
    assert reason == "SAME_CONTRACT"


def test_successful_finalize_never_creates_pending():
    old = meta("A", 15)
    new = meta("B", 30)
    active, pending, reason = rollover_retention_step(
        old,
        None,
        new,
        active_finalize_succeeded=True,
    )
    assert active == new
    assert pending is None
    assert reason == "ROLLOVER_FINALIZED"


def test_existing_unfinished_pending_is_never_overwritten():
    pending_old = meta("A", 15)
    active = meta("B", 30)
    new = ContractMeta(
        ticker="C",
        close_dt=active.close_dt + timedelta(minutes=15),
        target=78045.0,
    )
    got_active, pending, reason = rollover_retention_step(
        active,
        pending_old,
        new,
        pending_finalize_succeeded=False,
        active_finalize_succeeded=False,
    )
    assert got_active == new
    assert pending == pending_old
    assert reason == "ROLLOVER_PENDING_ALREADY_OCCUPIED"
