import copy
import hashlib
import unittest

from v6_qualification_threshold_audit_v1 import ThresholdAuditError, audit_thresholds


BASE = """\
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


def lock_for(text: str) -> dict:
    data = text.encode()
    return {
        "collector_git_blob_sha": blob_sha(data),
        "qualification_constants": copy.deepcopy(EXPECTED),
    }


class ThresholdAuditTests(unittest.TestCase):
    def test_exact_lock_passes(self):
        result = audit_thresholds(BASE.encode(), lock_for(BASE))
        self.assertTrue(result["ok"])
        self.assertEqual(result["observed_constant_count"], 11)

    def test_changed_constant_fails(self):
        text = BASE.replace("V6_MAX_ASK = 0.45", "V6_MAX_ASK = 0.46")
        lock = lock_for(text)
        lock["qualification_constants"] = copy.deepcopy(EXPECTED)
        result = audit_thresholds(text.encode(), lock)
        self.assertFalse(result["ok"])
        self.assertEqual(result["changed"][0]["name"], "V6_MAX_ASK")

    def test_missing_constant_fails(self):
        text = BASE.replace("V6_HIGH_BTC30 = 0.0\n", "")
        lock = lock_for(text)
        result = audit_thresholds(text.encode(), lock)
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing"], ["V6_HIGH_BTC30"])

    def test_duplicate_assignment_fails(self):
        text = BASE + "V6_MIN_ASK = 0.07\n"
        lock = lock_for(text)
        result = audit_thresholds(text.encode(), lock)
        self.assertFalse(result["ok"])
        self.assertEqual(result["duplicate"], ["V6_MIN_ASK"])

    def test_nonliteral_assignment_fails(self):
        text = BASE.replace("V6_HIGH_ACCEL = 10.0", "V6_HIGH_ACCEL = float('10.0')")
        lock = lock_for(text)
        result = audit_thresholds(text.encode(), lock)
        self.assertFalse(result["ok"])
        self.assertEqual(result["nonliteral"], ["V6_HIGH_ACCEL"])

    def test_blob_mismatch_fails_even_when_constants_match(self):
        lock = lock_for(BASE)
        changed_bytes = (BASE + "# harmless-looking drift\n").encode()
        result = audit_thresholds(changed_bytes, lock)
        self.assertFalse(result["ok"])
        self.assertFalse(result["collector_blob_matches"])
        self.assertEqual(result["changed"], [])

    def test_incomplete_lock_fails_closed(self):
        lock = lock_for(BASE)
        del lock["qualification_constants"]["V6_HIGH_BTC30"]
        with self.assertRaises(ThresholdAuditError):
            audit_thresholds(BASE.encode(), lock)


if __name__ == "__main__":
    unittest.main()
