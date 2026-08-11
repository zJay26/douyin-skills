from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from douyin.urls import content_urls, parse_content_ref, search_url


class UrlTests(unittest.TestCase):
    def test_search_keyword_is_encoded_as_one_path_segment(self) -> None:
        self.assertEqual(
            search_url("猫 / 日常"),
            "https://www.douyin.com/search/%E7%8C%AB%20%2F%20%E6%97%A5%E5%B8%B8?type=video",
        )

    def test_public_video_and_note_links_are_accepted(self) -> None:
        self.assertEqual(
            parse_content_ref("https://www.douyin.com/video/123456789?modal=1"),
            ("123456789", "video"),
        )
        self.assertEqual(
            content_urls("https://www.douyin.com/note/987654321"),
            [("note", "https://www.douyin.com/note/987654321")],
        )

    def test_non_douyin_links_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_content_ref("https://example.com/video/123456789")


if __name__ == "__main__":
    unittest.main()
