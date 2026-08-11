from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import cli


class CliTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
