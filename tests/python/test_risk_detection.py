from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from douyin import interact, login, publish, search
from douyin.page_states import (
    RISK_DOM_SIGNALS_JS,
    RISK_SIGNAL_KEYS,
    classify_detail_snapshot,
    classify_login_snapshot,
    classify_search_snapshot,
    classify_trending_snapshot,
    has_risk_evidence,
)


class RiskDetectionTests(unittest.TestCase):
    def test_structural_signals_override_authenticated_ui_and_nonempty_content(self):
        for key in RISK_SIGNAL_KEYS:
            snapshot = {
                key: True,
                "hasProfileUi": True,
                "hasAuthCookie": True,
                "hasRiskKeyword": False,
                "title": "Public content",
                "text": "An otherwise normal public page",
                "bodyText": "An otherwise normal public page",
                "url": "https://www.douyin.com/video/123",
                "items": [{"title": "item"}],
                "topics": [{"name": "topic"}],
            }
            with self.subTest(signal=key):
                self.assertFalse(classify_login_snapshot(snapshot)["logged_in"])
                for classifier in (
                    classify_login_snapshot,
                    classify_search_snapshot,
                    classify_trending_snapshot,
                    lambda data: classify_detail_snapshot(data, "video"),
                ):
                    self.assertTrue(classifier(snapshot)["risk_page"])

    def test_english_challenges_are_case_insensitive_but_sms_labels_are_allowed(self):
        for text in (
            "CAPTCHA",
            "Security verification",
            "Slide to verify",
            "Verify you are human",
        ):
            with self.subTest(text=text):
                self.assertTrue(has_risk_evidence("", text))
                self.assertTrue(
                    classify_login_snapshot({"bodyText": text})["risk_page"]
                )
        self.assertFalse(has_risk_evidence("SMS login", "Enter your one-time code"))

    def test_dom_probe_executes_for_textless_hidden_and_ordinary_controls(self):
        cases = [
            ({"tag": "IFRAME", "title": "CAPTCHA"}, "hasCaptchaFrame"),
            ({"tag": "IFRAME", "src": "about:blank#captcha"}, "hasCaptchaFrame"),
            ({"class": "secsdk-captcha-drag-icon"}, "hasCaptchaControl"),
            ({"id": "verify_slider"}, "hasCaptchaControl"),
            ({"tag": "IMG", "src": "data:image/png;captcha"}, "hasCaptchaImage"),
            ({"class": "captcha", "visibility": "hidden"}, None),
            ({"class": "captcha", "display": "none"}, None),
            ({"class": "captcha", "size": 0}, None),
            ({"class": "video-volume-slider", "role": "slider"}, None),
            (
                {"tag": "INPUT", "class": "sms-code", "autocomplete": "one-time-code"},
                None,
            ),
            ({"tag": "IMG", "src": "data:image/png;qrcode", "alt": "二维码"}, None),
        ]
        harness = r"""
import vm from 'node:vm';
let input = '';
for await (const chunk of process.stdin) input += chunk;
const {expression, cases} = JSON.parse(input);
const output = cases.map(([attributes]) => {
  const node = {
    tagName: attributes.tag || 'DIV', offsetWidth: attributes.size ?? 20,
    offsetHeight: attributes.size ?? 20,
    getClientRects: () => attributes.size === 0 ? [] : [{}],
    getAttribute: key => attributes[key] || null
  };
  return vm.runInNewContext(expression, {
    document: {body: {}, querySelectorAll: () => [node]},
    location: {pathname: '/video/123'},
    getComputedStyle: () => ({display: attributes.display || 'block', visibility: attributes.visibility || 'visible'})
  });
});
for (const context of [
  {body: {}, querySelectorAll: () => []},
  {body: {}, querySelectorAll: () => {throw new Error('unreadable');}}
]) {
  output.push(vm.runInNewContext(expression, {
    document: context, location: {pathname: '/verify/challenge'},
    getComputedStyle: () => ({})
  }));
}
process.stdout.write(JSON.stringify(output));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", harness],
            input=json.dumps({"expression": RISK_DOM_SIGNALS_JS, "cases": cases}),
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        snapshots = json.loads(result.stdout)
        for (attributes, expected), snapshot in zip(cases, snapshots):
            with self.subTest(attributes=attributes):
                self.assertEqual(
                    has_risk_evidence(snapshot=snapshot), expected is not None
                )
                if expected:
                    self.assertTrue(snapshot[expected])
        self.assertTrue(snapshots[-2]["hasChallengeUrl"])
        self.assertTrue(snapshots[-1]["riskDetectionFailed"])

    def test_read_flows_stop_on_textless_challenges_before_extracting_or_fallback(self):
        for operation, arguments in (
            (search.list_feeds, ()),
            (search.search_videos, ("query",)),
            (search.get_trending_topics, ()),
            (search.get_video_detail, ("123",)),
        ):
            page = mock.Mock()
            with (
                self.subTest(operation=operation.__name__),
                mock.patch.object(
                    search,
                    "wait_for_meaningful_text",
                    return_value={"hasCaptchaFrame": True},
                ),
            ):
                result = operation(page, *arguments)
            self.assertFalse(result["success"])
            self.assertTrue(result["risk_page"])
            page.evaluate.assert_not_called()
            self.assertEqual(page.navigate.call_count, 1)

    def test_late_dom_evidence_survives_search_result_classification(self):
        page = mock.Mock()
        page.evaluate.side_effect = [
            True,
            {"hasCaptchaImage": True, "items": [{"href": "/video/123"}]},
        ]
        with mock.patch.object(
            search, "wait_for_meaningful_text", return_value={"text": "public content"}
        ):
            result = search.search_videos(page, "query")
        self.assertFalse(result["success"])
        self.assertTrue(result["risk_page"])
        self.assertEqual(result["videos"], [])

    def test_interaction_flows_stop_before_any_control_is_clicked(self):
        for operation, arguments in (
            (interact.like_video, ("123",)),
            (interact.favorite_video, ("123",)),
            (interact.comment_video, ("123", "synthetic comment")),
            (interact.get_interaction_state, ("123",)),
            (interact.share_video, ("123",)),
        ):
            page = mock.Mock()
            page.evaluate.return_value = {"hasCaptchaControl": True}
            with (
                self.subTest(operation=operation.__name__),
                mock.patch.object(interact.time, "sleep"),
            ):
                result = operation(page, *arguments)
            self.assertTrue(result["risk_page"])
            self.assertFalse(result["success"])
            page.click.assert_not_called()
            self.assertEqual(page.evaluate.call_count, 1)

    def test_publish_validation_blocks_both_publish_dispatches(self):
        for operation in (publish.click_publish, publish.click_publish_video):
            page = mock.Mock()
            page.evaluate.return_value = {
                "hasCaptchaFrame": True,
                "hasImage": True,
                "hasVideo": True,
            }
            with (
                self.subTest(operation=operation.__name__),
                mock.patch.object(publish, "_dispatch_publish_click") as dispatch,
            ):
                result = operation(page)
            self.assertFalse(result["success"])
            self.assertTrue(result["risk_page"])
            dispatch.assert_not_called()
            page.click.assert_not_called()

    def test_login_snapshot_includes_dom_evidence_in_the_runtime_expression(self):
        page = mock.Mock()
        page.evaluate.return_value = {"hasCaptchaFrame": True, "hasAuthCookie": True}
        result = login.check_login_state(page)
        self.assertTrue(result["risk_page"])
        self.assertFalse(result["logged_in"])
        self.assertIn(RISK_DOM_SIGNALS_JS, page.evaluate.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
