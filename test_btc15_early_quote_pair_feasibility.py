"""Adversarial tests for exact native EARLY / later quote pairing (offline only)."""
import unittest
from copy import deepcopy
from candidates.early_feasibility_20261014.pair_probe import validate_pair

START=1790000000.
LATE=START+300


def fixture():
    v=dict(status='AVAILABLE',signal_only=True,orders=False,
           contract='KXBTC15M-TEST',native_sequence=42,published_ts=LATE,
           early=dict(guidance='PASS',conditions={'confidence':False}),
           final=dict(ready=False),prices=dict(up_bid=.30,up_ask=.32,down_bid=.67,down_ask=.69))
    q=dict(schema='BTC15_EXECUTABLE_QUOTE_R1',
           authority='PRICE_PRESENTATION_ONLY',status='AVAILABLE',
           signal_only=True,orders=False,
           official_identity=dict(contract='KXBTC15M-TEST',
                                  official_open=START,official_close=START+900),
           exchange_ts=LATE+1,accepted_ts=LATE+1.1,
           published_ts=LATE+1.2,served_ts=LATE+1.3,
           expires_at=LATE+7,up_bid=.40,up_ask=.41,down_bid=.58,down_ask=.60)
    return v,q


class ProspectivePair(unittest.TestCase):
    def test_real_later_quote_match_is_not_filled_trade(self):
        v,q=fixture()
        r=validate_pair(v,q)
        self.assertTrue(r['valid'])
        self.assertTrue(r['later_quote_source'])
        self.assertTrue(r['later_quote_accepted'])
        self.assertTrue(r['continuity_unproven'])
        self.assertTrue(r['manual_fill_unproven'])

    def test_quote_source_before_decision_is_not_called_later(self):
        v,q=fixture()
        q['exchange_ts']=LATE-.2
        q['accepted_ts']=LATE-.1
        q['published_ts']=LATE+.1
        q['served_ts']=LATE+.3
        q['expires_at']=LATE+5.8
        r=validate_pair(v,q)
        self.assertTrue(r['valid'])
        self.assertFalse(r['later_quote_source'])
        self.assertFalse(r['later_quote_accepted'])

    def test_contract_rollover_prevents_false_join(self):
        v,q=fixture()
        q['official_identity']['contract']='NEXT'
        self.assertEqual(validate_pair(v,q)['reason'],'CONTRACT_MISMATCH')

    def test_unavailable_or_missing_source_rejects_join(self):
        v,q=fixture()
        q['status']='UNAVAILABLE'
        self.assertEqual(validate_pair(v,q)['reason'],'SOURCE_UNAVAILABLE')
        v,q=fixture()
        q.pop('accepted_ts')
        self.assertEqual(validate_pair(v,q)['reason'],'QUOTE_CLOCK_MISSING')

    def test_crossed_book_and_untrusted_schema_rejected(self):
        v,q=fixture()
        q['up_ask']=.35
        self.assertEqual(validate_pair(v,q)['reason'],'CROSSED_OR_INVALID_BOOK')
        v,q=fixture()
        q['authority']='LIVE_FILL_CONFIRMED'
        self.assertEqual(validate_pair(v,q)['reason'],'QUOTE_PROJECTION_IDENTITY')

    def test_future_or_expired_quote_rejected(self):
        v,q=fixture()
        q['expires_at']=q['exchange_ts']+7
        self.assertEqual(validate_pair(v,q)['reason'],'QUOTE_CLOCK_INVALID')
        v,q=fixture()
        q['published_ts']=q['served_ts']+1
        self.assertEqual(validate_pair(v,q)['reason'],'QUOTE_CLOCK_INVALID')

    def test_missing_early_or_native_decision_is_not_pairable(self):
        v,q=fixture()
        v.pop('early')
        self.assertEqual(validate_pair(v,q)['reason'],'EARLY_DECISION_MISSING')
        v,q=fixture()
        v.pop('native_sequence')
        self.assertEqual(validate_pair(v,q)['reason'],'NATIVE_DECISION_CLOCK_MISSING')


if __name__=='__main__':
    unittest.main()
