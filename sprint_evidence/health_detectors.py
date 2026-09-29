"""Read-only corruption diagnostics over already detached immutable BTC15 events.

Recorded contradictions can be detected without claiming qualified clocks or live
health. All outputs remain UNAVAILABLE for guidance. No source clock, fill, origin,
strategy decision or future observation is manufactured. Only producer-emitted
field paths are used. This is an additive diagnostic layer, not an authority gate.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from sprint_evidence.monitoring import alert
from sprint_evidence.passive_capture import digest, pack, strict

MAX_RECORDS = 512
# Exact existing structural tolerance, not a new clock-admission bound.
FROZEN_RECORDED_ALIGNMENT_TOLERANCE_SECONDS = 2.0
SOURCE_LABELS = {"early": "FROZEN_TIER1", "final": "FROZEN_V4_6_FINAL", "scalp": "FROZEN_STRONG_SCALP"}


def mapping(value):
    return value if isinstance(value, Mapping) else {}


def numeric(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (ValueError, InvalidOperation):
        return None


def timestamp(value):
    # This is parsing an original label, never clock certification.
    if isinstance(value, Mapping) and value.get("representation") == "datetime.isoformat":
        value = value.get("observed_value")
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, OverflowError):
        return None


def explicit_false(value):
    # Existing parity exporter stores CSV booleans as strings.
    return value is False or (isinstance(value, str) and value.strip().lower() == "false")


def inspect_events(envelopes: Sequence, *, expected_build: str | None = None,
                   expected_run: str | None = None) -> dict:
    """Inspect one bounded archive slice. Not observing corruption is not HEALTHY.

    Input order must be immutable receiver order, not wall-clock sorting. Generation
    linkage across omitted slice history is unavailable, never silently reconstructed.
    """
    findings, observed, missing = [], [], set()
    previous_seq, generations, targets = {}, {}, {}

    def note(code, affected, evidence, why, next_check, values=None):
        item = alert("UNAVAILABLE", code, why, affected, evidence, next_check).__dict__.copy()
        item["diagnostic_scope"] = "RECORDED_EVIDENCE_ONLY_NOT_CERTIFIED_LIVE_HEALTH"
        item["observed_values"] = values or {}
        findings.append(item)

    if not isinstance(envelopes, (list, tuple)) or len(envelopes) > MAX_RECORDS:
        return {"state": "UNAVAILABLE", "reason": "MALFORMED_OR_OVERSIZED_ARCHIVE_SLICE", "findings": [], "observed": []}
    for index, envelope in enumerate(envelopes):
        fallback = f"archive_slice_index:{index}"
        if not isinstance(envelope, Mapping):
            note("MALFORMED_DETACHED_EVENT", "CAPTURE", [fallback], "Archived event is not an object.", "Inspect immutable receiver bytes and parser rejection.")
            continue
        event = mapping(envelope.get("event"))
        evidence = str(envelope.get("sha256") or envelope.get("archive_digest") or fallback)
        if not event:
            note("MALFORMED_DETACHED_EVENT", "CAPTURE", [evidence], "Missing original event object.", "Inspect immutable receiver bytes.")
            continue
        try:
            content_hash = digest(pack(event))
        except (ValueError, TypeError, OverflowError):
            note("NONCANONICAL_DETACHED_EVENT", "CAPTURE", [evidence], "Event includes malformed or nonfinite values.", "Inspect receiver schema rejection and original bytes.")
            continue
        if envelope.get("sha256") and envelope["sha256"] != content_hash:
            note("DETACHED_HASH_MISMATCH", "CAPTURE", [evidence], "Stored envelope hash disagrees with its archived event content.", "Reverify immutable receiver row and acquisition integrity.")
            continue
        identity = mapping(event.get("identity")); body = mapping(event.get("body"))
        kind = event.get("kind")
        stream = tuple(identity.get(k) for k in ("producer_id", "run_id", "boot_id"))
        if not all(isinstance(v, str) and v for v in stream):
            note("PRODUCER_RUN_EPOCH_MISSING", "SYSTEM", [evidence], "Producer/run/epoch cannot be identified.", "Compare original manifest and producer identity fields.")
            continue
        seq = event.get("sequence")
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
            note("INVALID_EVENT_SEQUENCE", "CAPTURE", [evidence], "Sequence is missing or invalid.", "Inspect receiver sequence tracking and original packet.")
            continue
        prior = previous_seq.get(stream)
        if prior and seq != prior[0] + 1:
            note("RECORDED_SEQUENCE_GAP_OR_REPLAY", "CAPTURE", [prior[1], evidence], "Adjacent archived sequence is discontinuous or repeated.", "Inspect receiver continuity and producer loss counters; do not bridge the interval.", {"prior_sequence": prior[0], "sequence": seq})
        previous_seq[stream] = (seq, evidence)
        if event.get("prior_dropped") not in (None, 0):
            note("PRODUCER_REPORTED_DROPPED_EVIDENCE", "CAPTURE", [evidence], "Producer explicitly reports lost evidence.", "Inspect drop count, bounded socket/backlog state and affected contract intervals.", {"prior_dropped": event.get("prior_dropped")})
        if expected_build is not None and identity.get("build_sha") != expected_build:
            note("PRODUCER_BUILD_MISMATCH", "SYSTEM", [evidence], "Recorded build differs from the reviewed expected build.", "Compare exact detached manifest and approved code hashes.")
        if expected_run is not None and identity.get("run_id") != expected_run:
            note("PRODUCER_RUN_MISMATCH", "SYSTEM", [evidence], "Recorded run differs from the reviewed expected run.", "Inspect explicit restart/epoch manifest; do not pool runs.")
        if event.get("orders") is not False or event.get("signal_only") is not True:
            note("SIGNAL_ONLY_FLAG_VIOLATION_OR_MISSING", "SYSTEM", [evidence], "Detached envelope does not explicitly preserve signal-only/no-order flags.", "Review changed producer and no-order integrity controls before deployment.")
        missing.add("real_admitted_clock_certificates")
        if kind in {"NATIVE_WAIT", "NATIVE_ERROR"}:
            note("RECORDED_"+kind, "SYSTEM", [evidence], "Native producer explicitly emitted WAIT/error; missing guidance is not a performance loss.", "Inspect native source availability and recorded error context without rerunning decisions.")
        if kind in {"PROTECTED_GENERATION", "PROTECTED_FILE_WRITE_COMPLETED"}:
            state = mapping(body.get("state"))
            if not state:
                note("PROTECTED_STATE_MISSING", "EARLY/FINAL/SCALP", [evidence], "Protected event has no original state.", "Inspect producer snapshot copy failure and receiver bytes.")
                continue
            actual_hash = digest(pack(state))
            if body.get("state_sha256") != actual_hash:
                note("PROTECTED_STATE_HASH_MISMATCH", "PUBLICATION", [evidence], "Recorded state fingerprint disagrees with the original state object.", "Inspect protected-generation and file-write identities.")
            gid = body.get("generation_id")
            if kind == "PROTECTED_GENERATION":
                if not isinstance(gid, str) or not gid:
                    missing.add("generation_id")
                else:
                    key = (stream, gid)
                    if key in generations and generations[key][0] != actual_hash:
                        note("IMMUTABLE_GENERATION_REWRITTEN", "PUBLICATION", [generations[key][1], evidence], "One generation identity names different protected states.", "Inspect producer generation binding; preserve both conflicting records.")
                    generations[key] = (actual_hash, evidence, seq)
            else:
                prior_generation = generations.get((stream, gid)) if isinstance(gid, str) else None
                if body.get("linkage_status") != "OBSERVED_SAME_OBJECT_UNCHANGED" or not gid:
                    note("PROTECTED_WRITE_GENERATION_LINK_UNAVAILABLE", "PUBLICATION", [evidence], "File completion explicitly lacks an unchanged generation link.", "Inspect original generation/write pair; do not substitute wall time or neighboring state.")
                elif not prior_generation:
                    missing.add("generation_outside_archive_slice")
                elif prior_generation[0] != actual_hash or prior_generation[2] >= seq:
                    note("PROTECTED_WRITE_GENERATION_CONFLICT", "PUBLICATION", [prior_generation[1], evidence], "File-write state differs from or precedes its explicitly linked generation.", "Inspect exact generation hash and original file completion event.")
                else:
                    observed.append({"kind": "EXPLICIT_GENERATION_FILE_WRITE_LINK", "evidence": [prior_generation[1], evidence], "generation_id": gid, "browser_delivery_proven": False})
            safety = mapping(state.get("safety"))
            if safety.get("orders_enabled") is not False or safety.get("read_only") is not True:
                note("PROTECTED_SIGNAL_ONLY_FLAG_VIOLATION_OR_MISSING", "SYSTEM", [evidence], "Protected state does not explicitly preserve read-only/no-order declarations.", "Inspect protected safety object and exact build's no-order controls.")
            contract = state.get("contract"); market = mapping(state.get("market")); timer = mapping(state.get("timer"))
            health = mapping(state.get("health")); parity = mapping(state.get("parity"))
            for field in ("contract", "api_contract"):
                if contract and parity.get(field) and parity[field] != contract:
                    note("RECORDED_TICKER_PARITY_MISMATCH", "KALSHI", [evidence], "Recorded parity ticker differs from protected contract; parity may itself be stale.", "Inspect original parity timestamp/contract and native official metadata; do not assume current exchange mismatch.", {"contract": contract, field: parity[field]})
            for flag, affected in (("contract_match", "KALSHI"), ("clock_match", "ALIGNMENT"), ("target_match", "KALSHI_START_PRICE"), ("quote_match", "QUOTES"), ("brti_match", "BRTI")):
                if explicit_false(parity.get(flag)):
                    note("RECORDED_PARITY_"+flag.upper()+"_FALSE", affected, [evidence], "Original parity producer explicitly reported a mismatch; this is recorded telemetry, not a new exchange query.", "Inspect original parity payload/time and matched source contract before classifying cause.")
            close, source = timestamp(timer.get("close_utc")), timestamp(state.get("source_timestamp_utc"))
            left = numeric(timer.get("seconds_left"))
            if left is not None and not 0 <= left <= 900:
                note("RECORDED_REMAINING_OUTSIDE_CONTRACT", "ALIGNMENT", [evidence], "Recorded remaining time is outside a 15-minute contract.", "Inspect original timer and official window; do not alter recorded labels.")
                left = None
            if close and source and left is not None:
                try:
                    canonical = datetime.fromtimestamp(round(close.timestamp()/900)*900, timezone.utc)
                    label_delta = abs((source+timedelta(seconds=float(left))-close).total_seconds())
                except (OverflowError, ValueError, OSError):
                    note("RECORDED_WINDOW_LABEL_OVERFLOW", "ALIGNMENT", [evidence], "Recorded labels cannot be represented safely for structural comparison.", "Inspect malformed original timestamp labels; no replacement timestamp is permitted.")
                    continue
                if abs((close-canonical).total_seconds()) > FROZEN_RECORDED_ALIGNMENT_TOLERANCE_SECONDS or label_delta > FROZEN_RECORDED_ALIGNMENT_TOLERANCE_SECONDS:
                    note("RECORDED_WINDOW_LABEL_CONFLICT", "ALIGNMENT", [evidence], "Original source/remaining/close labels contradict frozen two-second structural alignment tolerance.", "Inspect unmodified native timer labels and official contract window; no clock qualification is implied.")
                expected_ticker = "KXBTC15M-"+canonical.astimezone(ZoneInfo("America/New_York")).strftime("%y%b%d%H%M-%M").upper()
                if contract and contract != expected_ticker:
                    note("RECORDED_TICKER_CLOSE_CONFLICT", "ALIGNMENT", [evidence], "Recorded close labels imply a different contract ticker under the frozen mapping.", "Compare original official window/ticker witness; do not alter source timestamps.")
            else:
                missing.add("complete_recorded_window_labels")
            for lane, source_label in SOURCE_LABELS.items():
                item = mapping(state.get(lane))
                if not item or "source" not in item:
                    missing.add(lane+"_source_label")
                elif item.get("source") != source_label:
                    note("WRONG_"+lane.upper()+"_SOURCE_LABEL", lane.upper(), [evidence], "Recorded lane object uses a source other than its frozen protected producer.", "Inspect original producer path; startup/shadow values cannot substitute protected lane state.", {"source": item.get("source"), "expected": source_label})
            _market_diagnostics(market, health, evidence, note, missing)
        elif kind in {"NATIVE_CYCLE", "NATIVE_WAIT", "NATIVE_ERROR"}:
            state = mapping(body.get("snap")); contract = body.get("ticker") or state.get("contract")
            market = state
            for field in ("contract",):
                if body.get("ticker") and state.get(field) and body["ticker"] != state[field]:
                    note("NATIVE_SNAPSHOT_TICKER_CONFLICT", "KALSHI", [evidence], "Native local ticker and emitted snapshot contract disagree.", "Inspect same-cycle native locals; do not combine neighboring contracts.")
            if numeric(body.get("target")) is not None and numeric(state.get("target")) is not None and numeric(body["target"]) != numeric(state["target"]):
                note("NATIVE_SNAPSHOT_START_PRICE_CONFLICT", "KALSHI_START_PRICE", [evidence], "Native local target and same-cycle snapshot target differ.", "Inspect official target witness and native snapshot binding.")
            brti = mapping(body.get("_brti_contract"))
            diag_market = dict(market)
            if "ready" in brti: diag_market["brti_ready"] = brti["ready"]
            if "age" in brti: diag_market["brti_age_seconds"] = brti["age"]
            _market_diagnostics(diag_market, {}, evidence, note, missing)
        else:
            continue
        target = numeric(market.get("target"))
        if isinstance(contract, str) and target is not None:
            key = (stream, contract)
            if key in targets and targets[key][0] != target:
                note("RECORDED_CONTRACT_START_PRICE_CHANGED", "KALSHI_START_PRICE", [targets[key][1], evidence], "Same producer/run/epoch and contract emitted different start prices.", "Inspect immutable official target and any explicit correction witness; do not silently rebase origins.", {"previous": str(targets[key][0]), "current": str(target)})
            targets[key] = (target, evidence)
    return {"state": "UNAVAILABLE", "reason": "CLOCK_AND_FULL_LIVE_HEALTH_NOT_QUALIFIED",
            "findings": findings, "observed": observed, "missing": sorted(missing),
            "records_inspected": len(envelopes), "source_timestamps_created": 0,
            "strategy_mutations": 0, "orders": 0,
            "limit": "No finding means only no recorded contradiction detected in this bounded slice; not HEALTHY or live qualified."}


def _market_diagnostics(market, health, evidence, note, missing):
    if market.get("brti_ready") is False or health.get("brti_fresh") is False:
        note("RECORDED_BRTI_WAIT_OR_NOT_FRESH", "BRTI", [evidence], "Original producer explicitly recorded BRTI unready/not fresh; no inferred source timestamp.", "Inspect BRTI owner source witness, WAIT reason and original admission result.")
    for field in ("brti_age_seconds", "brti_effective_age_seconds"):
        age = numeric(market.get(field))
        if age is not None and (age < 0 or age > 5):
            note("RECORDED_BRTI_AGE_OUTSIDE_5S", "BRTI", [evidence], "Recorded age telemetry is outside [0,5] seconds; it is a rejection diagnostic, never a clock certificate.", "Inspect actual source/receipt/decision witnesses and interval guard; do not reconstruct source time from age.", {field: str(age)})
    for flag in ("source_fresh", "paired_quotes"):
        if health.get(flag) is False:
            note("RECORDED_"+flag.upper()+"_FALSE", "QUOTES/SOURCE", [evidence], "Protected producer explicitly reported source/quote unavailability.", "Inspect original quote continuity and source WAIT/recovery records.")
    for side in ("up", "down"):
        bid, ask = numeric(market.get(side+"_bid")), numeric(market.get(side+"_ask"))
        if bid is None or ask is None:
            missing.add(side+"_original_quote_pair")
            continue
        if not 0 <= bid <= 1 or not 0 <= ask <= 1 or bid > ask:
            note("RECORDED_INVALID_OR_CROSSED_"+side.upper()+"_QUOTE", "QUOTES/SCALP", [evidence], "Original same-side decimal quote pair is out of [0,1] or BID exceeds ASK.", "Inspect original book/source/receipt identity; do not infer fills or replace the entry ASK.", {"bid": str(bid), "ask": str(ask)})


def inspect_database(path, *, expected_build=None, expected_run=None):
    """Read only already detached receiver storage; no native/common endpoint."""
    try:
        with sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True, timeout=0) as db:
            rows = db.execute("SELECT raw FROM (SELECT rowid,raw FROM producer_events ORDER BY rowid DESC LIMIT ?) ORDER BY rowid", (MAX_RECORDS,)).fetchall()
        return inspect_events([strict(row[0]) for row in rows], expected_build=expected_build, expected_run=expected_run)
    except (sqlite3.Error, ValueError, TypeError, OSError) as exc:
        return {"state": "UNAVAILABLE", "reason": "DETACHED_DIAGNOSTIC_READ_FAILED", "detail": str(exc), "findings": []}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receiver-db", required=True)
    parser.add_argument("--expected-build")
    parser.add_argument("--expected-run")
    args = parser.parse_args()
    print(json.dumps(inspect_database(args.receiver_db, expected_build=args.expected_build,
                                     expected_run=args.expected_run), sort_keys=True, allow_nan=False))
    return 2  # Diagnostic-only output never admits live guidance.


if __name__ == "__main__":
    raise SystemExit(main())
