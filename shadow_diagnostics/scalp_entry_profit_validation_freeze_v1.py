#!/usr/bin/env python3
"""Validation-only role freeze for BTC15 entry + profit ladder V1.

RESEARCH ONLY | HOLDOUT MUST NOT SELECT | NO ORDERS

The role definitions below are frozen before any V1 holdout metrics are exposed.
They operate only on each policy row's VALIDATION summary.
"""
from __future__ import annotations

from typing import Any, Mapping

import scalp_entry_profit_ladder_v1 as ladder

VERSION = "BTC15_SCALP_ENTRY_PROFIT_VALIDATION_FREEZE_V1"
MIN_SIGNALS = 30
FULL_RETENTION = 0.999
AFFORDABLE_RETENTION_FLOOR = 0.90


def n(v: Any, fallback: float = -1.0) -> float:
    try:
        return float(v) if v is not None else fallback
    except Exception:
        return fallback


def wait_seconds(entry_policy: str) -> float:
    p = ladder.ENTRY_POLICIES.get(entry_policy) or {}
    if p.get("mode") == "immediate":
        return 0.0
    try:
        return float(p.get("wait_sec") or 0.0)
    except Exception:
        return 999.0


def validation(row: Mapping[str, Any]) -> Mapping[str, Any]:
    return row.get("validation") or {}


def eligible_rows(policy_grid: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [r for r in policy_grid if int(validation(r).get("signals") or 0) >= MIN_SIGNALS]


def select_roles(policy_grid: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    rows = eligible_rows(policy_grid)
    roles: dict[str, dict[str, Any]] = {}

    full = [r for r in rows if n(validation(r).get("true_contract_coverage"), 0.0) >= FULL_RETENTION]
    if full:
        # Preserve every baseline signal contract, then maximize +10 reach. Exit
        # capture and affordable-entry share are tie-breakers only.
        r = max(full, key=lambda x: (
            n(validation(x).get("plus10_rate")),
            n(validation(x).get("avg_executable_exit_gain_c")),
            n(validation(x).get("entry_le50_rate")),
            -wait_seconds(str(x.get("entry_policy") or "")),
        ))
        roles["FULL_RETENTION_QUALITY"] = freeze_row(r)

    affordable = [
        r for r in rows
        if n(validation(r).get("true_contract_coverage"), 0.0) >= AFFORDABLE_RETENTION_FLOOR
        and n(validation(r).get("entry_le50_rate"), 0.0) >= 0.999
    ]
    if affordable:
        # Every selected entry <=50c and retain >=90% of baseline signal
        # contracts. Maximize +10, then exit capture; shortest wait wins ties.
        r = max(affordable, key=lambda x: (
            n(validation(x).get("plus10_rate")),
            n(validation(x).get("avg_executable_exit_gain_c")),
            n(validation(x).get("true_contract_coverage")),
            -wait_seconds(str(x.get("entry_policy") or "")),
        ))
        roles["AFFORDABLE_COVERAGE"] = freeze_row(r)

    serial = [r for r in rows if n(validation(r).get("true_contract_coverage"), 0.0) >= FULL_RETENTION]
    if serial:
        # Preserve every baseline signal contract while maximizing the number of
        # observed serial opportunities unlocked by real protection exits.
        r = max(serial, key=lambda x: (
            n(validation(x).get("avg_opportunities_per_covered_contract")),
            n(validation(x).get("positive_exit_rate")),
            n(validation(x).get("plus10_rate")),
            n(validation(x).get("avg_executable_exit_gain_c")),
        ))
        roles["SERIAL_PROTECTION"] = freeze_row(r)

    return roles


def freeze_row(row: Mapping[str, Any]) -> dict[str, Any]:
    v = dict(validation(row))
    return {
        "entry_policy": row.get("entry_policy"),
        "exit_policy": row.get("exit_policy"),
        "validation": v,
        "baseline_contract_retention": v.get("true_contract_coverage"),
        "coverage_scope": "BASELINE_QUALIFIED_SIGNAL_CONTRACTS",
        "selection_source": "VALIDATION_ONLY",
    }


def audit(policy_grid: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "roles": select_roles(policy_grid),
        "min_signals": MIN_SIGNALS,
        "affordable_retention_floor": AFFORDABLE_RETENTION_FLOOR,
        "coverage_scope": "BASELINE_QUALIFIED_SIGNAL_CONTRACTS",
        "holdout_used_for_selection": False,
        "retuning_after_holdout_prohibited": True,
        "automatic_promotion": False,
        "orders": False,
    }
