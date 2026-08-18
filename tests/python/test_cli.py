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
                "version": "1.1.1",
                "result_contract_version": "1.0",
            },
        )

    def test_doctor_command_is_exposed(self) -> None:
        args = cli.build_parser().parse_args(["doctor"])
        self.assertEqual(args.command, "doctor")

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


if __name__ == "__main__":
    unittest.main()
