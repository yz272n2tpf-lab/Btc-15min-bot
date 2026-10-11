"""Offline release gates. Synthetic journals only; never start production."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from btc15_v2_product import REVISION
from btc15_v2_product import release
from btc15_v2_product.directional import Directional
from btc15_v2_product.early_origin_transfer import PREDECESSORS
from btc15_v2_product.journal import RevisionJournal, ProcessorEnvelope, public_view
from btc15_ladder_journal_v1 import Journal, atomic_json
from test_btc15_supported_early import value_frame, step


class ReleaseIntegrity(unittest.TestCase):
    def test_committed_manifest_and_frozen_files(self):
        manifest = release.verify_files('main')
        self.assertIs(manifest['signal_only'], True)
        self.assertIs(manifest['manual_execution_only'], True)
        self.assertIs(manifest['orders'], False)

    def test_tampered_handoff_fails_actual_release_verifier(self):
        root = release.ROOT
        manifest = json.loads(release.MANIFEST.read_text())
        freeze = json.loads((root/'BTC15_LADDER_COMPLETION_FREEZE_20261003.json').read_text())
        names = set(manifest['files_sha256']) | set(manifest['lane_protected_files']['main']) | set(freeze['files_sha256'])
        names |= {release.MANIFEST.name, 'BTC15_LADDER_COMPLETION_FREEZE_20261003.json'}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            for name in names:
                dest = target/name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root/name, dest)
            with (target/'btc15_v2_product/early_origin_transfer.py').open('a') as out:
                out.write('\n# unreviewed bytes\n')
            with self.assertRaisesRegex(ValueError, 'RELEASE_FILE_MISMATCH:btc15_v2_product/early_origin_transfer.py'):
                release.verify_files('main', target)

    def environment(self):
        return dict(BTC15_V2_APPROVED_BUILD='a'*40,
            BTC15_V2_APPROVED_MANIFEST_SHA256=hashlib.sha256(release.MANIFEST.read_bytes()).hexdigest(),
            RAILWAY_GIT_COMMIT_SHA='a'*40, RAILWAY_PROJECT_ID=release.PROJECT,
            RAILWAY_ENVIRONMENT_ID=release.ENVIRONMENT, RAILWAY_SERVICE_ID=release.SERVICES['main'],
            RAILWAY_VOLUME_ID=release.VOLUMES['main'], RAILWAY_VOLUME_MOUNT_PATH='/data',
            RAILWAY_DEPLOYMENT_ID='11111111-1234-1234-1234-123456789abc')

    def test_authorization_binds_build_manifest_service_environment_volume(self):
        # verify_environment only validates identities; it launches no processes.
        expected = self.environment()
        with patch.dict(os.environ, expected, clear=True):
            receipt = release.verify_environment('main')
            self.assertFalse(receipt['orders'])
            self.assertTrue(receipt['signal_only'])
            self.assertEqual(receipt['evidence_class'], 'RUNTIME_ONLY_NOT_CONTROL_PLANE_VERIFIED')
            self.assertEqual(os.environ['BTC15_LADDER_DATA_ROOT'],
                '/data/btc15_v2_product/'+REVISION+'/'+expected['RAILWAY_DEPLOYMENT_ID'])
        for key in expected:
            bad = dict(expected)
            bad[key] = 'wrong'
            with self.subTest(key=key), patch.dict(os.environ, bad, clear=True):
                with self.assertRaises(ValueError):
                    release.verify_environment('main')
        with patch.dict(os.environ, {**expected, 'BTC15_LADDER_DATA_ROOT':'/tmp/foreign-root'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'COHORT_ROOT_OVERRIDE_FORBIDDEN'):
                release.verify_environment('main')

    def test_launcher_without_approval_never_assembles_or_starts(self):
        import btc15_v2_launch
        with patch.dict(os.environ, {}, clear=True), patch('sys.argv',
            ['btc15_v2_launch.py', '--lane', 'main', '--run-reviewed-production']):
            with self.assertRaisesRegex(ValueError, 'DEPLOYMENT_NOT_AUTHORIZED'):
                btc15_v2_launch.main()


class JournalContinuity(unittest.TestCase):
    def test_actual_journal_handoff_restart_rollover_and_source_lease(self):
        engine = Directional(); engine.restore({})
        first, saved, view = step(engine, value_frame())
        _, saved, ended = step(engine, value_frame(2, side='DOWN', p=.6))
        self.assertEqual(ended['terminal']['state'], 'EXIT')
        old_id = view['origin']['origin_id']
        deployment, build = PREDECESSORS['main']
        env = dict(RAILWAY_DEPLOYMENT_ID='22222222-1234-1234-1234-123456789abc',
                   RAILWAY_GIT_COMMIT_SHA='a'*40)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prior_path = root/deployment/'main.sqlite3'
            prior = Journal(prior_path, 'main')
            prior.commit(first, saved)
            for key, value in dict(product_revision=REVISION, deployment=deployment, build=build).items():
                prior.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, value))
            prior.db.commit(); prior.close()
            before = prior_path.read_bytes()
            destination = root/env['RAILWAY_DEPLOYMENT_ID']/'main.sqlite3'
            at = value_frame(3)['captured_ts']
            with patch.dict(os.environ, env, clear=True), patch('btc15_v2_product.early_origin_transfer.time.time', return_value=at):
                journal = RevisionJournal(destination, 'main')
                receipt = deepcopy(journal.get('origin_transfer'))
                self.assertEqual(receipt['history_count'], 1)
                self.assertFalse(receipt['publication_imported'])
                self.assertIsNone(journal.get('latest'))
                self.assertEqual(journal.get('state')['signal_history'][0]['origin_id'], old_id)
                self.assertEqual(journal.get('state')['signal_history'][0]['terminal'], saved['signal_history'][0]['terminal'])
                processor = ProcessorEnvelope(Directional(), 'main')
                processor.restore(journal.get('state'))
                # A real new opportunity in the same contract survives restart.
                f = value_frame(3, ask=.99, p=.995)
                r, state, _ = processor.process((f, None), f['captured_ts']+.001)
                journal.commit(r, state)
                journal.close()
                journal = RevisionJournal(destination, 'main')
                self.assertEqual(journal.get('origin_transfer'), receipt)
                processor.restore(journal.get('state'))
                f = value_frame(4)
                r, state, v = processor.process((f, None), f['captured_ts']+.001)
                self.assertEqual(r['event'], 'BUY')
                self.assertNotEqual(v['origin']['origin_id'], old_id)
                journal.commit(r, state)
                self.assertEqual(journal.db.execute('SELECT count(*) FROM events').fetchone()[0], 2)
                atomic_json(destination.with_suffix('.json'), v)
                self.assertEqual(public_view(destination.parent, 'main', v['published_ts'])['status'], 'AVAILABLE')
                self.assertEqual(public_view(destination.parent, 'main', v['expires_at'])['status'], 'UNAVAILABLE')
                self.assertEqual(public_view(destination.parent, 'main', f['official_close'])['status'], 'UNAVAILABLE')
                journal.close()
                journal = RevisionJournal(destination, 'main')
                self.assertEqual(len(journal.get('state')['signal_history']), 2)
                self.assertEqual(journal.get('origin_transfer'), receipt)
                journal.close()
            self.assertEqual(prior_path.read_bytes(), before)
            # Another rollout cannot silently open or rewrite this cohort.
            with patch.dict(os.environ, {**env, 'RAILWAY_GIT_COMMIT_SHA':'b'*40}, clear=True):
                before_dest = destination.read_bytes()
                with self.assertRaisesRegex(ValueError, 'COHORT_IDENTITY_CHANGED:build'):
                    RevisionJournal(destination, 'main')
                self.assertEqual(destination.read_bytes(), before_dest)


if __name__ == '__main__':
    unittest.main()
