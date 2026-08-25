from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import cli


class CliTests(unittest.TestCase):
    def test_all_documented_commands_are_exposed(self) -> None:
        expected = {
            "version",
            "doctor",
            "check-login",
            "get-qrcode",
            "wait-login",
            "list-accounts",
            "send-code",
            "verify-code",
            "add-account",
            "remove-account",
            "set-default-account",
            "search-videos",
            "get-trending-topics",
            "get-video-detail",
            "fill-publish-image",
            "fill-publish-video",
            "set-video-cover",
            "select-music",
            "validate-publish",
            "click-publish",
            "validate-publish-video",
            "click-publish-video",
            "like-video",
            "favorite-video",
            "comment-video",
            "get-interaction-state",
            "share-video",
        }
        parser = cli.build_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )

        self.assertEqual(set(subparsers.choices), expected)

    def test_version_command_returns_contract_metadata_without_chrome(self) -> None:
        stdout = io.StringIO()
        with (
            mock.patch.object(
                cli,
                "_connect",
                side_effect=AssertionError("version must not connect to Chrome"),
            ),
            contextlib.redirect_stdout(stdout),
            self.assertRaises(SystemExit) as exit_context,
        ):
            cli.main(["version"])

        self.assertEqual(exit_context.exception.code, 0)
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "success": True,
                "project": "douyin-skills",
                "version": "1.4.0",
                "result_contract_version": "1.0",
            },
        )

    def test_doctor_command_is_exposed(self) -> None:
        args = cli.build_parser().parse_args(["doctor"])
        self.assertEqual(args.command, "doctor")

    def test_trending_topics_command_is_exposed(self) -> None:
        args = cli.build_parser().parse_args(["get-trending-topics"])
        self.assertEqual(args.command, "get-trending-topics")

    def test_comment_command_requires_target_and_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["comment-video", "--video-id", "123456789", "--comment", "学到了！！"]
        )
        self.assertEqual(args.command, "comment-video")
        self.assertEqual(args.comment, "学到了！！")

    def test_interaction_state_command_is_exposed(self) -> None:
        args = cli.build_parser().parse_args(
            ["get-interaction-state", "--video-id", "123456789"]
        )
        self.assertEqual(args.command, "get-interaction-state")

    def test_publish_validation_and_confirmation_are_explicit(self) -> None:
        validate_args = cli.build_parser().parse_args(["validate-publish"])
        publish_args = cli.build_parser().parse_args(["click-publish", "--confirm"])
        validate_video_args = cli.build_parser().parse_args(["validate-publish-video"])
        publish_video_args = cli.build_parser().parse_args(
            ["click-publish-video", "--confirm"]
        )

        self.assertEqual(validate_args.command, "validate-publish")
        self.assertTrue(publish_args.confirm)
        self.assertEqual(validate_video_args.command, "validate-publish-video")
        self.assertTrue(publish_video_args.confirm)

    def test_non_loopback_hosts_are_rejected(self) -> None:
        self.assertTrue(cli._is_loopback_host("127.0.0.1"))
        self.assertTrue(cli._is_loopback_host("::1"))
        self.assertTrue(cli._is_loopback_host("localhost"))
        self.assertFalse(cli._is_loopback_host("0.0.0.0"))
        self.assertFalse(cli._is_loopback_host("example.com"))

    def test_port_range_is_validated(self) -> None:
        self.assertEqual(cli._valid_port("9222"), 9222)
        with self.assertRaises(argparse.ArgumentTypeError):
            cli._valid_port("70000")

    def test_search_limit_is_validated(self) -> None:
        self.assertEqual(cli._valid_search_limit("1"), 1)
        self.assertEqual(cli._valid_search_limit("20"), 20)
        for value in ("0", "-1", "21", "many"):
            with (
                self.subTest(value=value),
                self.assertRaises(argparse.ArgumentTypeError),
            ):
                cli._valid_search_limit(value)

    def test_connect_reuses_existing_browser_unless_headed_is_explicit(self) -> None:
        page = mock.Mock(target_id="target")
        browser = mock.Mock()
        browser.get_page_by_target_id.return_value = page
        with (
            mock.patch.object(cli, "ensure_chrome", return_value=True) as ensure,
            mock.patch.object(cli, "Browser", return_value=browser),
            mock.patch.object(cli, "_load_session_tab", return_value="target"),
            mock.patch.object(cli, "_save_session_tab"),
        ):
            cli._connect(cli.build_parser().parse_args(["check-login"]))
            self.assertFalse(ensure.call_args.kwargs["force_mode"])

            cli._connect(cli.build_parser().parse_args(["--headed", "check-login"]))
            self.assertTrue(ensure.call_args.kwargs["force_mode"])

    def test_check_login_accepts_recovery_after_headed_switch(self) -> None:
        initial_page = mock.Mock()
        headed_page = mock.Mock()
        adapter = mock.Mock()
        risk_state = {
            "success": True,
            "logged_in": False,
            "risk_page": True,
        }
        recovered_state = {
            "success": True,
            "logged_in": True,
            "risk_page": False,
        }
        stdout = io.StringIO()
        with (
            mock.patch.object(cli, "get_default_adapter", return_value=adapter),
            mock.patch.object(
                cli,
                "_connect",
                side_effect=[
                    (mock.Mock(), initial_page),
                    (mock.Mock(), headed_page),
                ],
            ),
            mock.patch.object(
                cli,
                "settle_login_state",
                side_effect=[risk_state, recovered_state],
            ),
            contextlib.redirect_stdout(stdout),
            self.assertRaises(SystemExit) as exit_context,
        ):
            cli.main(["check-login"])

        result = json.loads(stdout.getvalue())
        self.assertEqual(exit_context.exception.code, 0)
        self.assertTrue(result["logged_in"])
        self.assertFalse(result["risk_page"])
        self.assertFalse(result["needs_user_verification"])
        self.assertTrue(result["risk_recovered"])
        self.assertEqual(result["action"], "risk_recovered_after_headed_switch")
        self.assertEqual(adapter.navigate_home.call_count, 2)

    def test_check_login_preserves_persistent_headed_risk(self) -> None:
        initial_page = mock.Mock()
        headed_page = mock.Mock()
        adapter = mock.Mock()
        risk_state = {
            "success": True,
            "logged_in": False,
            "risk_page": True,
        }
        stdout = io.StringIO()
        with (
            mock.patch.object(cli, "get_default_adapter", return_value=adapter),
            mock.patch.object(
                cli,
                "_connect",
                side_effect=[
                    (mock.Mock(), initial_page),
                    (mock.Mock(), headed_page),
                ],
            ),
            mock.patch.object(
                cli,
                "settle_login_state",
                side_effect=[risk_state, risk_state],
            ),
            mock.patch.object(cli, "_risk_or_verify_text", return_value="risk"),
            contextlib.redirect_stdout(stdout),
            self.assertRaises(SystemExit) as exit_context,
        ):
            cli.main(["check-login"])

        result = json.loads(stdout.getvalue())
        self.assertEqual(exit_context.exception.code, 2)
        self.assertFalse(result["logged_in"])
        self.assertTrue(result["risk_page"])
        self.assertTrue(result["needs_user_verification"])


if __name__ == "__main__":
    unittest.main()
