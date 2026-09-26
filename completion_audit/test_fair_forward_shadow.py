import copy
import unittest
from fair_forward_shadow import gates


class FrozenNumericGates(unittest.TestCase):
    def setUp(self):
        self.row=dict(observed_utc='2026-09-23T20:38:00Z',features={'dist_over_range5':1.2},inputs=dict(
            target=85000.,btc_price=85080.,brti_value=85075.,brti_source_ts_ms=1790195879000,
            close_utc='2026-09-23T20:45:00Z',up_bid=.34,up_ask=.35,down_bid=.65,down_ask=.66,
            quote_transport='timestamped_contiguous_ws',quote_validation_utc='2026-09-23T20:38:00Z'))
    def test_existing_gates_overlap_without_removing_a_family(self):
        r=gates(self.row,.94,.06)
        self.assertEqual(r['raw_gates'],dict(early=True,final=True,scalp=True))
        self.assertTrue(r['input_qualified']);self.assertFalse(r['actual_main_publication_verified'])
    def test_early_price_preference_is_preserved(self):
        self.row['inputs']['up_ask']=.46
        r=gates(self.row,.94,.06);self.assertFalse(r['raw_gates']['early']);self.assertTrue(r['raw_gates']['final'])
    def test_final_authority_disagreement_does_not_remove_early(self):
        self.row['inputs']['brti_value']=84980.
        r=gates(self.row,.94,.06);self.assertFalse(r['raw_gates']['final']);self.assertTrue(r['raw_gates']['early'])
    def test_stale_source_blocks_all_strict_candidate_gates(self):
        self.row['inputs']['brti_source_ts_ms']-=6000
        r=gates(self.row,.94,.06);self.assertFalse(any(r['qualified_input_gates'].values()))
    def test_down_direction_is_symmetric(self):
        self.row['inputs'].update(btc_price=84920.,brti_value=84925.,up_bid=.65,up_ask=.66,down_bid=.34,down_ask=.35)
        r=gates(self.row,.06,.94);self.assertEqual(r['side'],'DOWN');self.assertTrue(all(r['raw_gates'].values()))
    def test_invalid_quote_cannot_be_a_qualified_final(self):
        self.row['inputs']['up_bid']=1.1
        with self.assertRaises(ValueError):gates(self.row,.94,.06)


if __name__=='__main__':unittest.main()
