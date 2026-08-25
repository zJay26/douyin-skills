from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from douyin import login, publish, search  # noqa: E402
from douyin.page_states import (  # noqa: E402
    FIXTURE_ROOT,
    classify_fixture,
    load_fixtures,
    select_fixtures,
    validate_fixture,
    validate_fixture_set,
)


class PageStateFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = load_fixtures()
        cls.by_id = {fixture["id"]: fixture for fixture in cls.fixtures}

    def test_versioned_fixture_set_is_complete_and_consistent(self) -> None:
        self.assertEqual(len(self.fixtures), 19)
        self.assertEqual(validate_fixture_set(self.fixtures), [])
        self.assertTrue((FIXTURE_ROOT.parent / "README.md").is_file())

    def test_focused_detail_selection_can_skip_global_flow_coverage(self) -> None:
        selected = select_fixtures(self.fixtures, flow="detail")

        self.assertEqual(
            [fixture["id"] for fixture in selected],
            [
                "detail-content-unavailable",
                "detail-page-drift",
                "detail-risk-verification",
                "detail-video-ready",
            ],
        )
        self.assertEqual(validate_fixture_set(selected, require_all_flows=False), [])

    def test_every_fixture_matches_its_expected_certainty_fields(self) -> None:
        for fixture in self.fixtures:
            with self.subTest(fixture=fixture["id"]):
                actual = classify_fixture(fixture)
                self.assertEqual(
                    {key: actual.get(key) for key in fixture["expected"]},
                    fixture["expected"],
                )

    def test_privacy_validator_rejects_sensitive_content(self) -> None:
        fixture = copy.deepcopy(self.by_id["search-results"])
        fixture["input"]["snapshot"]["phone_number"] = "13800138000"
        fixture["input"]["snapshot"]["profile_path"] = "C:\\Users\\demo"
        fixture["input"]["snapshot"]["access_token"] = "synthetic-secret"
        fixture["input"]["snapshot"]["items"][0]["href"] = "https://example.com/private"
        fixture["input"]["snapshot"]["items"][1]["href"] = (
            "https://www.douyin.com/note/1000000000000000002?sessionid=synthetic"
        )

        errors = validate_fixture(fixture)

        self.assertTrue(any("sensitive key" in error for error in errors))
        self.assertTrue(any("phone number" in error for error in errors))
        self.assertTrue(any("Windows path" in error for error in errors))
        self.assertTrue(any("allowed public Douyin URL" in error for error in errors))
        self.assertTrue(any("sensitive query parameters" in error for error in errors))

    def test_login_runtime_uses_shared_fixture_classifier(self) -> None:
        snapshot = self.by_id["risk-verification"]["input"]["snapshot"]
        with mock.patch.object(login, "inspect_login_state", return_value=snapshot):
            result = login.check_login_state(mock.Mock())

        self.assertFalse(result["logged_in"])
        self.assertTrue(result["risk_page"])

    def test_search_runtime_uses_shared_fixture_classifier(self) -> None:
        snapshot = self.by_id["search-results"]["input"]["snapshot"]
        page = mock.Mock()
        page.evaluate.side_effect = [True, snapshot]
        with mock.patch.object(
            search,
            "wait_for_meaningful_text",
            return_value={"title": snapshot["title"], "text": snapshot["text"]},
        ):
            result = search.search_videos(page, "synthetic query", limit=2)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["videos"][0]["kind"], "video")
        self.assertEqual(result["videos"][1]["kind"], "note")

    def test_trending_runtime_uses_shared_fixture_classifier(self) -> None:
        fixture = self.by_id["trending-topics-ready"]
        snapshot = fixture["input"]["snapshot"]
        page = mock.Mock()
        page.evaluate.return_value = snapshot
        with (
            mock.patch.object(
                search,
                "wait_for_meaningful_text",
                return_value={"title": snapshot["title"], "text": snapshot["text"]},
            ),
            mock.patch.object(search.time, "sleep"),
        ):
            result = search.get_trending_topics(page)

        self.assertTrue(result["success"])
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["count"], 2)
        extraction_script = page.evaluate.call_args_list[-1].args[0]
        self.assertIn("feed-right-list-container", extraction_script)
        parsed = subprocess.run(
            [
                "node",
                "--input-type=module",
                "-e",
                "new Function(process.argv[1])",
                extraction_script,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(parsed.returncode, 0, parsed.stderr)

    def test_trending_runtime_reports_page_drift_without_topics(self) -> None:
        fixture = self.by_id["trending-page-drift"]
        snapshot = fixture["input"]["snapshot"]
        page = mock.Mock()
        page.evaluate.return_value = snapshot
        with mock.patch.object(
            search,
            "wait_for_meaningful_text",
            return_value={"title": snapshot["title"], "text": snapshot["text"]},
        ):
            result = search.get_trending_topics(page)

        self.assertFalse(result["success"])
        self.assertEqual(result["state"], "page_drift")
        self.assertFalse(result["risk_page"])

    def test_detail_runtime_uses_shared_fixture_classifier(self) -> None:
        fixture = self.by_id["detail-video-ready"]
        snapshot = fixture["input"]["snapshot"]
        page = mock.Mock()
        page.evaluate.return_value = json.dumps(snapshot)
        with mock.patch.object(
            search,
            "wait_for_meaningful_text",
            return_value={"title": snapshot["title"], "text": snapshot["bodyText"]},
        ):
            result = search.get_video_detail(page, "1000000000000000003")

        self.assertTrue(result["success"])
        self.assertEqual(result["content_type"], "video")
        self.assertEqual(result["video_info"]["url"], snapshot["url"])

    def test_detail_title_falls_back_to_content_description(self) -> None:
        page = mock.Mock()
        page.evaluate.return_value = json.dumps(
            {
                "title": "",
                "description": "Synthetic content caption",
                "comments": [],
                "url": "https://www.douyin.com/video/1000000000000000005",
                "bodyText": "Synthetic public content is visible.",
            }
        )
        with mock.patch.object(
            search,
            "wait_for_meaningful_text",
            return_value={"title": "", "text": "Synthetic public content is visible."},
        ):
            result = search.get_video_detail(page, "1000000000000000005")

        self.assertTrue(result["success"])
        self.assertEqual(result["video_info"]["title"], "Synthetic content caption")

    def test_detail_runtime_marks_adapter_loading_as_unavailable(self) -> None:
        page = mock.Mock()
        page.evaluate.return_value = json.dumps(
            {
                "title": "",
                "description": "",
                "comments": [],
                "url": "https://www.douyin.com/video/1000000000000000006",
                "bodyText": "视频数据加载中",
            }
        )
        with (
            mock.patch.object(
                search,
                "wait_for_meaningful_text",
                return_value={"title": "", "text": "视频数据加载中"},
            ),
            mock.patch.object(search.time, "sleep"),
        ):
            result = search.get_video_detail(page, "1000000000000000006")

        self.assertFalse(result["success"])
        self.assertEqual(result["state"], "unavailable")

    def test_detail_runtime_keeps_seed_risk_evidence_when_extraction_is_empty(
        self,
    ) -> None:
        page = mock.Mock()
        page.evaluate.return_value = json.dumps(
            {
                "title": "",
                "bodyText": "",
                "url": "https://www.douyin.com/video/1000000000000000004",
            }
        )
        with mock.patch.object(
            search,
            "wait_for_meaningful_text",
            return_value={"title": "安全验证", "text": "请完成验证"},
        ):
            result = search.get_video_detail(page, "1000000000000000004")

        self.assertFalse(result["success"])
        self.assertTrue(result["risk_page"])

    def test_publish_runtime_uses_shared_fixture_classifier(self) -> None:
        fixture = self.by_id["publish-missing-music"]
        page = mock.Mock()
        page.evaluate.return_value = fixture["input"]["snapshot"]

        result = publish.validate_publish_state(page)

        self.assertFalse(result["success"])
        self.assertEqual(result["state"], "incomplete")
        self.assertEqual(result["errors"], ["未选择音乐"])

    def test_video_publish_fixture_requires_cover(self) -> None:
        fixture = self.by_id["publish-video-missing-cover"]

        result = classify_fixture(fixture)

        self.assertFalse(result["success"])
        self.assertEqual(result["state"], "incomplete")
        self.assertEqual(result["errors"], ["未设置视频封面"])

    def test_publish_classifier_distinguishes_uploading_from_missing_image(
        self,
    ) -> None:
        snapshot = {
            "hasImage": False,
            "uploadInProgress": True,
            "title": "Synthetic title",
            "editorText": "Synthetic body",
            "hasMusic": True,
            "hasTopic": False,
        }

        result = publish.classify_publish_snapshot(snapshot)

        self.assertFalse(result["success"])
        self.assertEqual(result["errors"], ["图片上传未完成"])


if __name__ == "__main__":
    unittest.main()
