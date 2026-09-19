#!/usr/bin/env python3
"""Read-only production state diagnostics. No signal decisions or orders."""
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

MAX_AGE_SEC = 5.0
TIMER_TOLERANCE_SEC = 0.1  # production rounds logged seconds_left


def number(value):
    if isinstance(value, bool):
        raise ValueError("boolean_number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("nonfinite_number")
    return value


def timestamp(value):
    value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("timestamp_without_timezone")
    return value.timestamp()


def state_url(base):
    base = base.strip().rstrip("/")
    if "://" not in base:
        base = "https://" + base
    parts = urllib.parse.urlsplit(base)
    if (parts.scheme != "https" or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment
            or any(c.isspace() for c in base)):
        raise ValueError("invalid_state_url")
    return base + "/dashboard_state.json"


def inspect_state(data, observed_at):
    """Use source-time ages; generated_utc is never a BRTI timestamp."""
    timer, market, safety = data["timer"], data["market"], data["safety"]
    source = timestamp(data["source_timestamp_utc"])
    generated = timestamp(data["generated_utc"])
    close = timestamp(timer["close_utc"])
    observed = number(observed_at)
    source_age = observed - source
    generated_age = observed - generated
    logged_age = number(data["source_age_sec"])
    brti_at_source = number(market["brti_age_seconds"])
    brti_age = brti_at_source + source_age
    logged_remaining = number(timer["seconds_left"])
    generated_remaining = number(timer["remaining_at_generation_sec"])
    remaining = close - observed
    timer_delta = max(abs(close - source - logged_remaining),
                      abs(close - generated - generated_remaining))
    contract = data["contract"]
    if not isinstance(contract, str) or not contract.startswith("KXBTC15M-"):
        raise ValueError("invalid_contract")
    source_fresh = 0 <= source_age <= MAX_AGE_SEC
    brti_fresh = brti_at_source >= 0 and 0 <= brti_age <= MAX_AGE_SEC
    chronology_ok = 0 <= generated - source and generated_age >= 0
    reported_age_ok = logged_age >= 0 and abs(logged_age - (generated - source)) <= 0.01
    timer_ok = (timer_delta <= TIMER_TOLERANCE_SEC
                and 0 < remaining <= 900 and 0 < logged_remaining <= 900
                and 0 < generated_remaining <= 900)
    safety_ok = safety.get("read_only") is True and safety.get("orders_enabled") is False
    reasons = []
    for ok, reason in [(chronology_ok, "TIMESTAMP_ORDER"),
                       (reported_age_ok, "SOURCE_AGE_MISMATCH"),
                       (source_fresh, "SOURCE_STALE_OR_FUTURE"),
                       (brti_fresh, "BRTI_STALE_OR_FUTURE"),
                       (timer_ok, "TIMER_INVALID"),
                       (safety_ok, "SAFETY_FLAGS")]:
        if not ok:
            reasons.append(reason)
    return {
        "schema": "PASS", "contract": contract,
        "source_timestamp_utc": data["source_timestamp_utc"],
        "generated_utc": data["generated_utc"],
        "seconds_left_at_source": logged_remaining,
        "seconds_left_now": round(remaining, 3),
        "source_age_sec": round(source_age, 3),
        "brti_age_sec": round(brti_age, 3),
        "timer_consistency": "PASS" if timer_ok else "WAIT",
        "timer_delta_sec": round(timer_delta, 6),
        "close_basis": timer.get("close_basis"),
        "safety": "PASS" if safety_ok else "WAIT",
        "state_gate": "PASS" if not reasons else "WAIT",
        "reasons": reasons,
        "official_kalshi_alignment": "NOT_CHECKED",
        "cutover_approved": False, "probe_orders": False,
    }


def inspect_alignment(data, official, observed_at):
    """Compare against Kalshi metadata, never inferred ticker time or old CSVs."""
    opened = timestamp(official["open_time"])
    closed = timestamp(official["close_time"])
    source = timestamp(data["source_timestamp_utc"])
    close_delta = abs(timestamp(data["timer"]["close_utc"]) - closed)
    ok = (official["ticker"] == data["contract"]
          and abs(closed - opened - 900) <= 0.001
          and opened <= source <= observed_at < closed
          and close_delta <= TIMER_TOLERANCE_SEC)
    return {"official_kalshi_alignment": "PASS" if ok else "WAIT",
            "official_close_utc": official["close_time"],
            "close_delta_sec": round(close_delta, 6)}


def official_market(contract):
    # Reuse the canary's existing GET-only signing helper. No CF/BRTI polling.
    from btc15_kalshi_parity_shadow_gateway_v1 import auth_headers
    path = "/trade-api/v2/markets/" + urllib.parse.quote(contract, safe="")
    request = urllib.request.Request("https://external-api.kalshi.com" + path,
                                     headers=auth_headers("GET", path), method="GET")
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.load(response)["market"]


def main():
    try:
        request = urllib.request.Request(
            state_url(os.environ["BTC15_PRODUCTION_STATE_BASE"]),
            headers={"Accept": "application/json", "Cache-Control": "no-cache"},
            method="GET")
        with urllib.request.urlopen(request, timeout=3) as response:
            data = json.load(response)
        result = inspect_state(data, datetime.now(timezone.utc).timestamp())
        try:
            official = official_market(result["contract"])
            observed = datetime.now(timezone.utc).timestamp()
            # Include time spent waiting for the metadata response in freshness.
            result = inspect_state(data, observed)
            result.update(inspect_alignment(data, official, observed))
        except Exception as exc:
            result = inspect_state(data, datetime.now(timezone.utc).timestamp())
            result.update({"official_kalshi_alignment": "WAIT",
                           "alignment_error_type": type(exc).__name__})
    except Exception as exc:
        # Never print credentials, URLs, or arbitrary server response bodies.
        result = {"schema": "UNVERIFIED", "state_gate": "WAIT",
                  "error_type": type(exc).__name__,
                  "official_kalshi_alignment": "NOT_CHECKED",
                  "cutover_approved": False, "probe_orders": False}
    result["probe_gate"] = "PASS" if (result["state_gate"] == "PASS"
        and result["official_kalshi_alignment"] == "PASS") else "WAIT"
    print("BTC15_PROD_STATE_PROBE | " + json.dumps(result, separators=(",", ":"))
          + " | NO ORDERS", flush=True)
    return 0 if result["probe_gate"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
