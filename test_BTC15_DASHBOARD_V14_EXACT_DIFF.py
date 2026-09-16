#!/usr/bin/env python3
import unittest

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V13 as v13
import BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 as v14


class V14ExactGeneratedDiffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p13 = v13.build_dashboard()
        cls.v13_text = p13.read_text(encoding="utf-8", errors="replace")
        # Rebuild from V13 fresh inside V14, then capture patched output.
        p14 = v14.build_dashboard()
        cls.v14_text = p14.read_text(encoding="utf-8", errors="replace")

    def test_exact_allowed_delta_only(self):
        expected = self.v13_text
        self.assertEqual(expected.count(v14.OLD_BTC_COLOR_JS), 1)
        expected = expected.replace(v14.OLD_BTC_COLOR_JS, v14.NEW_BTC_COLOR_JS, 1)
        self.assertEqual(expected.count("</head>"), 1)
        expected = expected.replace("</head>", v14.V14_CSS + "\n</head>", 1)
        self.assertEqual(expected.count("</body>"), 1)
        expected = expected.replace("</body>", f"<!-- {v14.MARKER} -->\n</body>", 1)
        self.assertEqual(self.v14_text, expected)

    def test_no_existing_v13_marker_or_safety_count_changes(self):
        for anchor in v14.SAFETY_ANCHORS:
            self.assertEqual(self.v13_text.count(anchor), self.v14_text.count(anchor), anchor)

    def test_no_existing_dom_anchor_count_changes(self):
        for anchor in v14.REQUIRED_UNIQUE_ANCHORS:
            self.assertEqual(self.v13_text.count(anchor), 1, anchor)
            self.assertEqual(self.v14_text.count(anchor), 1, anchor)

    def test_no_new_visible_timer(self):
        self.assertEqual(self.v13_text.count('id="timerRemaining"'), self.v14_text.count('id="timerRemaining"'))
        self.assertEqual(self.v13_text.count('<span>Contract time left</span>'), 0)
        self.assertEqual(self.v14_text.count('<span>Contract time left</span>'), 0)

    def test_no_numeric_flip_risk_in_either_candidate(self):
        self.assertNotIn("flip_risk_percent", self.v13_text)
        self.assertNotIn("flip_risk_percent", self.v14_text)


if __name__ == "__main__":
    unittest.main()
