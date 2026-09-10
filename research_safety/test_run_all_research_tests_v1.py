import tempfile
import textwrap
import unittest
from pathlib import Path

import run_all_research_tests_v1 as runner


class ResearchTestRunnerTests(unittest.TestCase):
    def test_discovers_only_sorted_test_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "test_zeta.py").write_text("import unittest\n", encoding="utf-8")
            (root / "test_alpha.py").write_text("import unittest\n", encoding="utf-8")
            (root / "helper.py").write_text("", encoding="utf-8")
            self.assertEqual(
                runner.discover_test_files(root),
                ["test_alpha.py", "test_zeta.py"],
            )

    def test_passes_valid_tests_and_counts_skips(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "test_runner_pass_case.py").write_text(
                textwrap.dedent(
                    """
                    import unittest

                    class T(unittest.TestCase):
                        def test_ok(self):
                            self.assertEqual(2 + 2, 4)

                        @unittest.skip("fixture")
                        def test_skip(self):
                            pass
                    """
                ),
                encoding="utf-8",
            )
            result = runner.run_tests(root)
            self.assertTrue(result["ok"])
            self.assertEqual(result["tests_run"], 2)
            self.assertEqual(result["skipped"], 1)
            self.assertEqual(result["failures"], 0)
            self.assertEqual(result["errors"], 0)

    def test_failure_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "test_runner_fail_case.py").write_text(
                textwrap.dedent(
                    """
                    import unittest

                    class T(unittest.TestCase):
                        def test_bad(self):
                            self.assertTrue(False)
                    """
                ),
                encoding="utf-8",
            )
            result = runner.run_tests(root)
            self.assertFalse(result["ok"])
            self.assertEqual(result["tests_run"], 1)
            self.assertEqual(result["failures"], 1)

    def test_no_tests_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            result = runner.run_tests(Path(td))
            self.assertFalse(result["ok"])
            self.assertEqual(result["tests_run"], 0)
            self.assertIn("no research tests discovered", result["output"])


if __name__ == "__main__":
    unittest.main()
