"""One offline run on the existing research service and preserved evidence.

No production SSH, configuration, deployment, capture, or strategy execution.
The old 600k receipt and original compression measurements are READ ONLY.
"""
from collections import Counter
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time
import unittest

from ops.live_recording.policy import atomic,canonical,file_sha,sha
from ops.live_recording.windowed_campaign import run
from ops.recording_workflow.evidence import lines,clocks
from research.early_reader_qualification_20261016.run_isolated import TESTS

IDENTITY={
 'RAILWAY_PROJECT_ID':'87ad03d5-e1d6-47d6-b1ea-159cd7594686',
 'RAILWAY_ENVIRONMENT_ID':'12d241b7-23b4-4421-aafd-142e943555ee',
 'RAILWAY_SERVICE_ID':'1fff593b-8b09-4cc4-8c51-f9603082657f',
 'RAILWAY_VOLUME_ID':'2dba2ef6-b84d-4abf-9d04-58a1e77082c5',
 'RAILWAY_VOLUME_MOUNT_PATH':'/research-evidence'}


def source_hashes(root):
    return {str(p.relative_to(root)):dict(bytes=p.stat().st_size,sha256=file_sha(p))
            for p in sorted(root.rglob('*.jsonl.gz'))}


def producer_analysis(root,benchmark):
    counts=Counter();decoded=Counter();times={};largest={};gaps=Counter()
    candle_rows=0;candle_bad=0;candle_examples=[]
    for p in sorted(root.rglob('*.jsonl.gz')):
        for _,r,raw in lines(p):
            k=r['kind'];v=r['payload'];counts[k]+=1;decoded[k]+=len(raw)
            largest[k]=max(largest.get(k,0),len(raw))
            at=clocks(v)
            if type(at) in (int,float):
                first,last,n=times.get(k,(at,at,0));times[k]=(min(first,at),max(last,at),n+1)
            if k=='EVIDENCE_GAP':
                for reason,n in (v.get('reasons') or {}).items() if isinstance(v.get('reasons'),dict) else ():
                    if type(n) is int:gaps[reason]+=n
            if k=='CANDLE_ACCEPTANCE':
                rows=json.loads(v['raw'])
                for row in rows:
                    candle_rows+=1
                    if len(row)!=7 or row[0]!=row[1]+60:
                        candle_bad+=1
                        if len(candle_examples)<3:candle_examples.append(dict(index_time=row[0],source_time=row[1],difference=row[0]-row[1]))
    original=json.loads(benchmark.read_bytes())
    return dict(original_benchmark_path=str(benchmark),original_benchmark_sha256=file_sha(benchmark),
                preserved_benchmark=original,per_kind=dict(counts),decoded_by_kind=dict(decoded),
                largest_retained_envelope_bytes=largest,clock_ranges_by_kind=times,gap_reason_totals=dict(gaps),
                candle_clock_diagnostics=dict(rows=candle_rows,failed_existing_end_clock_rule=candle_bad,examples=candle_examples),
                total_compressed_bytes=sum(p.stat().st_size for p in root.rglob('*.jsonl.gz')),
                caution='Receipt clock spans/counts and historical burst denominator are distinct; no sustained full-day rate measured. Rejected oversized payload is absent.')


def replay(root,out):
    before=source_hashes(root);out.mkdir()
    started=time.monotonic()
    baseline=run(root,out/'baseline',window_records=1000)
    elapsed=time.monotonic()-started
    script='''
import os,signal,sys
from ops.live_recording.windowed_campaign import run
def fault(phase,v):
 if phase=='after_commit' and sum(v.counts.values())>=100 and v.generation>=2:
  os.kill(os.getpid(),signal.SIGKILL)
run(sys.argv[1],sys.argv[2],window_records=1000,fault=fault)
'''
    killed=subprocess.run([sys.executable,'-B','-c',script,str(root),str(out/'resumed')],capture_output=True,timeout=120)
    if killed.returncode!=-signal.SIGKILL:raise RuntimeError('AUTHENTIC_INTERRUPTION_NOT_REACHED:'+killed.stderr.decode()[-200:])
    if (out/'resumed'/'window_inventory_manifest.json').exists():raise RuntimeError('FALSE_FINAL_MANIFEST')
    resumed=run(root,out/'resumed',resume=True,window_records=1000)
    if baseline!=resumed:raise RuntimeError('AUTHENTIC_SUMMARY_RESUME_MISMATCH')
    ledgers={}
    for name in ('windows.jsonl','associations.jsonl','issues.jsonl','v81_native_original_associations.jsonl'):
        a=file_sha(out/'baseline'/name);b=file_sha(out/'resumed'/name)
        if a!=b:raise RuntimeError('AUTHENTIC_LEDGER_RESUME_MISMATCH:'+name)
        ledgers[name]=dict(bytes=(out/'baseline'/name).stat().st_size,sha256=a)
    if source_hashes(root)!=before:raise RuntimeError('AUTHENTIC_SOURCE_CHANGED')
    return dict(records=baseline['record_count'],decoded_bytes=baseline['decoded_bytes'],
                source_manifest_sha256=sha(canonical(before)),sources=before,source_unchanged=True,
                windows=baseline['windows'],loss_indicators=baseline['loss_indicators'],
                campaign=baseline['campaign_verification'],ledger_receipts=ledgers,
                baseline_seconds=round(elapsed,3),checkpoint_sigkill_resume_exact=True,
                max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                native_capture_complete=False)


def main(prior_retention=None):
    if any(os.getenv(k)!=v for k,v in IDENTITY.items()):raise RuntimeError('ISOLATED_IDENTITY_REQUIRED')
    deployment=os.environ['RAILWAY_DEPLOYMENT_ID']
    if not deployment or any(c not in '0123456789abcdef-' for c in deployment):raise RuntimeError('DEPLOYMENT_ID')
    base=Path('/research-evidence')
    out=base/('bounded_reader_recovery_20261016_'+deployment);out.mkdir(mode=0o700)
    if shutil.disk_usage(out).free<16*1024**3:raise RuntimeError('RESEARCH_STORAGE_RESERVE')
    started=time.monotonic()
    receipt=base/'early_capacity_probe_second_attempt'/'QUALIFICATION.json'
    prior=dict(path=str(receipt),sha256=file_sha(receipt),rerun=False)
    suite=unittest.defaultTestLoader.loadTestsFromNames(TESTS+[
        'research.bounded_reader_recovery_20261016.test_recovery'])
    with (out/'regressions.log').open('x') as log,redirect_stdout(log):
        tests=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        log.flush();os.fsync(log.fileno())
    test_result=dict(run=tests.testsRun,failures=len(tests.failures),errors=len(tests.errors),
                     skipped=len(tests.skipped),passed=tests.wasSuccessful(),log_sha256=file_sha(out/'regressions.log'))
    print('BTC15_RECOVERY_TESTS '+json.dumps(test_result,sort_keys=True),flush=True)
    authentic={};capacity={};stress={}
    retained_receipt=None
    if prior_retention:
        path=Path(prior_retention)
        if path.is_symlink() or not path.resolve().is_relative_to(base):raise RuntimeError('PRIOR_RETENTION_PATH')
        old=json.loads(path.read_bytes())
        if old.get('commit')!='3d1b5919ac843bff89d9321e023541a1a88b5cc3':raise RuntimeError('PRIOR_RETENTION_COMMIT')
        stress=old['stress']
        if set(stress)!={'source','quote','v81'} or not all(z.get('resume_exact') and z.get('old_dependency_still_exact') for z in stress.values()):
            raise RuntimeError('PRIOR_RETENTION_NOT_PASSED')
        retained_receipt=dict(path=str(path),sha256=file_sha(path),commit=old['commit'],rerun=False)
    elif tests.wasSuccessful():
        # Serialized writers only. Independent processes keep RSS measurements
        # separate; each finishes before the next starts, on this volume.
        for kind in ('source','quote','v81'):
            try:
                with (out/('stress-'+kind+'.log')).open('x') as log:
                    proc=subprocess.run([sys.executable,'-B','-m',
                        'research.bounded_reader_recovery_20261016.stress',str(out/('stress-'+kind)),kind],
                        stdout=log,stderr=subprocess.STDOUT,timeout=180)
                if proc.returncode:raise RuntimeError('STRESS_EXIT:'+str(proc.returncode))
                stress[kind]=json.loads((out/('stress-'+kind)/'RESULTS.json').read_bytes())
            except Exception as exc:stress[kind]=dict(status='BLOCKED',reason=type(exc).__name__+':'+str(exc))
            print('BTC15_ISOLATED_RETENTION '+json.dumps(dict(workload=kind,result=stress[kind]),sort_keys=True),flush=True)
    for role in ('MAIN','V81'):
        source=base/'native_sample_window_inventory_20261016'/role/'input'
        try:
            capacity[role]=producer_analysis(source,base/('early_'+role.lower()+'_oct13_batch_benchmark_20261016')/'BENCHMARK.json')
        except Exception as exc:capacity[role]=dict(status='BLOCKED',reason=type(exc).__name__+':'+str(exc))
        print('BTC15_PRESERVED_CAPACITY '+json.dumps(dict(role=role,analysis=capacity[role]),sort_keys=True),flush=True)
        if tests.wasSuccessful():
            try:authentic[role]=replay(source,out/role)
            except Exception as exc:authentic[role]=dict(status='BLOCKED',reason=type(exc).__name__+':'+str(exc))
        else:authentic[role]=dict(status='BLOCKED',reason='REGRESSION_FAILURE')
        print('BTC15_AUTHENTIC_RECOVERY '+json.dumps(dict(role=role,result=authentic[role]),sort_keys=True),flush=True)
    summary=dict(schema='BTC15_BOUNDED_RECOVERY_RESEARCH_V1',commit=os.getenv('RAILWAY_GIT_COMMIT_SHA'),
                 deployment=deployment,tests=test_result,prior_600k=prior,authentic=authentic,capacity=capacity,stress=stress,
                 retained_stress_receipt=retained_receipt,
                 elapsed_seconds=round(time.monotonic()-started,3),production_mutations=False,
                 capture_started=False,orders=False,decision='NO_GO',result_path=str(out/'RESULTS.json'))
    atomic(out/'RESULTS.json',summary)
    print('BTC15_RECOVERY_RESULT '+json.dumps({k:v for k,v in summary.items() if k not in ('authentic','capacity','stress')},sort_keys=True),flush=True)
    if not tests.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--prior-retention')
    main(parser.parse_args().prior_retention)
