from __future__ import annotations

import copy
import json
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
    validate_fixture,
    validate_fixture_set,
)


class PageStateFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = load_fixtures()
        cls.by_id = {fixture["id"]: fixture for fixture in cls.fixtures}

    def test_versioned_fixture_set_is_complete_and_consistent(self) -> None:
        self.assertEqual(len(self.fixtures), 11)
        self.assertEqual(validate_fixture_set(self.fixtures), [])
        self.assertTrue((FIXTURE_ROOT.parent / "README.md").is_file())

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


if __name__ == "__main__":
    unittest.main()
