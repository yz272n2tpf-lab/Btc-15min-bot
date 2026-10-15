"""Offline bounded throughput benchmark. Never accesses live Railway data."""
import argparse
import csv
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time

from btc15_cohort_closeout_incremental_research_v1 import IncrementalCloseout, COHORT_SCHEMA
from test_btc15_cohort_closeout_incremental_research_v1 import FIELDS, parity_row


def fixture(root, parity_n, cohort_n):
    parity = root / "benchmark_parity.csv"
    cohort = root / "benchmark_cohort.jsonl"
    with parity.open("w", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS)
        writer.writeheader()
        for i in range(parity_n):
            writer.writerow(parity_row("UNQUALIFIED"+str(i%100),
                                    timestamp_utc="2026-10-15T13:40:00Z",
                                    final60_count="59"))
    with cohort.open("w") as fp:
        for i in range(cohort_n):
            fp.write(json.dumps(dict(schema=COHORT_SCHEMA, final_status="PASS",
                                     contract="HISTORY"+str(i), seconds_left=840,
                                     signal_only=True, orders=False)) + "\n")
    return parity, cohort


def legacy(parity, cohort, polls):
    found = 0
    for _ in range(polls):
        with parity.open(newline="") as src:
            rows = list(csv.DictReader(src))
        persisted = set()
        with cohort.open() as src:
            for line in src:
                try: prior = json.loads(line)
                except Exception: continue
                if prior.get("schema") == COHORT_SCHEMA and prior.get("final_status") == "CLOSEOUT_ONLY":
                    persisted.add(prior.get("contract"))
        for row in rows:
            if (row.get("contract") and row["contract"] not in persisted
                    and str(row.get("final60_complete", "")).lower() in ("true", "1")
                    and int(float(row.get("final60_count") or 0)) == 60
                    and row.get("final60_average") not in (None, "")
                    and row.get("final60_side") in ("UP", "DOWN")
                    and row.get("target") not in (None, "")):
                found += 1
    return found


def incremental(parity, cohort, polls):
    found = []
    engine = IncrementalCloseout(parity, cohort, lambda t, v: found.append(t))
    for _ in range(polls):
        engine.poll_once()
    return len(found), engine.stats()


def main():
    a=argparse.ArgumentParser();a.add_argument("--mode", choices=["baseline","incremental"],required=True)
    a.add_argument("--parity-rows", type=int, default=70000)
    a.add_argument("--cohort-rows", type=int, default=70000)
    a.add_argument("--polls", type=int, default=12)
    args=a.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        parity,cohort=fixture(root,args.parity_rows,args.cohort_rows)
        sizes={"parity_bytes":parity.stat().st_size,"cohort_bytes":cohort.stat().st_size}
        before_wall=time.perf_counter();before_cpu=time.process_time()
        if args.mode=="baseline":
            found=legacy(parity,cohort,args.polls)
            bytes_read=args.polls*sum(sizes.values())
        else:
            found,stats=incremental(parity,cohort,args.polls)
            bytes_read=stats["parity_bytes_read"]+stats["cohort_bytes_read"]+stats["audit_bytes_read"]
        result=dict(mode=args.mode, polls=args.polls, parity_rows=args.parity_rows,
                    cohort_rows=args.cohort_rows, **sizes, bytes_read=bytes_read,
                    cpu_s=round(time.process_time()-before_cpu,4),
                    wall_s=round(time.perf_counter()-before_wall,4),
                    maxrss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    found=found, orders=False)
        print(json.dumps(result,sort_keys=True))

if __name__ == "__main__": main()
