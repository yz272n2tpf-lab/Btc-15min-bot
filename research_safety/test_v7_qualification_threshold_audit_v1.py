import copy
import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "audit", HERE / "v7_qualification_threshold_audit_v1.py"
)
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)

VALUES = {
    "MOM_MIN_ASK": 0.07,
    "MOM_PREF_MAX": 0.30,
    "MOM_MAX_ASK": 0.45,
    "MOM_HIGH_BTC5": 20.0,
    "MOM_HIGH_BTC15": 25.0,
    "MOM_HIGH_BRTI5": 15.0,
    "MOM_HIGH_BRTI15": 5.0,
    "MOM_HIGH_ACCEL": 10.0,
    "MOM_HIGH_BTC30": 0.0,
    "REV_MIN_ASK": 0.03,
    "REV_MAX_ASK": 0.069999,
    "REV_MIN_LEFT": 120.0,
    "REV_BTC5_MIN": 8.0,
    "REV_BTC15_FLOOR": -15.0,
    "REV_ACCEL_MIN": 8.0,
    "REV_BRTI5_MIN": 4.0,
    "REV_BRTI_ACCEL_MIN": 4.0,
    "REV_ASK5_FLOOR": -0.01,
    "REV_ASK5_CEIL": 0.03,
    "REV_ASK15_CEIL": 0.04,
    "CONFIRM_WINDOW": 4.0,
    "CONFIRM_COUNT": 2,
}


def source(values=VALUES):
    return ("\n".join(f"{k} = {v!r}" for k, v in values.items()) + "\n").encode()


def lock_for(data):
    return {
        "collector_git_blob_sha": audit.git_blob_sha(data),
        "qualification_constants": copy.deepcopy(VALUES),
    }


class V7ThresholdAuditTests(unittest.TestCase):
    def test_exact_lock_passes(self):
        data = source()
        result = audit.audit_thresholds(data, lock_for(data))
        self.assertTrue(result["ok"])
        self.assertEqual(result["locked_constant_count"], 22)
        self.assertEqual(result["observed_constant_count"], 22)

    def test_changed_threshold_fails(self):
        data = source()
        lock = lock_for(data)
        lock["qualification_constants"]["REV_BTC5_MIN"] = 9.0
        result = audit.audit_thresholds(data, lock)
        self.assertFalse(result["ok"])
        self.assertEqual(result["changed"][0]["name"], "REV_BTC5_MIN")

    def test_missing_constant_in_collector_fails(self):
        values = dict(VALUES)
        del values["MOM_HIGH_BRTI15"]
        data = source(values)
        lock = lock_for(source())
        lock["collector_git_blob_sha"] = audit.git_blob_sha(data)
        result = audit.audit_thresholds(data, lock)
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing"], ["MOM_HIGH_BRTI15"])

    def test_duplicate_constant_fails(self):
        base = source()
        data = base + b"MOM_MIN_ASK = 0.07\n"
        lock = lock_for(base)
        lock["collector_git_blob_sha"] = audit.git_blob_sha(data)
        result = audit.audit_thresholds(data, lock)
        self.assertFalse(result["ok"])
        self.assertEqual(result["duplicate"], ["MOM_MIN_ASK"])

    def test_nonliteral_constant_fails(self):
        text = source().decode().replace(
            "REV_ACCEL_MIN = 8.0", "REV_ACCEL_MIN = float('8.0')"
        )
        data = text.encode()
        lock = lock_for(source())
        lock["collector_git_blob_sha"] = audit.git_blob_sha(data)
        result = audit.audit_thresholds(data, lock)
        self.assertFalse(result["ok"])
        self.assertEqual(result["nonliteral"], ["REV_ACCEL_MIN"])

    def test_blob_mismatch_fails_even_if_constants_match(self):
        data = source()
        lock = lock_for(data)
        lock["collector_git_blob_sha"] = "0" * 40
        result = audit.audit_thresholds(data, lock)
        self.assertFalse(result["ok"])
        self.assertFalse(result["collector_blob_matches"])

    def test_lock_cannot_omit_frozen_constant(self):
        data = source()
        lock = lock_for(data)
        del lock["qualification_constants"]["REV_MIN_LEFT"]
        with self.assertRaises(audit.ThresholdAuditError):
            audit.audit_thresholds(data, lock)

    def test_lock_cannot_add_unapproved_constant(self):
        data = source()
        lock = lock_for(data)
        lock["qualification_constants"]["HORIZON"] = 180
        with self.assertRaises(audit.ThresholdAuditError):
            audit.audit_thresholds(data, lock)


if __name__ == "__main__":
    unittest.main()
