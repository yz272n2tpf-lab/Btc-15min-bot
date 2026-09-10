import os
import tempfile
import unittest
from pathlib import Path

from v6_replay_evidence_manifest_v1 import (
    ManifestError,
    build_manifest,
    canonical_json,
    verify_manifest,
)


class ReplayEvidenceManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
        return path

    def test_manifest_is_deterministic_and_order_independent(self):
        self.write("b.log", "b\n")
        self.write("a.jsonl", '{"a":1}\n')
        first = build_manifest(["b.log", "a.jsonl"], root=self.root)
        second = build_manifest(["a.jsonl", "b.log"], root=self.root)
        self.assertEqual(canonical_json(first), canonical_json(second))
        self.assertEqual([f["path"] for f in first["files"]], ["a.jsonl", "b.log"])

    def test_verify_detects_mutation(self):
        path = self.write("sample.log", "one\n")
        manifest = build_manifest(["sample.log"], root=self.root)
        path.write_text("two\n", encoding="utf-8")
        errors = verify_manifest(manifest, root=self.root)
        self.assertTrue(any("sha256 mismatch" in e for e in errors))

    def test_verify_detects_missing_file(self):
        path = self.write("sample.log", "one\n")
        manifest = build_manifest(["sample.log"], root=self.root)
        path.unlink()
        errors = verify_manifest(manifest, root=self.root)
        self.assertTrue(errors)
        self.assertIn("sample.log", errors[0])

    def test_duplicate_evidence_path_is_rejected(self):
        self.write("sample.log", "one\n")
        with self.assertRaises(ManifestError):
            build_manifest(["sample.log", "./sample.log"], root=self.root)

    def test_path_outside_root_is_rejected(self):
        outside_dir = tempfile.TemporaryDirectory()
        self.addCleanup(outside_dir.cleanup)
        outside = Path(outside_dir.name) / "outside.log"
        outside.write_text("x\n", encoding="utf-8")
        with self.assertRaises(ManifestError):
            build_manifest([outside], root=self.root)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_symlink_is_rejected(self):
        target = self.write("real.log", "x\n")
        link = self.root / "link.log"
        link.symlink_to(target)
        with self.assertRaises(ManifestError):
            build_manifest(["link.log"], root=self.root)

    def test_line_count_handles_missing_trailing_newline(self):
        self.write("sample.log", b"one\ntwo")
        manifest = build_manifest(["sample.log"], root=self.root)
        self.assertEqual(manifest["files"][0]["line_count"], 2)
        self.assertEqual(manifest["files"][0]["size_bytes"], 7)

    def test_wrong_schema_fails_closed(self):
        self.write("sample.log", "x\n")
        manifest = build_manifest(["sample.log"], root=self.root)
        manifest["schema"] = "other/v9"
        self.assertEqual(
            verify_manifest(manifest, root=self.root),
            ["unsupported or missing manifest schema"],
        )


if __name__ == "__main__":
    unittest.main()
