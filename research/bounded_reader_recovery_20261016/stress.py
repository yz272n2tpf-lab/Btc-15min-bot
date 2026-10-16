"""New targeted retention workloads, NOT the completed 600,000-record test.

Source: 70,000 unique exact observations, exceeding the old 65,536 cap.
Quote: 33,000 same-timestamp sequence increments, exceeding the old 32,768 LRU.
V81: 8,300 accepted attempts then a native reference to the FIRST input.
These artificial rates/labels are not authentic decisions or live throughput.
"""
from contextlib import closing,redirect_stdout
import io
import json
from pathlib import Path
import resource
import sqlite3
import time

from candidates.early_recording_20261012.archive import BUDGET
from ops.live_recording.burst_journal_research import BufferedCaptureArchive
from ops.live_recording.policy import atomic,canonical,file_sha
from ops.live_recording.windowed_campaign import run
from ops.recording_workflow.policy import local_policy
from research.bounded_reader_recovery_20261016.test_recovery import v81


def archive(root):
    a=BufferedCaptureArchive(root/'source',evidence_class='FIXTURE',
         source_binding='DECLARED_RETENTION_STRESS',budget=dict(BUDGET,max_total_bytes=256*1024**2),
         storage_policy=local_policy())
    a.start();return a


def workload(root,kind):
    root.mkdir();a=archive(root)
    if kind=='source':
        count=70000
        for i in range(count):
            at=1577836800+i*1.25
            a.source(dict(asset='BTC' if i%2==0 else 'BRTI',value=60000.+i%101,
                          source_ts=at,receipt_ts=at+.01,original_receipt_ts=at+.01,available_at=at+.01,
                          feed='DECLARED_STRESS',epoch='SYNTHETIC',basis='ORIGINAL',accepted_by_owner=True,
                          epoch_basis='SYNTHETIC_FIXTURE',receipt_basis='SYNTHETIC_RECEIPT'))
    elif kind in ('quote','v81'):
        v81.original_market(a);q=v81.quote_book(a)
        btc=v81.btc_http(a);b,h,at=v81.brti_read(a)
        first=v81.v81_row(a,q,b,btc,(b,h,at),attempt='oldest-retained-attempt')
        count=33000 if kind=='quote' else 8300
        if kind=='quote':
            for i in range(count):
                event=dict(type='orderbook_delta',sid=7,seq=i+3,msg=dict(
                    market_ticker=v81.TICKER,market_id=v81.MARKET,ts_ms=int((v81.NOW-1)*1000),
                    side='yes',price_dollars='0.35',delta_fp='1'))
                v81.quote_event(a,canonical(event),v81.NOW-.8)
        else:
            for i in range(count-1):
                v81.v81_row(a,q,b,btc,(b,h,at),attempt='retention-attempt-'+str(i))
        v81.scalp_native(a,first,attempt='oldest-retained-attempt')
    else:raise ValueError('WORKLOAD_KIND')
    a.write('STOP',dict(clean=True));a.close()
    return count,a.seq


def measure(output,kind,preserved_input=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    source=Path(preserved_input) if preserved_input else out/'input'
    if preserved_input:
        count={'source':70000,'quote':33000,'v81':8300}[kind]
        records=None
    else:
        with (out/'generation.log').open('w') as log,redirect_stdout(log):
            count,records=workload(source,kind)
    samples=[];started=time.monotonic()
    def sample(phase,v):
        if phase=='after_commit':
            n=sum(v.counts.values())
            if not samples or n-samples[-1]['records']>=8000:
                samples.append(dict(records=n,rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                    db_bytes=v.db.execute('PRAGMA page_count').fetchone()[0]*4096,
                                    elapsed_seconds=round(time.monotonic()-started,3)))
    result=run(source,out/'reader',window_records=1000,fault=sample)
    if records is not None and records!=result['record_count']:raise AssertionError('STRESS_RECORD_COUNT')
    records=result['record_count']
    elapsed=time.monotonic()-started
    with closing(sqlite3.connect(out/'reader'/'verification.sqlite3')) as db:
        # Exact first/last retention, not just a count of insert attempts.
        retained={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0]
                  for t in ('sources','accepted','book_quotes','live_inputs','handoff_state','raw')}
        first_last=db.execute('SELECT min(source),max(source) FROM sources').fetchone()
        checkpoint=db.execute('SELECT h FROM recovery_checkpoint').fetchone()[0]
    started=time.monotonic()
    again=run(source,out/'reader',resume=True,window_records=1000)
    if result!=again:raise AssertionError('STRESS_RECOVERY_NOT_EQUIVALENT')
    if kind in ('quote','v81') and result['campaign_verification']['v81_causal_matches']!=1:
        raise AssertionError('OLDEST_DEPENDENCY_NOT_RETAINED')
    if kind=='source' and retained['sources']!=count:raise AssertionError('SOURCE_RETENTION')
    receipt=dict(schema='BTC15_TARGETED_RETENTION_STRESS_V1',workload=kind,fixture_only=True,
                 logical_items=count,envelopes=records,retained_rows=retained,
                 source_time_range=first_last,reader_seconds=round(elapsed,3),
                 reader_records_per_second=records/elapsed,
                 integrity_restart_seconds=round(time.monotonic()-started,3),
                 max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 db_bytes=(out/'reader'/'verification.sqlite3').stat().st_size,
                 compressed_input_bytes=sum(p.stat().st_size for p in source.rglob('*.gz')),
                 source_files={str(p.relative_to(source)):file_sha(p) for p in sorted(source.rglob('*.gz'))},
                 decoded_input_bytes=result['decoded_bytes'],memory_samples=samples,
                 checkpoint_sha256=checkpoint,resume_exact=True,
                 old_dependency_still_exact=True,v81_native_matches=result['campaign_verification']['v81_causal_matches'],
                 native_readiness=False,prior_600k_rerun=False)
    atomic(out/'RESULTS.json',receipt)
    print('BTC15_RETENTION_STRESS '+json.dumps(receipt,sort_keys=True),flush=True)
    return receipt


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('kind',choices=('source','quote','v81'))
    p.add_argument('--preserved-input')
    args=p.parse_args();measure(args.output,args.kind,args.preserved_input)
