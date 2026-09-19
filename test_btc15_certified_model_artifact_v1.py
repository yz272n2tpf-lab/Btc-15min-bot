#!/usr/bin/env python3
import pathlib,tempfile
import btc15_certified_model_artifact_v1 as a
class M: pass
with tempfile.TemporaryDirectory() as d:
 p=pathlib.Path(d)/"models.pkl"
 man=a.write_bundle(p,general_model=M(),fair_rf=M(),fair_sigmoid=M(),metadata={"training_boundary_sha256":"abc","fair_chronology_sha256":"def"})
 assert man["orders"] is False
 x=a.load_bundle(p,man["artifact_sha256"])
 assert x["metadata"]["general_features"]==a.GENERAL_FEATURES
 assert x["metadata"]["fair_features"]==a.FAIR_FEATURES
 bad=bytearray(p.read_bytes());bad[-1]^=1;p.write_bytes(bad)
 try:a.load_bundle(p,man["artifact_sha256"])
 except RuntimeError as e:assert "SHA MISMATCH" in str(e)
 else:raise AssertionError("tamper accepted")
print("CERTIFIED_MODEL_ARTIFACT_TEST_PASS | NO ORDERS")
