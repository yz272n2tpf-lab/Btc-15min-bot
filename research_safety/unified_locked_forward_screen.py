#!/usr/bin/env python3
"""Research-only locked forward validator for unified 3c-45c gate candidates.

A rule is chosen *before* the forward window. This utility then evaluates only
later independent contract-side clusters so candidate thresholds cannot move as
new evidence arrives. Qualification features must be entry-time and
price-neutral. Entry price/zone and outcome-lookahead fields are forbidden.

Signal-only research utility. NO ORDERS. Does not change the live gate.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_safety.unified_gate_tighten_screen import cluster, parse  # noqa:E402

ALLOWED_FEATURES = {
    "quality",
    "btc5",
    "btc15",
    "btc30",
    "accel",
    "brti5",
    "brti15",
    "left",
}
FORBIDDEN_FEATURES = {
    "entry",
    "zone",
    "gain",
    "adverse",
    "pre10",
    "t5",
    "t10",
    "t20",
    "hit10",
    "style",
}
MIN_FORWARD_WINNER_CLUSTERS = 5
MIN_FAILURE_CLUSTERS_REMOVED = 3
MIN_FAILURES_REMOVED = 3
MIN_FAILURE_ZONES_REMOVED = 2


def parse_rule(text):
    """Parse comma-separated lower floors, e.g. btc5>=23,brti15>=25."""
    conds = []
    for raw in (x.strip() for x in text.split(",")):
        if not raw:
            continue
        m = re.fullmatch(r"([A-Za-z0-9_]+)\s*>=\s*(-?\d+(?:\.\d+)?)", raw)
        if not m:
            raise ValueError("bad rule term %r; expected feature>=number" % raw)
        feature = m.group(1)
        threshold = float(m.group(2))
        if feature in FORBIDDEN_FEATURES or feature not in ALLOWED_FEATURES:
            raise ValueError("feature %r is not allowed for qualification research" % feature)
        conds.append((feature, threshold))
    if not conds:
        raise ValueError("empty rule")
    if len({f for f, _ in conds}) != len(conds):
        raise ValueError("duplicate feature in rule")
    return tuple(conds)


def ordered_clusters(rows):
    seen = set()
    out = []
    for row in rows:
        key = cluster(row)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def forward_rows(rows, skip_clusters):
    keys = ordered_clusters(rows)
    if skip_clusters < 0:
        raise ValueError("skip-clusters must be >= 0")
    kept = set(keys[skip_clusters:])
    return [r for r in rows if cluster(r) in kept], keys


def passes(row, conds):
    return all(float(row[f]) >= threshold for f, threshold in conds)


def evaluate(rows, conds):
    eligible = [r for r in rows if all(f in r for f, _ in conds)]
    removed = [r for r in eligible if not passes(r, conds)]
    wins_removed = [r for r in removed if r["hit10"]]
    failures_removed = [r for r in removed if not r["hit10"]]
    winner_clusters = {cluster(r) for r in eligible if r["hit10"]}
    failure_clusters_removed = {cluster(r) for r in failures_removed}
    failure_zones_removed = {r["zone"] for r in failures_removed}

    if wins_removed:
        decision = "REJECT"
    elif (
        len(winner_clusters) >= MIN_FORWARD_WINNER_CLUSTERS
        and len(failure_clusters_removed) >= MIN_FAILURE_CLUSTERS_REMOVED
        and len(failures_removed) >= MIN_FAILURES_REMOVED
        and len(failure_zones_removed) >= MIN_FAILURE_ZONES_REMOVED
    ):
        decision = "TIGHTEN"
    else:
        decision = "MORE_DATA"

    return {
        "decision": decision,
        "n": len(eligible),
        "winner_clusters": len(winner_clusters),
        "wins_removed": wins_removed,
        "failures_removed": len(failures_removed),
        "failure_clusters_removed": len(failure_clusters_removed),
        "failure_zones_removed": len(failure_zones_removed),
    }


def rule_text(conds):
    return " AND ".join("%s>=%.2f" % (f, threshold) for f, threshold in conds)


def counterexample_text(row, conds):
    failed = ["%s=%.2f<%.2f" % (f, float(row[f]), threshold)
              for f, threshold in conds if float(row[f]) < threshold]
    return (
        "WINNER_COUNTEREXAMPLE ticker=%s side=%s zone=%s entry=%.3f "
        "quality=%.2f failed=%s"
        % (
            row["ticker"],
            row["side"],
            row["zone"],
            row["entry"],
            row["quality"],
            ",".join(failed),
        )
    )


def analyze(rows, conds, skip_clusters):
    forward, keys = forward_rows(rows, skip_clusters)
    stats = evaluate(forward, conds)
    out = [
        "POLICY PRICE_ONLY=REJECT OUTCOME_LOOKAHEAD_QUALIFICATION=REJECT "
        "ULTRA_CHEAP_SEPARATE_LANE=REJECT LIVE_GATE_CHANGE=NO",
        "LOCKED_RULE %s" % rule_text(conds),
        "FORWARD_WINDOW total_clusters=%d skipped_clusters=%d forward_clusters=%d n=%d"
        % (len(keys), min(skip_clusters, len(keys)), max(0, len(keys) - skip_clusters), stats["n"]),
        "FORWARD_SCORE decision=%s winner_clusters=%d wins_removed=%d "
        "failures_removed=%d failure_clusters_removed=%d failure_zones_removed=%d"
        % (
            stats["decision"],
            stats["winner_clusters"],
            len(stats["wins_removed"]),
            stats["failures_removed"],
            stats["failure_clusters_removed"],
            stats["failure_zones_removed"],
        ),
    ]
    for row in stats["wins_removed"]:
        out.append(counterexample_text(row, conds))
    return out


def self_test():
    rows = [
        {"ticker": "A", "side": "UP", "zone": "UNIFIED_VALUE_15_30C", "entry": .20,
         "quality": 1.2, "btc5": 30., "brti15": 30., "hit10": True},
        {"ticker": "B", "side": "DOWN", "zone": "UNIFIED_HIGH_30_45C", "entry": .34,
         "quality": 1.1, "btc5": 22., "brti15": 30., "hit10": False},
        {"ticker": "C", "side": "UP", "zone": "UNIFIED_CHEAP_7_15C", "entry": .08,
         "quality": 1.3, "btc5": 30., "brti15": 24., "hit10": False},
        {"ticker": "D", "side": "DOWN", "zone": "UNIFIED_VALUE_15_30C", "entry": .24,
         "quality": 1.4, "btc5": 30., "brti15": 30., "hit10": True},
        {"ticker": "E", "side": "UP", "zone": "UNIFIED_HIGH_30_45C", "entry": .32,
         "quality": 1.5, "btc5": 32., "brti15": 32., "hit10": True},
        {"ticker": "F", "side": "DOWN", "zone": "UNIFIED_CHEAP_7_15C", "entry": .12,
         "quality": 1.6, "btc5": 31., "brti15": 31., "hit10": True},
        {"ticker": "G", "side": "UP", "zone": "UNIFIED_VALUE_15_30C", "entry": .19,
         "quality": 1.7, "btc5": 35., "brti15": 35., "hit10": True},
        {"ticker": "H", "side": "DOWN", "zone": "UNIFIED_HIGH_30_45C", "entry": .34,
         "quality": 1.05, "btc5": 25., "brti15": 19., "hit10": True},
    ]
    conds = parse_rule("btc5>=23,brti15>=25")
    s = evaluate(rows, conds)
    assert s["decision"] == "REJECT"
    assert len(s["wins_removed"]) == 1
    assert s["wins_removed"][0]["ticker"] == "H"
    assert "brti15=19.00<25.00" in counterexample_text(s["wins_removed"][0], conds)
    try:
        parse_rule("entry>=.10")
    except ValueError:
        pass
    else:
        raise AssertionError("entry price must be forbidden")
    print("SELF_TEST PASS")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="Railway log text file; stdin if omitted")
    ap.add_argument("--rule", required=False, help="locked floors, e.g. btc5>=23,brti15>=25")
    ap.add_argument("--skip-clusters", type=int, default=0,
                    help="number of earliest contract-side clusters excluded as discovery")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return
    if not args.rule:
        ap.error("--rule is required unless --self-test is used")

    conds = parse_rule(args.rule)
    lines = open(args.path, encoding="utf-8", errors="replace") if args.path else sys.stdin
    rows, unmatched_candidates, unmatched_results, bad_lines = parse(lines)
    for line in analyze(rows, conds, args.skip_clusters):
        print(line)
    print(
        "PAIRING unmatched_candidates=%d unmatched_results=%d bad_lines=%d"
        % (unmatched_candidates, unmatched_results, bad_lines)
    )
    if unmatched_results or bad_lines:
        print("DECISION MORE_DATA reason=incomplete_or_unparseable_evidence")


if __name__ == "__main__":
    main()
