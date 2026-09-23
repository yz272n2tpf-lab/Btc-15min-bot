import copy
import unittest
from summarize_passive_acceptance import analyze, stamp


class PassiveEvidenceAccounting(unittest.TestCase):
    def setUp(self):
        self.start=stamp('2026-09-23T12:30:00Z')
        self.end=stamp('2026-09-23T13:00:00Z')
        self.markets=[dict(ticker='KXBTC15M-A',open_time='2026-09-23T12:30:00Z',close_time='2026-09-23T12:45:00Z',status='finalized',result='yes'),
                      dict(ticker='KXBTC15M-B',open_time='2026-09-23T12:45:00Z',close_time='2026-09-23T13:00:00Z',status='finalized',result='no')]
        now='2026-09-23T12:38:00+00:00'
        self.state=dict(generated_utc=now,source_timestamp_utc=now,contract='KXBTC15M-A',
                        health=dict(paired_quotes=True),safety=dict(read_only=True,orders_enabled=False),
                        timer=dict(seconds_left=420),market=dict(brti_ready=True,brti_value=85000.,brti_age_seconds=1,up_ask=.4,down_ask=.61),
                        parity=dict(status='PASS',contract='KXBTC15M-A',api_contract='KXBTC15M-A',timestamp_utc=now),
                        final=dict(ready=True,side='UP',confidence=.94),early=dict(ready=False),scalp=dict(ready=False))

    def records(self,state):
        return [dict(service='main',start_epoch=stamp(state['generated_utc']).timestamp(),state=state)]

    def test_no_call_contract_stays_in_denominator_and_first_call_is_frozen(self):
        later=copy.deepcopy(self.state)
        later['generated_utc']='2026-09-23T12:38:01+00:00'
        later['final']['side']='DOWN'
        r=analyze(self.records(self.state)+self.records(later),self.start,self.end,self.markets)
        final=r['lanes']['final']
        self.assertEqual(final['official_universe_n'],2)
        self.assertEqual(final['strict_coverage'],.5)
        self.assertEqual(final['correct'],1)
        self.assertEqual(final['calls'][0]['side'],'UP')
        self.assertFalse(r['certified_performance'])

    def test_raw_winner_is_not_certified_when_parity_waits_or_source_is_future(self):
        for defect in ('parity','future'):
            s=copy.deepcopy(self.state)
            if defect=='parity':s['parity']['status']='WAIT'
            else:s['source_timestamp_utc']='2026-09-23T12:38:01+00:00'
            r=analyze(self.records(s),self.start,self.end,self.markets)
            self.assertEqual(r['lanes']['final']['raw_ready_contracts'],1)
            self.assertEqual(r['lanes']['final']['strict_qualified_contracts'],0)
            self.assertIsNone(r['lanes']['final']['accuracy'])

    def test_empty_observation_is_not_signal_only_acceptance(self):
        r=analyze([],self.start,self.end,self.markets)
        self.assertFalse(r['main']['signal_only_all'])


if __name__=='__main__':unittest.main()
