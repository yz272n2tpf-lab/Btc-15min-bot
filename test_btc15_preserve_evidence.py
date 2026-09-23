import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from btc15_preserve_evidence_v1 import preserve

class EvidenceArchive(unittest.TestCase):
    def test_original_bytes_preserved_and_rerun_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            data=root/'kalshi_probe.csv';data.write_bytes(b'x,y\n1,2\n')
            (root/'private_key.pem').write_text('excluded-test-data')
            (root/'credentials.json').write_text('excluded-test-data')
            (root/'scalp_symlink.csv').symlink_to(data)
            result=preserve(root,'pre-v2')
            self.assertEqual(result['files'],1)
            with zipfile.ZipFile(result['archive']) as z:
                self.assertEqual(set(z.namelist()),{'kalshi_probe.csv','manifest.json'})
                self.assertEqual(z.read('kalshi_probe.csv'),data.read_bytes())
                self.assertFalse(json.loads(z.read('manifest.json'))['orders'])
            self.assertEqual(preserve(root,'pre-v2')['status'],'PRESERVED_EXISTING')
            self.assertEqual(data.read_bytes(),b'x,y\n1,2\n')

    def test_partial_or_missing_root_fails_without_touching_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);data=root/'scalp_probe.csv';data.write_text('evidence')
            (root/'btc15-evidence-pre-v2.partial').write_text('partial-evidence')
            with self.assertRaises(RuntimeError):preserve(root,'pre-v2')
            self.assertEqual(data.read_text(),'evidence')
            with self.assertRaises(ValueError):preserve(root/'missing','pre-v2')

if __name__=='__main__': unittest.main()
