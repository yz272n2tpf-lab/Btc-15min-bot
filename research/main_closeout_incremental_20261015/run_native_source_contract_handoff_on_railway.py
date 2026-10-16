"""Run EXISTING reader's bounded quote, native and exact source/settlement handoffs.

No new validator, new source feed, producer change, or EARLY scoring.
FAIL results are preserved as explicit negatives; an incomplete original
recording can never be reported as full qualifying evidence.
"""
import json
import os
from pathlib import Path
import resource
import shutil
import time

from ops.recording_workflow.evidence import streaming_window_inventory
from ops.live_recording.quote_window_handoff_research import QuoteWindowHandoff
from ops.live_recording.native_window_handoff_research import NativeJournalWindowHandoff
from ops.live_recording.source_contract_window_handoff_research import SourceContractWindowHandoff

BASE=Path('/research-evidence')
INPUT=BASE/'native_sample_window_inventory_20261016'
OUTPUT=BASE/'native_quote_journal_source_handoff_20261016'
EXPECTED={'MAIN':2942,'V81':26484}

def main():
    identity={
      'RAILWAY_PROJECT_ID':'87ad03d5-e1d6-47d6-b1ea-159cd7594686',
      'RAILWAY_ENVIRONMENT_ID':'12d241b7-23b4-4421-aafd-142e943555ee',
      'RAILWAY_SERVICE_ID':'1fff593b-8b09-4cc4-8c51-f9603082657f',
      'RAILWAY_VOLUME_ID':'2dba2ef6-b84d-4abf-9d04-58a1e77082c5',
      'RAILWAY_VOLUME_MOUNT_PATH':'/research-evidence'
    }
    if any(os.getenv(k)!=v for k,v in identity.items()):
        raise RuntimeError('ISOLATED_IDENTITY_REQUIRED')
    if OUTPUT.exists():raise RuntimeError('RESEARCH_OUTPUT_ALREADY_EXISTS')
    if shutil.disk_usage(BASE).free<8*1024**3:
        raise RuntimeError('ISOLATED_STORAGE_RESERVE')
    OUTPUT.mkdir(mode=0o700)
    results={}
    for name,expected_rows in EXPECTED.items():
        source=INPUT/name/'input'
        if not source.is_dir() or source.is_symlink():
            raise RuntimeError('PRESERVED_SOURCE_MISSING')
        observer=QuoteWindowHandoff(max_books=16,max_raw_bytes=16*1024**2,
                                     max_pending=4096,max_requests=512)
        native=NativeJournalWindowHandoff()
        source_causal=SourceContractWindowHandoff()
        dest=OUTPUT/name
        started=time.monotonic()
        try:
            report=streaming_window_inventory(
                source,dest,quote_handoff=observer,native_handoff=native,
                source_handoff=source_causal,
                window_seconds=900,
                max_window_bytes=8*1024**2,max_window_records=20000)
            if report['record_count']!=expected_rows:
                raise ValueError('ORIGINAL_RECORD_COUNT_DRIFT')
            if report['structural_integrity']!='PASS':
                raise ValueError('ORIGINAL_SHA_CHAIN_INVALID')
            q=report['quote_state_handoff']
            n=report['native_journal_handoff']
            ca=report['source_contract_handoff']
            result=dict(role=name,result='STRUCTURAL_SOURCE_QUOTE_AND_NATIVE_PREFIX_CHECK',
                        original_records=report['record_count'],
                        original_gap_envelopes=report['loss_indicators'],
                        quote_audit=q,native_journal_audit=n,
                        source_contract_audit=ca,
                        audit_file_bytes=(dest/'windows.jsonl').stat().st_size,
                        source_windows=report['windows'],
                        elapsed_seconds=round(time.monotonic()-started,3),
                        max_process_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        full_live_capture_qualified=False,
                        native_early_qualified=False,
                        production_modified=False,orders=False)
        except Exception as exc:
            # Retain an explicit fail report; never replace a partial stream
            # with "successful" evidence, never automatically retry/replay.
            result=dict(role=name,result='BLOCKED',
                        reason=type(exc).__name__+':'+str(exc)[:220],
                        quote_prefix_counts=observer.finish(),
                        native_prefix_counts=native.finish(),
                        source_contract_prefix_counts=source_causal.finish(),
                        elapsed_seconds=round(time.monotonic()-started,3),
                        full_live_capture_qualified=False,
                        native_early_qualified=False,
                        production_modified=False,orders=False)
        results[name]=result
        print('BTC15_REAL_QUOTE_NATIVE_SOURCE_HANDOFF '+json.dumps(result,sort_keys=True),flush=True)
    summary=dict(schema='BTC15_EXISTING_READER_QUOTE_NATIVE_SOURCE_HANDOFF_REAL_RESEARCH_V1',
                 results=results,original_source_mutated=False,
                 complete_day=False,production_modified=False,
                 new_early_validator=False,orders=False)
    (OUTPUT/'RESULTS.json').write_text(json.dumps(summary,sort_keys=True))
    print('BTC15_REAL_QUOTE_NATIVE_SOURCE_HANDOFF_SUMMARY '+json.dumps(summary,sort_keys=True),flush=True)

if __name__=='__main__':main()