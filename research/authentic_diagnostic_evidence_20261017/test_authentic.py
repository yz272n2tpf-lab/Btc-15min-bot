"""Focused regressions over the exact sealed diagnostic; no synthetic substitutes.

BTC15_AUTHENTIC_ROOT must name an extracted evidence directory containing raw/,
forensics-final/findings.json, replay-f1/ and replay-repeat/. Missing evidence is
an error, never a skip or an invented input. Run readers sequentially beforehand.
"""
import json
import os
from pathlib import Path
import sqlite3
import unittest

from ops.live_recording.finish import validate_seals
from ops.live_recording.policy import canonical, file_sha, sha

REPO=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent

class AuthenticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(os.environ['BTC15_AUTHENTIC_ROOT'])
        cls.f=json.loads((cls.root/'forensics-final/findings.json').read_bytes())
        cls.summary=json.loads((cls.root/'replay-f1/verification/summary.json').read_bytes())

    def test_original_bytes_seals_and_runtime_bindings(self):
        items=json.loads((HERE/'recovered.json').read_bytes())['verified']
        for x in items:
            p=self.root/'raw'/x['path']
            self.assertEqual(p.stat().st_size,x['size'])
            self.assertEqual(file_sha(p),x['sha256'])
        self.assertEqual(sum(x['size'] for x in items if x['path'].endswith('.gz')),10890786)
        seals={}
        for role in ('main','v81','information'):
            raw=(self.root/'raw'/role/'seal.json').read_bytes()
            seals[role]=dict(seal=json.loads(raw),sha256=sha(raw))
        config=json.loads((REPO/'research/native_diagnostic_20261017/campaign.approval-draft.json').read_bytes())
        validate_seals(config,seals)

    def test_exact_original_charge_deficits_without_evidence_reclassification(self):
        expected={'main':(3000,12257232,10275140,1982092),
                  'v81':(30644,67731083,45850179,21880904),
                  'information':(146,19358782,19358782,0)}
        for role,numbers in expected.items():
            a=self.f['accounting'][role]
            self.assertEqual(tuple(a[k] for k in ('observations','admitted_charge','old_processed_charge','exact_charge_difference')),numbers)
            self.assertTrue(a['accounting_reconciled'])
            self.assertFalse(a['recovered_evidence'])
            self.assertEqual(a['queue'],0);self.assertEqual(a['unfinished'],0)
            self.assertEqual(a['reported_losses'],{})
            self.assertEqual(a['original_terminal_status'],'SEALED' if role=='information' else 'INCOMPLETE')

    def test_308_exact_partial_http_row_never_gets_completed_credit(self):
        c=self.f['candle'];m=c['http_matches']
        self.assertEqual(c['native_schema_row'],[1792241040.,1792241040.,1792240980.,81398.48,81398.48,81398.47,81398.47,.01092997])
        self.assertEqual(len(m),1);self.assertEqual(m[0]['record_sequence'],34)
        self.assertEqual(m[0]['response_sha256'],'0410120b0ca785807fda325717d81c117d03e6adc8a2204c6986f18bb2a11aa1')
        self.assertLess(m[0]['received_at'],c['cache_accepted_at'])
        self.assertLess(c['cache_accepted_at'],c['bucket_end'])
        row=[*c['native_schema_row'][:2],*c['native_schema_row'][3:]]
        db=self.root/'replay-f1/verification/verification.sqlite3'
        with sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True) as con:
            got=con.execute('SELECT at,original_http FROM candles WHERE h=?',(sha(canonical(row)),)).fetchall()
        self.assertEqual(got,[(c['cache_accepted_at'],0)])
        self.assertNotIn('RECORD_VERIFICATION',self.summary['issue_counts'])

    def test_native_decision_cutoffs_preserved(self):
        c=self.f['candle'];uses=c['information_anchor_uses']
        self.assertEqual(len(uses),79)
        self.assertEqual(sum(x['included'] for x in uses),15)
        self.assertTrue(all(not x['included'] or x['decision']>=c['bucket_end'] for x in uses))
        original=[x for x in c['native_records'] if x['sequence']==329][0]
        self.assertEqual(original['payload']['evidence']['kind'],'UNAVAILABLE')

    def test_all_seven_inputs_intact_progressing_and_rejections_unresolved(self):
        i=self.f['information'];self.assertEqual((i['input_count'],i['published_count']),(79,72))
        self.assertEqual([x['failure_sequence'] for x in i['failures']],[141,158,185,189,209,215,227])
        for x in i['failures']:
            self.assertEqual(x['input_sequence']+1,x['failure_sequence'])
            self.assertIs(x['source_progress'],True)
            self.assertFalse(x['published']);self.assertIsNone(x['frame_id'])
            self.assertFalse(x['native_health_and_publish_clock_recorded'])
            self.assertGreater(x['freshness_slack_at_capture'],0)
        self.assertEqual(self.summary['issue_counts']['INFORMATION_FAILURE'],7)

    def test_first_information_source_is_outside_main_capture(self):
        s=self.f['scope'];self.assertEqual(s['first_information_input'],38)
        self.assertEqual(s['main_boundary'],1792241021.5355039)
        self.assertEqual(s['first_information_brti']['received'],1792241021.5875683)
        self.assertAlmostEqual(s['brti_receipt_after_main_boundary'],.05206441879272461)
        self.assertEqual(s['exact_brti_source_matches'],[])
        self.assertEqual(self.summary['issue_counts']['INFORMATION_ASSOCIATION'],1)

    def test_deterministic_replay_retains_quarantine_and_incomplete_seals(self):
        self.assertEqual(self.summary['status'],'INCOMPLETE')
        self.assertFalse(self.summary['complete_supplied_scope'])
        self.assertEqual(self.summary['v81_causal_matches'],27)
        self.assertEqual(self.summary['metrics']['records_quarantined_after_loss'],195)
        self.assertEqual(self.summary['issue_counts']['QUOTE_RECEIVED_WITHOUT_OWNER_ACCEPTANCE'],1)
        for name in ('summary.json','windows.jsonl','issues.jsonl','associations.jsonl','v81_native_original_associations.jsonl'):
            self.assertEqual((self.root/'replay-f1/verification'/name).read_bytes(),
                             (self.root/'replay-repeat/verification'/name).read_bytes(),name)

if __name__=='__main__':unittest.main()
