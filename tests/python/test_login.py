from __future__ import annotations

import subprocess
import sys
import tempfile
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

    def test_settle_login_state_accepts_transient_risk_before_authenticated_ui(
        self,
    ) -> None:
        risk_state = {"logged_in": False, "risk_page": True}
        authenticated_state = {"logged_in": True, "risk_page": False}
        with (
            mock.patch.object(
                login,
                "check_login_state",
                side_effect=[risk_state, authenticated_state],
            ),
            mock.patch.object(login.time, "sleep"),
        ):
            state = login.settle_login_state(
                mock.Mock(), timeout_seconds=2, interval_seconds=1
            )

        self.assertTrue(state["logged_in"])
        self.assertFalse(state["risk_page"])
        self.assertTrue(state["risk_recovered"])
        self.assertEqual(state["risk_recheck_count"], 2)

    def test_settle_login_state_preserves_persistent_risk_checkpoint(self) -> None:
        risk_state = {"logged_in": False, "risk_page": True}
        with (
            mock.patch.object(login, "check_login_state", return_value=risk_state),
            mock.patch.object(login.time, "sleep"),
        ):
            state = login.settle_login_state(
                mock.Mock(), timeout_seconds=0, interval_seconds=1
            )

        self.assertFalse(state["logged_in"])
        self.assertTrue(state["risk_page"])
        self.assertEqual(state["risk_recheck_count"], 1)

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

    def test_qrcode_data_is_written_to_a_nonempty_temporary_file(self) -> None:
        page = mock.Mock()
        data_url = "data:image/png;base64,aGVsbG8="
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            mock.patch.object(login.tempfile, "gettempdir", return_value=temp_dir),
            mock.patch.object(login, "_find_qrcode_data_url", return_value=data_url),
        ):
            result = login.get_qrcode(page)
            qrcode_path = Path(result["qrcode_path"])

            self.assertTrue(result["success"])
            self.assertEqual(qrcode_path.read_bytes(), b"hello")

    def test_valid_phone_dispatches_one_code_request(self) -> None:
        page = mock.Mock()
        page.evaluate.side_effect = [True, True]

        result = login.send_code(page, "+86 138-0013-8000")

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "code_sent")
        self.assertEqual(page.evaluate.call_count, 2)
        self.assertIn("13800138000", page.evaluate.call_args_list[0].args[0])

    def test_valid_code_reports_confirmed_login(self) -> None:
        page = mock.Mock()
        page.evaluate.return_value = True
        with (
            mock.patch.object(login.time, "sleep"),
            mock.patch.object(
                login,
                "check_login_state",
                return_value={"logged_in": True, "risk_page": False},
            ),
        ):
            result = login.verify_code(page, "123456")

        self.assertTrue(result["success"])
        self.assertTrue(result["logged_in"])
        self.assertIn("123456", page.evaluate.call_args.args[0])

    def test_wait_login_returns_immediately_on_risk_page(self) -> None:
        state = {"logged_in": False, "risk_page": True}
        with mock.patch.object(login, "check_login_state", return_value=state):
            result = login.wait_login(mock.Mock(), timeout_seconds=1)

        self.assertTrue(result["risk_page"])


if __name__ == "__main__":
    unittest.main()
