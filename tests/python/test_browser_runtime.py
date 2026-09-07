from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import browser_runtime as runtime
from douyin.cdp import Browser, Page


class BrowserRuntimeTests(unittest.TestCase):
    def test_legacy_imports_share_the_platform_neutral_runtime(self) -> None:
        self.assertIs(Browser, runtime.Browser)
        self.assertIs(Page, runtime.Page)

    def test_large_unicode_payload_uses_utf8_stdin(self) -> None:
        expression = "中文内容" * 20000
        response = subprocess.CompletedProcess(
            [], 0, '{"success":true,"value":"中文"}', ""
        )
        with mock.patch.object(runtime.subprocess, "run", return_value=response) as run:
            result = runtime._run_node("evaluate", {"expression": expression})
        self.assertEqual(result["value"], "中文")
        self.assertEqual(run.call_args.args[0][-1], "-")
        self.assertNotIn(expression, run.call_args.args[0])
        self.assertEqual(
            json.loads(run.call_args.kwargs["input"])["expression"], expression
        )
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")

    def test_rejected_endpoints_never_start_a_process(self) -> None:
        for payload in (
            {"host": "example.test"},
            {"host": "0.0.0.0"},
            {"port": True},
            {"port": 0},
            {"port": 65536},
        ):
            with (
                self.subTest(payload=payload),
                mock.patch.object(runtime.subprocess, "run") as run,
                self.assertRaises(ValueError),
            ):
                runtime._run_node("list", payload)
            run.assert_not_called()

    def test_protocol_failure_preserves_machine_readable_error_code(self) -> None:
        for status in (0, 1):
            response = subprocess.CompletedProcess(
                [],
                status,
                '{"success":false,"error":"failed","error_code":"evaluation_failed"}',
                "",
            )
            with (
                self.subTest(status=status),
                mock.patch.object(runtime.subprocess, "run", return_value=response),
                self.assertRaises(runtime.CDPError) as error,
            ):
                runtime._run_node("evaluate", {})
            self.assertEqual(error.exception.code, "evaluation_failed")

    def test_process_timeout_is_bounded_and_not_retried(self) -> None:
        with (
            mock.patch.object(
                runtime.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("node", 45),
            ) as run,
            self.assertRaises(runtime.CDPError) as error,
        ):
            runtime._run_node("evaluate", {})
        self.assertEqual(error.exception.code, "timeout")
        run.assert_called_once()

    def test_invalid_response_shape_is_a_transport_error(self) -> None:
        response = subprocess.CompletedProcess([], 0, "[]", "")
        with (
            mock.patch.object(runtime.subprocess, "run", return_value=response),
            self.assertRaises(runtime.CDPError) as error,
        ):
            runtime._run_node("evaluate", {})
        self.assertEqual(error.exception.code, "invalid_response")

    def test_new_session_does_not_reuse_arbitrary_tabs(self) -> None:
        with mock.patch.object(
            runtime,
            "_run_node",
            return_value={"success": True, "targetId": "dedicated"},
        ) as run:
            page = Browser().get_or_create_page()
        self.assertEqual(page.target_id, "dedicated")
        self.assertEqual(run.call_args.args[0], "new-page")
        run.assert_called_once()

    def test_saved_worker_target_is_not_a_page(self) -> None:
        browser = Browser()
        with mock.patch.object(
            browser,
            "list_pages",
            return_value=[{"id": "worker", "type": "service_worker"}],
        ):
            self.assertIsNone(browser.get_page_by_target_id("worker"))

    def test_missing_click_acknowledgement_is_not_reported_as_no_click(self) -> None:
        page = Page("127.0.0.1", 9222, "target")
        with (
            mock.patch.object(page, "evaluate", return_value=None),
            self.assertRaises(runtime.CDPError) as error,
        ):
            page.click("button")
        self.assertEqual(error.exception.code, "invalid_response")
