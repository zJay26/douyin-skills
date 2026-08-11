from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import chrome_launcher


class ChromeLauncherTests(unittest.TestCase):
    def test_launch_command_binds_debugging_to_loopback(self) -> None:
        command = chrome_launcher._prepare_launch_cmd(
            "chrome", 9222, True, "/tmp/douyin-profile"
        )

        self.assertIn("--remote-debugging-address=127.0.0.1", command)
        self.assertIn("--remote-debugging-port=9222", command)
        self.assertIn("--headless=new", command)

    def test_headed_command_does_not_add_headless_flag(self) -> None:
        command = chrome_launcher._prepare_launch_cmd(
            "chrome", 9222, False, "/tmp/douyin-profile"
        )

        self.assertNotIn("--headless=new", command)

    def test_chrome_bin_environment_variable_takes_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = Path(temp_dir) / (
                "chrome.exe" if sys.platform == "win32" else "chrome"
            )
            executable.touch()
            with mock.patch.dict(os.environ, {"CHROME_BIN": str(executable)}):
                self.assertEqual(chrome_launcher.find_chrome(), str(executable))


if __name__ == "__main__":
    unittest.main()
