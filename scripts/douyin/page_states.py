from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

FIXTURE_SCHEMA_VERSION = "1.0"
FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "page_states" / "v1"
SUPPORTED_FIXTURE_FLOWS = {"detail", "login", "publish", "search"}
RISK_PAGE_KEYWORDS = ["验证码", "安全验证", "风险提示", "身份验证"]
RISK_STRONG_HINTS = [
    "验证码中间页",
    "请完成验证",
    "请进行验证",
    "拖动滑块",
    "点击按钮进行验证",
    "发送短信验证",
    "接收短信验证码",
]
INACCESSIBLE_CONTENT_HINTS = ["作品不存在", "内容不可见", "已删除"]
ALLOWED_PUBLIC_HOSTS = {"creator.douyin.com", "www.douyin.com"}
FORBIDDEN_FIXTURE_KEYS = {
    "access_token",
    "auth_token",
    "authorization",
    "cookie_header",
    "cookie_value",
    "cookies",
    "local_profile_path",
    "phone",
    "phone_number",
    "profile_path",
    "qr_code",
    "qrcode",
    "session_token",
    "sessionid",
    "token",
    "user_data_dir",
}
SENSITIVE_KEY_PARTS = {
    "access_token",
    "auth_token",
    "authorization",
    "cookie",
    "phone",
    "profile_path",
    "qr_code",
    "qrcode",
    "session_id",
    "session_token",
    "user_data_dir",
}
SENSITIVE_STRING_PATTERNS = {
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "mainland phone number": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "Windows path": re.compile(r"\b[A-Za-z]:[\\/]"),
    "home path": re.compile(r"(?:^|[\s\"'])/(?:home|Users)/[^\s\"']+"),
    "embedded image": re.compile(r"data:image/", re.I),
    "session assignment": re.compile(
        r"(?:sessionid|sid_guard|uid_tt)(?:_ss)?\s*=", re.I
    ),
}


def has_risk_evidence(title: str = "", text: str = "") -> bool:
    combined = f"{title or ''}\n{text or ''}"
    return any(keyword in combined for keyword in RISK_PAGE_KEYWORDS)


def classify_login_snapshot(snapshot: dict) -> dict:
    risk_page = bool(snapshot.get("hasRiskKeyword"))
    has_login_panel = bool(snapshot.get("hasLoginPanel"))
    high_confidence_marker = bool(snapshot.get("hasProfileUi")) or bool(
        snapshot.get("hasAuthCookie")
    )
    corroborated_ui = int(snapshot.get("loggedInHintCount", 0) or 0) >= 2 and not bool(
        snapshot.get("hasLoginKeyword")
    )
    logged_in = (
        not risk_page
        and not has_login_panel
        and (high_confidence_marker or corroborated_ui)
    )
    return {
        "logged_in": logged_in,
        "risk_page": risk_page,
        "certainty": "high" if logged_in else "not_authenticated",
    }


def classify_search_snapshot(snapshot: dict) -> dict:
    title = str(snapshot.get("title") or "")
    text = str(snapshot.get("text") or "")
    items = snapshot.get("items") or []
    if has_risk_evidence(title, text):
        return {"state": "risk", "risk_page": True, "count": 0}
    if not items and not text.strip():
        return {"state": "empty_or_blocked", "risk_page": True, "count": 0}
    return {"state": "ready", "risk_page": False, "count": len(items)}


def classify_detail_snapshot(snapshot: dict, expected_kind: str) -> dict:
    title = str(snapshot.get("title") or "")
    text = str(snapshot.get("bodyText") or "")
    href = str(snapshot.get("url") or "")
    if has_risk_evidence(title, text):
        return {"state": "risk", "risk_page": True, "available": False}
    if any(hint in text for hint in INACCESSIBLE_CONTENT_HINTS):
        return {"state": "unavailable", "risk_page": False, "available": False}
    if expected_kind in {"note", "video"} and f"/{expected_kind}/" in href:
        return {"state": "ready", "risk_page": False, "available": True}
    return {"state": "page_drift", "risk_page": False, "available": False}


def classify_publish_snapshot(snapshot: dict, require_topic: bool = False) -> dict:
    state = dict(snapshot)
    errors: list[str] = []
    if not bool(state.get("hasImage")):
        errors.append("缺少图片")
    if not str(state.get("title") or "").strip():
        errors.append("标题为空")
    if not str(state.get("editorText") or "").strip():
        errors.append("正文为空")
    if not bool(state.get("hasMusic")):
        errors.append("未选择音乐")
    if require_topic and not bool(state.get("hasTopic")):
        errors.append("未关联热点")
    state.update(
        {
            "success": not errors,
            "requireTopic": bool(require_topic),
            "errors": errors,
            "state": "ready" if not errors else "incomplete",
        }
    )
    return state


def classify_publish_outcome(clicked: bool, confirmation: dict | None) -> dict:
    if not clicked:
        return {
            "status": "not_clicked",
            "published": False,
            "retry_safe": True,
        }
    if confirmation and confirmation.get("confirmed"):
        return {
            "status": "publish_confirmed",
            "published": True,
            "retry_safe": False,
        }
    return {
        "status": "publish_clicked_unconfirmed",
        "published": False,
        "retry_safe": False,
    }


def load_fixtures(root: Path = FIXTURE_ROOT) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(root.glob("*.json"))
    ]


def _walk(value, path: str = "$"):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def fixture_privacy_errors(fixture: dict) -> list[str]:
    errors: list[str] = []
    for path, value in _walk(fixture):
        key = path.rsplit(".", 1)[-1].lower()
        contains_sensitive_key_part = any(part in key for part in SENSITIVE_KEY_PARTS)
        safe_derived_signal = isinstance(value, (bool, int, float)) or value is None
        if key in FORBIDDEN_FIXTURE_KEYS or (
            contains_sensitive_key_part and not safe_derived_signal
        ):
            errors.append(f"{path}: sensitive key is not allowed")
        if not isinstance(value, str):
            continue
        for label, pattern in SENSITIVE_STRING_PATTERNS.items():
            if pattern.search(value):
                errors.append(f"{path}: contains {label}")
        if value.startswith(("http://", "https://")):
            parsed = urlsplit(value)
            if parsed.scheme != "https" or parsed.hostname not in ALLOWED_PUBLIC_HOSTS:
                errors.append(f"{path}: URL is not an allowed public Douyin URL")
            if parsed.username or parsed.password:
                errors.append(f"{path}: URL credentials are not allowed")
            if re.search(
                r"(?:^|&)(?:access_token|auth_token|authorization|code|phone|session(?:id|_id|_token)?|token)=",
                parsed.query,
                re.I,
            ):
                errors.append(f"{path}: URL contains sensitive query parameters")
    return errors


def validate_fixture(fixture: dict) -> list[str]:
    errors: list[str] = []
    required = {
        "description",
        "expected",
        "flow",
        "id",
        "input",
        "schema_version",
        "source",
    }
    missing = sorted(required - fixture.keys())
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")
        return errors
    if fixture.get("schema_version") != FIXTURE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {FIXTURE_SCHEMA_VERSION}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(fixture.get("id"))):
        errors.append("id must use lowercase kebab-case")
    if fixture.get("flow") not in SUPPORTED_FIXTURE_FLOWS:
        errors.append(f"unsupported flow: {fixture.get('flow')!r}")
    source = fixture.get("source")
    if source != {"kind": "synthetic", "contains_real_account_data": False}:
        errors.append("source must declare synthetic data and no real account data")
    if not isinstance(fixture.get("input"), dict):
        errors.append("input must be an object")
    if not isinstance(fixture.get("expected"), dict) or not fixture.get("expected"):
        errors.append("expected must be a non-empty object")
    errors.extend(fixture_privacy_errors(fixture))
    return errors


def classify_fixture(fixture: dict) -> dict:
    flow = fixture["flow"]
    fixture_input = fixture["input"]
    if flow == "login":
        return classify_login_snapshot(fixture_input["snapshot"])
    if flow == "search":
        return classify_search_snapshot(fixture_input["snapshot"])
    if flow == "detail":
        return classify_detail_snapshot(
            fixture_input["snapshot"], fixture_input["expected_kind"]
        )
    if flow == "publish" and fixture_input.get("mode") == "validation":
        return classify_publish_snapshot(
            fixture_input["snapshot"],
            require_topic=bool(fixture_input.get("require_topic")),
        )
    if flow == "publish" and fixture_input.get("mode") == "outcome":
        return classify_publish_outcome(
            bool(fixture_input.get("clicked")), fixture_input.get("confirmation")
        )
    raise ValueError(f"unsupported fixture input for flow {flow!r}")


def validate_fixture_set(fixtures: list[dict]) -> list[str]:
    errors: list[str] = []
    ids: list[str] = []
    flows: Counter[str] = Counter()
    for index, fixture in enumerate(fixtures):
        fixture_id = str(fixture.get("id") or f"index-{index}")
        ids.append(fixture_id)
        flows[str(fixture.get("flow") or "")] += 1
        fixture_errors = validate_fixture(fixture)
        errors.extend(f"{fixture_id}: {error}" for error in fixture_errors)
        if fixture_errors:
            continue
        actual = classify_fixture(fixture)
        for key, expected in fixture["expected"].items():
            if actual.get(key) != expected:
                errors.append(
                    f"{fixture_id}: expected {key}={expected!r}, "
                    f"classified {actual.get(key)!r}"
                )
    duplicates = sorted(item for item, count in Counter(ids).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate fixture ids: {', '.join(duplicates)}")
    missing_flows = sorted(SUPPORTED_FIXTURE_FLOWS - flows.keys())
    if missing_flows:
        errors.append(f"missing fixture flows: {', '.join(missing_flows)}")
    return errors
