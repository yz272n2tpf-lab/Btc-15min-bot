import tempfile
import unittest
from pathlib import Path

from research_safety_preflight_v1 import PreflightError, check_preflight, git_blob_sha


class PreflightTests(unittest.TestCase):
    def make_collector(self, content=b"print('v6')\n"):
        td = tempfile.TemporaryDirectory()
        path = Path(td.name) / "scalp_lead_shadow_v6.py"
        path.write_bytes(content)
        self.addCleanup(td.cleanup)
        return path, git_blob_sha(content)

    def common(self):
        path, sha = self.make_collector()
        return dict(
            active_branch="scalp-lead-research-v3",
            work_branch="research-safe-20260910",
            collector_path=str(path),
            expected_collector_blob=sha,
            active_start_command="python scalp_lead_shadow_v6.py",
            expected_start_command="python scalp_lead_shadow_v6.py",
        )

    def test_passes_on_isolated_branch_with_frozen_collector(self):
        result = check_preflight(**self.common())
        self.assertTrue(result["ok"])

    def test_blocks_active_deploy_branch(self):
        args = self.common()
        args["work_branch"] = args["active_branch"]
        with self.assertRaisesRegex(PreflightError, "unsafe branch"):
            check_preflight(**args)

    def test_blocks_collector_drift(self):
        args = self.common()
        args["expected_collector_blob"] = "0" * 40
        with self.assertRaisesRegex(PreflightError, "collector drift"):
            check_preflight(**args)

    def test_blocks_start_command_drift(self):
        args = self.common()
        args["active_start_command"] = "python another_file.py"
        with self.assertRaisesRegex(PreflightError, "start-command drift"):
            check_preflight(**args)

    def test_fails_closed_on_missing_provenance(self):
        args = self.common()
        args["active_branch"] = ""
        with self.assertRaisesRegex(PreflightError, "missing required provenance"):
            check_preflight(**args)


if __name__ == "__main__":
    unittest.main()
