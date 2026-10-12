"""Only changed verifier/report/package tests plus impacted bounded regressions."""
from pathlib import Path
from contextlib import ExitStack
import json,socket,sys,time,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
NAMES=['ops.recording_workflow.test_whole_run',*['ops.recording_workflow.test_workflow.Workflow.'+name for name in (
 'test_capture_default_off_no_threads_or_paths',
 'test_live_mode_flags_protected_paths_and_policy_rejected',
 'test_bounded_contract_range_source_context_and_index_corruption',
 'test_automatic_completion_report_package_idempotence_and_failure_channel',
 'test_empty_partial_and_corrupt_archives_cannot_be_complete')]]
started=time.time()
with ExitStack() as stack:
 stack.enter_context(patch('socket.socket.connect',side_effect=AssertionError('NETWORK_FORBIDDEN')))
 stack.enter_context(patch('socket.create_connection',side_effect=AssertionError('NETWORK_FORBIDDEN')))
 suite=unittest.defaultTestLoader.loadTestsFromNames(NAMES)
 result=unittest.TextTestRunner(verbosity=2).run(suite)
summary=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),successful=result.wasSuccessful(),started_utc=__import__('datetime').datetime.fromtimestamp(started,__import__('datetime').timezone.utc).isoformat(),completed_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),seconds=time.time()-started,network_blocked=True,model_calls=0,research_or_economic_evaluation=False)
if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary));raise SystemExit(0 if result.wasSuccessful() else 1)
