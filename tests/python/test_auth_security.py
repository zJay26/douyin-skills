from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import cli
from douyin import login


class SensitiveInputTests(unittest.TestCase):
    def invoke(self, arguments, stdin=""):
        output, errors = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(sys, "stdin", io.StringIO(stdin)),
            mock.patch.object(
                cli, "start_worker", side_effect=AssertionError("auth worker")
            ),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
            self.assertRaises(SystemExit) as exit_context,
        ):
            cli.main(arguments, background_updates=True)
        return (
            exit_context.exception.code,
            json.loads(output.getvalue()),
            errors.getvalue(),
        )

    def test_stdin_and_environment_secrets_reach_only_the_auth_handler(self):
        for command, name, secret in (
            ("send-code", "phone", "13800138000"),
            ("verify-code", "code", "123456"),
        ):
            for source in ("stdin", "env"):
                arguments = [command, f"--{name}-{source}"]
                if source == "env":
                    arguments.append("DOUYIN_TEST_SECRET")
                with (
                    self.subTest(command=command, source=source),
                    mock.patch.dict(os.environ, {"DOUYIN_TEST_SECRET": secret}),
                    mock.patch.object(
                        cli, "_connect", return_value=(None, mock.Mock())
                    ),
                    mock.patch.object(
                        cli,
                        name == "phone" and "send_code" or "verify_code",
                        return_value={"success": True, "logged_in": True},
                    ) as auth,
                ):
                    code, payload, errors = self.invoke(arguments, secret + "\n")
                    self.assertEqual(code, 0)
                    self.assertEqual(auth.call_args.args[1], secret)
                    self.assertNotIn(secret, json.dumps(payload) + errors)
                    self.assertNotIn(secret, arguments)
                    if source == "env":
                        self.assertNotIn("DOUYIN_TEST_SECRET", os.environ)

    def test_missing_empty_or_oversized_sources_fail_before_connecting(self):
        for arguments, data in (
            (["send-code", "--phone-stdin"], ""),
            (["verify-code", "--code-stdin"], "\n"),
            (["verify-code", "--code-stdin"], "9" * 4097),
            (["send-code", "--phone-env", "DOUYIN_TEST_MISSING"], ""),
        ):
            with (
                self.subTest(arguments=arguments),
                mock.patch.dict(os.environ, {}, clear=True),
                mock.patch.object(cli, "_connect") as connect,
            ):
                code, payload, _errors = self.invoke(arguments, data)
                self.assertEqual(code, 2)
                self.assertFalse(payload["success"])
                connect.assert_not_called()

    def test_conflicting_sources_and_missing_code_are_argument_errors(self):
        for arguments in (
            ["send-code", "--phone-stdin", "--phone-env", "NAME"],
            ["verify-code", "--code-stdin", "--code-env", "NAME"],
            ["verify-code"],
        ):
            with (
                self.subTest(arguments=arguments),
                mock.patch.object(cli, "_connect") as connect,
            ):
                code, payload, _errors = self.invoke(arguments)
                self.assertEqual(code, 2)
                self.assertEqual(payload["error_code"], "invalid_arguments")
                connect.assert_not_called()

    def test_legacy_flags_remain_usable_with_a_value_free_warning(self):
        for name, secret in (("phone", "13800138000"), ("code", "123456")):
            errors = io.StringIO()
            with self.subTest(name=name), contextlib.redirect_stderr(errors):
                value = cli._sensitive_input(argparse.Namespace(**{name: secret}), name)
            self.assertEqual(value, secret)
            self.assertIn(f"--{name}-stdin", errors.getvalue())
            self.assertNotIn(secret, errors.getvalue())
        self.assertEqual(cli._sensitive_input(argparse.Namespace(), "phone"), "")

    def test_terminal_input_uses_no_echo_prompt(self):
        terminal = mock.Mock()
        terminal.isatty.return_value = True
        with (
            mock.patch.object(sys, "stdin", terminal),
            mock.patch.object(cli.getpass, "getpass", return_value="123456") as prompt,
        ):
            value = cli._sensitive_input(argparse.Namespace(code_stdin=True), "code")
        self.assertEqual(value, "123456")
        prompt.assert_called_once()
        terminal.readline.assert_not_called()


class QrcodeSecurityTests(unittest.TestCase):
    data_url = "data:image/png;base64,aGVsbG8="

    def page(self):
        page = mock.Mock()
        page.evaluate.return_value = {}
        return page

    def test_concurrent_qr_files_are_private_unique_and_ignore_legacy_symlinks(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(login.tempfile, "gettempdir", return_value=directory),
            mock.patch.object(
                login, "_find_qrcode_data_url", return_value=self.data_url
            ),
        ):
            legacy = Path(directory) / "douyin-skills"
            legacy.mkdir()
            target = Path(directory) / "sentinel"
            target.write_bytes(b"unchanged")
            # Windows may not grant unprivileged symlink creation.
            if os.name != "nt":
                (legacy / "douyin-login-qrcode.png").symlink_to(target)
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(
                    pool.map(lambda _: login.get_qrcode(self.page()), range(8))
                )
            paths = [Path(result["qrcode_path"]) for result in results]
            self.assertEqual(len(set(paths)), 8)
            self.assertEqual(target.read_bytes(), b"unchanged")
            for result, path in zip(results, paths):
                self.assertTrue(result["success"])
                self.assertNotIn("qrcode_data_url", result)
                self.assertNotIn(self.data_url, json.dumps(result))
                self.assertEqual(path.read_bytes(), b"hello")
                self.assertNotEqual(path.parent, legacy)
                if os.name != "nt":
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                    self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_invalid_qr_data_creates_no_file_and_does_not_echo_data(self):
        for value in (
            "broken",
            "data:image/png;base64,?secret?",
            "data:image/png;base64,",
        ):
            with (
                self.subTest(value=value),
                mock.patch.object(login, "_find_qrcode_data_url", return_value=value),
                mock.patch.object(login.tempfile, "mkdtemp") as create,
            ):
                result = login.get_qrcode(self.page())
            self.assertFalse(result["success"])
            self.assertNotIn(value, json.dumps(result))
            create.assert_not_called()

    def test_failed_private_write_cleans_up(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(login.tempfile, "gettempdir", return_value=directory),
            mock.patch.object(
                login, "_find_qrcode_data_url", return_value=self.data_url
            ),
            mock.patch.object(
                login.os, "fchmod", create=True, side_effect=OSError("denied")
            ),
        ):
            result = login.get_qrcode(self.page())
            self.assertFalse(result["success"])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_captcha_blocks_qr_extraction_sms_request_and_code_submission(self):
        for command, arguments in (
            (login.get_qrcode, ()),
            (login.send_code, ("13800138000",)),
            (login.verify_code, ("123456",)),
        ):
            page = self.page()
            with (
                self.subTest(command=command.__name__),
                mock.patch.object(
                    login, "check_login_state", return_value={"risk_page": True}
                ),
                mock.patch.object(login, "_find_qrcode_data_url") as extract,
            ):
                result = command(page, *arguments)
            self.assertFalse(result["success"])
            self.assertTrue(result["risk_page"])
            page.evaluate.assert_not_called()
            extract.assert_not_called()


if __name__ == "__main__":
    unittest.main()
