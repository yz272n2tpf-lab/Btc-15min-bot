import gzip
import json
from pathlib import Path
import tempfile
import unittest

from joint_diagnosis import BASE,calls,gates,metric,epoch
from joint_validate import validate
from joint_v81 import BASE as VBASE,candidates,rows


class JointDiagnosisTests(unittest.TestCase):
    def row(self,**extra):
        r=dict(t=100.,source_t=100.,ticker='KXBTC15M-TEST',target=100.,side='UP',fair=.8,
            ask=.4,bid=.39,edge=.4,left=8.,receipt_left=8.,gap=30.,ratio=1.,range5=30.,
            target_agrees=True,brti_authority=True,brti_agrees=True)
        return dict(r,**extra)

    def test_first_call_never_selected_by_label_or_later_price(self):
        first=self.row();later=self.row(t=200.,side='DOWN',ask=.25)
        self.assertEqual(calls([first,later],'early',BASE['early']),[first])

    def test_final_authority_cannot_be_replaced_by_model_confidence(self):
        r=self.row(fair=.99,gap=100.,brti_authority=False)
        self.assertFalse(all(gates(r,'final',BASE['final']).values()))

    def test_scheduled_outage_denominator_is_preserved(self):
        m={'KXBTC15M-TEST':dict(open_time='1970-01-01T00:00:00Z',close_time='1970-01-01T00:15:00Z',floor_strike=100.,result='yes')}
        result=metric([self.row()],m,3,'early')
        self.assertEqual(result['coverage_official'],1.)
        self.assertEqual(result['coverage_scheduled'],1/3)

    def test_outcome_change_changes_score_only(self):
        rows=[self.row(),self.row(t=200.)];entry=calls(rows,'early',BASE['early'])
        m={'KXBTC15M-TEST':dict(open_time='1970-01-01T00:00:00Z',close_time='1970-01-01T00:15:00Z',floor_strike=100.,result='yes')}
        self.assertEqual(metric(entry,m,1,'early')['wins'],1)
        m['KXBTC15M-TEST']['result']='no'
        self.assertEqual(metric(entry,m,1,'early')['wins'],0)
        self.assertEqual(calls(rows,'early',BASE['early']),entry)

    def test_fixed_target_mismatch_is_not_silently_scored(self):
        m={'KXBTC15M-TEST':dict(open_time='1970-01-01T00:00:00Z',close_time='1970-01-01T00:15:00Z',floor_strike=101.,result='yes')}
        with self.assertRaises(ValueError):metric([self.row()],m,1,'early')

    def test_candidate_lock_tampering_blocks_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'lock.json';p.write_text(json.dumps(dict(canonical_sha256='0'*64,policies={})))
            with self.assertRaises(ValueError):validate(Path(directory),Path(directory),p,Path(directory)/'out')

    def vr(self,**extra):
        return self.row(**dict(dict(features_ready=True,brti_fresh=True,btc5=30.,btc15=30.,brti5=30.,
            brti15=20.,btc30=10.,accel=20.,ask5=0.,ask15=0.,structure_ok=True),**extra))

    def test_confirmation_cannot_bridge_rejection_or_long_gap(self):
        a=self.vr();b=self.vr(t=101.,source_t=101.,btc5=-1.);c=self.vr(t=102.,source_t=102.)
        self.assertEqual(candidates([a,b,c],VBASE),[])
        self.assertEqual(candidates([a,self.vr(t=105.,source_t=105.)],VBASE),[])
        self.assertEqual(len(candidates([a,self.vr(t=101.,source_t=101.)],VBASE)),1)

    def test_v81_source_missing_never_becomes_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'v81.gz'
            with gzip.open(path,'wt') as f:f.write(json.dumps(dict(receipt_epoch=100.,state=dict(primary_wait_reason='WAIT')))+'\n')
            extracted,_,bad=rows(path,0.,1000.)
            self.assertEqual(extracted,[])
            self.assertEqual(bad['unqualified_source_or_publication'],1)


if __name__=='__main__':unittest.main()
