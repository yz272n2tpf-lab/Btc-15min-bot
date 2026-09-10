import unittest

from v7_app_state_replay_v1 import parse_jsonl, replay_events


class AppStateReplayTests(unittest.TestCase):
    def test_valid_lifecycle(self):
        common = {"ticker": "A", "lane": "MOMENTUM_EXPANSION", "side": "UP"}
        report = replay_events([
            {**common, "event": "watch"},
            {**common, "event": "entry"},
            {**common, "event": "hold"},
            {**common, "event": "take_profit"},
            {**common, "event": "exit"},
        ])
        self.assertTrue(report["ok"])
        self.assertEqual(report["active_states"]["A|MOMENTUM_EXPANSION|UP"], "EXIT")
        self.assertFalse(report["orders_enabled"])

    def test_streams_are_isolated(self):
        report = replay_events([
            {"ticker": "A", "lane": "MOMENTUM_EXPANSION", "side": "UP", "event": "watch"},
            {"ticker": "B", "lane": "ULTRA_CHEAP_REVERSAL", "side": "DOWN", "event": "entry"},
            {"ticker": "A", "lane": "MOMENTUM_EXPANSION", "side": "UP", "event": "entry"},
        ])
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["active_states"]), 2)

    def test_invalid_transition_is_reported_without_mutating_prior_state(self):
        common = {"ticker": "A", "lane": "MOMENTUM_EXPANSION", "side": "UP"}
        report = replay_events([{**common, "event": "watch"}, {**common, "event": "hold"}])
        self.assertFalse(report["ok"])
        self.assertEqual(report["events_accepted"], 1)
        self.assertEqual(report["active_states"]["A|MOMENTUM_EXPANSION|UP"], "SCALP WATCH")

    def test_missing_identity_fails_closed(self):
        report = replay_events([{"lane": "MOMENTUM_EXPANSION", "side": "UP", "event": "watch"}])
        self.assertFalse(report["ok"])
        self.assertEqual(report["events_accepted"], 0)

    def test_execution_field_still_forbidden(self):
        report = replay_events([{"ticker": "A", "lane": "MOMENTUM_EXPANSION", "side": "UP", "event": "entry", "quantity": 1}])
        self.assertFalse(report["ok"])

    def test_jsonl_parser(self):
        events = parse_jsonl('{"ticker":"A","lane":"MOMENTUM_EXPANSION","side":"UP","event":"watch"}\n')
        self.assertEqual(len(events), 1)
        with self.assertRaises(ValueError):
            parse_jsonl('[]')


if __name__ == "__main__":
    unittest.main()
