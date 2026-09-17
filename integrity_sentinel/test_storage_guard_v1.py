import tempfile
import unittest
from unittest.mock import patch
from collections import namedtuple

from integrity_sentinel.storage_guard_v1 import storage_status

Usage = namedtuple("Usage", "total used free")


class StorageGuardTests(unittest.TestCase):
    def test_ok_warn_fail_boundaries(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("integrity_sentinel.storage_guard_v1.shutil.disk_usage", return_value=Usage(100, 50, 50)):
                self.assertEqual(storage_status(td)["state"], "OK")
            with patch("integrity_sentinel.storage_guard_v1.shutil.disk_usage", return_value=Usage(100, 85, 15)):
                self.assertEqual(storage_status(td)["state"], "WARN")
            with patch("integrity_sentinel.storage_guard_v1.shutil.disk_usage", return_value=Usage(100, 95, 5)):
                self.assertEqual(storage_status(td)["state"], "FAIL")

    def test_bad_thresholds_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                storage_status(td, fail_free_ratio=.5, warn_free_ratio=.4)


if __name__ == "__main__":
    unittest.main()
