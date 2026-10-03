"""Only the Oct 3 evidence capacity amendment; no strategy evaluation."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from capture2 import qualification as q
from capture2.test_qualification import QualificationTests

ROOT = Path(__file__).resolve().parents[1]

class CapacityTests(unittest.TestCase):
    def test_exact_repaired_transport_and_only_capacity_source_changes(self):
        self.assertEqual(hashlib.sha256((ROOT/'capture2/runtime.py').read_bytes()).hexdigest(),
                         '2d0cbd1d0062fbc3bb5b77086d5892bad0b0f3bd1215adcee8770d6d5fddb051')
        payload=json.loads((ROOT/'capture2_payload.json').read_text())
        self.assertEqual(len(payload),13)
        for name,source in payload.items():
            self.assertEqual((ROOT/name).read_text(),source,name)
            compile(source,name,'exec')
        source=(ROOT/'capture2/install.py').read_text()
        quota=next(n.value for n in ast.walk(ast.parse(source)) if isinstance(n,ast.keyword) and n.arg=='quota_bytes')
        self.assertEqual(eval(compile(ast.Expression(quota),'quota','eval'),{'__builtins__':{}}),3*1024**3)
        self.assertEqual(q.MAX_ARCHIVE,3*1024**3)
        self.assertGreaterEqual(q.MAX_RECORDS,2250*2105+2250)

    def test_observed_burst_and_sustained_excursions_admit_under_amended_policy(self):
        for side,count,spacing in [('main',2000,40000),('v81',2000,40000),
                                  ('main',6000,150000),('v81',6000,150000)]:
            with self.subTest(side=side,count=count),tempfile.TemporaryDirectory() as d:
                root=Path(d); c=QualificationTests().fixture(root,side,count,spacing)
                result=q.qualify(root,c)
                self.assertEqual(result['qualification_state'],'QUALIFIED',result)
                for ladder in ('EARLY','FINAL','SCALP'):
                    self.assertEqual(sum(1 for _ in q.admitted_events(root,c,ladder)),count)

    def test_above_new_bound_is_sticky_and_never_admitted(self):
        for side in ('main','v81'):
            with self.subTest(side=side),tempfile.TemporaryDirectory() as d:
                root=Path(d); c=QualificationTests().fixture(root,side,2251,1)
                state=q.qualify(root,c)
                reason=next(r for r in state['reasons'] if r['code']=='RATE_ENVELOPE_EXCEEDED')
                self.assertEqual((reason['measured'],reason['limit'],reason['window_ms']),(2251,2250,100))
                self.assertEqual(q.read_state(root,c),json.loads(json.dumps(state)))
                for ladder in ('EARLY','FINAL','SCALP'):
                    with self.assertRaisesRegex(ValueError,'EVIDENCE_NOT_QUALIFIED:UNQUALIFIED'):
                        list(q.admitted_events(root,c,ladder))

    def test_old_failed_interval_cannot_be_reclassified(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); c=QualificationTests().fixture(root,'v81')
            latch=q.Latch(root,c);latch.fail('CAPTURE_FAILURE',detail='UNAVAILABLE_QUOTA')
            self.assertEqual(q.qualify(root,c)['qualification_state'],'UNQUALIFIED')
            self.assertEqual(q.read_state(root,c)['reasons'][0]['detail'],'UNAVAILABLE_QUOTA')

if __name__=='__main__':unittest.main()
