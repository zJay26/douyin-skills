from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_release import (  # noqa: E402
    build_archive,
    build_release,
    normalize_version,
    safe_relative_path,
    should_include,
)


class BuildReleaseTests(unittest.TestCase):
    def test_version_requires_stable_semantic_versioning(self) -> None:
        self.assertEqual(normalize_version("v1.0.0"), "1.0.0")
        self.assertEqual(normalize_version("2.3.4"), "2.3.4")
        for value in ("1", "1.0", "01.0.0", "v1.0.0-rc.1", "latest", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_version(value)

    def test_release_version_must_match_runtime_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "does not match runtime version"):
                build_release(root, "v2.0.0", root / "dist")

    def test_archive_paths_reject_traversal_and_absolute_values(self) -> None:
        self.assertEqual(
            safe_relative_path("docs/guide.md").as_posix(), "docs/guide.md"
        )
        for value in ("../secret", "docs/../../secret", "/absolute/file", "C:\\secret"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                safe_relative_path(value)

    def test_local_and_generated_directories_are_excluded(self) -> None:
        self.assertTrue(should_include("scripts/cli.py"))
        for value in (
            ".douyin-skills/profile/Cookies",
            ".chrome/Default/Cookies",
            "node_modules/ws/index.js",
            "dist/old.zip",
            "scripts/__pycache__/cli.pyc",
        ):
            with self.subTest(value=value):
                self.assertFalse(should_include(value))

    def test_archive_is_safe_and_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "docs" / "guide.md").write_text("Guide\n", encoding="utf-8")
            first = root / "first.zip"
            second = root / "second.zip"
            files = ["README.md", "docs/guide.md"]

            first_digest = build_archive(
                root, files, first, "project-v1.0.0", 1_700_000_000
            )
            second_digest = build_archive(
                root, reversed(files), second, "project-v1.0.0", 1_700_000_000
            )

            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first_digest, second_digest)
            self.assertEqual(
                first_digest, hashlib.sha256(first.read_bytes()).hexdigest()
            )
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    archive.namelist(),
                    [
                        "project-v1.0.0/README.md",
                        "project-v1.0.0/docs/guide.md",
                    ],
                )
                self.assertTrue(
                    all(
                        name.startswith("project-v1.0.0/") and ".." not in name
                        for name in archive.namelist()
                    )
                )


if __name__ == "__main__":
    unittest.main()
