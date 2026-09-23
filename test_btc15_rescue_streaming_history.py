import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import tracemalloc
import unittest
from btc15_run_with_rescue_v2_shadow_v1 import new_source_rows, parse_dt


class RescueRetainedHistory(unittest.TestCase):
    def test_matches_previous_filter_with_duplicate_and_out_of_order_rows(self):
        start=datetime(2026,9,23,tzinfo=timezone.utc)
        rows=[{'timestamp_utc':(start+timedelta(seconds=s)).isoformat(),
               'side':side,'note':'quoted, text\nand newline'}
              for s,side in [(-1,'UP'),(0,'DOWN'),(2,'UP'),(1,'DOWN'),(2,'DOWN')]]
        rows.append({'timestamp_utc':'invalid','side':'UP','note':''})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.csv'
            with p.open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            for last in (None,start,start+timedelta(seconds=1)):
                expected=[(parse_dt(r['timestamp_utc']),r) for r in rows
                          if parse_dt(r['timestamp_utc']) and parse_dt(r['timestamp_utc'])>=start
                          and (last is None or parse_dt(r['timestamp_utc'])>last)]
                self.assertEqual(new_source_rows(p,start,last),expected)

    def test_retained_rows_do_not_accumulate_in_memory(self):
        start=datetime(2026,9,23,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.csv'
            with p.open('w',newline='') as f:
                w=csv.writer(f);w.writerow(['timestamp_utc']+['field'+str(i) for i in range(40)])
                for n in range(20000):
                    w.writerow([(start-timedelta(seconds=1)).isoformat()]+[str(n)+'x'*50]*40)
                w.writerow([start.isoformat()]+['new']*40)
            tracemalloc.start()
            try:
                rows=new_source_rows(p,start,None)
                _,peak=tracemalloc.get_traced_memory()
            finally:tracemalloc.stop()
            self.assertEqual(len(rows),1)
            self.assertLess(peak,2_000_000,'retained CSV rows must not build an in-memory list')


if __name__=='__main__':unittest.main()
