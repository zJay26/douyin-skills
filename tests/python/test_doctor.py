from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import doctor


class DoctorTests(unittest.TestCase):
    def inspect(self, node: str, accounts_error=None) -> dict:
        with (
            mock.patch.object(
                doctor, "_command_version", side_effect=[(True, node), (True, "10.0.0")]
            ),
            mock.patch.object(doctor, "_check_ws", return_value=(True, "available")),
            mock.patch.object(doctor, "find_chrome", return_value="chrome"),
            mock.patch.object(
                doctor, "list_accounts", return_value=[], side_effect=accounts_error
            ),
        ):
            return doctor.run_doctor()

    def test_unsupported_node_is_not_ready(self) -> None:
        for version in ("v16.20.0", "unrecognized"):
            with self.subTest(version=version):
                result = self.inspect(version)
                self.assertFalse(result["success"])
                self.assertIn("node", result["required_failures"])

    def test_corrupt_accounts_preserve_other_diagnostics(self) -> None:
        result = self.inspect("v24.0.0", ValueError("corrupt config"))
        self.assertFalse(result["success"])
        self.assertEqual(result["required_failures"], ["accounts"])
        self.assertIsNone(result["accounts"]["count"])
        self.assertTrue(
            next(check["ok"] for check in result["checks"] if check["name"] == "node")
        )

    def test_supported_runtime_is_ready(self) -> None:
        self.assertTrue(self.inspect("v18.0.0")["success"])
