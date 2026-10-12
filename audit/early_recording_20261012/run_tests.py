"""Bounded offline gate. Synthetic mechanisms only; no fit, calibration or sockets."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
NAMES=[
 'candidates.early_recording_20261012.test_recording',
 'test_btc15_quote_proof_offpath_v1',
 'test_btc15_quote_proof_offpath_timing',
 'test_btc15_brti_delivery_v1',
 'test_btc15_kalshi_quote_provenance_regressions',
 'test_btc15_supported_early',
 'test_btc15_scalp_journal_v1',
 'test_btc15_information_v1.InformationTests.test_durable_journal_reconstructs_exact_frame_after_memory_eviction',
 'test_btc15_information_v1.InformationTests.test_durable_journal_records_only_successful_qualified_publications',
 'test_btc15_information_v1.InformationTests.test_journal_survives_publisher_restart_and_appends_without_overwrite',
 'test_btc15_information_v1.InformationTests.test_journal_reconstructs_two_contracts_without_cross_labeling',
]

if __name__=='__main__':
    with patch('socket.socket.connect',side_effect=AssertionError('NETWORK_NOT_AUTHORIZED')), \
         patch('socket.create_connection',side_effect=AssertionError('NETWORK_NOT_AUTHORIZED')), \
         patch('candidates.early_rebuild_20261012.continuation.fit',side_effect=AssertionError('FIT_NOT_AUTHORIZED')), \
         patch('candidates.early_rebuild_20261012.continuation.solve',side_effect=AssertionError('FIT_NOT_AUTHORIZED')), \
         patch('candidates.early_rebuild_20261012.continuation.calibrate',side_effect=AssertionError('CALIBRATION_NOT_AUTHORIZED')):
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(NAMES))
    summary=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                 successful=result.wasSuccessful(),network_blocked=True,fit_calibration_blocked=True,
                 economic_evaluation=False,modules=NAMES)
    (Path(__file__).parent/'TEST_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))
    raise SystemExit(not result.wasSuccessful())
