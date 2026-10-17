"""Offline safety tests of NEW operational preparation only. No SSH/DB/capture."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from research.native_operational_20261017 import probe


class OperationalPreparation(unittest.TestCase):
    def test_wrong_environment_fails_before_subprocess_or_receipt(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(probe.subprocess, 'run') as ssh:
            with self.assertRaisesRegex(ValueError, 'ISOLATED_RESEARCH_IDENTITY'):
                probe.run()
            ssh.assert_not_called()

    def test_strict_existing_host_pin_and_one_attempt(self):
        cmd = probe.command('example.invalid')
        for arg in ('-oStrictHostKeyChecking=yes', '-oConnectionAttempts=1',
                    '-oUpdateHostKeys=no', '-oBatchMode=yes', '-oIdentitiesOnly=yes'):
            self.assertIn(arg, cmd)
        self.assertEqual(cmd[cmd.index('-F')+1], '/dev/null')
        self.assertTrue(cmd[-1].startswith('python -B -c '))
        compile(probe.REMOTE, '<remote-read-only>', 'exec')

    def test_identity_mismatch_blocks_before_source_assessment(self):
        with self.assertRaisesRegex(ValueError, 'REMOTE_IDENTITY_MISMATCH'):
            probe.assess({'identity':{'id':'expected'}},
                         {'result':'READ_COMPLETE','identity':{'id':'different'}})

    def test_space_floor_and_dependency_mismatch_are_not_readiness(self):
        p = {'identity':{}, 'files':{'a':'sha'}, 'dependencies':{'x':'1'}}
        a = {'result':'READ_COMPLETE','identity':{},'source_hashes':{'a':'sha'},
             'dependencies':{'x':'2'},'filesystem':[
                 {'monotonic':1,'available_bytes':probe.PRODUCER_MIN_FREE},
                 {'monotonic':11,'available_bytes':probe.PRODUCER_MIN_FREE-1}]}
        r = probe.assess(p, copy.deepcopy(a))['assessment']
        self.assertFalse(r['capture_plus_reserve_floor_pass'])
        self.assertEqual(r['dependency_mismatches'], ['x'])
        self.assertTrue(r['growth_allowance_still_requires_review'])
        self.assertTrue(r['native_import_and_hook_compatibility_not_proven'])

    def test_supplied_patch_cannot_include_staged_shadow_or_volumes(self):
        approved = json.loads((probe.ROOT.parent/'native_diagnostic_20261017/PROPOSED_SETTINGS.json').read_text())
        for filename in ('ACTIVATE_NOT_AUTHORIZED.patch.json','ROLLBACK_EXACT_SOURCE_NOT_AUTHORIZED.patch.json'):
            data = json.loads((probe.ROOT/filename).read_text())
            self.assertEqual(set(data), {'services'})
            self.assertEqual(set(data['services']), {s['service'] for s in approved['services'].values()})
            for name,s in approved['services'].items():
                item = data['services'][s['service']]
                self.assertEqual(set(item), {'source','deploy','variables'})
                self.assertEqual(set(item['source']), {'repo','branch','commitSha'})
                self.assertEqual(set(item['deploy']), {'startCommand'})
                if filename.startswith('ACTIVATE'):
                    self.assertEqual(item['source']['commitSha'], s['source_commit'])
                    self.assertEqual(item['deploy']['startCommand'], s['start_command_proposed'])
                    self.assertEqual(item['variables'], {k:{'value':v} for k,v in s['recording_variables_proposed'].items()})
                else:
                    self.assertEqual(item['source']['commitSha'], s['rollback']['source_commit'])
                    self.assertEqual(item['deploy']['startCommand'], s['start_command_before'])
                    self.assertEqual(item['variables'], {'BTC15_RECORDING_ENABLED':{'value':'0'}})


if __name__ == '__main__':
    unittest.main()
