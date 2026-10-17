"""Check inert approval inputs and identity guard; no native execution."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ops.live_recording.policy import canonical, validate
from research.native_diagnostic_20261017 import lease_probe

ROOT = Path(__file__).resolve().parent

class ApprovalTests(unittest.TestCase):
    def test_config_exact_hash_and_all_role_package_pins(self):
        raw = (ROOT / 'campaign.approval-draft.json').read_bytes()
        c = json.loads(raw)
        p = json.loads((ROOT / 'PACKAGES.json').read_bytes())['packages']
        s = json.loads((ROOT / 'PROPOSED_SETTINGS.json').read_bytes())
        self.assertEqual(raw, canonical(c))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), s['config_sha256'])
        self.assertEqual(c['duration_seconds'], 60)
        self.assertFalse(c['orders'])
        for role in ('main', 'v81', 'information'):
            self.assertEqual(c['roles'][role]['build'], p[role]['github_commit'])
            self.assertEqual(c['roles'][role]['manifest_sha256'], p[role]['manifest_sha256'])
        with tempfile.TemporaryDirectory() as temp:
            offline = dict(c, root=temp)
            for role in c['roles']:
                self.assertEqual(validate(offline, role, offline=True), Path(temp) / role)

    def test_start_commands_only_replace_the_two_reviewed_identity_pins(self):
        p = json.loads((ROOT / 'PACKAGES.json').read_bytes())['packages']
        s = json.loads((ROOT / 'PROPOSED_SETTINGS.json').read_bytes())
        import re
        for lane in ('main', 'v81'):
            row = s['services'][lane]
            old = row['start_command_before']
            old_manifest = re.search(r'BTC15_V2_APPROVED_MANIFEST_SHA256=([0-9a-f]{64})', old).group(1)
            self.assertEqual(row['start_command_proposed'],
                             old.replace(p[lane]['deployed']['commit'], p[lane]['github_commit'])
                                .replace(old_manifest, p[lane]['manifest_sha256']))
            self.assertEqual(row['rollback']['recording_enabled'], '0')
        self.assertFalse(s['executed'])
        self.assertFalse(s['selective_change_route_verified'])

    def test_research_probe_refuses_local_or_production_identity_before_import(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(lease_probe.run()['reason'], 'ISOLATED_RESEARCH_IDENTITY')
        with patch.dict('os.environ', dict(lease_probe.EXPECTED,
                        RAILWAY_PROJECT_ID='baea4e22-d004-4434-b2c5-81a7fbc05086'), clear=True):
            self.assertEqual(lease_probe.run()['result'], 'BLOCKED')

if __name__ == '__main__':
    unittest.main()
