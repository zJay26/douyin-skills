from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import quote, urlparse

from platform_adapter import PlatformSelectors

from .page_states import (
    INACCESSIBLE_CONTENT_HINTS,
    RISK_PAGE_KEYWORDS,
    RISK_STRONG_HINTS,
)

_CONTENT_PATH_RE = re.compile(r"/(video|note)/(\d+)")
_CONTENT_ID_RE = re.compile(r"^\d{1,32}$")


DOUYIN_SELECTORS = PlatformSelectors(
    login_text_keywords=("登录", "立即登录", "扫码登录", "手机号登录"),
    login_panel_markers=("扫码登录", "手机号登录", "立即登录"),
    logged_in_text_hints=("创作者服务中心", "投稿", "私信", "消息"),
    login_qrcode_selectors=('img[alt*="二维码"]', "canvas"),
    profile_ui_selectors=(
        'a[href*="/user/self"]',
        '[data-e2e*="user-avatar"]',
        '[data-e2e="user-info"]',
    ),
    auth_cookie_names=(
        "sessionid",
        "sessionid_ss",
        "sid_guard",
        "uid_tt",
        "uid_tt_ss",
    ),
    phone_input_selectors=('input[placeholder*="手机号"]', 'input[type="tel"]'),
    send_code_texts=("获取验证码", "发送验证码", "接收短信验证码", "发送短信验证"),
    verification_input_selectors=(
        'input[placeholder*="验证码"]',
        'input[inputmode="numeric"]',
        'input[type="number"]',
    ),
    submit_code_texts=("登录", "确定", "验证", "提交"),
    agreement_text="已阅读并同意",
    search_result_selectors=(
        'a[href*="/video/"]',
        'a[href*="/note/"]',
        '[data-e2e="search-result-item"] a',
    ),
    feed_card_selector="div[data-aweme-id]",
    feed_content_id_attribute="data-aweme-id",
    trending_node_selectors=(
        '[data-e2e="feed-right-list-container"] li',
        "li",
        "a",
        "div",
    ),
    trending_tab_texts=("抖音热榜",),
    trending_topic_keywords=(
        "热",
        "榜",
        "话题",
        "挑战",
        "同城",
        "推荐",
        "音乐",
        "剧情",
        "搞笑",
        "美食",
        "穿搭",
        "旅行",
        "开箱",
        "测评",
    ),
    detail_desc_selectors=(
        '[data-e2e="video-desc"]',
        "h1 span span span span span",
        'div[class*="title"] span',
    ),
    comment_item_selectors=(
        '[data-e2e="comment-item"]',
        '[class*="comment"] [class*="item"]',
        'div[class*="comment"] li',
    ),
    like_button_selectors=(
        '[data-e2e="video-player-digg"]',
        '[data-e2e="feed-digg-icon"]',
        '[class*="video-player-digg"]',
        'button[data-e2e*="like"]',
        '[class*="like"] button',
        'div[role="button"][aria-label*="赞"]',
    ),
    favorite_button_selectors=(
        '[data-e2e="video-player-collect"]',
        '[data-e2e*="collect"]',
        '[data-e2e*="favorite"]',
        'button[aria-label*="收藏"]',
        '[role="button"][aria-label*="收藏"]',
        'button[title*="收藏"]',
        '[class*="collect"] button',
        '[class*="favorite"] button',
    ),
    comment_action_selectors=(
        '[class*="comment-input-inner-container"]',
        '[data-e2e="video-player-comment"]',
        'button[data-e2e*="comment"]',
        '[role="button"][data-e2e*="comment"]',
        'button[aria-label*="评论"]',
        '[role="button"][aria-label*="评论"]',
    ),
    comment_input_selectors=(
        '[data-e2e="comment-input"]',
        '[class*="comment-input-inner-container"] [contenteditable="true"]',
        '.public-DraftEditor-content[contenteditable="true"]',
        '[contenteditable="true"][role="combobox"]',
        'textarea[placeholder*="留下你的精彩评论"]',
        'textarea[placeholder*="精彩评论"]',
        'textarea[placeholder*="评论"]',
        'input[placeholder*="留下你的精彩评论"]',
        'input[placeholder*="评论"]',
        '[contenteditable="true"][data-placeholder*="留下你的精彩评论"]',
        '[contenteditable="true"][data-placeholder*="评论"]',
        '[contenteditable="true"][aria-label*="留下你的精彩评论"]',
        '[contenteditable="true"][aria-label*="评论"]',
        '[contenteditable="true"]',
        '[role="textbox"]',
    ),
    comment_submit_selectors=(
        '[class*="commentInput-right-ct"] span:last-of-type',
        '[data-e2e="comment-submit"]',
        'button[type="submit"]',
        '[role="button"][data-e2e*="comment"]',
        'button[aria-label*="发送"]',
        '[role="button"][aria-label*="发送"]',
        'button[title*="发送"]',
        '[class*="send"] button',
        '[class*="send"][role="button"]',
    ),
    comment_submit_texts=("发送", "发表评论"),
    comment_composer_texts=("留下你的精彩评论吧",),
    like_active_texts=("已赞", "取消赞", "已点赞", "取消点赞"),
    favorite_active_texts=("已收藏", "取消收藏"),
    like_active_style_tokens=("rgb(255, 44, 85)", "#ff2c55"),
    favorite_active_style_tokens=("rgb(255, 184, 2)", "#ffb802"),
    note_action_bar_marker="分享",
    like_action_text="赞",
    favorite_action_text="收藏",
    share_action_text="分享",
    comment_action_text="评论",
    copy_link_text="复制链接",
    publish_file_input_selector='input[type="file"]',
    publish_title_input_selector='input[placeholder="添加作品标题"]',
    publish_editor_selectors=(
        '[data-slate-editor="true"]',
        ".editor-kit-container",
        '[contenteditable="true"]',
        'div[role="textbox"]',
    ),
    publish_image_markers=("继续添加", "编辑图片", "已添加"),
    music_open_selectors=(
        "span.action-Q1y01k",
        ".container-right-uW7Pj",
        ".container-JngpiB",
    ),
    music_open_texts=("选择音乐", "添加音乐"),
    music_panel_selector=".semi-portal",
    music_panel_markers=("选择音乐", "热门榜"),
    music_name_selectors=(
        ".song-name-oRge4d",
        '[class*="song-name"]',
    ),
    music_apply_selectors=(
        "button.apply-btn-LUPP0D",
        'button[class*="apply-btn"]',
    ),
    music_apply_text="使用",
    selected_music_text="修改音乐",
    publish_button_text="发布",
    publish_success_texts=("发布成功", "作品发布成功"),
    publish_success_path_fragment="/content/manage",
    topic_markers=("已关联热点", "修改热点", "关联热点\n#", "关联热点\n话题"),
)


@dataclass(frozen=True)
class DouyinAdapter:
    """Douyin's URLs, selectors, and page-entry flows."""

    key: str = "douyin"
    home_url: str = "https://www.douyin.com/"
    featured_url: str = "https://www.douyin.com/jingxuan"
    trending_url: str = "https://www.douyin.com/hot"
    creator_home_url: str = "https://creator.douyin.com/creator-micro/home"
    creator_upload_url: str = (
        "https://creator.douyin.com/creator-micro/content/upload?default-tab=3"
    )
    search_base_url: str = "https://www.douyin.com/search/"
    default_content_kind: str = "video"
    content_path_fragments: tuple[str, ...] = ("/video/", "/note/")
    content_url_templates: Mapping[str, str] = field(
        default_factory=lambda: {
            "video": "https://www.douyin.com/video/{id}",
            "note": "https://www.douyin.com/note/{id}",
        }
    )
    platform_hosts: tuple[str, ...] = ("douyin.com",)
    selectors: PlatformSelectors = DOUYIN_SELECTORS
    risk_page_keywords: tuple[str, ...] = tuple(RISK_PAGE_KEYWORDS)
    risk_strong_hints: tuple[str, ...] = tuple(RISK_STRONG_HINTS)
    inaccessible_content_markers: tuple[str, ...] = tuple(
        (*INACCESSIBLE_CONTENT_HINTS, "视频数据加载中")
    )
    detail_loading_markers: tuple[str, ...] = ("视频数据加载中",)

    def _is_platform_host(self, hostname: str) -> bool:
        hostname = (hostname or "").lower()
        return any(
            hostname == host or hostname.endswith(f".{host}")
            for host in self.platform_hosts
        )

    def is_platform_url(self, value: str) -> bool:
        parsed = urlparse(str(value or ""))
        return parsed.scheme == "https" and self._is_platform_host(
            parsed.hostname or ""
        )

    def is_publish_url(self, value: str) -> bool:
        current = urlparse(str(value or ""))
        expected = urlparse(self.creator_upload_url)
        supported_paths = {
            expected.path.rstrip("/"),
            "/creator-micro/content/post/image",
        }
        return (
            current.scheme == expected.scheme
            and current.hostname == expected.hostname
            and current.path.rstrip("/") in supported_paths
        )

    def parse_content_ref(self, value: str) -> tuple[str, str | None]:
        value = str(value or "").strip()
        if _CONTENT_ID_RE.fullmatch(value):
            return value, None
        parsed = urlparse(value)
        if self._is_platform_host(parsed.hostname or ""):
            match = _CONTENT_PATH_RE.search(parsed.path)
            if match:
                return match.group(2), match.group(1)
        raise ValueError(
            "作品 ID 必须是数字，或使用 douyin.com 的 /video/、/note/ 公开链接"
        )

    def search_url(self, keyword: str) -> str:
        keyword = str(keyword or "").strip()
        if not keyword:
            raise ValueError("搜索关键词不能为空")
        return f"{self.search_base_url}{quote(keyword, safe='')}?type=video"

    def content_urls(self, content_ref: str) -> list[tuple[str, str]]:
        content_id, kind = self.parse_content_ref(content_ref)
        if kind:
            return [(kind, self.content_url(kind, content_id))]
        return [
            (
                self.default_content_kind,
                self.content_url(self.default_content_kind, content_id),
            ),
            ("note", self.content_url("note", content_id)),
        ]

    def content_url(self, kind: str, content_id: str) -> str:
        template = self.content_url_templates[kind]
        return template.format(id=content_id)

    def content_kind(self, value: str) -> str | None:
        parsed = urlparse(str(value or ""))
        if not self._is_platform_host(parsed.hostname or ""):
            return None
        match = _CONTENT_PATH_RE.search(parsed.path)
        return match.group(1) if match else None

    def extract_content_id(self, value: str) -> str:
        match = _CONTENT_PATH_RE.search(str(value or ""))
        return match.group(2) if match else ""

    def extract_author_id(self, value: str) -> str:
        for pattern in (r"modal_id=(\d+)", r"sec_uid=([^&#]+)", r"/user/([^/?&#]+)"):
            match = re.search(pattern, str(value or ""))
            if match:
                return match.group(1)
        return ""

    def is_risk_page(self, title: str, text: str) -> bool:
        combined = f"{title or ''}\n{text or ''}"
        return any(keyword in combined for keyword in self.risk_page_keywords)

    def navigate_home(self, page) -> None:
        page.navigate(self.home_url)

    def navigate_featured(self, page) -> None:
        page.navigate(self.featured_url)

    def navigate_search(self, page, keyword: str) -> None:
        page.navigate(self.search_url(keyword))

    def navigate_trending(self, page) -> None:
        page.navigate(self.trending_url)

    def navigate_publish_image(self, page) -> None:
        page.navigate(self.creator_upload_url)


DEFAULT_ADAPTER = DouyinAdapter()
