"""Independent seven-finding reproductions using synthetic evidence only.

Run: python -m integrity.adversarial_hardening_v1
No test fixtures are imported. Actual CLI subprocesses exercise output safety.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from integrity.evidence_integrity_adapter_v1 import aggregate_contract
from integrity.evidence_integrity_reconciler_v1 import reconcile_contract
from integrity.railway_evidence_log_adapter_v1 import (
    build_contract_windows, parse_many, to_integrity_observations,
)


CID = "KXBTC15M-ADVERSARIAL"
BASE = datetime(2026, 9, 17, 3, 0, tzinfo=timezone.utc)


def full_path():
    return [{
        "contract_id": CID,
        "observed_at_utc": (BASE + timedelta(seconds=s)).isoformat(),
        "seconds_left": 900 - s,
        "service_deployment_ok": True, "process_alive": True, "storage_ok": True,
        "collector_advancing": True, "scorer_advancing": True,
        "runtime_config_match": True, "cutoff_valid": True,
        "kalshi_age_sec": 1.0, "brti_age_sec": 1.0, "coinbase_age_sec": 1.0,
        "parity_ok": True, "brti_attempts_total": 999 + s, "brti_429_total": 0,
    } for s in range(1, 842, 5)]


def assess(rows):
    record = aggregate_contract(CID, rows)
    return record, reconcile_contract(record)


def blocked(assessment):
    return not assessment.valid_for_certification and assessment.classification.value in {"UNKNOWN", "INVALID_FOR_CERT"}


def probe_outputs():
    cases = 0
    for option in ("--output", "--summary"):
        for protected in ("input", "policy"):
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                source = root / "input"
                source.write_text(json.dumps(assess(full_path())[0]) + "\n")
                policy = root / "policy"
                policy.write_text("{}\n")
                before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (source, policy)}
                args = {"--input": source, "--policy": policy, "--output": root / "out", "--summary": root / "summary"}
                args[option] = root / protected
                proc = subprocess.run([sys.executable, "-m", "integrity.evidence_integrity_reconciler_v1",
                    *[str(x) for pair in args.items() for x in pair]], capture_output=True, text=True)
                assert proc.returncode != 0, f"CLI accepted {option} overlapping {protected}"
                assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}, "source changed"
                assert len(list(root.iterdir())) == 2, "partial outputs before rejection"
                cases += 1
    for filename in ("summary.json", "parsed_events.jsonl", "contract_windows.json",
                     "integrity_observations.jsonl", "contract_records.jsonl", "assessments.jsonl"):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / filename
            source.write_text('{"timestamp":"2026-09-17T03:00:00Z","message":"synthetic"}\n')
            before = source.read_bytes()
            proc = subprocess.run([sys.executable, "-m", "integrity.evidence_bundle_builder_v1",
                "--log", f"synthetic={source}", "--out-dir", str(root)], capture_output=True, text=True)
            assert proc.returncode != 0, f"bundle accepted source named {filename}"
            assert source.read_bytes() == before, "bundle changed source"
            assert len(list(root.iterdir())) == 1, "bundle wrote before checking all targets"
            cases += 1
    return {"cases": cases, "source_bytes_unchanged": True}


def probe_numbers():
    cases = 0
    for field in ("kalshi_max_age_sec", "brti_max_age_sec", "coinbase_max_age_sec", "max_source_gap_sec", "rollover_lag_sec"):
        for value in (float("nan"), float("inf"), float("-inf"), -1.0):
            record, _ = assess(full_path())
            record[field] = value
            assert blocked(reconcile_contract(record)), f"{field}={value} certified"
            cases += 1
    for field in ("kalshi_age_sec", "brti_age_sec", "coinbase_age_sec", "max_source_gap_sec", "exact_ticker_rollover_quote_lag_sec"):
        for value in (float("nan"), float("inf"), float("-inf"), -1.0):
            rows = full_path()
            rows[80][field] = value
            _, assessment = assess(rows)
            assert blocked(assessment), f"aggregate hid {field}={value}"
            cases += 1
    return {"cases": cases, "all_invalid_values_blocked": True}


def probe_coverage():
    results = {}
    for feed in ("kalshi", "brti", "coinbase"):
        rows = full_path()
        for i, row in enumerate(rows):
            if i != 80:
                row.pop(f"{feed}_age_sec")
        record, assessment = assess(rows)
        assert len(rows) == 169
        assert blocked(assessment), f"single {feed} sample certified"
        assert record.get(f"{feed}_coverage_complete") is False
        assert record.get(f"{feed}_sample_count") == 1
        results[feed] = assessment.classification.value
    return {"path_observations": 169, "feed_samples": 1, "results": results}


def probe_parity():
    rows = full_path()
    for row in rows:
        row["parity_fail_count"] = 0
    rows[80]["parity_ok"] = False
    record, assessment = assess(rows)
    assert blocked(assessment), "zero cumulative parity count masked explicit failure"
    assert record["parity_fail_count"] >= 1
    return {"parity_fail_count": record["parity_fail_count"], "classification": assessment.classification.value}


def probe_counter_reset():
    results = {}
    for field in ("brti_attempts_total", "brti_429_total"):
        rows = full_path()
        for row in rows:
            row.pop(field)
        for i, value in ((0, 1000), (80, 1), (168, 1840)):
            rows[i][field] = value
        record, assessment = assess(list(reversed(rows)))
        assert blocked(assessment), f"{field} intermediate reset certified"
        assert record.get("brti_counter_reset") is True
        assert record["brti_counter_metadata"][field]["delta"] is None
        results[field] = assessment.classification.value
    return {"sequence": [1000, 1, 1840], "delta": None, "results": results}


def parsed_rows(messages):
    events = parse_many([{
        "timestamp": "2026-09-17T03:00:50Z",
        "message": f"ROLLOVER PROBE V3 SUMMARY | boundary=2026-09-17T03:00:00Z | target={CID} | exact_active_quoted=1.0",
    }, *messages], source="synthetic")
    return to_integrity_observations(events, build_contract_windows(events))


def probe_trouble():
    results = {}
    for field, message in (
        ("brti_feed_clean", "BRTI_SHARED HEARTBEAT | status=PRIMARY_ERROR | clean=False | age_ms=500 | seq=1 | upstream_ok=1/1300 (90%) | 429=0 | errors=0"),
        ("direct_brti_ready", "DIRECT BRTI | price | age 0.5s | ready False"),
        ("coinbase_timeout", "Coinbase ReadTimeout"),
    ):
        rows = parsed_rows([{"timestamp": "2026-09-17T03:05:01Z", "message": message}])
        record, assessment = assess(full_path() + rows)
        assert blocked(assessment), f"explicit {field} trouble lost"
        assert f"FAIL_{field.upper()}" in assessment.reasons
        results[field] = assessment.classification.value
    return results


def probe_rollover():
    results = {}
    for field, message in (
        ("exact_ticker", f"ROLLOVER PROBE V3 SUMMARY | boundary=2026-09-17T03:00:00Z | target={CID} | exact_active_quoted=35.7"),
        ("combined", f"COMBINED V2 LATE START | {CID} | first_seen_lag=35.7s | EXCLUDED FROM GATE"),
    ):
        rows = parsed_rows([{"timestamp": "2026-09-17T03:00:55Z", "message": message}])
        record, assessment = assess(full_path() + rows)
        assert blocked(assessment), "recorded 35.7s lag certified"
        assert record["rollover_lag_sec"] == 35.7, "recorded lag reduced"
        results[field] = {"lag_sec": record["rollover_lag_sec"], "classification": assessment.classification.value}
    return {"inferred_lag_sec": 1.0, "results": results}


def main():
    # Positive control prevents an always-fail classifier from passing probes.
    _, control = assess(full_path())
    assert control.valid_for_certification, "clean positive control failed"
    results = []
    probes = (probe_outputs, probe_numbers, probe_coverage, probe_parity,
              probe_counter_reset, probe_trouble, probe_rollover)
    for number, probe in enumerate(probes, 1):
        try:
            details = probe()
            results.append({"finding": number, "result": "PASS", "details": details})
        except Exception as exc:
            results.append({"finding": number, "result": "FAIL", "error": str(exc)})
    passed = sum(r["result"] == "PASS" for r in results)
    print(json.dumps({"positive_control": "CLEAN", "passed": passed, "total": 7, "findings": results}, indent=2))
    return 0 if passed == 7 else 1


if __name__ == "__main__":
    raise SystemExit(main())
