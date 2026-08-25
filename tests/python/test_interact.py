from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from douyin import interact


class InteractTests(unittest.TestCase):
    def _evaluate_action_state_expression(
        self,
        data_e2e_state: str,
        active_state_token: str,
        inactive_state_token: str,
    ) -> dict:
        page = mock.Mock()
        page.evaluate.return_value = {}
        interact._read_action_state_with_styles(
            page,
            '[data-e2e="video-player-digg"]',
            ("已赞",),
            ("rgb(255, 44, 85)",),
            (active_state_token,),
            (inactive_state_token,),
        )
        expression = page.evaluate.call_args.args[0]
        node_script = """
        const stateValue = process.argv[1];
        const expression = process.argv[2];
        const root = {
          innerText: '',
          className: '',
          getAttribute(name) {
            return name === 'data-e2e-state' ? stateValue : null;
          },
          querySelectorAll() { return []; }
        };
        globalThis.document = {querySelector() { return root; }};
        globalThis.getComputedStyle = () => ({color:'', fill:'', stroke:''});
        process.stdout.write(JSON.stringify(eval(expression)));
        """
        result = subprocess.run(
            [
                "node",
                "--input-type=module",
                "-e",
                node_script,
                data_e2e_state,
                expression,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_action_state_javascript_is_syntactically_valid(self) -> None:
        page = mock.Mock()
        page.evaluate.return_value = {}

        interact._read_action_state_with_styles(
            page,
            '[data-e2e="video-player-digg"]',
            ("已赞",),
            ("rgb(255, 44, 85)",),
        )
        expression = page.evaluate.call_args.args[0]
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

    def test_action_state_reads_explicit_platform_attribute(self) -> None:
        cases = (
            (
                "video-player-is-digged",
                "video-player-is-digged",
                "video-player-no-digged",
                "active",
            ),
            (
                "video-player-no-digged",
                "video-player-is-digged",
                "video-player-no-digged",
                "inactive",
            ),
            (
                "video-player-is-collected",
                "video-player-is-collected",
                "video-player-no-collect",
                "active",
            ),
            (
                "video-player-no-collect",
                "video-player-is-collected",
                "video-player-no-collect",
                "inactive",
            ),
        )
        for value, active_token, inactive_token, expected in cases:
            with self.subTest(value=value):
                result = self._evaluate_action_state_expression(
                    value, active_token, inactive_token
                )
                self.assertEqual(result["state"], expected)
                self.assertEqual(result["confidence"], "high")
                self.assertEqual(result["dataE2eState"], value)

    def test_unknown_action_state_blocks_without_clicking(self) -> None:
        page = mock.Mock()
        with mock.patch.object(
            interact,
            "_read_action_state_with_styles",
            return_value={"state": "unknown", "confidence": "none"},
        ):
            result = interact._ensure_action_active(page, "#like")

        self.assertFalse(result["success"])
        self.assertFalse(result["clicked"])
        self.assertEqual(result["blocked_reason"], "interaction_state_unverified")
        page.click.assert_not_called()

    def test_verified_inactive_state_clicks_once_and_confirms_active(self) -> None:
        page = mock.Mock()
        page.click.return_value = True
        with (
            mock.patch.object(
                interact,
                "_read_action_state_with_styles",
                return_value={"state": "inactive", "confidence": "high"},
            ),
            mock.patch.object(
                interact,
                "_wait_for_active_action",
                return_value={"state": "active", "confidence": "high"},
            ),
        ):
            result = interact._ensure_action_active(
                page,
                "#like",
                active_state_tokens=("video-player-is-digged",),
                inactive_state_tokens=("video-player-no-digged",),
            )

        self.assertTrue(result["success"])
        self.assertTrue(result["clicked"])
        self.assertTrue(result["state_verified"])
        page.click.assert_called_once_with("#like")

    def test_like_click_does_not_claim_final_state(self) -> None:
        opened = {
            "success": True,
            "kind": "video",
            "href": "https://www.douyin.com/video/123456789",
        }
        with (
            mock.patch.object(interact, "_open_detail", return_value=opened),
            mock.patch.object(interact, "_first_clickable", return_value="#like"),
            mock.patch.object(
                interact,
                "_ensure_action_active",
                return_value={
                    "success": True,
                    "clicked": True,
                    "state": "unknown",
                    "state_verified": False,
                },
            ),
        ):
            page = mock.Mock()
            result = interact.like_video(page, "123456789")

        self.assertTrue(result["success"])
        self.assertFalse(result["state_verified"])
        self.assertIn("不要自动重复", result["message"])

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

    def test_favorite_uses_platform_button_selector_before_text_fallback(self) -> None:
        opened = {
            "success": True,
            "kind": "video",
            "href": "https://www.douyin.com/video/123456789",
        }
        page = mock.Mock()
        page.click.return_value = True
        with (
            mock.patch.object(interact, "_open_detail", return_value=opened),
            mock.patch.object(
                interact,
                "_first_clickable",
                return_value='[data-e2e="video-player-collect"]',
            ),
            mock.patch.object(
                interact,
                "_ensure_action_active",
                return_value={
                    "success": True,
                    "clicked": True,
                    "state": "unknown",
                    "state_verified": False,
                },
            ),
            mock.patch.object(interact, "_click_text") as click_text,
        ):
            result = interact.favorite_video(page, "123456789")

        self.assertTrue(result["success"])
        self.assertEqual(result["selector"], '[data-e2e="video-player-collect"]')
        click_text.assert_not_called()

    def test_favorite_unknown_state_does_not_use_text_fallback(self) -> None:
        opened = {
            "success": True,
            "kind": "video",
            "href": "https://www.douyin.com/video/123456789",
        }
        with (
            mock.patch.object(interact, "_open_detail", return_value=opened),
            mock.patch.object(interact, "_first_clickable", return_value="#favorite"),
            mock.patch.object(
                interact,
                "_ensure_action_active",
                return_value={
                    "success": False,
                    "clicked": False,
                    "state": "unknown",
                    "state_verified": False,
                    "blocked_reason": "interaction_state_unverified",
                },
            ),
            mock.patch.object(interact, "_click_text", return_value=True) as click_text,
        ):
            result = interact.favorite_video(mock.Mock(), "123456789")

        self.assertFalse(result["success"])
        self.assertFalse(result["clicked"])
        self.assertEqual(result["selector"], "#favorite")
        self.assertEqual(result["blocked_reason"], "interaction_state_unverified")
        self.assertFalse(result["state_verified"])
        click_text.assert_not_called()

    def test_active_like_is_confirmed_without_clicking_again(self) -> None:
        opened = {
            "success": True,
            "kind": "video",
            "href": "https://www.douyin.com/video/123456789",
        }
        page = mock.Mock()
        with (
            mock.patch.object(interact, "_open_detail", return_value=opened),
            mock.patch.object(interact, "_first_clickable", return_value="#like"),
            mock.patch.object(
                interact,
                "_read_action_state_with_styles",
                return_value={
                    "state": "active",
                    "confidence": "high",
                    "selector": "#like",
                },
            ),
        ):
            result = interact.like_video(page, "123456789")

        self.assertTrue(result["success"])
        self.assertTrue(result["state_verified"])
        self.assertFalse(result["clicked"])
        page.click.assert_not_called()

    def test_interaction_state_reads_without_clicking(self) -> None:
        opened = {
            "success": True,
            "kind": "video",
            "href": "https://www.douyin.com/video/123456789",
        }
        page = mock.Mock()
        with (
            mock.patch.object(interact, "_open_detail", return_value=opened),
            mock.patch.object(
                interact,
                "_first_clickable",
                side_effect=["#like", "#favorite"],
            ),
            mock.patch.object(
                interact,
                "_read_action_state_with_styles",
                side_effect=[
                    {"state": "active", "confidence": "high"},
                    {"state": "inactive", "confidence": "high"},
                ],
            ),
        ):
            result = interact.get_interaction_state(page, "123456789")

        self.assertTrue(result["success"])
        self.assertEqual(result["states"]["like"]["state"], "active")
        self.assertEqual(result["states"]["favorite"]["state"], "inactive")
        page.click.assert_not_called()

    def test_comment_confirms_when_comment_appears(self) -> None:
        opened = {
            "success": True,
            "kind": "video",
            "href": "https://www.douyin.com/video/123456789",
        }
        page = mock.Mock()
        page.evaluate.side_effect = [
            {"ok": True, "current": "学到了！！"},
            0,
            {"ok": True, "text": "发送"},
            1,
        ]
        with (
            mock.patch.object(interact, "_open_detail", return_value=opened),
            mock.patch.object(interact.time, "sleep"),
        ):
            result = interact.comment_video(page, "123456789", "学到了！！")

        self.assertTrue(result["success"])
        self.assertEqual(result["state"], "comment_confirmed")
        self.assertTrue(result["state_verified"])
        self.assertEqual(page.evaluate.call_count, 4)

    def test_comment_uses_native_input_for_controlled_editor(self) -> None:
        page = mock.Mock()
        page.insert_text.return_value = True
        page.evaluate.side_effect = [
            {
                "ok": False,
                "reason": "comment-text-missing",
                "inputFound": True,
                "current": "",
            },
            {"ok": True, "current": "学到了！！", "inputFound": True},
        ]

        with mock.patch.object(interact.time, "sleep"):
            result = interact._prepare_comment(page, "学到了！！")

        self.assertTrue(result["ok"])
        self.assertTrue(result["nativeInput"])
        page.insert_text.assert_called_once_with("学到了！！")

    def test_comment_preserves_an_existing_draft(self) -> None:
        opened = {
            "success": True,
            "kind": "video",
            "href": "https://www.douyin.com/video/123456789",
        }
        page = mock.Mock()
        page.evaluate.return_value = {
            "ok": False,
            "reason": "comment-input-not-empty",
            "current": "用户原有草稿",
        }
        with (
            mock.patch.object(interact, "_open_detail", return_value=opened),
            mock.patch.object(interact, "_open_comment_composer") as open_composer,
        ):
            result = interact.comment_video(page, "123456789", "学到了！！")

        self.assertFalse(result["success"])
        self.assertEqual(result["state"], "comment_input_not_empty")
        open_composer.assert_not_called()
        page.insert_text.assert_not_called()

    def test_comment_does_not_send_without_input(self) -> None:
        opened = {
            "success": True,
            "kind": "video",
            "href": "https://www.douyin.com/video/123456789",
        }
        page = mock.Mock()
        page.evaluate.return_value = {
            "ok": False,
            "reason": "comment-input-not-found",
        }
        with (
            mock.patch.object(interact, "_open_detail", return_value=opened),
            mock.patch.object(
                interact,
                "_open_comment_composer",
                return_value={"ok": False, "reason": "comment-action-not-found"},
            ),
        ):
            result = interact.comment_video(page, "123456789", "学到了！！")

        self.assertFalse(result["success"])
        self.assertEqual(result["state"], "comment_input_not_found")
        self.assertEqual(page.evaluate.call_count, 1)

    def test_comment_click_unconfirmed_is_not_retried(self) -> None:
        opened = {
            "success": True,
            "kind": "video",
            "href": "https://www.douyin.com/video/123456789",
        }
        page = mock.Mock()
        page.evaluate.side_effect = [
            {"ok": True, "current": "学到了！！"},
            0,
            {"ok": True, "text": "发送"},
            0,
            0,
            0,
            0,
            0,
        ]
        with (
            mock.patch.object(interact, "_open_detail", return_value=opened),
            mock.patch.object(interact.time, "sleep"),
        ):
            result = interact.comment_video(page, "123456789", "学到了！！")

        self.assertTrue(result["success"])
        self.assertEqual(result["state"], "comment_clicked_unconfirmed")
        self.assertFalse(result["state_verified"])
        self.assertEqual(page.evaluate.call_count, 8)

    def test_existing_matching_comment_does_not_false_confirm(self) -> None:
        opened = {
            "success": True,
            "kind": "video",
            "href": "https://www.douyin.com/video/123456789",
        }
        page = mock.Mock()
        page.evaluate.side_effect = [
            {"ok": True, "current": "学到了！！"},
            1,
            {"ok": True, "text": "发送"},
            1,
            1,
            1,
            1,
            1,
        ]
        with (
            mock.patch.object(interact, "_open_detail", return_value=opened),
            mock.patch.object(interact.time, "sleep"),
        ):
            result = interact.comment_video(page, "123456789", "学到了！！")

        self.assertEqual(result["state"], "comment_clicked_unconfirmed")
        self.assertFalse(result["state_verified"])


if __name__ == "__main__":
    unittest.main()
