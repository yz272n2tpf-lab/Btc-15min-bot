#!/usr/bin/env python3
"""Research-only tightening screen for the current UNIFIED_V8 shadow.

Consumes Railway log text containing UNIFIED_V8 CANDIDATE / RESULT lines and
screens ONLY entry-time, price-neutral features. It cannot change the live
gate. Price/zone and outcome-lookahead fields are explicitly excluded from
qualification recommendations.

Signal-only research utility. NO ORDERS.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict, deque

GRIDS = {
    "quality": (1.05, 1.10, 1.20, 1.30, 1.40),
    "btc5": (22.0, 23.0, 24.0, 25.0, 27.5, 30.0),
    "btc15": (26.0, 27.5, 30.0, 32.5, 35.0),
    "btc30": (5.0, 10.0, 15.0, 20.0, 25.0),
    "accel": (11.0, 12.0, 15.0, 18.0, 20.0),
    "brti5": (20.0, 22.0, 23.0, 24.0, 25.0, 27.5, 30.0),
    "brti15": (10.0, 15.0, 20.0, 25.0, 27.5, 30.0),
}

MIN_WINNER_CLUSTERS_FOR_WATCH = 5
MIN_FAILURE_CLUSTERS_REMOVED_FOR_WATCH = 3
MIN_FAILURES_REMOVED_FOR_WATCH = 4
MIN_FAILURE_ZONES_FOR_WATCH = 2


def _num(text):
    return float(text)


def _maybe(text):
    return None if text == "None" else float(text)


def _parts(line):
    if "UNIFIED_V8 " not in line:
        return None, []
    body = line[line.index("UNIFIED_V8 "):].strip()
    return body.split(" | ")[0], [p.strip() for p in body.split(" | ")]


def _pref(part, prefix):
    if not part.startswith(prefix):
        raise ValueError("expected %r in %r" % (prefix, part))
    return part[len(prefix):].strip()


def _candidate(parts):
    if len(parts) != 14:
        raise ValueError("candidate field count %d" % len(parts))
    return {
        "ticker": parts[1],
        "side": parts[2],
        "zone": _pref(parts[3], "zone "),
        "setup": _pref(parts[4], "setup "),
        "entry": _num(_pref(parts[5], "ask ")),
        "quality": _num(_pref(parts[6], "quality ")),
        "btc5": _num(_pref(parts[7], "btc5 ")),
        "btc15": _num(_pref(parts[8], "btc15 ")),
        "btc30": _num(_pref(parts[9], "btc30 ")),
        "accel": _num(_pref(parts[10], "accel ")),
        "brti5": _num(_pref(parts[11], "brti5 ")),
        "brti15": _num(_pref(parts[12], "brti15 ")),
        "left": _num(_pref(parts[13], "left ").rstrip("s")),
    }


def _result(parts):
    if len(parts) != 14:
        raise ValueError("result field count %d" % len(parts))
    return {
        "ticker": parts[1],
        "side": parts[2],
        "zone": _pref(parts[3], "zone "),
        "setup": _pref(parts[4], "setup "),
        "style": _pref(parts[5], "style "),
        "entry": _num(_pref(parts[6], "entry ")),
        "quality": _num(_pref(parts[7], "quality ")),
        "gain": _num(_pref(parts[8], "max_gain ")),
        "adverse": _num(_pref(parts[9], "adverse ")),
        "pre10": _num(_pref(parts[10], "pre10_adverse ")),
        "t5": _maybe(_pref(parts[11], "to+5c ")),
        "t10": _maybe(_pref(parts[12], "to+10c ")),
        "t20": _maybe(_pref(parts[13], "to+20c ")),
    }


def _key(row):
    return (
        row["ticker"],
        row["side"],
        row["zone"],
        row["setup"],
        round(row["entry"], 3),
        round(row["quality"], 2),
    )


def parse(lines):
    queues = defaultdict(deque)
    rows = []
    bad_lines = 0
    unmatched_results = 0
    for line in lines:
        kind, parts = _parts(line)
        if not parts:
            continue
        try:
            if kind == "UNIFIED_V8 CANDIDATE":
                c = _candidate(parts)
                queues[_key(c)].append(c)
            elif kind == "UNIFIED_V8 RESULT":
                r = _result(parts)
                q = queues[_key(r)]
                c = q.popleft() if q else None
                if c is None:
                    unmatched_results += 1
                else:
                    for f in ("btc5", "btc15", "btc30", "accel", "brti5", "brti15", "left"):
                        r[f] = c[f]
                r["hit10"] = r["t10"] is not None
                rows.append(r)
        except (ValueError, IndexError):
            bad_lines += 1
    unmatched_candidates = sum(len(q) for q in queues.values())
    return rows, unmatched_candidates, unmatched_results, bad_lines


def pct(a, b):
    return 0.0 if not b else 100.0 * a / b


def cluster(row):
    return (row["ticker"], row["side"])


def screen_feature(rows, feature, threshold):
    paired = [r for r in rows if feature in r]
    removed = [r for r in paired if r[feature] < threshold]
    wins_removed = [r for r in removed if r["hit10"]]
    failures_removed = [r for r in removed if not r["hit10"]]
    winner_clusters = {cluster(r) for r in paired if r["hit10"]}
    failure_clusters_removed = {cluster(r) for r in failures_removed}
    failure_zones_removed = {r["zone"] for r in failures_removed}

    if wins_removed:
        decision = "REJECT"
    elif (
        len(winner_clusters) >= MIN_WINNER_CLUSTERS_FOR_WATCH
        and len(failure_clusters_removed) >= MIN_FAILURE_CLUSTERS_REMOVED_FOR_WATCH
        and len(failures_removed) >= MIN_FAILURES_REMOVED_FOR_WATCH
        and len(failure_zones_removed) >= MIN_FAILURE_ZONES_FOR_WATCH
    ):
        decision = "MORE_DATA_WATCH"
    else:
        decision = "MORE_DATA"

    return {
        "feature": feature,
        "threshold": threshold,
        "decision": decision,
        "wins_removed": len(wins_removed),
        "winner_clusters": len(winner_clusters),
        "failures_removed": len(failures_removed),
        "failure_clusters_removed": len(failure_clusters_removed),
        "failure_zones_removed": len(failure_zones_removed),
    }


def summarize(rows):
    out = []
    wins = sum(r["hit10"] for r in rows)
    clusters = {cluster(r) for r in rows}
    winner_clusters = {cluster(r) for r in rows if r["hit10"]}
    failure_clusters = {cluster(r) for r in rows if not r["hit10"]}
    out.append(
        "SAMPLE n=%d hit10=%d/%d (%.1f%%) contract_side_clusters=%d "
        "winner_clusters=%d failure_clusters=%d"
        % (
            len(rows),
            wins,
            len(rows),
            pct(wins, len(rows)),
            len(clusters),
            len(winner_clusters),
            len(failure_clusters),
        )
    )
    out.append(
        "POLICY PRICE_ONLY=REJECT OUTCOME_LOOKAHEAD_QUALIFICATION=REJECT "
        "ULTRA_CHEAP_SEPARATE_LANE=REJECT"
    )

    setup_counts = defaultdict(lambda: [0, 0])
    for r in rows:
        setup_counts[r["setup"]][0] += 1
        setup_counts[r["setup"]][1] += int(r["hit10"])
    for setup in sorted(setup_counts):
        n, w = setup_counts[setup]
        out.append("SETUP %s n=%d hit10=%d/%d (%.1f%%)" % (setup, n, w, n, pct(w, n)))
    if setup_counts.get("SURGE", [0, 0])[0] == 0:
        out.append("SETUP SURGE decision=MORE_DATA reason=no_completed_results")

    watch = []
    for feature, thresholds in GRIDS.items():
        best = None
        for threshold in thresholds:
            s = screen_feature(rows, feature, threshold)
            if s["decision"] == "MORE_DATA_WATCH":
                if (
                    best is None
                    or s["failure_clusters_removed"] > best["failure_clusters_removed"]
                    or (
                        s["failure_clusters_removed"] == best["failure_clusters_removed"]
                        and s["failures_removed"] > best["failures_removed"]
                    )
                ):
                    best = s
        if best:
            watch.append(best)
            out.append(
                "WATCH %s>=%.2f decision=MORE_DATA failures_removed=%d "
                "failure_clusters=%d failure_zones=%d winner_clusters=%d wins_removed=0"
                % (
                    best["feature"],
                    best["threshold"],
                    best["failures_removed"],
                    best["failure_clusters_removed"],
                    best["failure_zones_removed"],
                    best["winner_clusters"],
                )
            )

    if not watch:
        out.append("TIGHTENING decision=MORE_DATA reason=no_price_neutral_zero-winner-loss_candidate")
    else:
        out.append(
            "TIGHTENING decision=MORE_DATA reason=watch_candidates_need_future_contract_validation"
        )
    return out


def self_test():
    sample = [
        "UNIFIED_V8 CANDIDATE | A | UP | zone UNIFIED_VALUE_15_30C | setup CORE | ask 0.200 | quality 1.30 | btc5 +30.00 | btc15 +35.00 | btc30 +20.00 | accel +15.00 | brti5 +30.00 | brti15 +30.00 | left 500s",
        "UNIFIED_V8 RESULT | A | UP | zone UNIFIED_VALUE_15_30C | setup CORE | style BURST | entry 0.200 | quality 1.30 | max_gain +0.150 | adverse -0.010 | pre10_adverse -0.010 | to+5c 5.0 | to+10c 10.0 | to+20c None",
        "UNIFIED_V8 CANDIDATE | B | DOWN | zone UNIFIED_CHEAP_7_15C | setup CORE | ask 0.080 | quality 1.00 | btc5 +21.00 | btc15 +25.00 | btc30 +4.00 | accel +10.50 | brti5 +19.00 | brti15 +24.00 | left 400s",
        "UNIFIED_V8 RESULT | B | DOWN | zone UNIFIED_CHEAP_7_15C | setup CORE | style NO_EXPANSION | entry 0.080 | quality 1.00 | max_gain +0.020 | adverse -0.070 | pre10_adverse -0.070 | to+5c None | to+10c None | to+20c None",
    ]
    rows, uc, ur, bad = parse(sample)
    assert len(rows) == 2 and uc == 0 and ur == 0 and bad == 0
    s = screen_feature(rows, "brti5", 20.0)
    assert s["wins_removed"] == 0 and s["failures_removed"] == 1
    s2 = screen_feature(rows, "quality", 1.40)
    assert s2["decision"] == "REJECT" and s2["wins_removed"] == 1
    text = "\n".join(summarize(rows))
    assert "PRICE_ONLY=REJECT" in text
    assert "SURGE decision=MORE_DATA" in text
    print("SELF_TEST PASS")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="Railway log text file; stdin if omitted")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return

    lines = open(args.path, encoding="utf-8", errors="replace") if args.path else sys.stdin
    rows, uc, ur, bad = parse(lines)
    for line in summarize(rows):
        print(line)
    print("PAIRING unmatched_candidates=%d unmatched_results=%d bad_lines=%d" % (uc, ur, bad))
    if ur or bad:
        print("DECISION MORE_DATA reason=incomplete_or_unparseable_evidence")
    else:
        print("DECISION KEEP_RESEARCH_ONLY reason=no_live_gate_change")


if __name__ == "__main__":
    main()
