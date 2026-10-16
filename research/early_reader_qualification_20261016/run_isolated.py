"""One bounded qualification on the EXISTING Railway research service.

No capacity rerun, capture activation, producer mutation or new infrastructure.
Preserves original evidence and earlier results; unique deployment output only.
"""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import resource
import shutil
import time
import unittest

from ops.live_recording.policy import atomic,file_sha
from research.main_closeout_incremental_20261015.verify_isolated_railway_ssh_main import ISOLATED,check_local,KNOWN
from research.main_closeout_incremental_20261015.check_existing_live_recorder_readiness import assess
from research.main_closeout_incremental_20261015.verify_isolated_railway_ssh_transfer import PRODUCTION
from research.main_closeout_incremental_20261015 import run_v81_native_audit_on_railway as prior

TESTS=[
 'research.main_closeout_incremental_20261015.test_recorder_burst_batch_research',
 'research.main_closeout_incremental_20261015.test_existing_reader_window_inventory',
 'research.main_closeout_incremental_20261015.test_quote_window_handoff_research',
 'research.main_closeout_incremental_20261015.test_native_journal_window_handoff',
 'research.main_closeout_incremental_20261015.test_source_contract_window_handoff',
 'research.main_closeout_incremental_20261015.test_v81_exact_native_window_causality',
 'research.early_reader_qualification_20261016.test_main_reader',
 'research.early_reader_qualification_20261016.test_restart_and_drain',
]


def main():
    if any(os.getenv(k)!=v for k,v in ISOLATED.items()):raise RuntimeError('ISOLATED_IDENTITY_REQUIRED')
    deployment=os.environ['RAILWAY_DEPLOYMENT_ID']
    if not deployment or any(c not in '0123456789abcdef-' for c in deployment):raise RuntimeError('DEPLOYMENT_ID')
    root=Path('/research-evidence')/('early_reader_qualification_20261016_'+deployment)
    root.mkdir(mode=0o700)
    if shutil.disk_usage(root).free<8*1024**3:raise RuntimeError('ISOLATED_STORAGE_RESERVE')
    begun=time.monotonic()
    # The prior 600k receipt is read/hash checked; its workload is never invoked.
    receipt=Path('/research-evidence/early_capacity_probe_second_attempt/QUALIFICATION.json')
    capacity=dict(path=str(receipt),sha256=file_sha(receipt),rerun=False)
    suite=unittest.defaultTestLoader.loadTestsFromNames(TESTS)
    with (root/'regressions.log').open('x') as log, redirect_stdout(log):
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        log.flush();os.fsync(log.fileno())
    tests=dict(run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
               skipped=len(result.skipped),passed=result.wasSuccessful(),log_sha256=file_sha(root/'regressions.log'))
    print('BTC15_QUALIFICATION_TESTS '+json.dumps(tests,sort_keys=True),flush=True)
    native=dict(status='NOT_RUN_TEST_FAILURE')
    if result.wasSuccessful():
        # Reuse the established authentic-sample harness unchanged, new output.
        prior.OUTPUT=root/'authentic_samples'
        prior.main()
        native=json.loads((prior.OUTPUT/'RESULTS.json').read_bytes())
    production={}
    # Existing pinned SSH identity only. Do not create keys or repin a server.
    try:
        check_local()
        if not KNOWN.is_file() or KNOWN.is_symlink():raise RuntimeError('EXISTING_HOST_PIN_REQUIRED')
        for name,(domain,expected,role) in PRODUCTION.items():
            capture=io.StringIO()
            try:
                with redirect_stdout(capture):assess(name,domain,expected,role)
                lines=[x.split(' ',1)[1] for x in capture.getvalue().splitlines() if x.startswith('BTC15_LIVE_RECORDER_READINESS ')]
                if len(lines)!=1:raise RuntimeError('READINESS_RECEIPT_MISSING')
                production[name]=dict(status='READ_ONLY_VERIFIED',**json.loads(lines[0]))
            except (Exception,SystemExit) as exc:
                production[name]=dict(status='BLOCKED',reason=type(exc).__name__+':'+str(exc),diagnostic=capture.getvalue()[-1000:])
            print('BTC15_PRODUCER_READ_ONLY '+json.dumps(production[name],sort_keys=True),flush=True)
    except (Exception,SystemExit) as exc:
        production['access']=dict(status='BLOCKED',reason=type(exc).__name__+':'+str(exc))
    summary=dict(schema='BTC15_EARLY_READER_QUALIFICATION_20261016',decision='NO_GO',
                 commit=os.getenv('RAILWAY_GIT_COMMIT_SHA'),deployment=deployment,
                 tests=tests,prior_capacity=capacity,authentic_samples=native,
                 producer_read_only=production,elapsed_seconds=round(time.monotonic()-begun,3),
                 max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 production_mutations=False,orders=False,capacity_rerun=False,
                 capture_started=False,full_day_checkpoint_resume_qualified=False,
                 result_path=str(root/'RESULTS.json'))
    atomic(root/'RESULTS.json',summary)
    print('BTC15_QUALIFICATION_RESULT '+json.dumps({k:v for k,v in summary.items() if k!='authentic_samples'},sort_keys=True),flush=True)
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
