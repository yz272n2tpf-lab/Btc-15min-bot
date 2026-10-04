import copy
import unittest
from completeness_diagnostics import lane_diagnostic, diagnose


def row():
    return dict(missing=['JOURNAL_MISSING_OR_PARTIAL','UNAVAILABLE_INTERVALS'],
        coverage=dict(first_at=1,last_at=899,settlement_status='AUTHORITATIVE'),
        opened=0,closed=900,observation_count=900,unavailable_publications=1,
        publication_gaps=[],unavailable_observations=[dict(reason='TIMESTAMPED_QUOTES_UNAVAILABLE')],
        settled=True,fully_scoreable=False,final=dict(calls=[]))


class DiagnosticsTests(unittest.TestCase):
    def test_recorded_unavailable_is_not_storage_loss_or_pass(self):
        r=row(); before=copy.deepcopy(r); d=lane_diagnostic(r)
        self.assertTrue(d['observation_schedule_covered'])
        self.assertEqual(d['source_availability']['unavailable'],1)
        self.assertFalse(d['strict_fully_scoreable'])
        self.assertEqual(r,before)

    def test_edges_and_gaps_still_block_schedule_coverage(self):
        for reason in ('INCOMPLETE_WINDOW_EDGES','OBSERVATION_GAP_OR_TIME_REVERSAL',
                       'COVERAGE_CENSUS_MISMATCH','ORIGIN_NOT_IN_SNAPSHOT','UNRESOLVED_SCALP_PATH'):
            r=row();r['missing'].append(reason)
            self.assertFalse(lane_diagnostic(r)['observation_schedule_covered'])

    def test_unexplained_flag_stays_blocked(self):
        r=row();r['missing']=['JOURNAL_MISSING_OR_PARTIAL'];r['unavailable_publications']=0
        self.assertIn('UNEXPLAINED_JOURNAL_PARTIAL_FLAG',lane_diagnostic(r)['observation_limitations'])

    def test_absent_lane_is_not_reported_as_corrupt_census(self):
        r=row();r.update(coverage=None,observation_count=0,unavailable_publications=0,settled=False)
        r['missing'].append('COVERAGE_CENSUS_MISMATCH')
        d=lane_diagnostic(r)
        self.assertEqual(d['observation_state'],'NOT_IN_LANE_SNAPSHOT')
        self.assertEqual(d['observation_limitations'],['NOT_IN_LANE_SNAPSHOT'])

    def test_pending_is_separate_from_partial(self):
        r=row();r['settled']=False;r['coverage']['settlement_status']='PENDING_OR_NONBINARY'
        self.assertEqual(lane_diagnostic(r)['settlement_state'],'PENDING_OR_NONBINARY')

    def test_independent_calls_are_deduplicated_by_contract_not_publication(self):
        r=row();call=dict(publication_id='a',signal_ts=480,independent_final={'side':'UP'},correct=True,ref={})
        r['final']['calls']=[call,dict(call,publication_id='b',signal_ts=490)]
        report=dict(evidence_class='FIXTURE',counts={'fully_scoreable_settled':0},
                    contracts=[dict(contract='C',opened=0,lanes={'main':r,'v81':row()})])
        before=copy.deepcopy(report);d=diagnose(report)
        self.assertEqual(d['lanes']['main']['observed_settled_final_publications'],2)
        self.assertEqual(d['lanes']['main']['settled_contracts_with_retained_final_calls'],1)
        self.assertEqual(d['strict_counts_unchanged']['fully_scoreable_settled'],0)
        self.assertEqual(report,before)


if __name__=='__main__':unittest.main()
