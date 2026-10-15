"""Offline fixtures for one-shot EARLY-native-data read-only feasibility only."""
import unittest
from candidates.early_feasibility_20261014.public_probe import evaluate


def sample():
    coverage = dict(signal_only=True, orders=False,
                    contracts=[
                        dict(opened=1792000000,ticker="KXBTC15M-FIXTURE",
                             observations=100,unavailable=0,missing=0,
                             signals=1,settlement_status="AUTHORITATIVE",
                             settlement=dict(status="AUTHORITATIVE",
                                             ticker="KXBTC15M-FIXTURE",
                                             open_ts=1792000000,side="UP")),
                        dict(opened=1792000900,ticker="KXBTC15M-EMPTY",
                             observations=20,unavailable=5,missing=1,
                             signals=0,settlement_status="PENDING",
                             settlement=None)])
    view = dict(status="AVAILABLE", signal_only=True, orders=False,
                early=dict(side="UP",guidance="WATCH"),
                final=dict(side="UP",ready=False),
                prices=dict(up_bid=.41,up_ask=.43,down_bid=.55,down_ask=.58),
                native_sequence=23, feature_cutoff=1792000920.0,
                origin=dict(origin_id="fixture"), management=dict(state="WATCH"))
    return coverage,view


class ReadonlyFeasibility(unittest.TestCase):
    def test_live_interface_shapes_not_misreported_as_full_early_grading(self):
        c,v=sample()
        r=evaluate(c,v)
        self.assertTrue(r["access_confirmed"])
        self.assertEqual(r["status"],"EXISTING_JOURNAL_ACCESSIBLE_NEEDS_RAW_RECEIPTS")
        self.assertEqual(r["coverage"]["official_results"],1)
        self.assertEqual(r["coverage"]["pending_results"],1)
        self.assertEqual(r["coverage"]["missing_or_partial"],1)
        self.assertTrue(r["latest_view"]["fields"]["bid_ask_paired"])
        self.assertFalse(r["ready_to_grade_early"])
        self.assertFalse(r["native_event_bodies_exported"])
        self.assertEqual(r["requests"],2)

    def test_stale_latest_view_does_not_invent_quotes(self):
        c,v=sample()
        v={"status":"UNAVAILABLE","reason":"SOURCE_EXPIRED",
           "signal_only":True,"orders":False}
        r=evaluate(c,v)
        self.assertTrue(r["access_confirmed"])
        self.assertFalse(r["latest_view"]["fields"]["bid_ask_paired"])
        self.assertFalse(r["ready_to_grade_early"])

    def test_lookalike_official_label_does_not_count(self):
        c,v=sample()
        c["contracts"][0]["settlement"]["ticker"]="OTHER"
        r=evaluate(c,v)
        self.assertFalse(r["access_confirmed"])
        self.assertEqual(r["coverage"]["official_results"],0)
        self.assertIn("UNLINKED_OFFICIAL_SETTLEMENT",r["defects"])

    def test_no_market_observations_is_not_feasibility(self):
        c,v=sample()
        c["contracts"]=[]
        r=evaluate(c,v)
        self.assertFalse(r["access_confirmed"])
        self.assertFalse(r["ready_to_grade_early"])

    def test_orders_or_untrusted_source_fail_closed(self):
        c,v=sample()
        v["orders"]=True
        with self.assertRaisesRegex(ValueError,"SIGNAL_ONLY_IDENTITY"):
            evaluate(c,v)
        c,v=sample()
        c["signal_only"]=False
        with self.assertRaisesRegex(ValueError,"SIGNAL_ONLY_IDENTITY"):
            evaluate(c,v)


if __name__ == "__main__":
    unittest.main()
