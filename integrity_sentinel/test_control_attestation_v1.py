import unittest
from integrity_sentinel.control_attestation_v1 import compare_manifest, manifest_sha256


def expected():
    return {"sources": {"x": {
        "service_id": "svc", "deployment_id": "dep", "branch": "main",
        "commit_sha": "abc", "start_command": "python app.py", "role": "source",
        "cutoff_utc": None,
    }}}


class ControlAttestationTests(unittest.TestCase):
    def test_exact_match_passes(self):
        actual = {"sources": {"x": dict(expected()["sources"]["x"])}}
        self.assertTrue(compare_manifest(expected(), actual)["control_plane_pass"])

    def test_mismatch_fails(self):
        actual = {"sources": {"x": {**expected()["sources"]["x"], "deployment_id": "other"}}}
        report = compare_manifest(expected(), actual)
        self.assertFalse(report["control_plane_pass"])
        self.assertIn("deployment_id", report["sources"][0]["mismatches"])

    def test_missing_fact_is_unknown(self):
        actual = {"sources": {"x": {"service_id": "svc"}}}
        self.assertIsNone(compare_manifest(expected(), actual)["control_plane_pass"])

    def test_manifest_hash_is_deterministic(self):
        self.assertEqual(manifest_sha256(expected()), manifest_sha256(expected()))


if __name__ == "__main__":
    unittest.main()
