#!/usr/bin/env python3
"""BTC15 Evidence Integrity Reconciler V1.

Read-only, deterministic contract-level evidence classifier.

A contract is valid for certification only when BOTH:
  1) operational health passes, and
  2) evidence integrity passes.

No trading, no orders, no mutation of source evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

if __package__:
    from .measurement_validation_v1 import ROLLOVER_FIELDS, nonnegative_finite
    from .safe_outputs_v1 import validate_output_paths, write_new_text
else:  # Preserve direct-script CLI use as well as python -m.
    from measurement_validation_v1 import ROLLOVER_FIELDS, nonnegative_finite
    from safe_outputs_v1 import validate_output_paths, write_new_text


class Classification(str, Enum):
    CLEAN = "CLEAN"
    PARTIAL = "PARTIAL"
    INVALID_FOR_CERT = "INVALID_FOR_CERT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ReconcilerPolicy:
    # Operational gate
    require_service_deployment_ok: bool = True
    require_process_alive: bool = True
    require_storage_ok: bool = True
    require_collector_advancing: bool = True
    require_scorer_advancing: bool = True
    require_runtime_config_match: bool = True

    # Evidence gate
    require_cutoff_valid: bool = True
    require_start_observation: bool = True
    require_end_observation: bool = True
    require_continuous_path: bool = True

    # Feed requirements
    require_kalshi: bool = True
    require_brti: bool = True
    require_coinbase: bool = True
    require_parity: bool = True

    # Conservative certification thresholds.
    max_kalshi_age_sec: float = 5.0
    max_brti_age_sec: float = 5.0
    max_coinbase_age_sec: float = 5.0
    max_source_gap_sec: float = 10.0
    max_rollover_lag_sec: float = 15.0

    # A 429 itself is not automatically fatal if freshness remained inside
    # threshold; stale data or missing observations are the actual hard fail.
    max_429_share: float = 0.05

    # If true, any parity fail invalidates certification for the contract.
    parity_fail_is_hard: bool = True

    def __post_init__(self):
        for name, value in asdict(self).items():
            if name.startswith("require_") or name == "parity_fail_is_hard":
                if not isinstance(value, bool):
                    raise ValueError(f"policy flag must be boolean: {name}")
            elif not isinstance(value, (int, float)) or nonnegative_finite(value) is None:
                raise ValueError(f"policy threshold must be finite and non-negative: {name}")
        if self.max_429_share > 1:
            raise ValueError("max_429_share must be at most 1")


@dataclass
class GateResult:
    passed: Optional[bool]
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ContractAssessment:
    contract_id: str
    classification: Classification
    operational_health_pass: Optional[bool]
    evidence_integrity_pass: Optional[bool]
    valid_for_certification: bool
    quarantine: bool
    reasons: List[str]
    warnings: List[str]
    preserved_input: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["classification"] = self.classification.value
        return out


def _bool_field(record: Dict[str, Any], name: str) -> Optional[bool]:
    value = record.get(name)
    if isinstance(value, bool):
        return value
    return None


def _float_field(record: Dict[str, Any], name: str) -> Optional[float]:
    value = record.get(name)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return nonnegative_finite(value)
    return None


def _required_bool(
    record: Dict[str, Any],
    field_name: str,
    label: str,
    enabled: bool,
    reasons: List[str],
) -> Optional[bool]:
    if not enabled:
        return True
    value = _bool_field(record, field_name)
    if value is None:
        reasons.append(f"UNKNOWN_{label}")
        return None
    if value is False:
        reasons.append(f"FAIL_{label}")
    return value


def evaluate_operational_health(
    record: Dict[str, Any], policy: ReconcilerPolicy
) -> GateResult:
    reasons: List[str] = []
    checks = [
        _required_bool(record, "service_deployment_ok", "SERVICE_DEPLOYMENT", policy.require_service_deployment_ok, reasons),
        _required_bool(record, "process_alive", "PROCESS_ALIVE", policy.require_process_alive, reasons),
        _required_bool(record, "storage_ok", "STORAGE", policy.require_storage_ok, reasons),
        _required_bool(record, "collector_advancing", "COLLECTOR_ADVANCING", policy.require_collector_advancing, reasons),
        _required_bool(record, "scorer_advancing", "SCORER_ADVANCING", policy.require_scorer_advancing, reasons),
        _required_bool(record, "runtime_config_match", "RUNTIME_CONFIG_MATCH", policy.require_runtime_config_match, reasons),
    ]
    if any(x is False for x in checks):
        return GateResult(False, reasons)
    if any(x is None for x in checks):
        return GateResult(None, reasons)
    return GateResult(True, reasons)


def _age_check(
    record: Dict[str, Any],
    field_name: str,
    required: bool,
    threshold: float,
    label: str,
    reasons: List[str],
) -> Optional[bool]:
    if not required:
        return True
    value = _float_field(record, field_name)
    if value is None:
        reasons.append(f"UNKNOWN_{label}_AGE")
        return None
    if value > threshold:
        reasons.append(f"FAIL_{label}_STALE:{value:.3f}>{threshold:.3f}")
        return False
    return True


def evaluate_evidence_integrity(
    record: Dict[str, Any], policy: ReconcilerPolicy
) -> GateResult:
    reasons: List[str] = []
    warnings: List[str] = []
    hard: List[Optional[bool]] = []

    if record.get("invalid_measurements"):
        reasons.append("FAIL_INVALID_MEASUREMENTS")
        hard.append(False)

    hard.extend([
        _required_bool(record, "cutoff_valid", "CUTOFF_VALID", policy.require_cutoff_valid, reasons),
        _required_bool(record, "has_start_observation", "START_OBSERVATION", policy.require_start_observation, reasons),
        _required_bool(record, "has_end_observation", "END_OBSERVATION", policy.require_end_observation, reasons),
        _required_bool(record, "continuous_path_complete", "CONTINUOUS_PATH", policy.require_continuous_path, reasons),
    ])

    hard.append(_age_check(record, "kalshi_max_age_sec", policy.require_kalshi, policy.max_kalshi_age_sec, "KALSHI", reasons))
    hard.append(_age_check(record, "brti_max_age_sec", policy.require_brti, policy.max_brti_age_sec, "BRTI", reasons))
    hard.append(_age_check(record, "coinbase_max_age_sec", policy.require_coinbase, policy.max_coinbase_age_sec, "COINBASE", reasons))

    # Coverage is required independently for every enabled feed. One feed's
    # dense path must never fill another feed's missing observations.
    for feed, required in (("kalshi", policy.require_kalshi), ("brti", policy.require_brti),
                           ("coinbase", policy.require_coinbase)):
        if not required:
            continue
        for suffix in ("coverage_complete", "has_start_observation", "has_end_observation"):
            hard.append(_required_bool(record, f"{feed}_{suffix}", f"{feed}_{suffix}".upper(), True, reasons))
        count = record.get(f"{feed}_sample_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            reasons.append(f"UNKNOWN_{feed.upper()}_SAMPLE_COUNT")
            hard.append(None)
        elif count < 2:
            reasons.append(f"FAIL_{feed.upper()}_INSUFFICIENT_SAMPLES")
            hard.append(False)
        hard.append(_age_check(record, f"{feed}_max_observation_gap_sec", True,
                               policy.max_source_gap_sec, f"{feed.upper()}_OBSERVATION_GAP", reasons))

    for key, enabled, bad_value in (("brti_feed_clean", policy.require_brti, False),
                                    ("brti_clean", policy.require_brti, False),
                                    ("direct_brti_ready", policy.require_brti, False),
                                    ("brti_counter_reset", policy.require_brti, True),
                                    ("coinbase_timeout", policy.require_coinbase, True)):
        if enabled and record.get(key) is bad_value:
            reasons.append(f"FAIL_{key.upper()}")
            hard.append(False)
    if policy.require_brti:
        for item in record.get("brti_counter_metadata", {}).values():
            if item.get("reset_detected") is True or item.get("invalid_measurement") is True:
                reasons.append("FAIL_BRTI_COUNTER_INTEGRITY")
                hard.append(False)

    gap = _float_field(record, "max_source_gap_sec")
    if gap is None:
        reasons.append("UNKNOWN_SOURCE_GAP")
        hard.append(None)
    elif gap > policy.max_source_gap_sec:
        reasons.append(f"FAIL_SOURCE_GAP:{gap:.3f}>{policy.max_source_gap_sec:.3f}")
        hard.append(False)
    else:
        hard.append(True)

    rollover_values = [_float_field(record, name) for name in ROLLOVER_FIELDS if name in record]
    rollover = (max(rollover_values) if rollover_values and all(v is not None for v in rollover_values) else None)
    if rollover is None:
        reasons.append("UNKNOWN_ROLLOVER_LAG")
        hard.append(None)
    elif rollover > policy.max_rollover_lag_sec:
        reasons.append(f"FAIL_ROLLOVER_LATE:{rollover:.3f}>{policy.max_rollover_lag_sec:.3f}")
        hard.append(False)
    else:
        hard.append(True)

    if policy.require_parity:
        parity = record.get("parity_fail_count")
        if record.get("parity_ok") is False:
            reasons.append("FAIL_PARITY_EXPLICIT")
            hard.append(False)
        if isinstance(parity, int) and not isinstance(parity, bool) and parity >= 0:
            if parity > 0:
                if policy.parity_fail_is_hard:
                    reasons.append(f"FAIL_PARITY:{parity}")
                    hard.append(False)
                else:
                    warnings.append(f"WARN_PARITY:{parity}")
        else:
            reasons.append("UNKNOWN_PARITY")
            hard.append(None)

    attempts = record.get("brti_attempts")
    rate429 = record.get("brti_429_count")
    if isinstance(attempts, int) and attempts > 0 and isinstance(rate429, int) and rate429 >= 0:
        share = rate429 / attempts
        if share > policy.max_429_share:
            warnings.append(f"WARN_BRTI_429_SHARE:{share:.6f}>{policy.max_429_share:.6f}")
    elif policy.require_brti:
        warnings.append("WARN_UNKNOWN_BRTI_429_SHARE")

    if any(x is False for x in hard):
        return GateResult(False, reasons, warnings)
    if any(x is None for x in hard):
        return GateResult(None, reasons, warnings)
    return GateResult(True, reasons, warnings)


def reconcile_contract(
    record: Dict[str, Any], policy: Optional[ReconcilerPolicy] = None
) -> ContractAssessment:
    policy = policy or ReconcilerPolicy()
    contract_id = str(record.get("contract_id") or record.get("ticker") or "UNKNOWN_CONTRACT")

    op = evaluate_operational_health(record, policy)
    ev = evaluate_evidence_integrity(record, policy)

    all_reasons = op.reasons + ev.reasons
    all_warnings = op.warnings + ev.warnings

    if op.passed is False or ev.passed is False:
        classification = Classification.INVALID_FOR_CERT
    elif op.passed is None or ev.passed is None:
        classification = Classification.UNKNOWN
    elif all_warnings:
        classification = Classification.PARTIAL
    else:
        classification = Classification.CLEAN

    valid = op.passed is True and ev.passed is True and classification == Classification.CLEAN
    quarantine = not valid

    return ContractAssessment(
        contract_id=contract_id,
        classification=classification,
        operational_health_pass=op.passed,
        evidence_integrity_pass=ev.passed,
        valid_for_certification=valid,
        quarantine=quarantine,
        reasons=all_reasons,
        warnings=all_warnings,
        preserved_input=record,
    )


def reconcile_many(
    records: Iterable[Dict[str, Any]], policy: Optional[ReconcilerPolicy] = None
) -> List[ContractAssessment]:
    return [reconcile_contract(r, policy) for r in records]


def summary(assessments: Iterable[ContractAssessment]) -> Dict[str, Any]:
    rows = list(assessments)
    counts = {c.value: 0 for c in Classification}
    for row in rows:
        counts[row.classification.value] += 1
    return {
        "contracts": len(rows),
        "classification_counts": counts,
        "certifiable_contracts": sum(1 for r in rows if r.valid_for_certification),
        "quarantined_contracts": sum(1 for r in rows if r.quarantine),
        "dual_gate_rule": "OPERATIONAL_HEALTH_PASS + EVIDENCE_INTEGRITY_PASS + CLEAN = VALID_EVIDENCE",
        "orders": False,
        "source_mutation": False,
    }


def _load_policy(path: Optional[str]) -> ReconcilerPolicy:
    if not path:
        return ReconcilerPolicy()
    data = json.loads(Path(path).read_text())
    return ReconcilerPolicy(**data)


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line_no, line in enumerate(Path(path).read_text().splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object")
        rows.append(obj)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only BTC15 contract evidence reconciler")
    parser.add_argument("--input", required=True, help="JSONL contract-audit input")
    parser.add_argument("--output", required=True, help="JSONL assessment output")
    parser.add_argument("--summary", required=True, help="JSON summary output")
    parser.add_argument("--policy", help="Optional JSON policy override")
    args = parser.parse_args()

    out_path, summary_path = validate_output_paths(
        [args.input, args.policy], [args.output, args.summary]
    )

    policy = _load_policy(args.policy)
    records = _read_jsonl(args.input)
    assessments = reconcile_many(records, policy)

    write_new_text(out_path, "\n".join(json.dumps(a.to_dict(), sort_keys=True) for a in assessments) + ("\n" if assessments else ""))
    write_new_text(summary_path, json.dumps(summary(assessments), indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
