#!/usr/bin/env python3
"""
BTC15 existing bot + frozen Rescue V2 PROVISIONAL SHADOW.

- Existing bot runs as an unchanged child process.
- Rescue V2 remains shadow-only.
- Frozen thresholds are not retuned.
- No orders.
- Fresh candidate/resolution records persist under /data.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv, json, math, signal, subprocess, sys, time

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
DATA_ROOT = Path("/data") if Path("/data").exists() else Path(".")
UNIFIED = DATA_ROOT / "kalshi_subminute_unified_v1_1.csv"
OUT = DATA_ROOT / "kalshi_rescue_v2_shadow_v1.csv"
STATE = DATA_ROOT / "kalshi_rescue_v2_shadow_state_v1.json"

POLL_SECONDS = 5

# Frozen Rescue V2 — DO NOT RETUNE.
ASK_MAX = 0.60
FAIR_MIN = 0.70
EDGE_MIN = 0.08
MIN_LEFT = 2.0
MAX_LEFT = 12.0
GAP_MIN = 15.0
RANGE_RATIO_MIN = 0.0
PRIOR_SWITCH_MIN = 1
TARGET = 0.08
STOP = 0.08
HORIZON_SECONDS = 180

FIELDS = [
    "record_type","call_id","source_timestamp_utc","contract","side",
    "entry_ask","fair","edge","minutes_left","gap_abs","range_ratio",
    "prior_switches","base_seen_before","result","exit_bid",
    "resolved_timestamp_utc","notes"
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

def yes(x):
    return str(x or "").strip().lower() in {"1","true","yes","y"}

def first(r, names):
    for k in names:
        if k in r and str(r.get(k,"")).strip() != "":
            return r.get(k)
    return ""

def pref_side(r):
    ps = side(first(r, ["preferred_fair_side","preferred_side","fair_preferred_side"]))
    if ps:
        return ps
    rs = side(r.get("side"))
    sf = prob(r.get("side_fair"))
    pf = prob(r.get("preferred_fair"))
    if yes(r.get("preferred_side_match")):
        return rs
    if rs and math.isfinite(sf) and math.isfinite(pf) and abs(sf-pf) < 1e-7:
        return rs
    return ""

def pref_ask(r, ps):
    a = prob(r.get("side_ask"))
    if math.isfinite(a) and side(r.get("side")) == ps:
        return a
    if ps == "UP":
        return prob(first(r, ["up_ask","yes_ask"]))
    return prob(first(r, ["down_ask","no_ask"]))

def edge_value(r):
    v = num(first(r, ["edge_vs_ask","preferred_edge","edge"]))
    if math.isfinite(v) and abs(v) > 1.5:
        v /= 100.0
    return v

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

def append_row(row):
    new = not OUT.exists()
    with OUT.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k,"") for k in FIELDS})

def default_state():
    return {
        "started_utc": utcnow().isoformat(),
        "last_timestamp_utc": "",
        "prev_side": {},
        "switches": {},
        "fired_contracts": [],
        "base_seen": [],
        "pending": {},
    }

def load_state():
    if not STATE.exists():
        return default_state()
    try:
        s = json.loads(STATE.read_text(encoding="utf-8"))
        base = default_state()
        base.update(s)
        return base
    except Exception:
        return default_state()

def save_state(s):
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE)

def base_signal_now(r, ps, ask, fair, edge, ml, gap, ratio):
    tier1 = (
        math.isfinite(ask) and ask <= .45
        and math.isfinite(fair) and fair >= .75
        and math.isfinite(edge) and edge >= .08
        and math.isfinite(ml) and 2 <= ml <= 10
        and math.isfinite(gap) and gap >= 25
    )

    target = side(r.get("current_target_side"))
    need = 75 if math.isfinite(ml) and ml > 6 else 50
    final = (
        math.isfinite(fair) and fair >= .90
        and math.isfinite(ml) and ml <= 8
        and math.isfinite(gap) and gap >= need
        and math.isfinite(ratio) and ratio >= 1.0
        and ps and ps == target
    )

    strong_scalp_entry = (
        math.isfinite(ask) and ask <= .70
        and math.isfinite(fair) and fair >= .52
        and math.isfinite(edge) and edge >= 0
        and math.isfinite(ml) and 3 <= ml <= 10
        and math.isfinite(gap) and gap >= 50
    )
    return tier1 or final or strong_scalp_entry

def shadow_loop(bot_proc):
    s = load_state()
    started = parse_dt(s.get("started_utc")) or utcnow()
    last_ts = parse_dt(s.get("last_timestamp_utc"))
    fired = set(s.get("fired_contracts", []))
    base_seen = set(s.get("base_seen", []))
    prev_side = dict(s.get("prev_side", {}))
    switches = {k:int(v) for k,v in s.get("switches", {}).items()}
    pending = dict(s.get("pending", {}))

    print("="*78, flush=True)
    print("RESCUE V2 PROVISIONAL SHADOW: STARTING", flush=True)
    print("Frozen rule: ask<=60c | fair>=70% | edge>=8% | 2-12m | gap>=$15 | switch>=1", flush=True)
    print("Exit score: +8c target / -8c stop / 3m horizon", flush=True)
    print("Promotion gate: 15 CLOSED fresh calls at >=90% | NO RETUNING", flush=True)
    print(f"Shadow log: {OUT}", flush=True)
    print("NO ORDERS — EXISTING BOT RUNS UNCHANGED", flush=True)
    print("="*78, flush=True)

    while bot_proc.poll() is None:
        try:
            if not UNIFIED.exists():
                time.sleep(POLL_SECONDS)
                continue

            with UNIFIED.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
                rows = list(csv.DictReader(f))

            batch = []
            for r in rows:
                t = parse_dt(r.get("timestamp_utc"))
                if not t or t < started:
                    continue
                if last_ts is not None and t <= last_ts:
                    continue
                batch.append((t, r))

            if not batch:
                time.sleep(POLL_SECONDS)
                continue

            batch.sort(key=lambda x: x[0])
            max_ts = max(t for t,_ in batch)

            for t, r in batch:
                c = str(r.get("contract","")).strip()
                if not c:
                    continue

                p = pending.get(c)
                if p:
                    t0 = parse_dt(p["signal_utc"])
                    deadline = parse_dt(p["deadline_utc"])
                    bid = side_bid(r, p["side"])
                    if t0 and t > t0 and math.isfinite(bid):
                        result = None
                        if bid <= float(p["entry_ask"]) - STOP:
                            result = "LOSS"
                        elif bid >= float(p["entry_ask"]) + TARGET:
                            result = "WIN"
                        elif deadline and t >= deadline:
                            result = "MISS"

                        if result:
                            append_row({
                                "record_type":"RESOLUTION",
                                "call_id":p["call_id"],
                                "source_timestamp_utc":p["signal_utc"],
                                "contract":c,
                                "side":p["side"],
                                "entry_ask":p["entry_ask"],
                                "fair":p["fair"],
                                "edge":p["edge"],
                                "minutes_left":p["minutes_left"],
                                "gap_abs":p["gap_abs"],
                                "range_ratio":p["range_ratio"],
                                "prior_switches":p["prior_switches"],
                                "base_seen_before":p["base_seen_before"],
                                "result":result,
                                "exit_bid":round(bid,6),
                                "resolved_timestamp_utc":t.isoformat(),
                                "notes":"FROZEN_RESCUE_V2_PROSPECTIVE"
                            })
                            print(f"RESCUE V2 RESOLVED | {c} | {p['side']} | {result} | exit {bid:.3f}", flush=True)
                            pending.pop(c, None)

                ps = pref_side(r)
                rs = side(r.get("side"))
                if not ps or rs != ps:
                    continue

                prev = prev_side.get(c, "")
                sw = int(switches.get(c, 0))
                if prev and ps != prev:
                    sw += 1
                prev_side[c] = ps
                switches[c] = sw

                ask = pref_ask(r, ps)
                fair = prob(r.get("preferred_fair"))
                edge = edge_value(r)
                ml = num(r.get("minutes_left"))
                gap_raw = num(r.get("btc_gap"))
                gap = abs(gap_raw) if math.isfinite(gap_raw) else math.nan
                ratio = num(r.get("dist_over_range5"))

                if base_signal_now(r, ps, ask, fair, edge, ml, gap, ratio):
                    base_seen.add(c)

                if c in fired or c in base_seen:
                    continue

                qualifies = (
                    math.isfinite(ask) and ask <= ASK_MAX
                    and math.isfinite(fair) and fair >= FAIR_MIN
                    and math.isfinite(edge) and edge >= EDGE_MIN
                    and math.isfinite(ml) and MIN_LEFT <= ml <= MAX_LEFT
                    and math.isfinite(gap) and gap >= GAP_MIN
                    and math.isfinite(ratio) and ratio >= RANGE_RATIO_MIN
                    and sw >= PRIOR_SWITCH_MIN
                )
                if not qualifies:
                    continue

                call_id = f"{c}|{t.isoformat()}"
                p = {
                    "call_id":call_id,
                    "signal_utc":t.isoformat(),
                    "deadline_utc":(t + timedelta(seconds=HORIZON_SECONDS)).isoformat(),
                    "side":ps,
                    "entry_ask":round(ask,6),
                    "fair":round(fair,6),
                    "edge":round(edge,6),
                    "minutes_left":round(ml,4),
                    "gap_abs":round(gap,4),
                    "range_ratio":round(ratio,6),
                    "prior_switches":sw,
                    "base_seen_before":False,
                }
                pending[c] = p
                fired.add(c)
                append_row({
                    "record_type":"CANDIDATE",
                    "call_id":call_id,
                    "source_timestamp_utc":t.isoformat(),
                    "contract":c,
                    "side":ps,
                    "entry_ask":round(ask,6),
                    "fair":round(fair,6),
                    "edge":round(edge,6),
                    "minutes_left":round(ml,4),
                    "gap_abs":round(gap,4),
                    "range_ratio":round(ratio,6),
                    "prior_switches":sw,
                    "base_seen_before":False,
                    "result":"OPEN",
                    "notes":"FROZEN_RESCUE_V2_PROSPECTIVE"
                })
                print(
                    f"RESCUE V2 SHADOW | {c} | {ps} | ask {ask*100:.0f}c | "
                    f"fair {fair*100:.1f}% | edge {edge*100:.1f}% | "
                    f"{ml:.2f}m | gap ${gap:.2f} | switches {sw}",
                    flush=True
                )

            last_ts = max_ts
            save_state({
                "started_utc": started.isoformat(),
                "last_timestamp_utc": last_ts.isoformat(),
                "prev_side": prev_side,
                "switches": switches,
                "fired_contracts": sorted(fired),
                "base_seen": sorted(base_seen),
                "pending": pending,
            })

        except Exception as e:
            print(f"RESCUE V2 SHADOW WARNING: {type(e).__name__}: {e}", flush=True)

        time.sleep(POLL_SECONDS)

    return bot_proc.returncode

def main():
    if "--self-test" in sys.argv:
        lines = Path(__file__).read_text(encoding="utf-8").splitlines()
        if len(lines) < 100:
            raise SystemExit("SELF-TEST FAIL: wrapper is not a real multi-line Python file.")
        if not BOT.exists():
            raise SystemExit(f"SELF-TEST FAIL: missing {BOT}")
        print("RESCUE V2 WRAPPER SELF-TEST: PASS")
        print(f"Wrapper lines: {len(lines)}")
        print("Existing bot present: YES")
        print("Orders enabled by wrapper: NO")
        return 0

    if not BOT.exists():
        raise SystemExit(f"STOP: missing existing bot {BOT}")

    print("Starting existing BTC15 bot as unchanged child process...", flush=True)
    proc = subprocess.Popen([sys.executable, "-u", str(BOT)])

    def stop(signum, frame):
        if proc.poll() is None:
            proc.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    rc = shadow_loop(proc)
    if proc.poll() is None:
        proc.terminate()
    return rc or 0

if __name__ == "__main__":
    raise SystemExit(main())
