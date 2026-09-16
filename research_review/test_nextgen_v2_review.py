"""Regression tests for an independent reviewer; frozen scorer builds fixtures only."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shadow_diagnostics'))
import scalp_nextgen_shadow_v2 as frozen
from test_scalp_nextgen_shadow_v2 import fixture_rows
import nextgen_v2_review as review

MANIFEST = json.loads(review.MANIFEST_PATH.read_text())
CAPTURED = '2026-09-17T00:16:00+00:00'


def bundle():
    # Offline fixture generation does not fetch data or change the live collector.
    s = frozen.analyze_rows(fixture_rows(), sha='a'*64, cutoff_text=MANIFEST['cutoff_utc'], expected_code_sha256=MANIFEST['code_sha256'])
    assert s['ok'], s
    a = {k:s[k] for k in ('version','window_id','source_sha256','audit_records')}
    a.update(frozen.SAFETY)
    a['ok'] = True
    s.pop('audit_records')
    s.update(last_poll_utc=CAPTURED, source_latest_utc=CAPTURED)
    b = {'captured_utc': CAPTURED, 'manifest': MANIFEST, 'state': s, 'audit': a}
    return rehash(b)


def rehash(b):
    for label in ('state','audit'): b[label+'_sha256'] = review.canonical_sha(b[label])
    return b


def record(cid, contract='C', protected=True, ask=.50, net1=1., idx=1):
    return {'candidate_id':cid,'contract':contract,'opportunity_index':idx,
            'entry_ask':ask,'protected_exit_observed':protected,
            'one_lot_taker_taker_net_c':net1 if protected else None,
            'ten_lot_taker_taker_net_c':net1+1 if protected else None,'plus10':True}


class IndependentValidation(unittest.TestCase):
    def test_frozen_scorer_fixture_validates_and_all_28_comparisons_exist(self):
        b = bundle()
        self.assertEqual(review.validate(b,MANIFEST),[])
        r = review.build_review(b,MANIFEST)
        self.assertEqual(r['status'],'EARLY_DATA')
        self.assertEqual(len(r['comparisons']),28)
        self.assertFalse(r['winner_selected'])
        self.assertFalse(r['review_floor_met'])
        json.dumps(r,allow_nan=False)

    def test_changed_window_code_or_cutoff_fails_closed(self):
        for key in ('version','window_id','code_sha256','cutoff_utc'):
            b=bundle(); b['state'][key]='wrong'; rehash(b)
            r=review.build_review(b,MANIFEST)
            self.assertFalse(r['valid_snapshot'],key)
            self.assertEqual(r['comparisons'],[])

    def test_safety_and_missing_lane_are_independently_rejected(self):
        b=bundle(); b['audit']['orders']=True; rehash(b)
        self.assertTrue(review.validate(b,MANIFEST))
        b=bundle(); del b['audit']['audit_records']['selective_pullback_v2']['V1_LE35_60S']; rehash(b)
        self.assertTrue(review.validate(b,MANIFEST))

    def test_duplicate_opportunities_fail_even_when_signal_total_is_rewritten(self):
        b=bundle(); family='candidate_verify_v2'; lane='V2_DYNAMIC_CAUSAL'
        rows=b['audit']['audit_records'][family][lane]
        rows.append(copy.deepcopy(rows[0]))
        b['state'][family][lane]['signals']=len(rows)
        rehash(b)
        self.assertTrue(any('duplicate' in x for x in review.validate(b,MANIFEST)))

    def test_equal_exit_counts_do_not_hide_changed_exit_times(self):
        b=bundle()
        row=b['audit']['audit_records']['watch_exit_v2']['V2_FALLING_TREND'][0]
        row['exit_time_sec']+=1
        row['lead']+=1
        rehash(b)
        self.assertTrue(any('frozen exit/economics changed' in x for x in review.validate(b,MANIFEST)))

    def test_published_profit_must_match_audit(self):
        b=bundle()
        b['state']['candidate_verify_v2']['V1_IMMEDIATE']['one_lot_taker_taker_avg_net_c']=99
        rehash(b)
        self.assertTrue(any('economics mismatch' in x for x in review.validate(b,MANIFEST)))

    def test_premature_readiness_and_stale_source_are_rejected(self):
        b=bundle(); b['state']['evidence_readiness']['sample_ready']=True; rehash(b)
        self.assertTrue(any('readiness' in x for x in review.validate(b,MANIFEST)))
        b=bundle(); b['state']['source_latest_utc']='2026-09-16T20:00:00+00:00'; rehash(b)
        self.assertTrue(any('stale' in x for x in review.validate(b,MANIFEST)))

    def test_saved_digest_detects_modified_bundle(self):
        b=bundle(); b['audit']['audit_records']['scalp2_economics_v2']['CONTROL_V1_SCALP2'][0]['entry_ask']=.01
        self.assertTrue(any('digest mismatch' in x for x in review.validate(b,MANIFEST)))

    def test_archived_snapshot_uses_capture_time_not_today(self):
        b=bundle()
        self.assertEqual(review.validate(b,MANIFEST),[])
        self.assertTrue(review.validate(b,MANIFEST,as_of=datetime(2026,9,19,tzinfo=timezone.utc)))

    def test_quiet_full_contracts_remain_in_denominator(self):
        r=review.build_review(bundle(),MANIFEST)
        # The fixture's OLD contract is after this deployment's 22:30 cutoff;
        # both quiet contracts therefore belong in this window's denominator.
        self.assertEqual(r['future_full_contracts'],3)
        self.assertEqual(r['serial_signals'],2)
        self.assertEqual(r['remaining_full_contracts'],97)


class ComparisonAccounting(unittest.TestCase):
    def test_matching_uses_identity_not_row_order(self):
        control=[record('A',net1=10),record('B',net1=20)]
        shadow=[record('B',net1=23),record('A',net1=12)]
        r=review.economic_comparison(shadow,control)
        self.assertEqual(r['one_lot_paired_net_delta_c'],2.5)
        self.assertEqual(r['both_protected_exits'],2)
        self.assertEqual(r['both_protected_exit_contracts'],1)

    def test_filter_does_not_claim_improved_profit_on_identical_retained_trades(self):
        control=[record('A',net1=10),record('B',net1=-5)]
        r=review.economic_comparison(control[:1],control)
        self.assertEqual(r['one_lot_paired_net_delta_c'],0)
        self.assertEqual(r['control_only_entries'],1)
        self.assertEqual(r['one_lot_control_only_avg_net_c'],-5)
        self.assertEqual(r['control_only_observed_plus10'],1)

    def test_missing_exits_never_become_zero_net(self):
        control=[record('A',protected=False)]
        shadow=[record('A',net1=4)]
        r=review.economic_comparison(shadow,control)
        self.assertIsNone(r['one_lot_paired_net_delta_c'])
        self.assertEqual(r['both_protected_exits'],0)
        self.assertEqual(r['only_shadow_protected_exit_on_matched_entry'],1)

    def test_lost_entry_does_not_imply_lost_contract_coverage(self):
        controls=[record('A',contract='C'),record('B',contract='C')]
        r=review.economic_comparison(controls[:1],controls,full_contracts=2)
        self.assertEqual(r['control_only_entries'],1)
        self.assertEqual(r['contracts_lost_vs_control'],0)
        self.assertEqual(r['signal_retention_vs_control'],.5)
        self.assertEqual(r['shadow_true_contract_coverage'],.5)

    def test_watch_new_high_proxy_is_separate_from_unresolved(self):
        base={'contract':'C','candidate_id':'A','opportunity_index':1,'warning':True,
              'exit':False,'lead':None,'exit_time_sec':None,'exit_gain':None,
              'unresolved_warning':True,'recovered_new_high_after_warning':False}
        r=review.warning_comparison([base],[base])
        self.assertEqual(r['shadow_warning_metrics']['unresolved_warnings'],1)
        self.assertEqual(r['shadow_warning_metrics']['new_high_recovery_proxy_rate'],0)
        self.assertIsNone(r['paired_lead_improvement_sec'])
        self.assertIsNone(r['shadow_warning_metrics']['exits_with_ge5s_lead_rate'])

    def test_every_fixed_delay_and_pullback_is_compared(self):
        r=review.build_review(bundle(),MANIFEST)
        verify=[x for x in r['comparisons'] if x['family']=='candidate_verify_v2']
        self.assertEqual(len(verify),5)
        pullback=[x for x in r['comparisons'] if x['family']=='selective_pullback_v2']
        self.assertEqual(len(pullback),14)

    def test_rendered_watch_rows_preserve_control_names(self):
        r=review.build_review(bundle(),MANIFEST)
        watch=[x for x in r['comparisons'] if x['family']=='watch_exit_v2']
        self.assertEqual({x['control'] for x in watch},{'V1_1C','V1_2C','V1_3C'})
        output=review.markdown(r)
        self.assertIn('| V2_FALLING_TREND | V1_1C |',output)
        self.assertNotIn("{'warnings':",output)


class CaptureAndCli(unittest.TestCase):
    def test_capture_retries_whole_snapshot_after_refresh_race(self):
        b=bundle(); changed=copy.deepcopy(b['state']); changed['source_sha256']='b'*64
        sequence=[b['state'],b['audit'],changed,b['state'],b['audit'],b['state']]
        paths=[]
        def read(path): paths.append(path); return sequence.pop(0)
        captured=review.coherent_capture(read,MANIFEST,clock=lambda: review.timestamp(CAPTURED))
        self.assertEqual(paths,['/state','/audit','/state']*2)
        self.assertEqual(captured['state']['source_sha256'],'a'*64)

    def test_capture_refuses_unstable_source_after_bounded_retries(self):
        counter=0
        def read(path):
            nonlocal counter
            counter+=1
            return {'version':'v','window_id':'w','source_sha256':str(counter)}
        with self.assertRaises(ValueError): review.coherent_capture(read,MANIFEST)
        self.assertEqual(counter,9)

    def test_offline_cli_is_deterministic_and_never_overwrites_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'input.json'; source.write_text(json.dumps(bundle()))
            out=root/'out'
            with patch.object(review,'http_reader',side_effect=AssertionError('network forbidden')):
                self.assertEqual(review.main(['--bundle',str(source),'--output',str(out)]),0)
                first=(out/'review.json').read_bytes()
                self.assertEqual(review.main(['--bundle',str(source),'--output',str(out)]),2)
                self.assertEqual((out/'review.json').read_bytes(),first)
                self.assertEqual(review.main(['--bundle',str(source),'--output',str(root/'second')]),0)
                self.assertEqual((root/'second'/'review.json').read_bytes(),first)

    def test_empty_valid_snapshot_does_not_report_a_winner(self):
        b=bundle()
        s=frozen.analyze_rows([],sha='a'*64,cutoff_text=MANIFEST['cutoff_utc'],expected_code_sha256=MANIFEST['code_sha256'])
        a={k:s[k] for k in ('version','window_id','source_sha256','audit_records')}; a.update(frozen.SAFETY); a['ok']=True
        s.pop('audit_records'); s.update(last_poll_utc=CAPTURED,source_latest_utc=CAPTURED)
        b.update(state=s,audit=a); rehash(b)
        r=review.build_review(b,MANIFEST)
        self.assertEqual(r['status'],'WAITING_FOR_FULL_CONTRACT')
        self.assertFalse(r['winner_selected'])
        self.assertTrue(all(x.get('one_lot_paired_net_delta_c') is None for x in r['comparisons']))


if __name__=='__main__': unittest.main()
