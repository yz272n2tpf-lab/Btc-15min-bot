#!/usr/bin/env python3
from datetime import datetime, timezone, timedelta

from btc15_brti_rollover_target_fallback_candidate import (
    FinalizedBrtiWindow,
    candidate_target,
    reconcile_with_official,
)


def dt(hour, minute):
    return datetime(2026, 9, 8, hour, minute, tzinfo=timezone.utc)


def test_bad_1815_rollover_restores_known_target():
    prev = FinalizedBrtiWindow(
        ticker="KXBTC15M-26SEP081415-15",
        close_dt=dt(18, 15),
        final60_avg=78658.64,
        final60_count=60,
        final60_complete=True,
    )
    target, source = candidate_target(None, dt(18, 30), prev)
    assert target == 78658.64
    assert source == "PREVIOUS_COMPLETE_BRTI_FINAL60"


def test_official_target_always_wins():
    prev = FinalizedBrtiWindow(
        ticker="prev",
        close_dt=dt(18, 15),
        final60_avg=78658.64,
        final60_count=60,
        final60_complete=True,
    )
    target, source = candidate_target(78660.00, dt(18, 30), prev)
    assert target == 78660.00
    assert source == "KALSHI_OFFICIAL"


def test_incomplete_previous_window_is_rejected():
    prev = FinalizedBrtiWindow(
        ticker="prev",
        close_dt=dt(18, 15),
        final60_avg=78658.64,
        final60_count=59,
        final60_complete=False,
    )
    target, source = candidate_target(None, dt(18, 30), prev)
    assert target is None
    assert source == "PREVIOUS_FINAL60_INCOMPLETE"


def test_noncontiguous_contract_is_rejected():
    prev = FinalizedBrtiWindow(
        ticker="prev",
        close_dt=dt(18, 15),
        final60_avg=78658.64,
        final60_count=60,
        final60_complete=True,
    )
    target, source = candidate_target(None, dt(18, 45), prev)
    assert target is None
    assert source == "CONTRACT_NOT_CONTIGUOUS"


def test_reconcile_exact_and_mismatch():
    ok, delta = reconcile_with_official(78658.64, 78658.64)
    assert ok and delta == 0.0
    ok, delta = reconcile_with_official(78658.64, 78661.00)
    assert not ok and round(delta, 2) == 2.36


def test_real_rollover_evidence_matches_to_cent():
    # Captured from Railway runtime on 2026-09-08.
    # inferred target = direct BRTI - reported BRTI gap.
    cases = [
        (78643.16, 78611.68, -31.48),
        (78719.91, 78725.63, +5.72),
        (78658.64, 78708.18, +49.54),
    ]
    for prior_final60, direct_brti, reported_gap in cases:
        inferred_target = round(direct_brti - reported_gap, 2)
        assert inferred_target == prior_final60
