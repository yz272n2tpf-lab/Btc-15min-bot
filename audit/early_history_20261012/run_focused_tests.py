"""Narrow recovery gate. No model fitting/calibration or historical strategy run."""
from pathlib import Path
import json,sys,unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
PREFIX='candidates.early_rebuild_20261012.'
NAMES=['test_underlying_history','test_continuation.ContinuationTests','test_engine','test_blockers','test_replay']
EXCLUDE={'test_logistic_and_intercept_calibration','test_fixture_labels_cannot_train_empirical_artifact'}

def flatten(suite):
    for test in suite:
        if isinstance(test,unittest.TestSuite):yield from flatten(test)
        else:yield test

if __name__=='__main__':
    suite=unittest.TestSuite(t for t in flatten(unittest.defaultTestLoader.loadTestsFromNames([PREFIX+n for n in NAMES]))
                            if t._testMethodName not in EXCLUDE)
    # No estimator fitting or calibration is part of this readiness gate.
    with patch(PREFIX+'continuation.fit',side_effect=AssertionError('FIT_NOT_AUTHORIZED')), \
         patch(PREFIX+'continuation.solve',side_effect=AssertionError('FIT_NOT_AUTHORIZED')), \
         patch(PREFIX+'continuation.calibrate',side_effect=AssertionError('CALIBRATION_NOT_AUTHORIZED')):
        result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
          successful=result.wasSuccessful(),excluded_numerical_fixture_tests=sorted(EXCLUDE),
          legacy_artifact_integration_tests='incompatible artifact; replaced by explicit rejection checks')))
    raise SystemExit(not result.wasSuccessful())
