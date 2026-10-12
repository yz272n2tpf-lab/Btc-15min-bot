"""Small synthetic sizing fixture, not production throughput or data collection."""
import json
from pathlib import Path
import sys
import tempfile
import time
import tracemalloc
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from candidates.early_recording_20261012.archive import Archive,read_archive,bounded_size
from candidates.early_recording_20261012.seams import Observer
from btc15_quote_proof_offpath_v1 import OffPathProofWriter

def probe(kind):
    with tempfile.TemporaryDirectory() as d:
        tracemalloc.start();path=Path(d)/'fixture'
        a=Archive(path,evidence_class='FIXTURE',source_binding='SYNTHETIC_SIZING_ONLY')
        w=OffPathProofWriter(Path(d)/'unused',lambda p,x:x.identity,2*1024*1024,queue_size=64,archive=a)
        o=Observer(w,btc_feed='FIXTURE_BTC',btc_epoch='FIXTURE_PROCESS',brti_feed='FIXTURE_BRTI')
        latencies=[]
        for n in range(240):
            at=1000.+n
            start=time.perf_counter_ns()
            if kind=='source':o.source('BTC',80000+n/10,at,at+.05,'FIXTURE_PROCESS')
            else:
                event=dict(type='orderbook_delta' if n else 'orderbook_snapshot',sid=1,seq=n+1,
                    msg=dict(market_ticker='FIXTURE',market_id='FIXTURE_M',side='yes',
                             price_dollars='.45',delta_fp='1',ts_ms=int(at*1000)))
                raw=json.dumps(event)
                o.quote_receive(raw,'FIXTURE','FIXTURE_EPOCH',at+.05,n)
                o.quote_accept(raw,'FIXTURE','FIXTURE_EPOCH',at+.05,at+.051)
            latencies.append(time.perf_counter_ns()-start)
            if n%8==0:w.queue.join()
        w.queue.join();w.close();current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        disk=sum(f.stat().st_size for f in a.journal.directory.glob('*.gz'))
        result=dict(evidence_class='FIXTURE',observations=240,compressed_bytes=disk,
                    bytes_per_observation_including_overhead=disk/240,peak_traced_python_bytes=peak,
                    p99_submission_microseconds=sorted(latencies)[int(.99*len(latencies))]/1000,
                    writer_status=w.status(),records=len(read_archive(path)['records']))
        assert not result['writer_status']['losses'] and not result['writer_status']['archive_failed']
        return result

if __name__=='__main__':
    result={k:probe(k) for k in ('source','quote')}
    s=result['source']['bytes_per_observation_including_overhead'];q=result['quote']['bytes_per_observation_including_overhead']
    result['assumption_scenarios']=[dict(btc_per_second=1,brti_per_second=1,quote_messages_per_second=rate,
        estimated_MiB_per_day=(2*s+rate*q)*86400/(1024**2),
        estimated_hours_to_256MiB=(256*1024**2)/(2*s+rate*q)/3600) for rate in (1,10,100)]
    result['limits']='Synthetic small-message estimates only. Excludes raw information/proof/metadata contributions, Python RSS/native allocations and live latency. No production sizing certification.'
    (Path(__file__).parent/'RESOURCE_RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
