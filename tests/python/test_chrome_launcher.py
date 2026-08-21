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

    def test_reuses_existing_browser_even_when_mode_differs(self) -> None:
        with (
            mock.patch.object(chrome_launcher, "is_port_open", return_value=True),
            mock.patch.object(
                chrome_launcher, "_browser_headless_state", return_value=False
            ),
            mock.patch.object(chrome_launcher, "_stop_tracked_browser") as stop,
            mock.patch.object(chrome_launcher, "launch_chrome") as launch,
        ):
            self.assertTrue(chrome_launcher.ensure_chrome(port=9222, headless=True))

        stop.assert_not_called()
        launch.assert_not_called()

    def test_force_mode_switches_only_a_tracked_browser(self) -> None:
        with (
            mock.patch.object(chrome_launcher, "is_port_open", return_value=True),
            mock.patch.object(
                chrome_launcher, "_browser_headless_state", return_value=True
            ),
            mock.patch.object(
                chrome_launcher, "_stop_tracked_browser", return_value=True
            ) as stop,
            mock.patch.object(chrome_launcher, "launch_chrome") as launch,
        ):
            self.assertTrue(
                chrome_launcher.ensure_chrome(
                    port=9222, headless=False, force_mode=True
                )
            )

        stop.assert_called_once_with(9222)
        launch.assert_called_once_with(port=9222, headless=False, user_data_dir=None)


if __name__ == "__main__":
    unittest.main()
