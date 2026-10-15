"""Research-only fixture benchmark for the receipt-gated variant.

No live data, orders, network access or production credential.
"""
import argparse
import json
from pathlib import Path
import resource
import tempfile
import time
from benchmark_btc15_closeout_incremental_research_v1 import fixture
from btc15_closeout_receipt_guard_research_v2 import DurableReceiptInspector
from btc15_cohort_closeout_incremental_research_v2 import ReceiptGatedIncrementalCloseout


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--parity-rows', type=int,default=70000)
    p.add_argument('--cohort-rows', type=int,default=70000)
    p.add_argument('--polls',type=int,default=12)
    args=p.parse_args()
    with tempfile.TemporaryDirectory() as dirname:
        root=Path(dirname)
        parity,cohort=fixture(root,args.parity_rows,args.cohort_rows)
        sizes=dict(parity_bytes=parity.stat().st_size,cohort_bytes=cohort.stat().st_size)
        guard=DurableReceiptInspector(root/'missing-fixture-journal.sqlite3',
             deployment='fixture',build='fixture',revision='fixture')
        engine=ReceiptGatedIncrementalCloseout(parity,cohort,lambda *_:False,guard)
        cpu=time.process_time();wall=time.perf_counter()
        for _ in range(args.polls):engine.poll_once()
        stats=engine.stats()
        print(json.dumps(dict(mode='receipt_gated_v2',polls=args.polls,
            parity_rows=args.parity_rows,cohort_rows=args.cohort_rows,**sizes,
            bytes_read=stats['parity_bytes_read']+stats['cohort_bytes_read']+stats['audit_bytes_read'],
            cpu_s=round(time.process_time()-cpu,4),wall_s=round(time.perf_counter()-wall,4),
            maxrss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            found=len(engine.emitted),orders=False),sort_keys=True))

if __name__=='__main__':main()
