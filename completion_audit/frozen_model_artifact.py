"""Load only an explicitly trusted, immutable fitted model; never fit on startup.

The expected hashes must come from the separately reviewed policy, not from an
adjacent downloaded file. Artifact bytes are verified before joblib unpickles.
"""
import hashlib
from pathlib import Path
import joblib


def fitted_weight_hash(model):
    digest=hashlib.sha256()
    for estimator in model['forest'].estimators_:
        for field in ('children_left','children_right','feature','threshold','value'):
            digest.update(getattr(estimator.tree_,field).tobytes())
    digest.update(model['sigmoid'].coef_.tobytes())
    digest.update(model['sigmoid'].intercept_.tobytes())
    return digest.hexdigest()


def load_verified(path, *, expected_artifact_sha256, expected_weights_sha256):
    for value in (expected_artifact_sha256,expected_weights_sha256):
        if len(value)!=64 or any(c not in '0123456789abcdef'for c in value):
            raise ValueError('Explicit trusted SHA256 required')
    path=Path(path)
    if not 0<path.stat().st_size<=50*1024*1024:
        raise ValueError('Model artifact size outside bound')
    # One descriptor for check and load prevents path replacement between reads.
    with path.open('rb')as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=expected_artifact_sha256:
            raise ValueError('Model artifact hash mismatch')
        stream.seek(0)
        model=joblib.load(stream)
    if (model.get('weights_sha256')!=expected_weights_sha256 or
            fitted_weight_hash(model)!=expected_weights_sha256):
        raise ValueError('Fitted weight identity mismatch')
    if model['forest'].n_jobs!=1:
        raise ValueError('Serial prediction accumulation required')
    return model
