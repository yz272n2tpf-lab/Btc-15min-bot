#!/usr/bin/env python3
"""Research-only audit for UNIFIED_V8 Railway shadow logs.

Consumes log text containing UNIFIED_V8 CANDIDATE / RESULT lines.
It never changes qualification or trading behavior. It reports raw +10c rates,
contract-side clustering, adverse-path candidate cutoffs, and feature-floor
screens that preserve all observed +10c winners.

Signal-only research utility. NO ORDERS.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict, deque

FEATURES = ("quality", "btc5", "btc15", "btc30", "accel", "brti5", "brti15")


def _num(text):
    return float(text)


def _maybe(text):
    return None if text == "None" else float(text)


def _parts(line):
    if "UNIFIED_V8 " not in line:
        return None, []
    body = line[line.index("UNIFIED_V8 "):].strip()
    parts = [p.strip() for p in body.split(" | ")]
    return parts[0], parts


def _pref(part, prefix):
    if not part.startswith(prefix):
        raise ValueError("expected %r in %r" % (prefix, part))
    return part[len(prefix):].strip()


def _candidate_full(parts):
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
                c = _candidate_full(parts)
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


def summarize(rows):
    out = []
    n = len(rows)
    wins = sum(r["hit10"] for r in rows)
    out.append("RAW n=%d hit10=%d/%d (%.1f%%)" % (n, wins, n, pct(wins, n)))

    for field in ("zone", "setup"):
        buckets = defaultdict(list)
        for r in rows:
            buckets[r[field]].append(r)
        for name in sorted(buckets):
            b = buckets[name]
            w = sum(x["hit10"] for x in b)
            out.append("%s %s n=%d hit10=%d/%d (%.1f%%)" %
                       (field.upper(), name, len(b), w, len(b), pct(w, len(b))))

    clusters = defaultdict(list)
    for r in rows:
        clusters[(r["ticker"], r["side"])].append(r)
    anywin = sum(any(x["hit10"] for x in b) for b in clusters.values())
    mixed = sum(any(x["hit10"] for x in b) and not all(x["hit10"] for x in b)
                for b in clusters.values())
    max_cluster = max([len(b) for b in clusters.values()] or [0])
    out.append("INDEPENDENCE contract_side_clusters=%d any_hit10=%d/%d (%.1f%%) mixed=%d max_signals_per_cluster=%d" %
               (len(clusters), anywin, len(clusters), pct(anywin, len(clusters)), mixed, max_cluster))

    for cut in (-0.01, -0.03, -0.05, -0.10):
        kept = [r for r in rows if r["pre10"] >= cut]
        kw = sum(r["hit10"] for r in kept)
        failures_removed = (n - wins) - (len(kept) - kw)
        out.append("ADVERSE_CANDIDATE pre10>=%+.2f keeps=%d/%d wins_kept=%d/%d failures_removed=%d" %
                   (cut, len(kept), n, kw, wins, failures_removed))

    paired = [r for r in rows if all(f in r for f in FEATURES)]
    wins_p = [r for r in paired if r["hit10"]]
    if wins_p:
        for f in FEATURES:
            floor = min(r[f] for r in wins_p)
            fail_removed = sum((not r["hit10"]) and r[f] < floor for r in paired)
            out.append("FEATURE_CANDIDATE %s>=%.2f preserves_observed_winners=%d/%d failures_removed=%d" %
                       (f, floor, len(wins_p), len(wins_p), fail_removed))
    return out


def self_test():
    sample = [
        "UNIFIED_V8 CANDIDATE | T1 | UP | zone UNIFIED_VALUE_15_30C | setup CORE | ask 0.250 | quality 1.20 | btc5 +30.00 | btc15 +35.00 | btc30 +40.00 | accel +15.00 | brti5 +30.00 | brti15 +25.00 | left 500s",
        "UNIFIED_V8 RESULT | T1 | UP | zone UNIFIED_VALUE_15_30C | setup CORE | style BURST | entry 0.250 | quality 1.20 | max_gain +0.150 | adverse -0.010 | pre10_adverse -0.010 | to+5c 5.0 | to+10c 10.0 | to+20c None",
        "UNIFIED_V8 CANDIDATE | T2 | DOWN | zone UNIFIED_CHEAP_7_15C | setup CORE | ask 0.080 | quality 1.00 | btc5 +20.00 | btc15 +25.00 | btc30 +10.00 | accel +10.00 | brti5 +15.00 | brti15 +5.00 | left 400s",
        "UNIFIED_V8 RESULT | T2 | DOWN | zone UNIFIED_CHEAP_7_15C | setup CORE | style NO_EXPANSION | entry 0.080 | quality 1.00 | max_gain +0.020 | adverse -0.070 | pre10_adverse -0.070 | to+5c None | to+10c None | to+20c None",
    ]
    rows, uc, ur, bad = parse(sample)
    assert len(rows) == 2 and uc == 0 and ur == 0 and bad == 0
    assert rows[0]["hit10"] and not rows[1]["hit10"]
    text = "\n".join(summarize(rows))
    assert "RAW n=2 hit10=1/2 (50.0%)" in text
    assert "contract_side_clusters=2" in text
    assert "FEATURE_CANDIDATE quality>=1.20" in text
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
    elif not rows:
        print("DECISION MORE_DATA reason=no_results")
    else:
        print("DECISION KEEP_RESEARCH_ONLY reason=diagnostic_audit_no_live_gate_change")


if __name__ == "__main__":
    main()
