from __future__ import annotations

from .adapter import DEFAULT_ADAPTER

HOME_URL = DEFAULT_ADAPTER.home_url
JINGXUAN_URL = DEFAULT_ADAPTER.featured_url
CREATOR_URL = DEFAULT_ADAPTER.creator_home_url
SEARCH_BASE = DEFAULT_ADAPTER.search_base_url
TRENDING_URL = DEFAULT_ADAPTER.trending_url


def parse_content_ref(value: str) -> tuple[str, str | None]:
    return DEFAULT_ADAPTER.parse_content_ref(value)


def search_url(keyword: str) -> str:
    return DEFAULT_ADAPTER.search_url(keyword)


def jingxuan_url() -> str:
    return DEFAULT_ADAPTER.featured_url


def video_url(video_id: str) -> str:
    content_id, _kind = DEFAULT_ADAPTER.parse_content_ref(video_id)
    return DEFAULT_ADAPTER.content_url("video", content_id)


def note_url(note_id: str) -> str:
    content_id, _kind = DEFAULT_ADAPTER.parse_content_ref(note_id)
    return DEFAULT_ADAPTER.content_url("note", content_id)


def content_urls(content_ref: str) -> list[tuple[str, str]]:
    return DEFAULT_ADAPTER.content_urls(content_ref)


def trending_url() -> str:
    return DEFAULT_ADAPTER.trending_url
