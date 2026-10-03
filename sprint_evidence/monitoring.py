"""Consumer-only, deterministic BTC15 health classification; never strategy authority.

Inputs are receiver-admitted observations, not endpoint snapshots. This module performs
no network/disk I/O and does not poll or call a producer. It reports evidence gaps and
alerts; callers must not turn a monitoring result into an order or lifecycle event.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Mapping, Sequence

PROTOCOL_ID = "BTC15_SEVEN_DAY_COMPLETION_V1_20260929"
STATES = ("HEALTHY", "WATCH", "DRIFT", "UNAVAILABLE")
LANES = ("EARLY", "FINAL", "SCALP")
REQUIRED_CHECKS = {
    "kalshi_parity": "Contract ticker, official window and start price must match their original witnesses.",
    "alignment_rollover": "Official 15-minute alignment and staged rollover must remain intact.",
    "brti_freshness_owner": "Causal BRTI age must remain <=5 seconds with a healthy owner.",
    "quote_continuity": "Stale, missing or discontinuous quotes prevent executable-path claims.",
    "clock_certificate": "Unknown, expired, stepped or restarted clocks cannot qualify evidence.",
    "acquisition_capture": "A failed detached handoff cannot be hidden as a quiet market.",
    "evidence_completeness": "Missing evidence must remain visible in contract and origin denominators.",
    "producer_build_run": "Producer, build, run and epoch must match the approved manifest.",
    "early_final_linkage": "FINAL must reference an immutable actual or explicitly research-only EARLY origin.",
    "scalp_lifecycle": "SCALP ownership, strict ASK-to-later-BID chronology and lifecycle continuity must hold.",
    "logging_scoring": "Logging and scoring must preserve authoritative outcomes and unavailable records.",
    "publication_exposure": "Guidance exposure requires its genuine publication and current admission witnesses.",
    "signal_only": "No order path or automatic strategy mutation is permitted.",
    "native_cadence": "Passive capture must preserve native scheduling and evaluation semantics.",
}
NEXT_CHECK = {
    "clock_certificate": "Inspect the original certificate, epoch, reference and revocation; keep guidance unavailable until requalified.",
    "signal_only": "Review the exact changed build and its no-order controls before any further controlled deployment.",
    "producer_build_run": "Compare the detached run manifest and exact build hashes with the approved review package.",
    "early_final_linkage": "Inspect the immutable origin and explicit FINAL linkage; do not reconstruct a BUY from later state.",
    "scalp_lifecycle": "Inspect original publication, first post-publication ASK, later BID and ownership events in order.",
}
METRIC_NAMES = {
    "EARLY": {"correct", "ask_cents", "seconds_remaining", "failure_cluster", "calibration_probability"},
    "FINAL": {"confirmation_count", "weakening_count", "opposing_ready_false_count", "opposing_ready_true_count", "hold_count", "protect_count", "recovery_count", "warning_lead_seconds", "linkage_complete", "failure_cluster"},
    "SCALP": {"entry_available", "ask_cents", "published_entry_cents", "first_post_publication_ask_cents", "ask_later_bid_valid", "target_first_count", "stop_first_count", "neither_count", "ordering_unavailable_count", "mfe_cents", "mae_cents", "protection_giveback_cents", "serial_count", "reversal_count", "v81_lifecycle_complete", "failure_cluster"},
}


def utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Alert:
    alert_id: str
    state: str
    what_changed: str
    why_it_matters: str
    affected: str
    evidence: tuple[str, ...]
    safest_next_check: str
    action: str = "ALERT_AND_PRESERVE_EVIDENCE_ONLY"


def alert(state: str, what: str, why: str, affected: str, evidence: Sequence[str], next_check: str) -> Alert:
    payload = dict(state=state, what_changed=what, why_it_matters=why,
                   affected=affected, evidence=tuple(evidence), safest_next_check=next_check)
    return Alert(alert_id=digest(payload), **payload)


def check_system(observation: Mapping, *, now_utc: str, expected_build: str, expected_run: str,
                 max_heartbeat_age_seconds: float = 10.0) -> dict:
    """Classify an authenticated receiver result; never certify a raw clock here.

    Each required check: {status: PASS|WATCH|FAIL|UNKNOWN|CHANGED,
    evidence_ids: [...], detail: ...}. A PASS without original evidence is UNKNOWN.
    A trusted upstream interval guard must have supplied admission=QUALIFIED.
    """
    alerts = []
    if not isinstance(observation, Mapping):
        observation = {}
    try:
        now = utc(now_utc)
        observed = utc(observation["observed_at_utc"])
        expiry = utc(observation["admitted_until_utc"])
        age = (now-observed).total_seconds()
        if not 0 <= age <= max_heartbeat_age_seconds:
            raise ValueError("HEARTBEAT_STALE_OR_FUTURE")
        if now > expiry or observed > expiry:
            raise ValueError("ADMISSION_EXPIRED")
        if observation.get("admission") != "QUALIFIED":
            raise ValueError("RECEIVER_ADMISSION_UNAVAILABLE")
        if not observation.get("evidence_id"):
            raise ValueError("MISSING_HEALTH_EVIDENCE_ID")
        if observation.get("build_sha") != expected_build or observation.get("run_id") != expected_run:
            raise ValueError("BUILD_RUN_IDENTITY_MISMATCH")
        if not observation.get("producer_id") or not observation.get("clock_epoch"):
            raise ValueError("PRODUCER_OR_CLOCK_IDENTITY_MISSING")
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        alerts.append(alert("UNAVAILABLE", str(exc), "Current system health cannot be admitted from this evidence.",
                            "SYSTEM", [str(observation.get("evidence_id", "missing"))],
                            "Inspect the last admitted detached record and original clock/run evidence; preserve the gap."))
        return {"state": "UNAVAILABLE", "alerts": [asdict(a) for a in alerts], "checks": {}}
    states = {}
    checks = observation.get("checks", {})
    if not isinstance(checks, Mapping):
        checks = {}
    for name, why in REQUIRED_CHECKS.items():
        item = checks.get(name, {})
        if not isinstance(item, Mapping):
            item = {}
        evidence = item.get("evidence_ids", [])
        if not isinstance(evidence, (list, tuple)) or not evidence or not all(isinstance(x, str) and x for x in evidence):
            evidence = [observation["evidence_id"]]
            status = "UNKNOWN"
        else:
            status = item.get("status", "UNKNOWN")
        state = {"PASS": "HEALTHY", "WATCH": "WATCH", "CHANGED": "DRIFT",
                 "FAIL": "UNAVAILABLE", "UNKNOWN": "UNAVAILABLE"}.get(status, "UNAVAILABLE")
        states[name] = state
        if state != "HEALTHY":
            alerts.append(alert(state, f"{name}: {status}: {item.get('detail', 'missing check')}", why,
                                "SYSTEM" if name not in {"early_final_linkage", "scalp_lifecycle"} else
                                ("EARLY/FINAL" if name == "early_final_linkage" else "SCALP"), evidence,
                                NEXT_CHECK.get(name, "Inspect the original affected records and last known-good manifest; preserve evidence before review.")))
    state = max(states.values(), key=STATES.index)
    return {"state": state, "alerts": [asdict(a) for a in alerts], "checks": states}


def wilson(correct: int, count: int, z: float = 1.959963984540054) -> list[float] | None:
    if count == 0:
        return None
    p = correct/count
    denominator = 1+z*z/count
    center = (p+z*z/(2*count))/denominator
    radius = z*math.sqrt(p*(1-p)/count+z*z/(4*count*count))/denominator
    return [max(0.0, center-radius), min(1.0, center+radius)]


@dataclass(frozen=True)
class PerformanceRule:
    """Preregister before inspecting outcomes. Null rules mean no performance alarm.

    Only EARLY correctness currently has a defensible desired floor. FINAL/SCALP
    require separately reviewed binary estimands with exact causal extraction.
    """
    rule_id: str
    lane: str
    metric: str
    desired_floor: float
    minimum_contracts: int = 100
    minimum_distinct_days: int = 7


EARLY_RULE = PerformanceRule("EARLY_CONTRACT_CORRECT_085_V1", "EARLY", "correct", .85)


def _valid_metric(name: str, value: object) -> bool:
    if value is None:
        return True
    if name == "failure_cluster":
        return isinstance(value, str)
    if name in {"correct", "entry_available", "ask_later_bid_valid", "v81_lifecycle_complete", "linkage_complete"}:
        return isinstance(value, bool)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return False
    if name.endswith("_count"):
        return isinstance(value, int) and value >= 0
    if name.endswith("ask_cents") or name in {"ask_cents", "published_entry_cents"}:
        return 0 <= value <= 100
    if name == "seconds_remaining":
        return 0 <= value <= 900
    if name == "calibration_probability":
        return 0 <= value <= 1
    return True


def summarize_lane(lane: str, rows: Sequence[Mapping], *, eligible_contracts: Sequence[str],
                   now_utc: str, policy_hash: str, partition_id: str) -> dict:
    """Rolling descriptive metrics over one policy/partition, one summary per contract.

    Official eligible_contracts is externally witnessed; its identity must be archived
    by the caller. Missing rows remain unavailable, never PASS. Row metrics are
    previously scored causal observations, not instructions for reconstructing fills.
    Any conflicting duplicate or foreign lineage is rejected rather than pooled.
    """
    if lane not in LANES:
        raise ValueError("unknown lane")
    now = utc(now_utc)
    universe = set(eligible_contracts)
    failures = []
    by_contract = {}
    for row in rows:
        if not isinstance(row, Mapping):
            failures.append({"record_id": "missing", "reason": "MALFORMED_NONMAPPING_RECORD"})
            continue
        try:
            contract = row["contract_id"]
            if contract not in universe or row.get("lane") != lane:
                raise ValueError("FOREIGN_CONTRACT_OR_LANE")
            if row.get("policy_hash") != policy_hash or row.get("partition_id") != partition_id:
                raise ValueError("MIXED_POLICY_OR_PARTITION")
            if row.get("evidence_role") != "PROSPECTIVE":
                raise ValueError("HISTORICAL_OR_SHADOW_NOT_PROSPECTIVE")
            if not row.get("evidence_ids") or not row.get("record_id"):
                raise ValueError("MISSING_ORIGINAL_EVIDENCE")
            if utc(row["assessed_at_utc"]) > now or utc(row["official_close_utc"]) > now:
                raise ValueError("FUTURE_OR_UNSETTLED_RECORD")
            if row.get("status") not in {"SIGNAL", "PASS", "UNAVAILABLE"}:
                raise ValueError("BAD_LANE_STATUS")
            if row.get("status") != "UNAVAILABLE" and row.get("complete") is not True:
                raise ValueError("INCOMPLETE_RECORD")
            metrics = row.get("metrics", {})
            if not isinstance(metrics, Mapping) or any(k not in METRIC_NAMES[lane] or not _valid_metric(k, v) for k,v in metrics.items()):
                raise ValueError("INVALID_METRIC")
            if lane == "EARLY" and row.get("status") == "SIGNAL":
                if not isinstance(metrics.get("correct"), bool) or not row.get("authoritative_settlement_id"):
                    raise ValueError("MISSING_AUTHORITATIVE_OUTCOME")
            if lane == "FINAL" and row.get("status") == "SIGNAL" and metrics.get("linkage_complete") is not True:
                raise ValueError("FINAL_LINKAGE_UNAVAILABLE")
            if lane == "SCALP" and row.get("status") == "SIGNAL":
                if metrics.get("ask_later_bid_valid") is not True or metrics.get("v81_lifecycle_complete") is not True:
                    raise ValueError("SCALP_CHRONOLOGY_OR_LIFECYCLE_UNAVAILABLE")
            if contract in by_contract and digest(by_contract[contract]) != digest(row):
                raise ValueError("CONFLICTING_CONTRACT_DUPLICATE")
            by_contract[contract] = row
        except (KeyError, ValueError, TypeError, OverflowError) as exc:
            failures.append({"record_id": str(row.get("record_id", "missing")), "reason": str(exc)})
    observed = list(by_contract.values())
    signals = [r for r in observed if r["status"] == "SIGNAL"]
    missing = sorted(universe-set(by_contract))
    unavailable = len(missing)+sum(r["status"] == "UNAVAILABLE" for r in observed)
    stats = {}
    for name in sorted(METRIC_NAMES[lane]):
        vals = [r.get("metrics", {}).get(name) for r in signals]
        vals = [v for v in vals if v is not None]
        if not vals:
            stats[name] = {"count": 0, "unavailable": len(signals)}
        elif name == "failure_cluster":
            stats[name] = {"counts": {x: vals.count(x) for x in sorted(set(vals))}, "unavailable": len(signals)-len(vals)}
        elif all(isinstance(v, bool) for v in vals):
            stats[name] = {"true": sum(vals), "count": len(vals), "fraction": sum(vals)/len(vals), "wilson95": wilson(sum(vals), len(vals)), "unavailable": len(signals)-len(vals)}
        else:
            stats[name] = {"count": len(vals), "mean": sum(vals)/len(vals), "min": min(vals), "max": max(vals), "unavailable": len(signals)-len(vals)}
            if name.endswith("_count"):
                stats[name]["sum"] = sum(vals)
    asks = [r.get("metrics", {}).get("ask_cents") for r in signals if r.get("metrics", {}).get("ask_cents") is not None]
    economics = {"observed": len(asks), "at_most_50c": sum(v <= 50 for v in asks), "ideal_25_35c": sum(25 <= v <= 35 for v in asks)}
    state = "UNAVAILABLE" if failures or not universe or unavailable else "WATCH"
    return {"lane": lane, "state": state, "policy_hash": policy_hash, "partition_id": partition_id,
            "eligible_contracts": len(universe), "signal_contracts": len(signals),
            "pass_contracts": sum(r["status"] == "PASS" for r in observed),
            "unavailable_contracts": unavailable, "missing_contracts": missing,
            "coverage": len(signals)/len(universe) if universe else None,
            "evidence_complete_fraction": (len(universe)-unavailable)/len(universe) if universe else None,
            "metrics": stats, "economics": economics, "failures": failures,
            "note": "Descriptive contract summaries; WATCH until a preregistered performance checkpoint is assessable. Quote touches are not fills."}


def performance_checkpoint(rule: PerformanceRule | None, rows: Sequence[Mapping], *,
                           checkpoint_index: int, block_start_utc: str, block_end_utc: str,
                           now_utc: str, evidence_ids: Sequence[str], anchor_utc: str) -> dict:
    """One completed, fixed non-overlapping 7-day monitoring block; no rolling p-hunt.

    Alpha spending across checkpoints and three lanes is 0.05/[3*k*(k+1)].
    One-sided Hoeffding bound assumes a valid contract-level binary estimand and
    independent or conditionally bounded observations. These assumptions are NOT
    established by market records; use as a conditional heuristic alert screen. It is a conservative alert
    screen, never proof of a permanent population rate. Not a sprint completion gate.
    """
    if rule is None:
        return {"state": "WATCH", "reason": "NO_REVIEWED_PERFORMANCE_BASELINE", "alerts": []}
    if (checkpoint_index < 1 or rule.lane not in LANES or not 0 < rule.desired_floor < 1
            or rule.minimum_contracts < 100 or rule.minimum_distinct_days < 7):
        raise ValueError("invalid preregistered rule/checkpoint")
    start, end, now = map(utc, (block_start_utc, block_end_utc, now_utc))
    if ((end-start).total_seconds() != 7*86400 or now < end
            or (start-utc(anchor_utc)).total_seconds() != (checkpoint_index-1)*7*86400):
        return {"state": "WATCH", "reason": "FIXED_WEEK_BLOCK_NOT_COMPLETE", "alerts": []}
    if not evidence_ids:
        return {"state": "UNAVAILABLE", "reason": "CHECKPOINT_EVIDENCE_MISSING", "alerts": []}
    selected = {}
    dates = set()
    identities = set()
    daily = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return {"state": "UNAVAILABLE", "reason": "MALFORMED_NONMAPPING_RECORD", "alerts": []}
        try:
            when = utc(row["official_close_utc"])
            if not start <= when < end:
                continue
            if row.get("lane") != rule.lane or row.get("complete") is not True or row.get("evidence_role") != "PROSPECTIVE":
                raise ValueError("PERFORMANCE_PROVENANCE_UNAVAILABLE")
            if row.get("status") != "SIGNAL":
                continue
            if rule.lane == "EARLY" and not row.get("authoritative_settlement_id"):
                raise ValueError("AUTHORITATIVE_SETTLEMENT_MISSING")
            identity = (row.get("policy_hash"), row.get("partition_id"))
            if not all(identity) or not row.get("evidence_ids") or not row.get("record_id"):
                raise ValueError("PERFORMANCE_IDENTITY_MISSING")
            identities.add(identity)
            if len(identities) != 1:
                raise ValueError("MIXED_POLICY_OR_PARTITION")
            metrics = row.get("metrics", {})
            if not isinstance(metrics, Mapping):
                raise ValueError("BINARY_ESTIMAND_UNAVAILABLE")
            value = metrics.get(rule.metric)
            if not isinstance(value, bool):
                raise ValueError("BINARY_ESTIMAND_UNAVAILABLE")
            key = row["contract_id"]
            if key in selected:
                raise ValueError("DUPLICATE_CONTRACT_INFERENCE")
            selected[key] = value
            dates.add(when.date())
            day = when.date().isoformat()
            daily.setdefault(day, []).append(value)
        except (KeyError, ValueError, TypeError) as exc:
            return {"state": "UNAVAILABLE", "reason": str(exc), "alerts": []}
    n, k = len(selected), sum(selected.values())
    if n < rule.minimum_contracts or len(dates) < rule.minimum_distinct_days:
        return {"state": "WATCH", "reason": "LIMITED_SAMPLE_NOT_DRIFT", "n": n, "correct": k, "distinct_days": len(dates), "alerts": []}
    alpha = .05/(3*checkpoint_index*(checkpoint_index+1))
    upper = min(1., k/n+math.sqrt(math.log(1/alpha)/(2*n)))
    state = "DRIFT" if upper < rule.desired_floor else "HEALTHY"
    alerts = []
    if state == "DRIFT":
        alerts.append(asdict(alert(state, f"{rule.rule_id}: contract result {k}/{n} below the preregistered floor screen",
                                  "Sufficient completed evidence indicates potential material degradation; review, do not retune automatically.",
                                  rule.lane, evidence_ids,
                                  "Inspect complete contract failures, missingness, market regimes and the frozen scorer before proposing any change.")))
    return {"state": state, "n": n, "correct": k, "distinct_days": len(dates), "alpha": alpha,
            "one_sided_upper": upper, "desired_floor": rule.desired_floor, "alerts": alerts,
            "day_counts": {d: {"n": len(v), "correct": sum(v)} for d,v in sorted(daily.items())},
            "leave_one_day_out_rates": {d: (k-sum(v))/(n-len(v)) for d,v in sorted(daily.items()) if n > len(v)},
            "inference_limit": "Conditional heuristic alert screen; dependence assumptions unverified. HEALTHY is no detected alarm, not qualified accuracy or permanent 90-95% population proof."}


class AlertLatch:
    """Bounded latest-state deduplication, checkpointable by a detached consumer.

    Keyed by affected/check name, not ever-growing evidence IDs. A state change or
    changed diagnosis emits; a fresh certificate alone does not spam the user.
    """
    def __init__(self, saved: Mapping[str, str] | None = None, maximum_keys: int = 128):
        self.maximum_keys = maximum_keys
        self._last = dict(saved or {})
        if len(self._last) > maximum_keys:
            raise ValueError("alert checkpoint oversized")

    def emit(self, key: str, current: Mapping) -> dict | None:
        fingerprint = digest({k: current.get(k) for k in ("state", "what_changed", "why_it_matters", "affected")})
        if key not in self._last and len(self._last) >= self.maximum_keys:
            return asdict(alert("UNAVAILABLE", "ALERT_LATCH_CAPACITY", "Alert deduplication state is bounded; overflow must remain visible.", "MONITORING", [current.get("alert_id", "missing")], "Inspect checkpoint key cardinality; preserve unsent evidence in the detached archive."))
        if self._last.get(key) == fingerprint:
            return None
        self._last[key] = fingerprint
        return dict(current)

    def checkpoint(self) -> dict:
        return dict(self._last)


class AlertStore:
    """Durable bounded SQLite outbox; isolated consumer work, no external send.

    Initialize explicitly. A deleted database is a gap, never auto-recreated.
    Each alert and latest deduplication key commit together or neither does.
    User notifications require an independently reviewed delivery connector.
    """
    def __init__(self, path: str, *, initialize: bool = False, max_alerts: int = 10000):
        self.path = Path(path)
        self.max_alerts = max_alerts
        if initialize:
            if self.path.exists():
                raise ValueError("OUTBOX_ALREADY_EXISTS")
            # Exclusive creation prevents replacement of an existing evidence store.
            with self.path.open("xb"):
                pass
            conn = sqlite3.connect(self.path, timeout=0)
            try:
                conn.executescript("CREATE TABLE alerts (id TEXT PRIMARY KEY, payload TEXT NOT NULL); "
                                   "CREATE TABLE states (key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);")
                conn.commit()
            finally:
                conn.close()
        if not self.path.is_file():
            raise ValueError("OUTBOX_MISSING")

    def record(self, key: str, value: Mapping) -> dict:
        payload = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(payload.encode()) > 32768:
            return {"state": "UNAVAILABLE", "reason": "ALERT_OVERSIZED"}
        fingerprint = digest({k: value.get(k) for k in ("state", "what_changed", "why_it_matters", "affected")})
        try:
            conn = sqlite3.connect(f"file:{self.path}?mode=rw", uri=True, timeout=0)
            conn.execute("PRAGMA synchronous=FULL")
            try:
                conn.execute("BEGIN IMMEDIATE")
                old = conn.execute("SELECT fingerprint FROM states WHERE key=?", (key,)).fetchone()
                if old and old[0] == fingerprint:
                    conn.rollback()
                    return {"state": "RECORDED", "duplicate": True}
                if conn.execute("SELECT count(*) FROM alerts").fetchone()[0] >= self.max_alerts:
                    conn.rollback()
                    return {"state": "UNAVAILABLE", "reason": "ALERT_OUTBOX_FULL"}
                # Distinct later repeats may share an alert hash, but state remains exact.
                conn.execute("INSERT OR IGNORE INTO alerts VALUES (?,?)", (value["alert_id"], payload))
                conn.execute("INSERT OR REPLACE INTO states VALUES (?,?)", (key, fingerprint))
                conn.commit()
                return {"state": "RECORDED", "duplicate": False, "alert_id": value["alert_id"]}
            finally:
                conn.close()
        except (sqlite3.Error, OSError, KeyError) as exc:
            return {"state": "UNAVAILABLE", "reason": "ALERT_OUTBOX_FAILURE", "detail": str(exc)}


def main(argv: Sequence[str] | None = None) -> int:
    """Consume an immutable receiver-generated health JSON and spool alerts locally."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="Detached admitted health JSON; never a producer path")
    source.add_argument("--receiver-db", help="Read-only detached receiver SQLite; never a native producer path")
    parser.add_argument("--outbox", required=True)
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--now", required=True, help="Original monitoring check UTC; not a source witness")
    parser.add_argument("--expected-build", required=True)
    parser.add_argument("--expected-run", required=True)
    args = parser.parse_args(argv)
    try:
        if args.receiver_db:
            result = inspect_receiver_database(args.receiver_db, now_utc=args.now, expected_build=args.expected_build, expected_run=args.expected_run)
        else:
            path = Path(args.input)
            if path.stat().st_size > 1048576:
                raise ValueError("HEALTH_INPUT_OVERSIZED")
            envelope = json.loads(path.read_text())
            result = check_system(envelope, now_utc=args.now, expected_build=args.expected_build, expected_run=args.expected_run)
        store = AlertStore(args.outbox, initialize=args.initialize)
        receipts = []
        for item in result["alerts"]:
            key = item["affected"]+":"+item["what_changed"].split(":", 1)[0]
            receipts.append(store.record(key, item))
        result["outbox_receipts"] = receipts
        result["notification_delivery"] = "NOT_CONFIGURED_LOCAL_OUTBOX_ONLY"
        if any(r["state"] == "UNAVAILABLE" for r in receipts):
            result["state"] = "UNAVAILABLE"
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 2 if result["state"] == "UNAVAILABLE" else 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"state": "UNAVAILABLE", "reason": "MONITOR_INPUT_OR_OUTBOX_FAILURE", "detail": str(exc)}))
        return 2


def inspect_receiver_database(path: str, *, now_utc: str, expected_build: str, expected_run: str) -> dict:
    """Read only detached immutable events; real missing detectors remain unavailable.

    This integration supplies observed archive/sequence/build/no-order facts, never
    substitutes hook wall time for clock admission or asserts unobserved market parity.
    """
    utc(now_utc)
    found = []
    alerts = []
    try:
        conn = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True, timeout=0)
        try:
            rows = conn.execute("SELECT producer,run,seq,digest,raw,status,reason FROM producer_events ORDER BY rowid DESC LIMIT 256").fetchall()
        finally:
            conn.close()
        if not rows:
            raise ValueError("DETACHED_ARCHIVE_EMPTY")
        for producer, run, seq, hash_, raw, status, reason in rows:
            item = json.loads(raw)
            event = item.get("event", item)
            identity = event.get("identity", {})
            if not isinstance(identity, Mapping):
                raise ValueError("MALFORMED_PRODUCER_IDENTITY")
            facts = {"evidence_id": hash_, "producer": producer, "run": run, "seq": seq,
                     "receiver_status": status, "receiver_reason": reason,
                     "kind": event.get("kind"), "build_sha": identity.get("build_sha")}
            found.append(facts)
            if identity.get("build_sha") != expected_build or run != expected_run:
                alerts.append(asdict(alert("UNAVAILABLE", "DETACHED_BUILD_RUN_MISMATCH", REQUIRED_CHECKS["producer_build_run"], "SYSTEM", [hash_], NEXT_CHECK["producer_build_run"])))
            if event.get("orders") is not False or event.get("signal_only") is not True:
                alerts.append(asdict(alert("UNAVAILABLE", "DETACHED_SIGNAL_ONLY_VIOLATION", REQUIRED_CHECKS["signal_only"], "SYSTEM", [hash_], NEXT_CHECK["signal_only"])))
            if event.get("prior_dropped", 0) or "GAP" in str(reason).upper():
                alerts.append(asdict(alert("UNAVAILABLE", "DETACHED_EVIDENCE_GAP", REQUIRED_CHECKS["evidence_completeness"], "SYSTEM", [hash_], "Inspect receiver sequence and producer loss evidence; retain unavailable interval.")))
        evidence = [f["evidence_id"] for f in found[:3]]
        alerts.append(asdict(alert("UNAVAILABLE", "REAL_CLOCK_AND_COMPLETE_HEALTH_DETECTORS_NOT_ADMITTED", "Detached event persistence proves acquisition facts, not clock admission, complete market/ladder health or browser exposure.", "SYSTEM", evidence, "Bind qualified real clock receipts and each missing detector before any health/activation claim.")))
        return {"state": "UNAVAILABLE", "alerts": alerts, "detached_observations": found,
                "scope": "ARCHIVE_OBSERVATION_ONLY_NOT_LIVE_QUALIFICATION", "required_checks": list(REQUIRED_CHECKS)}
    except (sqlite3.Error, OSError, ValueError, TypeError, AttributeError) as exc:
        item = alert("UNAVAILABLE", "DETACHED_MONITOR_READ_FAILURE", "The receiver's immutable archive cannot currently support health detection.", "MONITORING", [str(path)], "Inspect the detached receiver database and preserve its failure record; do not query the native exporter.")
        return {"state": "UNAVAILABLE", "alerts": [asdict(item)], "reason": str(exc)}


if __name__ == "__main__":
    raise SystemExit(main())
