import unittest
from structural_position_protection import held_probability, position_flags, qualify_asof, evaluate


class PositionProtectionTests(unittest.TestCase):
    def entry(self, **updates):
        return dict(dict(ticker='A',target=100.,side='UP',ask=.31,t=100.),**updates)

    def row(self, **updates):
        return dict(dict(ticker='A',target=100.,side='UP',fair=.92,brti_authority=True,
            brti_agrees=True,target_agrees=True,brti_gap=80.,signed_gap=80.,gap=80.,ratio=2.,
            left=4.,receipt_left=4.,t=100.,brti_source_t=99.),**updates)

    def test_probability_follows_original_position_after_preferred_flip(self):
        self.assertAlmostEqual(held_probability('DOWN',.92,'UP'),.08)
        self.assertAlmostEqual(held_probability('DOWN',.92,'DOWN'),.92)

    def test_confirmation_does_not_require_cheap_final_quote(self):
        f=position_flags(self.entry(),self.row(),.96,.97)
        self.assertTrue(f['final_confirmation'])
        self.assertFalse(f['authoritative_flip'])

    def test_qualified_opposite_side_is_not_original_confirmation(self):
        f=position_flags(self.entry(),self.row(side='DOWN',brti_gap=-80.,signed_gap=-80.),.20,.75)
        self.assertTrue(f['final_opposition']);self.assertTrue(f['authoritative_flip'])
        self.assertFalse(f['final_confirmation'])

    def test_flip_requires_authority_not_just_low_model_probability(self):
        f=position_flags(self.entry(),self.row(side='DOWN',brti_authority=False,brti_gap=-80.),.20,.75)
        self.assertTrue(f['model_flip']);self.assertFalse(f['authoritative_flip'])

    def test_guard_is_warning_without_forcing_thesis_exit(self):
        f=position_flags(self.entry(),self.row(signed_gap=50.,receipt_left=2.9),.60,.61)
        self.assertTrue(f['guard_3m']);self.assertFalse(f['authoritative_flip'])

    def test_profit_warning_requires_armed_observed_bid_and_deterioration(self):
        f=position_flags(self.entry(),self.row(fair=.70),.43,.48)
        self.assertTrue(f['profit_warning'])
        self.assertFalse(position_flags(self.entry(),self.row(fair=.70),.34,.38)['profit_warning'])
        self.assertFalse(position_flags(self.entry(),self.row(),.43,.48)['profit_warning'])

    def test_quote_time_rechecks_true_brti_age_and_no_future_main(self):
        self.assertTrue(qualify_asof(self.row(),103.,100.))
        self.assertFalse(qualify_asof(self.row(),105.,100.))
        self.assertFalse(qualify_asof(self.row(t=104.),103.,100.))
        self.assertFalse(qualify_asof(self.row(),103.,101.))

    def test_other_contract_or_target_cannot_inherit_position(self):
        for r in [self.row(ticker='B'),self.row(target=101.)]:
            with self.assertRaises(ValueError):position_flags(self.entry(),r,.5,.5)

    def test_stale_main_never_emits_hold_or_exit_and_outcomes_cannot_select_warning(self):
        e=self.entry();q=[dict(t=103.,target=100.,up_bid=.4,up_ask=.31)]
        m=dict(open_time='1970-01-01T00:00:00Z',close_time='1970-01-01T00:15:00Z',floor_strike=100.,result='yes')
        stale=evaluate(e,[self.row(brti_source_t=90.)],q,m)
        self.assertEqual(stale['events'],{})
        one=evaluate(e,[self.row(fair=.7)],q,m)
        two=evaluate(e,[self.row(fair=.7)],q,dict(m,result='no'))
        self.assertEqual({k:v['t'] for k,v in one['events'].items()}, {k:v['t'] for k,v in two['events'].items()})


if __name__=='__main__':unittest.main()
