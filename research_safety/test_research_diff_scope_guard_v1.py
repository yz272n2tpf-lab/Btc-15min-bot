import unittest

from research_diff_scope_guard_v1 import ScopeError, audit_changed_paths


class DiffScopeGuardTests(unittest.TestCase):
    def test_allows_research_safety_files(self):
        result = audit_changed_paths([
            "research_safety/a.py",
            "research_safety/tests/b.py",
        ])
        self.assertTrue(result["ok"])
        self.assertEqual(result["changed_count"], 2)

    def test_blocks_frozen_v6_collector(self):
        result = audit_changed_paths(["scalp_lead_shadow_v6.py"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["blocked"][0]["reason"], "protected runtime/config path")

    def test_blocks_other_nonresearch_file(self):
        result = audit_changed_paths(["dashboard_server.py"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["blocked"][0]["reason"], "outside allowed research-only prefixes")

    def test_blocks_protected_config_even_with_broad_allow_prefix(self):
        result = audit_changed_paths(["railway.toml"], allowed_prefixes=("railway.toml",))
        self.assertFalse(result["ok"])
        self.assertEqual(result["blocked"][0]["reason"], "protected runtime/config path")

    def test_rejects_path_traversal(self):
        with self.assertRaisesRegex(ScopeError, "path traversal"):
            audit_changed_paths(["research_safety/../scalp_lead_shadow_v6.py"])

    def test_normalizes_and_deduplicates_paths(self):
        result = audit_changed_paths([
            "./research_safety/a.py",
            "research_safety/a.py",
            "research_safety\\b.py",
        ])
        self.assertTrue(result["ok"])
        self.assertEqual(result["changed_count"], 2)


if __name__ == "__main__":
    unittest.main()
