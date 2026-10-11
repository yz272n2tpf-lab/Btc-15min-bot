import copy,json,unittest
from pathlib import Path
from audit.existing_evidence_20261011.evaluate_recovered_exports import check_managed_publication

class RecoveredPublications(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=json.loads(Path(__file__).with_name('incident_selected_publications.json').read_text())
        cls.origin=cls.p['entry']['state']['origin']

    def test_actual_four_managed_publications_bind_original_origin(self):
        for tag,bid in [('first_protect',.67),('bid70',.70),('peak84',.84),('exit79',.79)]:
            with self.subTest(tag=tag):self.assertEqual(check_managed_publication(self.p[tag],self.origin)['up_bid'],bid)

    def test_wrong_contract_epoch_and_side_bid_fail(self):
        for key,value in [('ticker','WRONG'),('epoch','OTHER'),('up_bid',.01)]:
            p=copy.deepcopy(self.p['bid70']);p['state']['path']['last_quote'][key]=value
            with self.assertRaises(AssertionError):check_managed_publication(p,self.origin)

    def test_future_quote_later_validation_and_stale_display_fail(self):
        for field in ['source_ts_ms','validated_at_ms']:
            p=copy.deepcopy(self.p['bid70']);p['state']['path']['last_quote'][field]=p['state']['published_ts']*1000+1000
            with self.assertRaises(AssertionError):check_managed_publication(p,self.origin)
        p=copy.deepcopy(self.p['bid70']);p['state']['expires_at']=p['state']['published_ts']
        with self.assertRaises(AssertionError):check_managed_publication(p,self.origin)

    def test_protection_exit_keeps_gap_and_nonfill_disclosure(self):
        terminal=self.p['exit79']['state']['terminal']
        self.assertFalse(terminal['complete_path']);self.assertTrue(terminal['path']['missing'])
        self.assertEqual(terminal['reason'],'ARM5_GIVEBACK4')
        self.assertAlmostEqual(terminal['path']['mfe'],.24)
        self.assertAlmostEqual(terminal['path']['giveback'],.05)
        self.assertIsNone(terminal['realized_profit']);self.assertIsNone(terminal['manual_fill'])

if __name__=='__main__':unittest.main()
