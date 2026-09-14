#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V1 as v1
import BTC15_DASHBOARD_COMBINED_SCALP_UI_V2 as v2


class CombinedScalpUiV2Tests(unittest.TestCase):
    def test_v2_changes_only_bridge_version_acceptance(self):
        html = "<html><body>" + v1.SCALP_ANCHOR + "</body></html>"
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.html"
            p.write_text(html, encoding="utf-8")
            v1.patch_combined(p)
            before = p.read_text(encoding="utf-8")
            changes = v2.patch_v2_compat(p)
            after = p.read_text(encoding="utf-8")
        self.assertIn("accept-combined-v3-v4", changes)
        self.assertIn(v2.NEW, after)
        self.assertNotIn(v2.OLD, after)
        self.assertEqual(before.count('id="btc15-combined-scalp-script"'), after.count('id="btc15-combined-scalp-script"'))
        self.assertIn("COUNTERTREND_SCALP", after)
        self.assertIn("validated 4¢ giveback", after)

    def test_v2_is_idempotent(self):
        html = "<html><body>" + v1.SCALP_ANCHOR + "</body></html>"
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.html"
            p.write_text(html, encoding="utf-8")
            v1.patch_combined(p)
            v2.patch_v2_compat(p)
            v2.patch_v2_compat(p)
            out = p.read_text(encoding="utf-8")
        self.assertEqual(out.count(v2.MARKER), 1)
        self.assertEqual(out.count(v2.NEW), 1)


if __name__ == "__main__":
    unittest.main()
