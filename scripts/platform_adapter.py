"""Shared contract for platform-specific browser workflows.

The workflow modules use this contract for navigation and platform markers. A
concrete adapter owns URLs, selectors, and page-entry details; safety policy
and result classification remain shared runtime concerns.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class PlatformSelectors:
    """Selectors and visible text owned by one platform adapter."""

    login_text_keywords: tuple[str, ...]
    login_panel_markers: tuple[str, ...]
    logged_in_text_hints: tuple[str, ...]
    login_qrcode_selectors: tuple[str, ...]
    profile_ui_selectors: tuple[str, ...]
    auth_cookie_names: tuple[str, ...]
    phone_input_selectors: tuple[str, ...]
    send_code_texts: tuple[str, ...]
    verification_input_selectors: tuple[str, ...]
    submit_code_texts: tuple[str, ...]
    agreement_text: str
    search_result_selectors: tuple[str, ...]
    feed_card_selector: str
    feed_content_id_attribute: str
    trending_node_selectors: tuple[str, ...]
    trending_tab_texts: tuple[str, ...]
    trending_topic_keywords: tuple[str, ...]
    detail_desc_selectors: tuple[str, ...]
    comment_item_selectors: tuple[str, ...]
    like_button_selectors: tuple[str, ...]
    favorite_button_selectors: tuple[str, ...]
    comment_action_selectors: tuple[str, ...]
    comment_input_selectors: tuple[str, ...]
    comment_submit_selectors: tuple[str, ...]
    comment_submit_texts: tuple[str, ...]
    comment_composer_texts: tuple[str, ...]
    like_active_texts: tuple[str, ...]
    favorite_active_texts: tuple[str, ...]
    like_active_style_tokens: tuple[str, ...]
    favorite_active_style_tokens: tuple[str, ...]
    note_action_bar_marker: str
    like_action_text: str
    favorite_action_text: str
    share_action_text: str
    comment_action_text: str
    copy_link_text: str
    publish_file_input_selector: str
    publish_title_input_selector: str
    publish_editor_selectors: tuple[str, ...]
    publish_image_markers: tuple[str, ...]
    music_open_selectors: tuple[str, ...]
    music_open_texts: tuple[str, ...]
    music_panel_selector: str
    music_panel_markers: tuple[str, ...]
    music_name_selectors: tuple[str, ...]
    music_apply_selectors: tuple[str, ...]
    music_apply_text: str
    selected_music_text: str
    publish_button_text: str
    publish_success_texts: tuple[str, ...]
    publish_success_path_fragment: str
    topic_markers: tuple[str, ...]


@runtime_checkable
class PlatformAdapter(Protocol):
    """The platform-specific surface consumed by shared workflows."""

    key: str
    home_url: str
    featured_url: str
    trending_url: str
    creator_upload_url: str
    default_content_kind: str
    content_path_fragments: Sequence[str]
    content_url_templates: Mapping[str, str]
    selectors: PlatformSelectors
    risk_page_keywords: Sequence[str]
    risk_strong_hints: Sequence[str]
    inaccessible_content_markers: Sequence[str]
    detail_loading_markers: Sequence[str]

    def parse_content_ref(self, value: str) -> tuple[str, str | None]: ...

    def search_url(self, keyword: str) -> str: ...

    def content_urls(self, content_ref: str) -> list[tuple[str, str]]: ...

    def content_kind(self, value: str) -> str | None: ...

    def extract_content_id(self, value: str) -> str: ...

    def extract_author_id(self, value: str) -> str: ...

    def is_platform_url(self, value: str) -> bool: ...

    def is_publish_url(self, value: str) -> bool: ...

    def is_risk_page(self, title: str, text: str) -> bool: ...

    def navigate_home(self, page: Any) -> None: ...

    def navigate_featured(self, page: Any) -> None: ...

    def navigate_search(self, page: Any, keyword: str) -> None: ...

    def navigate_trending(self, page: Any) -> None: ...

    def navigate_publish_image(self, page: Any) -> None: ...


def get_default_adapter() -> PlatformAdapter:
    """Return the shipped adapter without making workflow modules platform-aware."""

    from douyin.adapter import DEFAULT_ADAPTER

    return DEFAULT_ADAPTER


def resolve_adapter(adapter: PlatformAdapter | None) -> PlatformAdapter:
    return adapter if adapter is not None else get_default_adapter()
