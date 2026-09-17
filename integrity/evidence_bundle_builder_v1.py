#!/usr/bin/env python3
"""BTC15 Evidence Bundle Builder V1.

Offline, read-only glue for the evidence-integrity pipeline.

Inputs are preserved exports/captures.  This program never contacts Railway,
Kalshi, Coinbase, or production services.  It parses captured Railway logs,
assembles contract windows, normalizes evidence, aggregates contract records,
and applies the dual-gate reconciler.

Pipeline:
captured logs -> parsed evidence -> contract observations ->
contract aggregate -> Operational Health + Evidence Integrity -> classification

Nothing in this program can promote strategy logic or place orders.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

from integrity.evidence_integrity_adapter_v1 import aggregate_all
from integrity.evidence_integrity_reconciler_v1 import (
    ReconcilerPolicy,
    reconcile_many,
    summary,
)
from integrity.railway_evidence_log_adapter_v1 import (
    ParsedEvent,
    build_contract_windows,
    parse_many,
    to_integrity_observations,
)


VERSION = "BTC15_EVIDENCE_BUNDLE_BUILDER_V1"
OPERATIONAL_FIELDS = (
    "service_deployment_ok",
    "process_alive",
    "storage_ok",
    "collector_advancing",
    "scorer_advancing",
    "runtime_config_match",
    "cutoff_valid",
)


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line_no, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        text = line.strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"{path}:{line_no}: expected object")
        rows.append(obj)
    return rows


def _write_json(path: str | Path, obj: Any) -> None:
    Path(path).write_text(
        json.dumps(obj, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = [dict(r) for r in rows]
    text = "\n".join(json.dumps(r, sort_keys=True) for r in materialized)
    Path(path).write_text(text + ("\n" if text else ""), encoding="utf-8")


def parse_log_arg(value: str) -> Tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--log must be SOURCE=PATH")
    source, path = value.split("=", 1)
    source = source.strip()
    path = path.strip()
    if not source or not path:
        raise argparse.ArgumentTypeError("--log must be SOURCE=PATH")
    return source, path


def load_captured_logs(specs: Iterable[Tuple[str, str]]) -> List[ParsedEvent]:
    events: List[ParsedEvent] = []
    for source, path in specs:
        rows = _read_jsonl(path)
        events.extend(parse_many(rows, source=source))
    events.sort(key=lambda e: e.observed_at_utc)
    return events


def _manifest_values(manifest: Mapping[str, Any], contract_id: str) -> Dict[str, Any]:
    """Return explicitly supplied interval facts; never default unknown to True."""
    out: Dict[str, Any] = {}
    global_values = manifest.get("global")
    if isinstance(global_values, Mapping):
        for key in OPERATIONAL_FIELDS:
            value = global_values.get(key)
            if isinstance(value, bool):
                out[key] = value

    per_contract = manifest.get("contracts")
    if isinstance(per_contract, Mapping):
        values = per_contract.get(contract_id)
        if isinstance(values, Mapping):
            for key in OPERATIONAL_FIELDS:
                value = values.get(key)
                if isinstance(value, bool):
                    out[key] = value
    return out


def apply_operational_manifest(
    contract_records: Iterable[Mapping[str, Any]],
    manifest: Mapping[str, Any] | None,
) -> List[Dict[str, Any]]:
    """Overlay only explicitly attested operational facts.

    This happens after evidence aggregation so the manifest cannot manufacture
    path samples, freshness, parity, or continuity.
    """
    out: List[Dict[str, Any]] = []
    manifest = manifest or {}
    for item in contract_records:
        row = dict(item)
        contract_id = str(row.get("contract_id") or "")
        for key, value in _manifest_values(manifest, contract_id).items():
            current = row.get(key)
            # Evidence-derived False always wins over a manifest True.
            if current is False:
                continue
            row[key] = value
        out.append(row)
    return out


def load_policy(path: str | None) -> ReconcilerPolicy:
    if not path:
        return ReconcilerPolicy()
    raw = _read_json(path)
    if not isinstance(raw, dict):
        raise ValueError("policy must be a JSON object")
    return ReconcilerPolicy(**raw)


def build_bundle(
    log_specs: Iterable[Tuple[str, str]],
    *,
    operational_manifest: Mapping[str, Any] | None = None,
    policy: ReconcilerPolicy | None = None,
) -> Dict[str, Any]:
    events = load_captured_logs(log_specs)
    windows = build_contract_windows(events)
    observations = to_integrity_observations(events, windows)
    contract_records = aggregate_all(observations)
    contract_records = apply_operational_manifest(
        contract_records, operational_manifest
    )
    assessments = reconcile_many(contract_records, policy or ReconcilerPolicy())
    report = summary(assessments)

    report.update(
        {
            "version": VERSION,
            "parsed_events": len(events),
            "contract_windows": len(windows),
            "integrity_observations": len(observations),
            "contract_records": len(contract_records),
            "read_only": True,
            "orders": False,
            "automatic_promotion": False,
            "missing_facts_default_to_healthy": False,
        }
    )

    return {
        "summary": report,
        "parsed_events": [e.to_dict() for e in events],
        "contract_windows": [asdict(w) for w in windows],
        "integrity_observations": observations,
        "contract_records": contract_records,
        "assessments": [a.to_dict() for a in assessments],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only BTC15 evidence-integrity bundle"
    )
    parser.add_argument(
        "--log",
        action="append",
        type=parse_log_arg,
        required=True,
        help="Captured Railway JSONL, specified as SOURCE=PATH; repeatable",
    )
    parser.add_argument(
        "--operational-manifest",
        help="Optional JSON with explicit global/per-contract operational facts",
    )
    parser.add_argument(
        "--policy",
        help="Optional reconciler policy JSON; default is conservative full-system policy",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="New or existing output directory; source evidence is never modified",
    )
    args = parser.parse_args()

    manifest: Mapping[str, Any] | None = None
    if args.operational_manifest:
        raw = _read_json(args.operational_manifest)
        if not isinstance(raw, dict):
            raise ValueError("operational manifest must be a JSON object")
        manifest = raw

    bundle = build_bundle(
        args.log,
        operational_manifest=manifest,
        policy=load_policy(args.policy),
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "summary.json", bundle["summary"])
    _write_jsonl(out_dir / "parsed_events.jsonl", bundle["parsed_events"])
    _write_json(out_dir / "contract_windows.json", bundle["contract_windows"])
    _write_jsonl(
        out_dir / "integrity_observations.jsonl",
        bundle["integrity_observations"],
    )
    _write_jsonl(out_dir / "contract_records.jsonl", bundle["contract_records"])
    _write_jsonl(out_dir / "assessments.jsonl", bundle["assessments"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
