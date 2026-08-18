from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs" / "ADAPTER_AUTHORING.md"


class AdapterAuthoringGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = GUIDE.read_text(encoding="utf-8")

    def test_guide_exists_and_covers_contract_surface(self) -> None:
        self.assertTrue(GUIDE.is_file())
        for term in (
            "PlatformAdapter",
            "PlatformSelectors",
            "parse_content_ref",
            "content_urls",
            "is_platform_url",
            "navigate_publish_image",
            "publish_clicked_unconfirmed",
        ):
            with self.subTest(term=term):
                self.assertIn(term, self.content)

    def test_guide_covers_safety_and_validation_boundaries(self) -> None:
        for term in (
            "captcha",
            "human checkpoint",
            "synthetic",
            "--confirm",
            "ruff check scripts tests/python",
            "npm test",
            "not a compatibility",
        ):
            with self.subTest(term=term):
                self.assertIn(term.lower(), self.content.lower())

    def test_guide_links_to_authoritative_files(self) -> None:
        for relative in (
            "scripts/platform_adapter.py",
            "scripts/douyin/adapter.py",
            "tests/python/test_platform_adapter.py",
            "docs/RESULT_CONTRACT.md",
            "docs/VALIDATION.md",
            "CONTRIBUTING.md",
        ):
            with self.subTest(relative=relative):
                self.assertIn(relative, self.content)
                self.assertTrue((ROOT / relative).is_file())


if __name__ == "__main__":
    unittest.main()
