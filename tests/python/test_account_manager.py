from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import account_manager
import cli


class AccountManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.patches = [
            mock.patch.object(account_manager, "_CONFIG_DIR", root),
            mock.patch.object(
                account_manager, "_ACCOUNTS_FILE", root / "accounts.json"
            ),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temp_dir.cleanup()

    def test_default_account_is_used_when_account_is_omitted(self) -> None:
        created = account_manager.add_account("work", "工作号")
        args = argparse.Namespace(account="", port=None)

        profile = cli._resolve_account(args)

        self.assertEqual(args.account, "work")
        self.assertEqual(args.port, created["port"])
        self.assertEqual(profile, created["profile_dir"])

    def test_explicit_port_bypasses_default_account(self) -> None:
        account_manager.add_account("work")
        args = argparse.Namespace(account="", port=9333)

        profile = cli._resolve_account(args)

        self.assertIsNone(profile)
        self.assertEqual(args.port, 9333)

    def test_rejects_path_traversal_account_name(self) -> None:
        for name in ("../work", "team\\work", ".", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                account_manager.add_account(name)

    def test_reuses_lowest_available_named_port(self) -> None:
        first = account_manager.add_account("first")
        account_manager.add_account("second")
        account_manager.remove_account("first")

        third = account_manager.add_account("third")

        self.assertEqual(third["port"], first["port"])

    def test_add_list_set_default_and_remove_account_lifecycle(self) -> None:
        account_manager.add_account("first", "first profile")
        account_manager.add_account("second", "second profile")

        account_manager.set_default_account("second")
        listed = account_manager.list_accounts()

        self.assertEqual([item["name"] for item in listed], ["first", "second"])
        self.assertFalse(listed[0]["is_default"])
        self.assertTrue(listed[1]["is_default"])

        account_manager.remove_account("second")
        remaining = account_manager.list_accounts()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["name"], "first")
        self.assertTrue(remaining[0]["is_default"])

    def test_corrupt_config_has_actionable_error(self) -> None:
        account_manager._CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        account_manager._ACCOUNTS_FILE.write_text("{broken", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "账号配置已损坏"):
            account_manager.list_accounts()

    def test_config_write_is_valid_json(self) -> None:
        account_manager.add_account("个人号", "日常使用")

        data = json.loads(account_manager._ACCOUNTS_FILE.read_text(encoding="utf-8"))

        self.assertEqual(data["default"], "个人号")
        self.assertEqual(data["accounts"]["个人号"]["description"], "日常使用")


if __name__ == "__main__":
    unittest.main()
