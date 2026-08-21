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
                "version": "1.2.0",
                "result_contract_version": "1.0",
            },
        )

    def test_doctor_command_is_exposed(self) -> None:
        args = cli.build_parser().parse_args(["doctor"])
        self.assertEqual(args.command, "doctor")

    def test_trending_topics_command_is_exposed(self) -> None:
        args = cli.build_parser().parse_args(["get-trending-topics"])
        self.assertEqual(args.command, "get-trending-topics")

    def test_publish_validation_and_confirmation_are_explicit(self) -> None:
        validate_args = cli.build_parser().parse_args(["validate-publish"])
        publish_args = cli.build_parser().parse_args(["click-publish", "--confirm"])

        self.assertEqual(validate_args.command, "validate-publish")
        self.assertTrue(publish_args.confirm)

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


if __name__ == "__main__":
    unittest.main()
