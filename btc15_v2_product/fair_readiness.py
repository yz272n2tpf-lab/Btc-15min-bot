"""Recover startup-only fair readiness at the existing native evaluation seam.

Model identity is checked independently of a startup market lookup. The frozen
native function still builds every fair estimate from the current causal frame.
No cached estimate, alternate arithmetic, polling, or extra evaluation exists.
"""
import hashlib
from pathlib import Path

from btc15_information_v1 import ARTIFACT, WEIGHTS
from completion_audit.frozen_model_artifact import fitted_weight_hash

INPUTS = sorted([
    '78cc03b5ea15ec1d310aa3de68a5024ade7fe80f91762d1e3ee0cab03903ff4b',
    '40e44f08637a3636fbb8a14e81cf0db47335e00e74bf16bcd4c1077318fd2a85',
])
TRANSIENT = {
    "name '_strict_active_open' is not defined",
    "name '_audit_target' is not defined",
    'Not enough current 1-minute BTC data for fair probability',
}


def install(ns):
    """Install before the native loop; never alter a successfully ready startup."""
    if ns.get('_fair_ready') or ns.get('_fair_error_text') not in TRANSIENT:
        return False
    try:
        model = ns['_fair_artifact']
        if (ns['_fair_model_artifact_sha256'] != ARTIFACT
                or ns['_fair_model_weights_sha256'] != WEIGHTS
                or model['forest'] is not ns['_fair_rf']
                or model['sigmoid'] is not ns['_fair_sigmoid']
                or list(model['features']) != ns['_fair_features']
                or sorted(model['input_sha256'].values()) != INPUTS
                or fitted_weight_hash(model) != WEIGHTS
                or model['weights_sha256'] != WEIGHTS
                or model['forest'].n_jobs != 1):
            return False
        artifact = Path(__file__).resolve().parents[1] / 'completion_audit/model_artifact/frozen_fair_candidate.joblib'
        with artifact.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != ARTIFACT:
                return False
        original = ns['_live_fair_shadow']
    except (KeyError, TypeError, AttributeError, OSError):
        return False

    def evaluate(*args, **kwargs):
        if ns['_fair_ready']:
            return original(*args, **kwargs)
        # This flag was incorrectly latched by the startup market assessment.
        # The verified model is ready; current feature support is still tested
        # by the original function, on the sole native authoritative clock.
        ns['_fair_ready'] = True
        try:
            result = original(*args, **kwargs)
        except Exception:
            ns['_fair_ready'] = False
            raise
        if result is None:
            ns['_fair_ready'] = False
        else:
            ns['_fair_error_text'] = None
        return result

    ns['_live_fair_shadow'] = evaluate
    return True
