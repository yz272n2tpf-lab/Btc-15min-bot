import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from btc15_clean_run_v1 import prepare


class CleanRun(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory())
        self.root=Path(self.temp)
        for name in ('scalp_move_shadow_v1.py','scalp_move_shadow_v2_finalprod_clean.py',
                     'btc15_brti_shared_consumer_v1.py','btc15_kalshi_quote_provenance_v1.py',
                     'btc15_common_observer_v1.py','scalp_path_export_bridge_v1.py'):
            (self.root/name).write_text('# frozen test input\n')

    def prepare(self): return prepare(self.root,'test-run',self.root,require_mount=False)

    def test_restart_preserves_manifest_and_original_data(self):
        first=self.prepare(); manifest=self.root/'scalp_test-run_manifest.json'
        original=manifest.read_bytes(); Path(first['event_csv']).write_text('evidence\n')
        self.assertEqual(self.prepare(),first)
        self.assertEqual(manifest.read_bytes(),original)
        self.assertEqual(Path(first['event_csv']).read_text(),'evidence\n')

    def test_changed_code_needs_new_run_identity(self):
        self.prepare();(self.root/'btc15_brti_shared_consumer_v1.py').write_text('# changed\n')
        with self.assertRaisesRegex(RuntimeError,'differs'): self.prepare()

    def test_unidentified_existing_dataset_is_not_appended(self):
        path=self.root/'scalp_test-run_events.csv';path.write_text('old evidence')
        with self.assertRaisesRegex(RuntimeError,'Unidentified'): self.prepare()
        self.assertEqual(path.read_text(),'old evidence')

    def test_missing_mount_or_unsafe_identity_fails_before_creation(self):
        with patch('os.path.ismount',return_value=False),self.assertRaisesRegex(RuntimeError,'mount'):
            prepare(self.root,'test-run',self.root)
        with self.assertRaises(ValueError):prepare(self.root,'../outside',self.root,require_mount=False)


if __name__ == '__main__': unittest.main()
