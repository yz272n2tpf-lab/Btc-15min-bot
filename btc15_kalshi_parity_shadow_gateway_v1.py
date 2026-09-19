#!/usr/bin/env python3
"""Live production / gateway parity diagnostic. Canary only. NO ORDERS."""
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from btc15_production_state_probe_v1 import (
    inspect_alignment, inspect_state, number, state_url, timestamp)

MAX_AGE_SEC = 5.0
MATCH_TIME_TOLERANCE_SEC = 0.250  # reconstructed BRTI source time, never latest tick
BRTI_VALUE_TOLERANCE = 2.0
TARGET_TOLERANCE = 1.0
QUOTE_TOLERANCE = 0.06
WAIT_ZONE_DOLLARS = 11.0

def load_private_key():
    from cryptography.hazmat.primitives import serialization
    kid = os.getenv("KALSHI_KEY_ID","").strip()
    b64 = os.getenv("KALSHI_PRIVATE_KEY_B64","").strip()
    if kid and b64:
        return kid, serialization.load_pem_private_key(base64.b64decode(b64), password=None)
    kid_path = Path.home()/".kalshi"/"key_id"
    key_path = Path.home()/".kalshi"/"private_key.pem"
    if kid_path.exists() and key_path.exists():
        return kid_path.read_text().strip(), serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    raise RuntimeError("Kalshi read-only credentials not available")

KEY_ID = None
PRIVATE_KEY = None

def auth_headers(method, path):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    if method.upper() != "GET":
        raise ValueError("Read-only authentication")
    global KEY_ID, PRIVATE_KEY
    if KEY_ID is None or PRIVATE_KEY is None:
        KEY_ID, PRIVATE_KEY = load_private_key()
    ts = str(int(time.time()*1000))
    sig = PRIVATE_KEY.sign(
        (ts + method.upper() + path).encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "Accept": "application/json",
        "User-Agent": "BTC15-parity-lowmem/3.0",
    }


def zone(gap):
    gap = number(gap)
    return "WAIT" if abs(gap) <= WAIT_ZONE_DOLLARS else ("UP" if gap > 0 else "DOWN")


def integer(value):
    n = number(value)
    if n != int(n):
        raise ValueError("noninteger")
    return int(n)


def quote(market, side, level):
    dollars = side + "_" + level + "_dollars"
    cents = side + "_" + level
    value = number(market[dollars]) if dollars in market else number(market[cents]) / 100
    if not 0 <= value <= 1:
        raise ValueError("invalid_quote")
    return value


def evaluate(data, official, before, ring, after, observed_at):
    result = {"status": "WAIT", "input": "LIVE_PRODUCTION",
              "cutover_approved": False, "orders": False, "signal_only": True}
    try:
        current = inspect_state(data, observed_at)
        alignment = inspect_alignment(data, official, observed_at)
        reasons = list(current["reasons"])
        failures = []
        result.update({"contract": current["contract"],
                       "source_age_sec": current["source_age_sec"],
                       "brti_age_sec": current["brti_age_sec"],
                       "kalshi_alignment": alignment["official_kalshi_alignment"],
                       "close_delta_sec": alignment["close_delta_sec"]})
        if alignment["official_kalshi_alignment"] != "PASS":
            reasons.append("CONTRACT_OR_CLOCK")
        if any(data["health"].get(k) is not True
               for k in ("source_fresh", "paired_quotes", "brti_fresh", "market_open")):
            reasons.append("PRODUCTION_HEALTH")
        if data["market"].get("brti_ready") is not True:
            reasons.append("PRODUCTION_BRTI_NOT_READY")

        epoch = before["owner_epoch"]
        if not isinstance(epoch, str) or not epoch or after["owner_epoch"] != epoch:
            reasons.append("OWNER_CHANGED")
        if integer(after["sequence"]) < integer(before["sequence"]):
            reasons.append("SEQUENCE_REGRESSION")
        for state in (before, after):
            if state.get("orders") is not False or state.get("signal_only") is not True:
                reasons.append("GATEWAY_SAFETY")
            age = observed_at - integer(state["source_ts_ms"]) / 1000
            if not 0 <= age <= MAX_AGE_SEC:
                reasons.append("GATEWAY_STALE_OR_FUTURE")
            if number(state["value"]) <= 0:
                raise ValueError("invalid_gateway_value")
        result["gateway_age_sec"] = round(observed_at - integer(after["source_ts_ms"]) / 1000, 3)
        if ring.get("orders") is not False:
            raise ValueError("invalid_ring_safety")
        observations = ring["ticks"]
        if not isinstance(observations, list):
            raise ValueError("invalid_ring")
        candidates = []
        previous_ts = previous_seq = None
        for tick in observations:
            if tick.get("owner_epoch") != epoch:
                continue
            if (tick.get("orders") is not False or tick.get("signal_only") is not True
                    or tick.get("index_id") != "BRTI"):
                raise ValueError("invalid_tick_safety")
            ts, seq = integer(tick["source_ts_ms"]), integer(tick["sequence"])
            value = number(tick["value"])
            if value <= 0 or (previous_ts is not None and (ts <= previous_ts or seq <= previous_seq)):
                raise ValueError("invalid_tick_order")
            previous_ts, previous_seq = ts, seq
            if seq > integer(after["sequence"]):
                raise ValueError("tick_after_final_state")
            candidates.append((ts / 1000, value))
        source = timestamp(data["source_timestamp_utc"])
        brti_at_source = number(data["market"]["brti_age_seconds"])
        inferred = source - brti_at_source
        result["timestamp_basis"] = "source_minus_logged_brti_age"
        matched = min(candidates, key=lambda x: abs(x[0] - inferred)) if candidates else None
        if matched is None or abs(matched[0] - inferred) > MATCH_TIME_TOLERANCE_SEC:
            reasons.append("NO_MATCHING_BRTI_TICK")
        else:
            result["match_delta_ms"] = round(abs(matched[0] - inferred) * 1000, 3)
            if not 0 <= observed_at - matched[0] <= MAX_AGE_SEC:
                reasons.append("MATCHED_TICK_STALE_OR_FUTURE")

        market = data["market"]
        target, official_target = number(market["target"]), number(official["floor_strike"])
        logged_value = number(market["brti_value"])
        if min(target, official_target, logged_value) <= 0:
            raise ValueError("invalid_price")
        target_delta = abs(target - official_target)
        result["target_delta"] = round(target_delta, 4)
        if target_delta > TARGET_TOLERANCE:
            failures.append("TARGET")
        gap = logged_value - target
        if abs(number(market["brti_gap"]) - gap) > 0.01:
            failures.append("LOGGED_BRTI_GAP")
        if matched is not None and "NO_MATCHING_BRTI_TICK" not in reasons:
            value_delta = abs(logged_value - matched[1])
            production_zone, gateway_zone = zone(gap), zone(matched[1] - official_target)
            result.update({"brti_delta": round(value_delta, 4),
                           "production_zone": production_zone, "gateway_zone": gateway_zone})
            if value_delta > BRTI_VALUE_TOLERANCE:
                failures.append("BRTI_VALUE")
            if production_zone != gateway_zone:
                failures.append("WAIT_ZONE_OR_DIRECTION")

        deltas = []
        for local_side, api_side in (("up", "yes"), ("down", "no")):
            bid, ask = (number(market[local_side + "_" + k]) for k in ("bid", "ask"))
            api_bid, api_ask = (quote(official, api_side, k) for k in ("bid", "ask"))
            if not 0 <= bid <= ask <= 1 or api_bid > api_ask:
                raise ValueError("crossed_or_invalid_quotes")
            deltas.extend((abs(bid - api_bid), abs(ask - api_ask)))
        result["quote_delta_cents"] = round(max(deltas) * 100, 3)
        if max(deltas) > QUOTE_TOLERANCE + 1e-9:
            failures.append("QUOTES")
        result["reasons"] = sorted(set(reasons + failures))
        result["scorable"] = not reasons
        result["status"] = "WAIT" if reasons else ("FAIL" if failures else "PASS")
    except Exception as exc:
        result.update({"status": "WAIT", "scorable": False,
                       "reasons": ["INVALID_OR_MISSING_INPUT"], "error_type": type(exc).__name__})
    return result


def get_json(url, timeout, headers=None):
    request = urllib.request.Request(url, headers=headers or {"Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def audit():
    # All reads are bounded. No archived CSV fallback and no upstream BRTI HTTP.
    from btc15_brti_ws_gateway_client_v1 import state as gateway_brti_state
    data = get_json(state_url(os.environ["BTC15_PRODUCTION_STATE_BASE"]), 3)
    contract = data["contract"]
    if not isinstance(contract, str) or not contract.startswith("KXBTC15M-"):
        raise ValueError("invalid_contract")
    path = "/trade-api/v2/markets/" + urllib.parse.quote(contract, safe="")
    official = get_json("https://external-api.kalshi.com" + path, 3,
                        auth_headers("GET", path))["market"]
    before = gateway_brti_state()
    base = os.environ["BTC15_BRTI_GATEWAY_URL"].rstrip("/")
    ring = get_json(base + "/ticks", 1)
    after = gateway_brti_state()
    return evaluate(data, official, before, ring, after, time.time())


def main():
    while True:
        try:
            result = audit()
        except Exception as exc:
            result = {"status": "WAIT", "input": "LIVE_PRODUCTION", "scorable": False,
                      "reasons": ["INPUT_UNAVAILABLE"], "error_type": type(exc).__name__,
                      "cutover_approved": False, "orders": False, "signal_only": True}
        print("BRTI_LIVE_PARITY | " + json.dumps(result, separators=(",", ":")) + " | NO ORDERS", flush=True)
        if "--once" in sys.argv:
            return 0 if result["status"] == "PASS" else 2
        time.sleep(15)


if __name__ == "__main__":
    sys.exit(main())
