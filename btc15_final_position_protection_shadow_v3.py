#!/usr/bin/env python3
"""
BTC15 FINAL POSITION-PROTECTION PROSPECTIVE SHADOW V3

Purpose:
- Observe only fresh post-start unified rows on Railway.
- Reconstruct the frozen FINAL trigger exactly enough for position-protection study.
- After FINAL triggers, persist the full post-FINAL trajectory through rollover.
- Record raw features needed to validate HOLD / WATCH / PROTECT PROFITS / EXIT.
- Do NOT invent protection thresholds yet.
- Read-only. No orders. No core logic changes.
"""

from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, deque
import csv
import json
import math
import sys
import time

DATA_ROOT = Path("/data") if Path("/data").exists() else Path(".")
SOURCE = DATA_ROOT / "kalshi_subminute_unified_v1_1.csv"
OUT = DATA_ROOT / "kalshi_final_position_protection_shadow_v3.csv"
STATE = DATA_ROOT / "kalshi_final_position_protection_shadow_v3_state.json"

POLL_SECONDS = 3

# Frozen FINAL qualification. Do not retune here.
FAIR_MIN = 0.90
MAX_MINUTES_LEFT = 8.0
GAP_EARLY = 75.0   # when >6m left
GAP_LATE = 50.0
DIST_RANGE_MIN = 1.0

FIELDS = [
    "collector_timestamp_utc",
    "source_timestamp_utc",
    "contract",
    "record_type",
    "final_side",
    "current_preferred_side",
    "final_trigger_fair",
    "current_fair",
    "fair_change_from_trigger",
    "minutes_left",
    "btc_price",
    "btc_gap",
    "signed_gap_for_final_side",
    "trigger_signed_gap",
    "signed_gap_change_from_trigger",
    "dist_over_range5",
    "brti_ready",
    "brti_side",
    "brti_gap",
    "reversal_state",
    "up_bid","up_ask","down_bid","down_ask",
    "final_side_bid",
    "trigger_final_side_bid",
    "bid_change_from_trigger",
    "current_target_side",
    "notes",
]

def utcnow():
    return datetime.now(timezone.utc)

def parse_dt(x):
    try:
        d = datetime.fromisoformat(str(x).strip().replace("Z","+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None

def num(x):
    try:
        return float(str(x).strip())
    except Exception:
        return math.nan

def prob(x):
    v = num(x)
    if math.isfinite(v) and abs(v) > 1.5:
        v /= 100.0
    return v

def side(x):
    s = str(x or "").strip().upper()
    if s in {"UP","YES","Y","HIGHER","ABOVE","TRUE","1"}:
        return "UP"
    if s in {"DOWN","NO","N","LOWER","BELOW","FALSE","0"}:
        return "DOWN"
    return ""

def truthy(x):
    return str(x or "").strip().lower() in {"1","true","yes","y"}

def first(r, names):
    for k in names:
        if k in r and str(r.get(k,"")).strip() != "":
            return r.get(k)
    return ""

def preferred_side(r):
    ps = side(first(r, ["preferred_side","preferred_fair_side","fair_preferred_side"]))
    if ps:
        return ps
    rs = side(r.get("side"))
    sf = prob(r.get("side_fair"))
    pf = prob(r.get("preferred_fair"))
    if truthy(r.get("preferred_side_match")):
        return rs
    if rs and math.isfinite(sf) and math.isfinite(pf) and abs(sf-pf) < 1e-7:
        return rs
    return ""

def preferred_row(r):
    ps = preferred_side(r)
    rs = side(r.get("side"))
    # Unified is side-row based; use only the row corresponding to preferred side.
    return bool(ps and (not rs or rs == ps))

def side_bid(r, sd):
    if sd == "UP":
        v = prob(first(r, ["up_bid","yes_bid"]))
    else:
        v = prob(first(r, ["down_bid","no_bid"]))
    if math.isfinite(v):
        return v
    if side(r.get("side")) == sd:
        return prob(r.get("side_bid"))
    return math.nan

def quote(r, sd, level):
    if sd == "UP" and level == "bid":
        return prob(first(r, ["up_bid","yes_bid"]))
    if sd == "UP":
        return prob(first(r, ["up_ask","yes_ask"]))
    if sd == "DOWN" and level == "bid":
        return prob(first(r, ["down_bid","no_bid"]))
    return prob(first(r, ["down_ask","no_ask"]))

def load_state():
    if not STATE.exists():
        return {
            "started_utc": utcnow().isoformat(),
            "last_source_utc": "",
            "active": None,
        }
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "started_utc": utcnow().isoformat(),
            "last_source_utc": "",
            "active": None,
        }

def save_state(s):
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE)

def append(rec):
    new = not OUT.exists()
    with OUT.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({k:rec.get(k,"") for k in FIELDS})

def read_rows():
    if not SOURCE.exists():
        return []
    with SOURCE.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
        return list(csv.DictReader(f))

def qualifies_final(r):
    ps = preferred_side(r)
    pf = prob(r.get("preferred_fair"))
    ml = num(r.get("minutes_left"))
    gap = num(r.get("btc_gap"))
    ratio = num(r.get("dist_over_range5"))
    target_side = side(r.get("current_target_side"))
    brti_ready = truthy(first(r, ["brti_ready","ready"]))
    brti_side = side(r.get("brti_side"))

    if not (ps and math.isfinite(pf) and math.isfinite(ml) and math.isfinite(gap) and math.isfinite(ratio)):
        return False

    gap_need = GAP_EARLY if ml > 6 else GAP_LATE
    return (
        pf >= FAIR_MIN
        and ml <= MAX_MINUTES_LEFT
        and abs(gap) >= gap_need
        and ratio >= DIST_RANGE_MIN
        and target_side == ps
        and brti_ready
        and brti_side == ps
    )

def make_record(r, record_type, active):
    ps_now = preferred_side(r)
    final_side = active["final_side"]
    pf = prob(r.get("preferred_fair"))
    ml = num(r.get("minutes_left"))
    btc = num(r.get("btc_price"))
    gap = num(r.get("btc_gap"))
    ratio = num(r.get("dist_over_range5"))
    brti_gap = num(r.get("brti_gap"))
    final_bid = side_bid(r, final_side)

    signed_gap = gap if final_side == "UP" else (-gap if math.isfinite(gap) else math.nan)
    fair_change = pf - float(active["trigger_fair"]) if math.isfinite(pf) else math.nan
    signed_change = (
        signed_gap - float(active["trigger_signed_gap"])
        if math.isfinite(signed_gap) else math.nan
    )
    bid_change = (
        final_bid - float(active["trigger_bid"])
        if math.isfinite(final_bid) and math.isfinite(float(active["trigger_bid"]))
        else math.nan
    )

    return {
        "collector_timestamp_utc":utcnow().isoformat(),
        "source_timestamp_utc":r.get("timestamp_utc",""),
        "contract":str(r.get("contract","")).strip(),
        "record_type":record_type,
        "final_side":final_side,
        "current_preferred_side":ps_now,
        "final_trigger_fair":active["trigger_fair"],
        "current_fair":pf if math.isfinite(pf) else "",
        "fair_change_from_trigger":fair_change if math.isfinite(fair_change) else "",
        "minutes_left":ml if math.isfinite(ml) else "",
        "btc_price":btc if math.isfinite(btc) else "",
        "btc_gap":gap if math.isfinite(gap) else "",
        "signed_gap_for_final_side":signed_gap if math.isfinite(signed_gap) else "",
        "trigger_signed_gap":active["trigger_signed_gap"],
        "signed_gap_change_from_trigger":signed_change if math.isfinite(signed_change) else "",
        "dist_over_range5":ratio if math.isfinite(ratio) else "",
        "brti_ready":truthy(first(r,["brti_ready","ready"])),
        "brti_side":side(r.get("brti_side")),
        "brti_gap":brti_gap if math.isfinite(brti_gap) else "",
        "reversal_state":first(r,["reversal_state","reversal"]),
        "up_bid":quote(r,"UP","bid") if math.isfinite(quote(r,"UP","bid")) else "",
        "up_ask":quote(r,"UP","ask") if math.isfinite(quote(r,"UP","ask")) else "",
        "down_bid":quote(r,"DOWN","bid") if math.isfinite(quote(r,"DOWN","bid")) else "",
        "down_ask":quote(r,"DOWN","ask") if math.isfinite(quote(r,"DOWN","ask")) else "",
        "final_side_bid":final_bid if math.isfinite(final_bid) else "",
        "trigger_final_side_bid":active["trigger_bid"] if math.isfinite(float(active["trigger_bid"])) else "",
        "bid_change_from_trigger":bid_change if math.isfinite(bid_change) else "",
        "current_target_side":side(r.get("current_target_side")),
        "notes":"RAW_PROTECTION_TELEMETRY_ONLY",
    }

def main():
    if "--self-test" in sys.argv:
        print("FINAL POSITION-PROTECTION V3 SELF-TEST: PASS")
        print("Prospective collector only. No network request. No orders.")
        return 0

    state = load_state()
    started = parse_dt(state.get("started_utc")) or utcnow()
    last = parse_dt(state.get("last_source_utc"))
    active = state.get("active")

    print("="*88, flush=True)
    print("BTC15 FINAL POSITION-PROTECTION PROSPECTIVE SHADOW V3: STARTING", flush=True)
    print(f"Source: {SOURCE}", flush=True)
    print(f"Output: {OUT}", flush=True)
    print("Purpose: collect raw post-FINAL evidence for HOLD/WATCH/PROTECT PROFITS/EXIT.", flush=True)
    print("NO protection thresholds invented yet. Existing bot unchanged. NO ORDERS.", flush=True)
    print("="*88, flush=True)

    while True:
        try:
            rows = read_rows()
            batch = []
            for r in rows:
                t = parse_dt(r.get("timestamp_utc"))
                if t is None or t < started:
                    continue
                if last is not None and t <= last:
                    continue
                if not preferred_row(r):
                    continue
                batch.append((t,r))

            if not batch:
                time.sleep(POLL_SECONDS)
                continue

            batch.sort(key=lambda z:z[0])

            for t,r in batch:
                c = str(r.get("contract","")).strip()
                if not c:
                    continue

                if active and c != active.get("contract"):
                    print(
                        f"POSITION-PROTECTION ROLLOVER | finished {active.get('contract')} FINAL {active.get('final_side')}",
                        flush=True,
                    )
                    active = None

                if active is None and qualifies_final(r):
                    ps = preferred_side(r)
                    pf = prob(r.get("preferred_fair"))
                    gap = num(r.get("btc_gap"))
                    signed_gap = gap if ps == "UP" else -gap
                    bid = side_bid(r,ps)
                    active = {
                        "contract":c,
                        "final_side":ps,
                        "trigger_utc":t.isoformat(),
                        "trigger_fair":float(pf),
                        "trigger_signed_gap":float(signed_gap),
                        "trigger_bid":float(bid) if math.isfinite(bid) else math.nan,
                    }
                    append(make_record(r,"FINAL_TRIGGER",active))
                    print(
                        f"POSITION-PROTECTION FINAL_TRIGGER | {c} | {ps} | "
                        f"fair {pf*100:.1f}% | {num(r.get('minutes_left')):.2f}m left | "
                        f"signed gap ${signed_gap:.2f}",
                        flush=True,
                    )

                elif active and c == active.get("contract"):
                    append(make_record(r,"POST_FINAL",active))

            last = max(t for t,_ in batch)
            save_state({
                "started_utc":started.isoformat(),
                "last_source_utc":last.isoformat(),
                "active":active,
            })

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"POSITION-PROTECTION WARNING | {type(e).__name__}: {e}", flush=True)

        time.sleep(POLL_SECONDS)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
