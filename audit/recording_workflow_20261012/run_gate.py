"""One impacted offline gate, inherited results stay immutable."""
from pathlib import Path
import json,sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
NAMES=['ops.recording_workflow.test_workflow',
 'candidates.early_recording_20261012.test_recording.QuoteMechanics',
 'candidates.early_recording_20261012.test_recording.Provenance',
 'test_btc15_quote_proof_offpath_v1',
 'test_btc15_quote_proof_offpath_timing']
if __name__=='__main__':
 with patch('socket.socket.connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch('socket.create_connection',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch('candidates.early_rebuild_20261012.continuation.fit',side_effect=AssertionError('FIT_FORBIDDEN')),patch('candidates.early_rebuild_20261012.continuation.calibrate',side_effect=AssertionError('CALIBRATION_FORBIDDEN')):
  result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(NAMES))
 summary=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),successful=result.wasSuccessful(),network_blocked=True,fit_calibration_blocked=True,predictive_evaluation=False)
 if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps(summary));raise SystemExit(not result.wasSuccessful())
