from __future__ import annotations

import re
from urllib.parse import quote, urlparse

HOME_URL = "https://www.douyin.com/"
JINGXUAN_URL = "https://www.douyin.com/jingxuan"
CREATOR_URL = "https://creator.douyin.com/creator-micro/home"
SEARCH_BASE = "https://www.douyin.com/search/"
TRENDING_URL = "https://www.douyin.com/hot"
_CONTENT_PATH_RE = re.compile(r"/(video|note)/(\d+)")
_CONTENT_ID_RE = re.compile(r"^\d{1,32}$")


def parse_content_ref(value: str) -> tuple[str, str | None]:
    value = str(value or "").strip()
    if _CONTENT_ID_RE.fullmatch(value):
        return value, None
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if hostname == "douyin.com" or hostname.endswith(".douyin.com"):
        match = _CONTENT_PATH_RE.search(parsed.path)
        if match:
            return match.group(2), match.group(1)
    raise ValueError(
        "作品 ID 必须是数字，或使用 douyin.com 的 /video/、/note/ 公开链接"
    )


def search_url(keyword: str) -> str:
    keyword = str(keyword or "").strip()
    if not keyword:
        raise ValueError("搜索关键词不能为空")
    return f"{SEARCH_BASE}{quote(keyword, safe='')}?type=video"


def jingxuan_url() -> str:
    return JINGXUAN_URL


def video_url(video_id: str) -> str:
    content_id, _kind = parse_content_ref(video_id)
    return f"https://www.douyin.com/video/{content_id}"


def note_url(note_id: str) -> str:
    content_id, _kind = parse_content_ref(note_id)
    return f"https://www.douyin.com/note/{content_id}"


def content_urls(content_ref: str) -> list[tuple[str, str]]:
    content_id, kind = parse_content_ref(content_ref)
    if kind == "note":
        return [("note", note_url(content_id))]
    if kind == "video":
        return [("video", video_url(content_id))]
    return [("video", video_url(content_id)), ("note", note_url(content_id))]


def trending_url() -> str:
    return TRENDING_URL
