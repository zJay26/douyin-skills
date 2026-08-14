from __future__ import annotations

import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from douyin import interact, login, publish, search  # noqa: E402
from douyin.adapter import DEFAULT_ADAPTER  # noqa: E402
from platform_adapter import PlatformAdapter  # noqa: E402


class PlatformAdapterTests(unittest.TestCase):
    def assert_javascript_parses(self, expression: str) -> None:
        result = subprocess.run(
            [
                "node",
                "--input-type=module",
                "-e",
                "new Function(process.argv[1])",
                expression,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_shipped_adapter_implements_shared_contract(self) -> None:
        self.assertIsInstance(DEFAULT_ADAPTER, PlatformAdapter)
        self.assertEqual(DEFAULT_ADAPTER.key, "douyin")
        self.assertEqual(
            DEFAULT_ADAPTER.content_urls("https://www.douyin.com/note/987"),
            [("note", "https://www.douyin.com/note/987")],
        )

    def test_login_uses_injected_platform_markers(self) -> None:
        selectors = replace(
            DEFAULT_ADAPTER.selectors,
            login_text_keywords=("adapter-login",),
            login_panel_markers=("adapter-panel",),
            logged_in_text_hints=("adapter-session",),
        )
        adapter = replace(DEFAULT_ADAPTER, selectors=selectors)
        page = mock.Mock()
        page.evaluate.return_value = {}

        login.inspect_login_state(page, adapter=adapter)

        expression = page.evaluate.call_args.args[0]
        self.assertIn("adapter-login", expression)
        self.assertIn("adapter-panel", expression)
        self.assertIn("adapter-session", expression)

    def test_search_uses_injected_navigation_and_result_selector(self) -> None:
        selectors = replace(
            DEFAULT_ADAPTER.selectors,
            search_result_selectors=("a[data-adapter-result]",),
        )
        adapter = replace(
            DEFAULT_ADAPTER,
            search_base_url="https://adapter.example/search/",
            selectors=selectors,
        )
        page = mock.Mock()
        page.evaluate.side_effect = [
            True,
            {
                "title": "ready",
                "text": "result",
                "items": [
                    {
                        "href": "https://www.douyin.com/video/123",
                        "text": "synthetic",
                        "title": "synthetic",
                        "author": "author",
                    }
                ],
            },
        ]
        with mock.patch.object(
            search,
            "wait_for_meaningful_text",
            return_value={"title": "ready", "text": "result"},
        ):
            result = search.search_videos(
                page, "adapter query", limit=1, adapter=adapter
            )

        page.navigate.assert_called_once_with(
            "https://adapter.example/search/adapter%20query?type=video"
        )
        self.assertTrue(
            any(
                "a[data-adapter-result]" in call.args[0]
                for call in page.evaluate.call_args_list
            )
        )
        self.assert_javascript_parses(page.evaluate.call_args_list[1].args[0])
        self.assertTrue(result["success"])

    def test_interaction_detail_urls_are_owned_by_injected_adapter(self) -> None:
        adapter = replace(
            DEFAULT_ADAPTER,
            platform_hosts=("adapter.example",),
            content_url_templates={
                "video": "https://adapter.example/post/{id}",
                "note": "https://adapter.example/note/{id}",
            },
        )
        page = mock.Mock()
        page.evaluate.side_effect = [
            "title",
            "收藏 分享 评论",
            "https://adapter.example/post/123",
        ]

        result = interact._open_detail(page, "123", adapter=adapter)

        self.assertTrue(result["success"])
        page.navigate.assert_called_once_with("https://adapter.example/post/123")

    def test_publish_validation_uses_injected_form_selectors(self) -> None:
        selectors = replace(
            DEFAULT_ADAPTER.selectors,
            publish_title_input_selector="input[data-adapter-title]",
            publish_editor_selectors=("[data-adapter-editor]",),
            publish_file_input_selector="input[data-adapter-file]",
        )
        adapter = replace(DEFAULT_ADAPTER, selectors=selectors)
        page = mock.Mock()
        page.evaluate.return_value = {
            "title": "title",
            "editorText": "body",
            "hasImage": True,
            "hasMusic": True,
            "hasTopic": False,
        }

        result = publish.validate_publish_state(page, adapter=adapter)

        expression = page.evaluate.call_args.args[0]
        self.assertIn("data-adapter-title", expression)
        self.assertIn("data-adapter-editor", expression)
        self.assertIn("data-adapter-file", expression)
        self.assert_javascript_parses(expression)
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
