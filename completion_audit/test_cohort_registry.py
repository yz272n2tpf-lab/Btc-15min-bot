import copy
import unittest
from cohort_registry import validate, registry


class CommonUniverse(unittest.TestCase):
    def setUp(self):
        self.manifest = dict(registered_utc='2026-09-23T20:00:00Z', orders=False, signal_only=True,
                             windows=[dict(role='development', start_utc='2026-09-23T20:30:00Z',
                                           end_utc='2026-09-23T21:00:00Z', scheduled_slots=2)])

    def test_missing_and_no_call_contracts_remain_in_denominator(self):
        official = [dict(ticker='KXBTC15M-EXAMPLE', open_time='2026-09-23T20:30:00Z',
                         close_time='2026-09-23T20:45:00Z')]
        rows = registry(validate(self.manifest)['windows'][0], official)
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(x['observed'] for x in rows), 0)
        self.assertFalse(rows[1]['official_identified'])
        self.assertTrue(all(x['retained_in_scheduled_denominator'] for x in rows))

    def test_no_retroactive_registration(self):
        self.manifest['registered_utc'] = '2026-09-23T20:30:00Z'
        with self.assertRaises(ValueError): validate(self.manifest)

    def test_roles_cannot_overlap(self):
        second = copy.deepcopy(self.manifest['windows'][0]); second['role'] = 'holdout'
        self.manifest['windows'].append(second)
        with self.assertRaises(ValueError): validate(self.manifest)

    def test_duplicate_official_slot_is_not_silently_deduplicated(self):
        a = dict(ticker='KXBTC15M-A',open_time='2026-09-23T20:30:00Z',close_time='2026-09-23T20:45:00Z')
        with self.assertRaises(ValueError): registry(self.manifest['windows'][0], [a,dict(a,ticker='KXBTC15M-B')])

    def test_naive_and_misaligned_clocks_are_rejected(self):
        for value in ('2026-09-23T20:30:00','2026-09-23T20:31:00Z'):
            self.manifest['windows'][0]['start_utc']=value
            with self.assertRaises(ValueError): validate(self.manifest)


if __name__ == '__main__': unittest.main()
