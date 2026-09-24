import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from frozen_model_artifact import fitted_weight_hash,load_verified


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory())
        self.path=Path(self.temp)/'model.joblib'
        x=np.arange(40).reshape(-1,1);y=np.array([0,1]*20)
        forest=RandomForestClassifier(n_estimators=5,max_depth=2,random_state=42,n_jobs=1).fit(x,y)
        sigmoid=LogisticRegression(random_state=42).fit(forest.predict_proba(x)[:,1].reshape(-1,1),y)
        self.model=dict(forest=forest,sigmoid=sigmoid,features=['x'])
        self.weight=fitted_weight_hash(self.model);self.model['weights_sha256']=self.weight
        joblib.dump(self.model,self.path,compress=3)
        self.sha=hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_reload_preserves_exact_predictions_without_fit(self):
        with patch.object(RandomForestClassifier,'fit',side_effect=AssertionError('No refit')):
            model=load_verified(self.path,expected_artifact_sha256=self.sha,expected_weights_sha256=self.weight)
        x=np.arange(40).reshape(-1,1)
        np.testing.assert_array_equal(self.model['forest'].predict_proba(x),model['forest'].predict_proba(x))

    def test_corrupt_bytes_rejected_before_deserialization(self):
        self.path.write_bytes(self.path.read_bytes()+b'changed')
        with patch('frozen_model_artifact.joblib.load',side_effect=AssertionError('Must not load')):
            with self.assertRaisesRegex(ValueError,'artifact hash mismatch'):
                load_verified(self.path,expected_artifact_sha256=self.sha,expected_weights_sha256=self.weight)

    def test_wrong_policy_weight_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'weight identity'):
            load_verified(self.path,expected_artifact_sha256=self.sha,expected_weights_sha256='0'*64)

    def test_no_implicit_trust_of_adjacent_manifest(self):
        with self.assertRaisesRegex(ValueError,'trusted SHA256'):
            load_verified(self.path,expected_artifact_sha256='',expected_weights_sha256=self.weight)


if __name__=='__main__':unittest.main()
