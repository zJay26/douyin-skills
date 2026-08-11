from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from validate_repository import (  # noqa: E402
    contains_cjk,
    extract_local_links,
    parse_gif,
    validate_repository,
)


class RepositoryValidationTests(unittest.TestCase):
    def test_english_visual_assets_reject_cjk_text(self) -> None:
        self.assertFalse(contains_cjk("Prepared. Not published."))
        self.assertTrue(contains_cjk("已准备，未发布。"))

    def test_demo_gif_has_release_metadata(self) -> None:
        metadata = parse_gif(ROOT / "assets" / "demo.gif")

        self.assertEqual((metadata.width, metadata.height), (960, 540))
        self.assertEqual(metadata.frames, 200)
        self.assertEqual(metadata.duration_seconds, 40)
        self.assertTrue(metadata.loops)

    def test_local_link_extraction_ignores_remote_and_anchor_links(self) -> None:
        markdown = """[local](./docs/guide.md)
[remote](https://example.com/readme)
[anchor](#usage)
<img src="./assets/demo.gif" alt="demo">
"""

        self.assertEqual(
            extract_local_links(markdown),
            [(1, "./docs/guide.md"), (4, "./assets/demo.gif")],
        )

    def test_missing_markdown_target_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("[missing](./nope.md)\n", encoding="utf-8")

            errors = validate_repository(root)

        self.assertTrue(
            any("missing link target: ./nope.md" in error for error in errors)
        )

    def test_current_repository_passes_integrity_checks(self) -> None:
        self.assertEqual(validate_repository(ROOT), [])


if __name__ == "__main__":
    unittest.main()
