"""Regression checks for the EARLY three-signal issued-record projection.
Run: python -m unittest test_early_three_signal_display_v1.py
No Railway access, orders, data collection, or live dependencies.
"""
import unittest
from btc15_v2_product.trade_clarity import early_display_state, early_watch_detail


class EarlyDisplayTests(unittest.TestCase):
    def test_three_visible_actions(self):
        expected = {
            'ENTER': 'BUY', 'BUY': 'BUY',
            'HOLD': 'WATCH', 'WATCH': 'WATCH', 'PROTECT': 'WATCH',
            'EXIT': 'EXIT',
        }
        for internal, visible in expected.items():
            with self.subTest(internal=internal):
                self.assertEqual(early_display_state(internal), visible)

    def test_watch_subtypes(self):
        self.assertEqual(early_watch_detail('HOLD'), 'STABLE')
        self.assertEqual(early_watch_detail('WATCH'), 'MONITOR')
        self.assertEqual(early_watch_detail('PROTECT'), 'COULD_FLIP')
        self.assertIsNone(early_watch_detail('EXIT'))
        self.assertIsNone(early_watch_detail('BUY'))

    def test_unavailable_not_actionable(self):
        self.assertEqual(early_display_state(None), None)
        self.assertEqual(early_display_state('UNAVAILABLE'), 'UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
