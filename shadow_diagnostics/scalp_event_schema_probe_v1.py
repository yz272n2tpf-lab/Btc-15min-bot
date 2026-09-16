#!/usr/bin/env python3
"""BTC15 scalp event-tape schema probe V1.

RESEARCH ONLY | READ ONLY | NO ORDERS

Reports field names and non-empty field availability by record type so research
models can adapt to the actual historical/export tape without inventing values.
No row values are emitted.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping

VERSION = "BTC15_SCALP_EVENT_SCHEMA_PROBE_V1"
RECORD_TYPES = ("CANDIDATE", "PATH", "RESULT", "SNAPSHOT")


def present(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    return True


def record_type(row: Mapping[str, Any]) -> str:
    return str(row.get("record_type") or "").strip().upper()


def schema_probe(rows: Iterable[Mapping[str, Any]], desired_features: Iterable[str] = ()) -> dict[str, Any]:
    rows = list(rows)
    columns = sorted({str(k) for r in rows for k in r.keys()})
    counts = Counter(record_type(r) or "UNKNOWN" for r in rows)

    nonempty: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        typ = record_type(r) or "UNKNOWN"
        for k, v in r.items():
            if present(v):
                nonempty[typ].add(str(k))

    by_type = {
        typ: {
            "rows": int(counts.get(typ, 0)),
            "nonempty_columns": sorted(nonempty.get(typ, set())),
        }
        for typ in sorted(set(counts) | set(RECORD_TYPES))
    }

    desired = {}
    candidate_nonempty = nonempty.get("CANDIDATE", set())
    for feature in desired_features:
        name = str(feature)
        desired[name] = {
            "column_exists": name in columns,
            "nonempty_any": any(name in s for s in nonempty.values()),
            "nonempty_candidate": name in candidate_nonempty,
        }

    return {
        "version": VERSION,
        "orders": False,
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": columns,
        "record_counts": dict(sorted(counts.items())),
        "by_record_type": by_type,
        "desired_feature_presence": desired,
    }
