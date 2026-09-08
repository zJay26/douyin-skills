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
            "capabilities",
            "browser-status",
            "update-account",
            "check-update",
            "update-status",
            "update-config",
            "download-update",
            "install-update",
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
                "version": "1.6.0",
                "result_contract_version": "1.1",
            },
        )

    def test_doctor_command_is_exposed(self) -> None:
        args = cli.build_parser().parse_args(["doctor"])
        self.assertEqual(args.command, "doctor")

    def run_json(self, arguments: list[str]) -> tuple[int, dict]:
        stdout = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            self.assertRaises(SystemExit) as result,
        ):
            cli.main(arguments)
        return result.exception.code, json.loads(stdout.getvalue())

    def test_capabilities_are_offline_and_describe_real_arguments(self) -> None:
        with mock.patch.object(cli, "_connect", side_effect=AssertionError("offline")):
            code, payload = self.run_json(["capabilities"])
        commands = {item["name"]: item for item in payload["commands"]}
        self.assertEqual(code, 0)
        publish = commands["click-publish-video"]
        self.assertTrue(publish["requires_confirmation"])
        self.assertEqual(publish["retry_policy"], "never_automatically")
        self.assertFalse(commands["capabilities"]["requires_browser"])
        arguments = {arg["name"]: arg for arg in commands["search-videos"]["arguments"]}
        self.assertTrue(arguments["keyword"]["required"])
        self.assertEqual(arguments["limit"]["maximum"], 20)

    def test_argument_errors_are_json_and_do_not_start_browser(self) -> None:
        for arguments in (
            [],
            ["unknown"],
            ["search-videos"],
            ["--port", "0", "check-login"],
            ["click-publish", "--conf"],
            ["click-publish-video", "--conf"],
        ):
            with (
                self.subTest(arguments=arguments),
                mock.patch.object(cli, "_connect") as connect,
            ):
                code, payload = self.run_json(arguments)
                self.assertEqual(code, 2)
                self.assertFalse(payload["success"])
                self.assertEqual(payload["error_code"], "invalid_arguments")
                connect.assert_not_called()

    def test_publish_without_confirmation_never_connects(self) -> None:
        for command in ("click-publish", "click-publish-video"):
            with (
                self.subTest(command=command),
                mock.patch.object(cli, "_connect") as connect,
            ):
                code, payload = self.run_json([command])
                self.assertEqual(code, 2)
                self.assertFalse(payload["success"])
                connect.assert_not_called()

    def test_browser_status_is_attach_only_and_hides_tab_contents_by_default(
        self,
    ) -> None:
        browser = mock.Mock()
        browser.version.return_value = {
            "success": True,
            "browser": "Chrome/test",
            "protocol_version": "1.3",
        }
        browser.list_pages.return_value = [
            {
                "id": "target",
                "type": "page",
                "title": "private title",
                "url": "https://example.test/private",
                "webSocketDebuggerUrl": "ws://private",
            }
        ]
        with (
            mock.patch.object(cli, "Browser", return_value=browser),
            mock.patch.object(cli, "ensure_chrome") as launch,
            mock.patch.object(cli, "_load_session_tab", return_value="target"),
            mock.patch.object(cli, "_save_session_tab") as save,
        ):
            code, payload = self.run_json(["--port", "9333", "browser-status"])
            self.assertEqual(code, 0)
            self.assertTrue(payload["session_target_found"])
            self.assertEqual(payload["page_count"], 1)
            self.assertNotIn("private", json.dumps(payload))
            _, expanded = self.run_json(
                ["--port", "9333", "browser-status", "--include-tabs"]
            )
            self.assertEqual(expanded["tabs"][0]["title"], "private title")
            self.assertNotIn("webSocketDebuggerUrl", expanded["tabs"][0])
            launch.assert_not_called()
            save.assert_not_called()
            browser.new_page.assert_not_called()

    def test_browser_status_reports_connection_failure_without_launch(self) -> None:
        browser = mock.Mock()
        browser.version.side_effect = cli.CDPError("closed", "connection_closed")
        with (
            mock.patch.object(cli, "Browser", return_value=browser),
            mock.patch.object(cli, "ensure_chrome") as launch,
        ):
            code, payload = self.run_json(["--port", "9333", "browser-status"])
        self.assertEqual(code, 2)
        self.assertFalse(payload["connected"])
        self.assertEqual(payload["error_code"], "connection_closed")
        launch.assert_not_called()

    def test_explicit_missing_target_never_creates_or_launches(self) -> None:
        browser = mock.Mock()
        browser.get_page_by_target_id.return_value = None
        with (
            mock.patch.object(cli, "Browser", return_value=browser),
            mock.patch.object(cli, "ensure_chrome") as launch,
        ):
            code, payload = self.run_json(
                ["--port", "9333", "--target-id", "gone", "check-login"]
            )
        self.assertEqual(code, 2)
        self.assertFalse(payload["success"])
        launch.assert_not_called()
        browser.get_or_create_page.assert_not_called()

    def test_missing_publish_session_never_selects_an_unrelated_page(self) -> None:
        browser = mock.Mock()
        with (
            mock.patch.object(cli, "Browser", return_value=browser),
            mock.patch.object(cli, "ensure_chrome", return_value=True),
            mock.patch.object(cli, "_load_session_tab", return_value=None),
        ):
            code, payload = self.run_json(["--port", "9333", "validate-publish"])
        self.assertEqual(code, 2)
        self.assertFalse(payload["success"])
        browser.get_or_create_page.assert_not_called()

    def test_session_keys_separate_profiles_and_loopback_endpoints(self) -> None:
        first = cli._session_tab_file(9333, "localhost", "first")
        self.assertEqual(first, cli._session_tab_file(9333, "127.0.0.1", "first"))
        self.assertNotEqual(first, cli._session_tab_file(9333, "127.0.0.1", "second"))
        self.assertNotEqual(first, cli._session_tab_file(9333, "::1", "first"))

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
