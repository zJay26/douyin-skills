from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from douyin import publish


class _RecordingPage:
    def __init__(self) -> None:
        self.navigations: list[str] = []

    def navigate(self, url: str) -> None:
        self.navigations.append(url)


class PublishTests(unittest.TestCase):
    def test_relative_image_path_fails_before_navigation(self) -> None:
        page = _RecordingPage()

        result = publish.fill_publish_image(
            page,
            ["relative.jpg"],
            "正文",
            "标题",
        )

        self.assertFalse(result["success"])
        self.assertIn("绝对路径", result["message"])
        self.assertEqual(page.navigations, [])

    def test_image_validation_accepts_existing_supported_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image = Path(temp_dir) / "cover.jpg"
            image.write_bytes(b"test")

            resolved = publish._resolve_image_paths([str(image.resolve())])

        self.assertEqual(resolved, [str(image.resolve())])

    def test_publish_never_clicks_when_validation_cannot_be_read(self) -> None:
        page = mock.Mock()
        with mock.patch.object(
            publish,
            "validate_publish_state",
            return_value={"success": False, "errors": ["无法读取发布页状态"]},
        ):
            result = publish.click_publish(page)

        self.assertFalse(result["success"])
        page.evaluate.assert_not_called()

    def test_unconfirmed_click_is_not_safe_to_retry(self) -> None:
        page = mock.Mock()
        page.evaluate.return_value = {
            "clicked": True,
            "hrefBefore": "https://example.test/upload",
        }
        with (
            mock.patch.object(
                publish,
                "validate_publish_state",
                return_value={"success": True, "errors": []},
            ),
            mock.patch.object(publish, "_wait_until", return_value=None),
            mock.patch.object(
                publish,
                "_page_snapshot",
                return_value={"href": "https://example.test/upload"},
            ),
        ):
            result = publish.click_publish(page)

        self.assertTrue(result["success"])
        self.assertFalse(result["published"])
        self.assertFalse(result["retry_safe"])
        self.assertEqual(result["status"], "publish_clicked_unconfirmed")

    def test_confirmed_publish_is_reported_separately(self) -> None:
        page = mock.Mock()
        page.evaluate.return_value = {"clicked": True}
        confirmation = {
            "confirmed": True,
            "href": "https://example.test/content/manage",
        }
        with (
            mock.patch.object(
                publish,
                "validate_publish_state",
                return_value={"success": True, "errors": []},
            ),
            mock.patch.object(publish, "_wait_until", return_value=confirmation),
        ):
            result = publish.click_publish(page)

        self.assertTrue(result["success"])
        self.assertTrue(result["published"])
        self.assertEqual(result["status"], "publish_confirmed")


if __name__ == "__main__":
    unittest.main()
