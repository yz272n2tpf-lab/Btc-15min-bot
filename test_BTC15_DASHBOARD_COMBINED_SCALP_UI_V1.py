#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

import BTC15_DASHBOARD_INLINE_SCALP_V1 as v1
from BTC15_DASHBOARD_COMBINED_SCALP_UI_V1 import patch_combined, FEED_URL


class CombinedScalpUiV1Tests(unittest.TestCase):
    def test_patch_replaces_legacy_hook_and_script(self):
        html=(
            '<html><body>'
            + v1.SCALP_HOOK
            + '<script id="v81-inline-scalp-script">window.old=true;</script>'
            + '</body></html>'
        )
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.html';p.write_text(html,encoding='utf-8')
            changes=patch_combined(p)
            out=p.read_text(encoding='utf-8')
        self.assertIn('combined-scalp-hook',changes)
        self.assertIn('legacy-v81-script-removed',changes)
        self.assertIn('renderCombinedScalpInline(d)',out)
        self.assertNotIn('renderV81ScalpInline(d)',out)
        self.assertNotIn('id="v81-inline-scalp-script"',out)
        self.assertEqual(out.count('id="btc15-combined-scalp-script"'),1)
        self.assertIn(FEED_URL,out)

    def test_patch_is_idempotent_about_combined_script(self):
        html='<html><body>'+v1.SCALP_ANCHOR+'</body></html>'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.html';p.write_text(html,encoding='utf-8')
            patch_combined(p);patch_combined(p)
            out=p.read_text(encoding='utf-8')
        self.assertEqual(out.count('id="btc15-combined-scalp-script"'),1)
        self.assertEqual(out.count('renderCombinedScalpInline(d)'),1)

    def test_safety_strings_present(self):
        html='<html><body>'+v1.SCALP_ANCHOR+'</body></html>'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.html';p.write_text(html,encoding='utf-8')
            patch_combined(p);out=p.read_text(encoding='utf-8')
        self.assertIn('BTC15_COMBINED_STATE_BRIDGE_V3',out)
        self.assertIn('numeric_flip_risk_validated!==false',out)
        self.assertIn('order_action!==null',out)
        self.assertIn('d.orders!==false',out)
        self.assertIn('SCALP WAIT',out)
        self.assertIn('COUNTERTREND_SCALP',out)
        self.assertIn('validated 4¢ giveback',out)
        self.assertNotIn('flip_risk_percent',out)


if __name__=='__main__':unittest.main()
