"""Focused offline package tests. Never import or start a native trading owner."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import unittest

from ops.live_recording.install import inventory
from ops.live_recording.policy import file_sha

ROOT = Path(__file__).resolve().parents[2]

class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = Path(os.environ['BTC15_TEST_BUNDLES']).resolve()
        cls.receipt = json.loads((cls.bundle / 'PACKAGES.json').read_bytes())

    def test_every_archive_member_exact_and_no_duplicate_or_extra_path(self):
        for lane in ('main', 'v81'):
            package = self.receipt['packages'][lane]
            expected = inventory(self.bundle / (lane + '-installed'))
            path = self.bundle / package['archive']
            self.assertEqual(file_sha(path), package['sha256'])
            seen = {}
            with tarfile.open(path, 'r:gz') as t:
                for member in t:
                    self.assertTrue(member.isfile())
                    self.assertNotIn(member.name, seen)
                    self.assertFalse(Path(member.name).is_absolute())
                    self.assertNotIn('..', Path(member.name).parts)
                    seen[member.name] = hashlib.sha256(t.extractfile(member).read()).hexdigest()
            self.assertEqual(seen, expected)

    def test_deployed_diff_strictly_recorder_evidence_and_manifests(self):
        for lane in ('main', 'v81'):
            p = self.receipt['packages'][lane]
            live = inventory(self.bundle / (lane + '-deployed'))
            after = inventory(self.bundle / (lane + '-installed'))
            actual = {n for n in set(live) | set(after) if live.get(n) != after.get(n)}
            self.assertEqual(actual, set(p['changed_vs_deployed']))
            self.assertTrue(all(n.startswith(('ops/live_recording/', 'ops/recording_workflow/',
                                             'candidates/early_recording_20261012/'))
                                or n in ('BTC15_RECORDER_INSTALL.json', 'BTC15_V2_PRODUCT_RELEASE_R1.json')
                                for n in actual))
            for n, digest in p['protected_files'].items():
                self.assertEqual(live[n], digest)
                self.assertEqual(after[n], digest)

    def test_release_integrity_in_each_actual_package(self):
        script = '''
import os,socket
def deny(*a,**k):raise AssertionError('NETWORK_FORBIDDEN')
socket.create_connection=socket.socket.connect=deny
from btc15_v2_product.release import verify_files
from ops.live_recording import bootstrap
assert os.environ.get('BTC15_RECORDING_ENABLED') != '1'
m=verify_files(os.environ['BTC15_TEST_LANE'])
assert m['orders'] is False and m['recorder']['signal_only'] is True
assert m['recorder']['default_off'] is True
for role in ('main','v81','information'):assert bootstrap.start(role) is None
assert bootstrap.ACTIVE is None and bootstrap.ACTIVE_ADAPTER is None
print('EXACT_PACKAGE_RELEASE_AND_DEFAULT_OFF_PASS')
'''
        for lane in ('main', 'v81'):
            env = dict(os.environ, BTC15_TEST_LANE=lane, PYTHONDONTWRITEBYTECODE='1')
            env.pop('BTC15_RECORDING_ENABLED', None)
            root = self.bundle / (lane + '-installed')
            proc = subprocess.run([sys.executable, '-B', '-c', script], cwd=root, env=env,
                                  capture_output=True, text=True, timeout=20)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn('EXACT_PACKAGE_RELEASE_AND_DEFAULT_OFF_PASS', proc.stdout)

    def test_all_installed_python_compiles_without_executing(self):
        for lane in ('main', 'v81'):
            root = self.bundle / (lane + '-installed')
            names = json.loads((root / 'BTC15_RECORDER_INSTALL.json').read_bytes())['candidate_files']
            for name in names:
                if name.endswith('.py'):
                    compile((root / name).read_bytes(), name, 'exec')

    def test_baseline_reader_checkpoint_and_capture_bytes_preserved(self):
        baseline = json.loads((ROOT / 'research/early_10_12h_20261017/TEST_RESULTS.json').read_bytes())['source_sha256']
        for lane in ('main', 'v81'):
            root = self.bundle / (lane + '-installed')
            for name, digest in baseline.items():
                if name.startswith('ops/live_recording/'):
                    self.assertEqual(file_sha(root / name), digest, name)

    def test_existing_entrypoints_bootstrap_once_and_keep_native_calls(self):
        expected = {'btc15_v2_native.py': ('main', 'native_main'),
                    'btc15_v2_launch.py': ('v81', 'v81_main'),
                    'btc15_v2_product/worker.py': ('information', 'service.main')}
        for lane in ('main', 'v81'):
            root = self.bundle / (lane + '-installed')
            for name, (role, native) in expected.items():
                tree = ast.parse((root / name).read_text())
                calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
                self.assertEqual(sum(ast.unparse(n.func) == 'start' and
                                     [ast.literal_eval(a) for a in n.args] == [role]
                                     for n in calls if ast.unparse(n.func) == 'start'), 1)
                self.assertEqual(sum(ast.unparse(n.func) == native for n in calls), 1)

    def test_information_is_existing_main_installation(self):
        main, info = (self.receipt['packages'][r] for r in ('main', 'information'))
        self.assertEqual(info['sha256'], main['sha256'])
        self.assertFalse(info['standalone_installation'])
        self.assertEqual(main['roles'], ['main', 'information'])

    def test_rollback_copies_exactly_restore_deployed_source(self):
        for lane in ('main', 'v81'):
            self.assertEqual(inventory(self.bundle / (lane + '-deployed')),
                             inventory(self.bundle / (lane + '-deployed-rollback-test')))
            self.assertEqual(inventory(self.bundle / (lane + '-base')),
                             inventory(self.bundle / (lane + '-rollback-test')))

if __name__ == '__main__':
    unittest.main()
