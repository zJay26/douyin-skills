from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from douyin import login


class LoginTests(unittest.TestCase):
    def test_login_inspection_javascript_is_syntactically_valid(self) -> None:
        page = mock.Mock()
        page.evaluate.return_value = {}

        login.inspect_login_state(page)
        expression = page.evaluate.call_args.args[0]
        result = subprocess.run(
            [
                "node",
                "--input-type=module",
                "-e",
                "new Function(process.argv[1])",
                expression,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_public_content_page_is_not_treated_as_logged_in(self) -> None:
        info = {
            "href": "https://www.douyin.com/video/123456789",
            "loggedInHintCount": 1,
            "hasProfileUi": False,
            "hasAuthCookie": False,
            "hasLoginPanel": False,
            "hasLoginKeyword": False,
            "hasRiskKeyword": False,
        }
        with mock.patch.object(login, "inspect_login_state", return_value=info):
            state = login.check_login_state(mock.Mock())

        self.assertFalse(state["logged_in"])

    def test_auth_cookie_is_high_confidence_login_marker(self) -> None:
        info = {
            "hasProfileUi": False,
            "hasAuthCookie": True,
            "hasLoginPanel": False,
            "hasLoginKeyword": False,
            "hasRiskKeyword": False,
        }
        with mock.patch.object(login, "inspect_login_state", return_value=info):
            state = login.check_login_state(mock.Mock())

        self.assertTrue(state["logged_in"])

    def test_visible_login_panel_overrides_stale_cookie(self) -> None:
        info = {
            "hasProfileUi": False,
            "hasAuthCookie": True,
            "hasLoginPanel": True,
            "hasLoginKeyword": True,
            "hasRiskKeyword": False,
        }
        with mock.patch.object(login, "inspect_login_state", return_value=info):
            state = login.check_login_state(mock.Mock())

        self.assertFalse(state["logged_in"])

    def test_invalid_phone_and_code_fail_before_page_actions(self) -> None:
        page = mock.Mock()

        phone_result = login.send_code(page, "123")
        code_result = login.verify_code(page, "12ab")

        self.assertFalse(phone_result["success"])
        self.assertFalse(code_result["success"])
        page.navigate.assert_not_called()
        page.evaluate.assert_not_called()

    def test_wait_login_returns_immediately_on_risk_page(self) -> None:
        state = {"logged_in": False, "risk_page": True}
        with mock.patch.object(login, "check_login_state", return_value=state):
            result = login.wait_login(mock.Mock(), timeout_seconds=1)

        self.assertTrue(result["risk_page"])


if __name__ == "__main__":
    unittest.main()
