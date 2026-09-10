import unittest

from v6_runtime_provenance_audit import audit, git_blob_sha


SOURCE = b'''\nV6_MIN_ASK = 0.07\nV6_PREFERRED_MAX = 0.30\nV6_MAX_ASK = 0.45\nV6_CONFIRM_WINDOW = 4.0\nV6_CONFIRM_COUNT = 2\nV6_HIGH_BTC5 = 20.0\nV6_HIGH_BTC15 = 25.0\nV6_HIGH_BRTI5 = 15.0\nV6_HIGH_BRTI15 = 5.0\nV6_HIGH_ACCEL = 10.0\nV6_HIGH_BTC30 = 0.0\n'''

FROZEN = {
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


def make_lock():
    return {
        "deployment_source_branch": "scalp-lead-research-v3",
        "deployment_source_commit": "locked123",
        "collectors": [{"path": "scalp_lead_shadow_v6.py", "github_blob_sha": git_blob_sha(SOURCE)}],
        "v6_frozen_constants": FROZEN,
    }


def make_snapshot():
    return {
        "service_name": "scalp-lead-v6",
        "source_repo": "yz272n2tpf-lab/Btc-15min-bot",
        "expected_repo": "yz272n2tpf-lab/Btc-15min-bot",
        "source_branch": "scalp-lead-research-v3",
        "deployment_commit": "locked123",
        "start_command": "python scalp_lead_shadow_v6.py",
    }


class RuntimeProvenanceAuditTests(unittest.TestCase):
    def test_exact_lock_passes(self):
        result = audit(make_lock(), make_snapshot(), SOURCE)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["failures"], [])

    def test_branch_tip_can_advance_when_collector_is_identical(self):
        snapshot = make_snapshot()
        snapshot["deployment_commit"] = "newtip456"
        result = audit(make_lock(), snapshot, SOURCE)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(any("branch tip advanced" in x for x in result["info"]))

    def test_collector_drift_fails(self):
        changed = SOURCE.replace(b"V6_MIN_ASK = 0.07", b"V6_MIN_ASK = 0.08")
        result = audit(make_lock(), make_snapshot(), changed)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("collector blob drift" in x for x in result["failures"]))
        self.assertTrue(any("constant drift V6_MIN_ASK" in x for x in result["failures"]))

    def test_wrong_start_command_fails(self):
        snapshot = make_snapshot()
        snapshot["start_command"] = "python scalp_lead_shadow_v5.py"
        result = audit(make_lock(), snapshot, SOURCE)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("start_command" in x for x in result["failures"]))

    def test_wrong_branch_fails(self):
        snapshot = make_snapshot()
        snapshot["source_branch"] = "main"
        result = audit(make_lock(), snapshot, SOURCE)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("source_branch" in x for x in result["failures"]))


if __name__ == "__main__":
    unittest.main()
