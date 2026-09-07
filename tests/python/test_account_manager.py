from __future__ import annotations

import argparse
import json
import os
import subprocess
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

    def test_windows_unsafe_names_are_rejected_before_profile_creation(self) -> None:
        for name in (
            "NUL",
            "com1.txt",
            "work.",
            "work:stream",
            "bad?name",
            "team|work",
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                account_manager.add_account(name)
        self.assertFalse(account_manager._ACCOUNTS_FILE.exists())

    def test_duplicate_ports_and_case_collisions_are_rejected_without_rewrite(
        self,
    ) -> None:
        for accounts in (
            {"a": {"port": 9333}, "b": {"port": 9333}},
            {"Work": {"port": 9333}, "work": {"port": 9334}},
        ):
            with self.subTest(accounts=accounts):
                original = json.dumps({"accounts": accounts})
                account_manager._ACCOUNTS_FILE.write_text(original, encoding="utf-8")
                with self.assertRaises(ValueError):
                    account_manager.add_account("new")
                self.assertEqual(
                    account_manager._ACCOUNTS_FILE.read_text(encoding="utf-8"), original
                )

    def test_update_description_preserves_profile_and_port(self) -> None:
        original = account_manager.add_account("work", "old")
        account_manager.update_account_description("work", "new")
        updated = account_manager.list_accounts()[0]
        self.assertEqual(updated["description"], "new")
        self.assertEqual(updated["port"], original["port"])
        self.assertEqual(updated["profile_dir"], original["profile_dir"])

    def test_parallel_process_updates_do_not_lose_accounts(self) -> None:
        script = (
            "import account_manager,time,sys; "
            "original=account_manager._save_config; "
            "account_manager._save_config=lambda config: (time.sleep(0.1), original(config)); "
            "account_manager.add_account(sys.argv[1])"
        )
        environment = {
            **os.environ,
            "DOUYIN_SKILLS_HOME": self.temp_dir.name,
            "PYTHONPATH": str(SCRIPTS_DIR),
        }
        processes = [
            subprocess.Popen(
                [sys.executable, "-c", script, f"worker-{index}"],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            for index in range(6)
        ]
        try:
            for process in processes:
                stdout, stderr = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, stdout + stderr)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate()
        accounts = account_manager.list_accounts()
        self.assertEqual(len(accounts), 6)
        self.assertEqual(len({account["port"] for account in accounts}), 6)
        self.assertEqual(sum(account["is_default"] for account in accounts), 1)

    def test_failed_atomic_replace_preserves_existing_configuration(self) -> None:
        account_manager.add_account("work", "original")
        previous = account_manager._ACCOUNTS_FILE.read_bytes()
        with (
            mock.patch("local_state.os.replace", side_effect=OSError("replace failed")),
            self.assertRaises(OSError),
        ):
            account_manager.update_account_description("work", "changed")
        self.assertEqual(account_manager._ACCOUNTS_FILE.read_bytes(), previous)
        self.assertFalse(list(account_manager._CONFIG_DIR.glob(".accounts.json.*")))
        account_manager.update_account_description("work", "recovered")
        self.assertEqual(account_manager.list_accounts()[0]["description"], "recovered")


if __name__ == "__main__":
    unittest.main()
