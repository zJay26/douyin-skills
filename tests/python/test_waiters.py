from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from douyin import waiters


class WaiterTests(unittest.TestCase):
    def test_polls_until_trimmed_text_meets_minimum_length(self):
        page = mock.Mock()
        page.evaluate.side_effect = [{"text": "  x  "}, {"text": "  ready  "}]
        with (
            mock.patch.object(waiters.time, "time", side_effect=[0, 0, 1]),
            mock.patch.object(waiters.time, "sleep") as sleep,
        ):
            result = waiters.wait_for_meaningful_text(page, timeout=2, min_len=5)
        self.assertEqual(result["text"], "  ready  ")
        self.assertEqual(page.evaluate.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_timeout_returns_last_snapshot_and_zero_timeout_does_not_poll(self):
        page = mock.Mock()
        page.evaluate.return_value = {"text": "short"}
        with (
            mock.patch.object(waiters.time, "time", side_effect=[0, 0, 2]),
            mock.patch.object(waiters.time, "sleep"),
        ):
            result = waiters.wait_for_meaningful_text(page, timeout=1, min_len=10)
        self.assertEqual(result, {"text": "short"})
        page.evaluate.reset_mock()
        self.assertEqual(
            waiters.wait_for_meaningful_text(page, timeout=0), {"title": "", "text": ""}
        )
        page.evaluate.assert_not_called()

    def test_textless_challenge_returns_immediately_without_waiting_for_text(self):
        page = mock.Mock()
        page.evaluate.return_value = {"text": "", "hasCaptchaFrame": True}
        with mock.patch.object(waiters.time, "sleep") as sleep:
            result = waiters.wait_for_meaningful_text(page, min_len=80)
        self.assertTrue(result["hasCaptchaFrame"])
        page.evaluate.assert_called_once()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
