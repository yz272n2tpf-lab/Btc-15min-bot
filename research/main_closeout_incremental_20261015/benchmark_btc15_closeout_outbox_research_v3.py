"""Synthetic-only CPU benchmark: one-time historical cutover vs ongoing append work.

No production files, live network, orders or deployment. Only the V3 isolated
outbox/test-double journal is written in a temporary directory.
"""
import argparse
import json
from pathlib import Path
import resource
import tempfile
import time

from benchmark_btc15_closeout_incremental_research_v1 import fixture
from btc15_closeout_outbox_research_v3 import ResearchJournalV3, ResearchOutboxV3
from test_btc15_cohort_closeout_incremental_research_v1 import parity_row, FIELDS
import csv


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--parity-rows',type=int,default=70000)
    parser.add_argument('--cohort-rows',type=int,default=70000)
    parser.add_argument('--polls',type=int,default=12)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        parity,cohort=fixture(root,args.parity_rows,args.cohort_rows)
        sizes=dict(parity_bytes=parity.stat().st_size,legacy_cohort_bytes=cohort.stat().st_size)
        journal=ResearchJournalV3(root/'journal.sqlite3',deployment='fixture',build='fixture',revision='fixture')
        journal.init_fixture()
        engine=ResearchOutboxV3(parity,root/'outbox.sqlite3',journal)
        t=time.process_time();w=time.perf_counter()
        engine.explicit_cutover()
        cutover_cpu=time.process_time()-t
        cutover_wall=time.perf_counter()-w
        t=time.process_time();w=time.perf_counter()
        completed=[]
        for i in range(args.polls):
            if i==1:
                with parity.open('a',newline='') as source:
                    writer=csv.DictWriter(source,fieldnames=FIELDS)
                    writer.writerow(parity_row('POST_CUTOVER_A'))
                    writer.writerow(parity_row('POST_CUTOVER_B',final60_side='DOWN'))
                    writer.writerow(parity_row('NON_ELIGIBLE',final60_count='59'))
            completed+=engine.poll_once()
        cpu=time.process_time()-t
        wall=time.perf_counter()-w
        projection=engine.read_only_cohort_projection()
        print(json.dumps(dict(mode='outbox_v3',fixture='synthetic',polls=args.polls,
                              parity_rows=args.parity_rows,cohort_rows=args.cohort_rows,
                              **sizes,cutover_cpu_s=round(cutover_cpu,4),
                              cutover_wall_s=round(cutover_wall,4),
                              steady_cpu_s=round(cpu,4),steady_wall_s=round(wall,4),
                              post_cutover_bytes_processed=engine.processed_bytes,
                              committed=completed,projection_lines=len(projection),
                              native_cohort_unchanged=cohort.stat().st_size==sizes['legacy_cohort_bytes'],
                              peak_rss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                              production_ready=False,orders=False),sort_keys=True))

if __name__=='__main__':main()
