from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from douyin import interact


class InteractTests(unittest.TestCase):
    def test_share_returns_public_url_when_panel_is_unavailable(self) -> None:
        opened = {
            "success": True,
            "kind": "video",
            "href": "https://www.douyin.com/video/123456789",
        }
        with (
            mock.patch.object(interact, "_open_detail", return_value=opened),
            mock.patch.object(interact, "_click_text", return_value=False),
        ):
            result = interact.share_video(
                mock.Mock(), "https://www.douyin.com/video/123456789"
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["share_url"], opened["href"])
        self.assertFalse(result["copied_to_clipboard"])


if __name__ == "__main__":
    unittest.main()
