#!/usr/bin/env python3
"""Read-only checkpoint auditor for BTC15 V5/V6 research tests.

This utility NEVER imports/runs the collectors, never calls Kalshi, and never
places orders. It verifies the frozen source identity/constants and summarizes
saved Railway log exports so a forward-test checkpoint can be judged quickly.

Examples:
  python research_tools/btc15_checkpoint_audit_v1.py
  python research_tools/btc15_checkpoint_audit_v1.py v5.log v6.log
  python research_tools/btc15_checkpoint_audit_v1.py railway*.log --out checkpoint_2000
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

DEFAULT_LOCK = Path(__file__).with_name("v6_forward_test_lock_v1.json")
ISO_TS = re.compile(r"(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2}))")
CANDIDATE = re.compile(
    r"LEAD_V(?P<ver>5|6) CANDIDATE \| (?P<grade>[^|]+?) \| (?P<ticker>[^|]+?) \| "
    r"(?P<side>UP|DOWN) \|(?: zone (?P<zone>[^|]+?) \|)? ask (?P<entry>[-+0-9.]+)"
)
RESULT = re.compile(
    r"LEAD_V(?P<ver>5|6) RESULT \| (?P<grade>[^|]+?) \| (?P<ticker>[^|]+?) \| "
    r"(?P<side>UP|DOWN) \| entry (?P<entry>[-+0-9.]+) \| max_exec_gain (?P<gain>[-+0-9.]+) "
    r"\| adverse (?P<adverse>[-+0-9.]+) \| hit10 (?P<hit10>True|False) "
    r"\| to_exec\+5c (?P<t5>[^ |]+) \| to_exec\+10c (?P<t10>[^ |]+) \| kalshi_reprice\+5c (?P<repr>[^ |]+)"
)
HEARTBEAT = re.compile(
    r"LEAD_V(?P<ver>5|6) HEARTBEAT \| (?P<ticker>[^|]+?) \| .*? BRTI (?P<brti>[^ |]+)"
)
WARNING = re.compile(r"LEAD_V(?P<ver>5|6) WARNING \| (?P<kind>[^:|]+):? ?(?P<msg>.*)")


def git_blob_sha(data: bytes) -> str:
    """Compute the same SHA-1 identity Git uses for a blob."""
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def parse_literal_constants(path: Path) -> dict[str, Any]:
    """Read uppercase literal assignments with AST; never execute source."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not target.id.isupper():
            continue
        try:
            out[target.id] = ast.literal_eval(node.value)
        except Exception:
            pass
    return out


def fnum(x: str | None) -> float | None:
    if x in (None, "None", "N/A", "nan", "NaN"):
        return None
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except Exception:
        return None


def parse_ts(line: str) -> float | None:
    m = ISO_TS.search(line)
    if not m:
        return None
    try:
        return datetime.fromisoformat(m.group("ts").replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def median(values: Iterable[float | None]) -> float | None:
    xs = [float(x) for x in values if x is not None and math.isfinite(float(x))]
    return round(statistics.median(xs), 3) if xs else None


def mean(values: Iterable[float | None]) -> float | None:
    xs = [float(x) for x in values if x is not None and math.isfinite(float(x))]
    return round(statistics.fmean(xs), 3) if xs else None


def pct(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 2) if d else None


def audit_lock(root: Path, lock_path: Path) -> dict[str, Any]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    checks = []
    ok = True
    for item in lock.get("collectors", []):
        p = root / item["path"]
        row = {"path": item["path"], "exists": p.exists(), "expected_blob": item["github_blob_sha"]}
        if p.exists():
            actual = git_blob_sha(p.read_bytes())
            row["actual_blob"] = actual
            row["match"] = actual == item["github_blob_sha"]
        else:
            row["actual_blob"] = None
            row["match"] = False
        ok = ok and bool(row["match"])
        checks.append(row)

    v6_path = root / "scalp_lead_shadow_v6.py"
    const_rows = []
    if v6_path.exists():
        actual_constants = parse_literal_constants(v6_path)
        for name, expected in lock.get("v6_frozen_constants", {}).items():
            actual = actual_constants.get(name)
            match = actual == expected
            const_rows.append({"name": name, "expected": expected, "actual": actual, "match": match})
            ok = ok and match
    else:
        ok = False

    return {
        "lock_name": lock.get("lock_name"),
        "base_main_commit": lock.get("base_main_commit"),
        "source_identity_ok": ok,
        "collector_checks": checks,
        "constant_checks": const_rows,
    }


def read_lines(paths: list[Path]) -> Iterable[tuple[Path, str]]:
    for p in paths:
        try:
            with p.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    yield p, line.rstrip("\n")
        except OSError:
            continue


def audit_logs(paths: list[Path]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    heartbeats: list[dict[str, Any]] = []
    source_counts = Counter()

    for path, line in read_lines(paths):
        source_counts[str(path)] += 1
        ts = parse_ts(line)
        m = CANDIDATE.search(line)
        if m:
            d = m.groupdict(); d["entry"] = fnum(d["entry"]); d["ts"] = ts; d["source"] = str(path)
            candidates.append(d); continue
        m = RESULT.search(line)
        if m:
            d = m.groupdict()
            for k in ("entry", "gain", "adverse", "t5", "t10", "repr"):
                d[k] = fnum(d[k])
            d["hit10"] = d["hit10"] == "True"; d["ts"] = ts; d["source"] = str(path)
            results.append(d); continue
        m = HEARTBEAT.search(line)
        if m:
            d = m.groupdict(); d["ts"] = ts; d["source"] = str(path)
            heartbeats.append(d); continue
        m = WARNING.search(line)
        if m:
            d = m.groupdict(); d["ts"] = ts; d["source"] = str(path)
            warnings.append(d)

    by_grade: dict[str, Any] = {}
    grades = sorted({(x["ver"], x["grade"].strip()) for x in candidates + results})
    for ver, grade in grades:
        cs = [x for x in candidates if x["ver"] == ver and x["grade"].strip() == grade]
        rs = [x for x in results if x["ver"] == ver and x["grade"].strip() == grade]
        hit5 = sum(x["t5"] is not None for x in rs)
        hit10 = sum(bool(x["hit10"]) for x in rs)
        repr5 = sum(x["repr"] is not None for x in rs)
        key = f"V{ver}:{grade}"
        by_grade[key] = {
            "candidates": len(cs),
            "resolved_results": len(rs),
            "resolution_ratio_pct": pct(len(rs), len(cs)),
            "exec_plus_5c_hit_pct": pct(hit5, len(rs)),
            "exec_plus_10c_hit_pct": pct(hit10, len(rs)),
            "ask_plus_5c_reprice_pct": pct(repr5, len(rs)),
            "avg_max_exec_gain": mean(x["gain"] for x in rs),
            "avg_adverse": mean(x["adverse"] for x in rs),
            "median_to_exec_plus_5c_sec": median(x["t5"] for x in rs),
            "median_to_exec_plus_10c_sec": median(x["t10"] for x in rs),
            "median_signal_lead_to_ask_plus_5c_sec": median(x["repr"] for x in rs),
            "preferred_zone_candidates": sum((x.get("zone") or "").strip() == "PREFERRED_7_30C" for x in cs),
            "high_price_strong_candidates": sum((x.get("zone") or "").strip() == "HIGH_PRICE_STRONG" for x in cs),
        }

    hb_by_ver: dict[str, Any] = {}
    for ver in sorted({x["ver"] for x in heartbeats}):
        hs = [x for x in heartbeats if x["ver"] == ver]
        brti_na = sum(str(x["brti"]).upper() == "N/A" for x in hs)
        ts = sorted(x["ts"] for x in hs if x["ts"] is not None)
        gaps = [b - a for a, b in zip(ts, ts[1:]) if b >= a]
        hb_by_ver[f"V{ver}"] = {
            "heartbeats": len(hs),
            "brti_na_count": brti_na,
            "brti_na_pct": pct(brti_na, len(hs)),
            "timestamped_heartbeats": len(ts),
            "max_heartbeat_gap_sec": round(max(gaps), 2) if gaps else None,
            "gaps_over_75s": sum(g > 75 for g in gaps),
        }

    return {
        "files": [{"path": p, "lines": n} for p, n in sorted(source_counts.items())],
        "totals": {
            "candidates": len(candidates),
            "results": len(results),
            "heartbeats": len(heartbeats),
            "warnings": len(warnings),
        },
        "by_grade": by_grade,
        "heartbeat_health": hb_by_ver,
        "warning_types": dict(Counter(f"V{x['ver']}:{x['kind'].strip()}" for x in warnings)),
        "notes": [
            "Resolution ratio can be below 100% if the exported log ends before the 90-second result horizon.",
            "Heartbeat gap checks require Railway timestamps to be present in the exported text.",
            "Signal lead to ask +5c is measured from candidate emission to the collector's observed +5c ask repricing.",
        ],
    }


def render_text(report: dict[str, Any]) -> str:
    lines = ["BTC15 V5/V6 RESEARCH CHECKPOINT", "=" * 34]
    lk = report["lock"]
    lines.append(f"SOURCE LOCK: {'PASS' if lk['source_identity_ok'] else 'FAIL'}")
    for x in lk["collector_checks"]:
        lines.append(f"  {x['path']}: {'MATCH' if x['match'] else 'DRIFT/MISSING'}")
    bad_const = [x["name"] for x in lk["constant_checks"] if not x["match"]]
    lines.append("  V6 frozen constants: " + ("MATCH" if not bad_const else "DRIFT " + ",".join(bad_const)))

    lg = report["logs"]
    lines.append("")
    lines.append("LOG COVERAGE")
    lines.append(f"  candidates={lg['totals']['candidates']} results={lg['totals']['results']} heartbeats={lg['totals']['heartbeats']} warnings={lg['totals']['warnings']}")
    if not lg["files"]:
        lines.append("  No log files supplied; source-lock verification completed only.")
    for key, x in lg["by_grade"].items():
        lines.append(
            f"  {key}: n={x['resolved_results']}/{x['candidates']} "
            f"+5c={x['exec_plus_5c_hit_pct']}% +10c={x['exec_plus_10c_hit_pct']}% "
            f"avg_gain={x['avg_max_exec_gain']} avg_adverse={x['avg_adverse']} "
            f"median_reprice_lead={x['median_signal_lead_to_ask_plus_5c_sec']}s"
        )
    for key, x in lg["heartbeat_health"].items():
        lines.append(
            f"  {key} health: heartbeats={x['heartbeats']} BRTI_NA={x['brti_na_pct']}% "
            f"max_gap={x['max_heartbeat_gap_sec']}s gaps>75s={x['gaps_over_75s']}"
        )
    if lg["warning_types"]:
        lines.append("  warnings: " + json.dumps(lg["warning_types"], sort_keys=True))
    lines.append("")
    lines.append("READ-ONLY: no collector imported/executed; no network calls; no orders; no thresholds changed.")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("logs", nargs="*", help="Saved Railway text log exports to summarize")
    ap.add_argument("--root", default=".", help="Repository root (default: current directory)")
    ap.add_argument("--lock", default=str(DEFAULT_LOCK), help="Forward-test lock manifest")
    ap.add_argument("--out", default="btc15_checkpoint", help="Output basename")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    lock_path = Path(args.lock)
    if not lock_path.is_absolute():
        lock_path = (Path.cwd() / lock_path).resolve()
    paths = [Path(x).resolve() for x in args.logs if Path(x).is_file()]

    report = {
        "analysis_only": True,
        "production_modified": False,
        "lock": audit_lock(root, lock_path),
        "logs": audit_logs(paths),
    }
    out = Path(args.out)
    out.with_suffix(".json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out.with_suffix(".txt").write_text(render_text(report), encoding="utf-8")
    print(render_text(report), end="")
    print(f"WROTE {out.with_suffix('.txt')} and {out.with_suffix('.json')}")
    return 0 if report["lock"]["source_identity_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
