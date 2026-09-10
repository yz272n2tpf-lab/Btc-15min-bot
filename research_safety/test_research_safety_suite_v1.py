import hashlib
import tempfile
import unittest
from pathlib import Path

from research_safety_suite_v1 import SafetySuiteError, run_suite
from research_safety_preflight_v1 import PreflightError


COLLECTOR = """\
V6_MIN_ASK = 0.07
V6_PREFERRED_MAX = 0.30
V6_MAX_ASK = 0.45
V6_CONFIRM_WINDOW = 4.0
V6_CONFIRM_COUNT = 2
V6_HIGH_BTC5 = 20.0
V6_HIGH_BTC15 = 25.0
V6_HIGH_BRTI5 = 15.0
V6_HIGH_BRTI15 = 5.0
V6_HIGH_ACCEL = 10.0
V6_HIGH_BTC30 = 0.0
"""
EXPECTED = {
    "V6_MIN_ASK": 0.07,
    "V6_PREFERRED_MAX": 0.30,
    "V6_MAX_ASK": 0.45,
    "V6_CONFIRM_WINDOW": 4.0,
    "V6_CONFIRM_COUNT": 2,
    "V6_HIGH_BTC5": 20.0,
    "V6_HIGH_BTC15": 25.0,
    "V6_HIGH_BRTI5": 15.0,
    "V6_HIGH_BRTI15": 5.0,
    "V6_HIGH_ACCEL": 10.0,
    "V6_HIGH_BTC30": 0.0,
}


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


class SafetySuiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.collector = Path(self.tmp.name) / "scalp_lead_shadow_v6.py"
        self.collector.write_text(COLLECTOR, encoding="utf-8")
        sha = blob_sha(COLLECTOR.encode())
        self.provenance = {
            "railway": {
                "source_branch": "active-v6",
                "start_command": "python scalp_lead_shadow_v6.py",
            },
            "frozen_collector": {
                "path": "scalp_lead_shadow_v6.py",
                "git_blob_sha": sha,
            },
        }
        self.threshold = {
            "collector_path": "scalp_lead_shadow_v6.py",
            "collector_git_blob_sha": sha,
            "qualification_constants": dict(EXPECTED),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def _run_suite(self, **overrides):
        args = {
            "active_branch": "active-v6",
            "work_branch": "research-safe",
            "collector_path": str(self.collector),
            "active_start_command": "python scalp_lead_shadow_v6.py",
            "provenance_lock": self.provenance,
            "threshold_lock": self.threshold,
            "changed_paths": ["research_safety/new_audit.py"],
        }
        args.update(overrides)
        return run_suite(**args)

    def test_happy_path_passes(self):
        result = self._run_suite()
        self.assertTrue(result["ok"])
        self.assertEqual(result["thresholds"]["locked_constant_count"], 11)

    def test_active_branch_as_work_branch_fails(self):
        with self.assertRaises(PreflightError):
            self._run_suite(work_branch="active-v6")

    def test_cross_lock_blob_mismatch_fails_closed(self):
        bad = dict(self.threshold)
        bad["collector_git_blob_sha"] = "0" * 40
        with self.assertRaises(SafetySuiteError):
            self._run_suite(threshold_lock=bad)

    def test_out_of_scope_change_blocks_suite(self):
        result = self._run_suite(changed_paths=["scalp_lead_shadow_v6.py"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["scope"]["blocked"][0]["reason"], "protected runtime/config path")

    def test_threshold_drift_blocks_suite(self):
        self.collector.write_text(COLLECTOR.replace("V6_MAX_ASK = 0.45", "V6_MAX_ASK = 0.46"), encoding="utf-8")
        with self.assertRaises(PreflightError):
            self._run_suite()

    def test_start_command_drift_fails(self):
        with self.assertRaises(PreflightError):
            self._run_suite(active_start_command="python something_else.py")


if __name__ == "__main__":
    unittest.main()
