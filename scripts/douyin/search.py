from __future__ import annotations

import json
import time

from platform_adapter import PlatformAdapter, resolve_adapter

from .page_states import (
    classify_detail_snapshot,
    classify_search_snapshot,
)
from .waiters import wait_for_meaningful_text

DEFAULT_SEARCH_LIMIT = 7


def _extract_content_id(url: str, adapter: PlatformAdapter | None = None) -> str:
    return resolve_adapter(adapter).extract_content_id(url)


def _extract_author_id(url: str, adapter: PlatformAdapter | None = None) -> str:
    return resolve_adapter(adapter).extract_author_id(url)


def _is_risk_page(
    title: str, text: str, adapter: PlatformAdapter | None = None
) -> bool:
    return resolve_adapter(adapter).is_risk_page(title, text)


def list_feeds(page, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    adapter.navigate_featured(page)
    page.wait_for_load(20)
    seed = wait_for_meaningful_text(page, timeout=45, min_len=80)
    title = seed.get("title", "") or ""
    text = seed.get("text", "") or ""
    if _is_risk_page(title, text, adapter):
        return {
            "success": False,
            "count": 0,
            "videos": [],
            "risk_page": True,
            "message": "当前处于验证码/风控页，无法抓取首页推荐。",
            "page_title": title,
        }

    page_info = {}
    feed_selector = json.dumps(adapter.selectors.feed_card_selector)
    feed_id_attribute = json.dumps(adapter.selectors.feed_content_id_attribute)
    feed_url_template = json.dumps(
        adapter.content_url_templates[adapter.default_content_kind],
        ensure_ascii=False,
    )
    for _ in range(20):
        raw = page.evaluate(
            f"""
            (() => JSON.stringify({{
              title: document.title || '',
              text: (document.body?.innerText || '').trim().slice(0, 4000),
              videos: Array.from(document.querySelectorAll({feed_selector})).slice(0, 20).map(card => {{
                const id = card.getAttribute({feed_id_attribute}) || '';
                const txt = (card.innerText || '').trim();
                const lines = txt.split(/\\n/).map(x => x.trim()).filter(Boolean);
                const author = (lines.find(x => x.startsWith('@')) || '').replace(/^@/, '');
                const duration = lines.find(x => /^(\\d{{1,2}}:\\d{{2}}|\\d{{1,2}}:\\d{{2}}:\\d{{2}})$/.test(x)) || '';
                const interactionText = lines.find(x => /^(\\d+(\\.\\d+)?[万亿]?\\+?)$/.test(x.replace(/,/g, ''))) || '';
                const title = lines.find(x => x && !x.startsWith('@') && !x.startsWith('·') && x !== '/' && x !== '共创' && !/^(\\d{{1,2}}:\\d{{2}}|\\d{{1,2}}:\\d{{2}}:\\d{{2}})$/.test(x) && !/^(\\d+(\\.\\d+)?[万亿]?\\+?)$/.test(x.replace(/,/g, ''))) || '';
                const authorIndex = lines.findIndex(x => x.startsWith('@'));
                const img = card.querySelector('img');
                return {{
                  id,
                  author_id: '',
                  title: title.slice(0, 120),
                  author,
                  publish_time: authorIndex >= 0 ? (lines[authorIndex + 1] || '').replace(/^·\\s*/, '') : '',
                  duration,
                  interaction_text: interactionText,
                  cover_url: img ? (img.src || '') : '',
                  url: id ? {feed_url_template}.replace('{{id}}', id) : '',
                  summary: txt.slice(0, 500)
                }};
              }})
            }}))()
            """
        )
        page_info = json.loads(raw) if raw else {}
        if page_info.get("videos"):
            break
        time.sleep(1)

    title = page_info.get("title", "") or title
    text = page_info.get("text", "") or text
    if _is_risk_page(title, text, adapter):
        return {
            "success": False,
            "count": 0,
            "videos": [],
            "risk_page": True,
            "message": "当前处于验证码/风控页，无法抓取首页推荐。",
            "page_title": title,
        }
    videos = page_info.get("videos", [])
    return {
        "success": True,
        "count": len(videos),
        "videos": videos,
        "page_title": title,
    }


def search_videos(
    page,
    keyword: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
    adapter: PlatformAdapter | None = None,
) -> dict:
    adapter = resolve_adapter(adapter)
    adapter.navigate_search(page, keyword)
    page.wait_for_load(20)
    seed = wait_for_meaningful_text(page, timeout=45, min_len=80)
    if _is_risk_page(seed.get("title", ""), seed.get("text", ""), adapter):
        return {
            "success": False,
            "keyword": keyword,
            "count": 0,
            "videos": [],
            "risk_page": True,
            "message": "当前处于验证码/风控页，无法执行搜索结果抓取。",
            "page_title": seed.get("title", ""),
        }
    for _ in range(30):
        if page.evaluate('document.querySelector(".search-result-card") !== null'):
            break
        time.sleep(1)
    page_info = {}
    result_selector = json.dumps(
        ", ".join(adapter.selectors.search_result_selectors), ensure_ascii=False
    )
    content_path_fragments = json.dumps(
        list(adapter.content_path_fragments), ensure_ascii=False
    )
    for _ in range(15):
        page_info = (
            page.evaluate(
                rf"""
            (() => {{
              const title = document.title || '';
              const text = document.body ? document.body.innerText : '';
              const contentPathFragments = {content_path_fragments};
              const anchors = Array.from(document.querySelectorAll({result_selector}));
              const seen = new Set();
              const items = [];
              for (const a of anchors) {{
                const href = a.href || a.getAttribute('href') || '';
                if (seen.has(href) || !contentPathFragments.some(fragment => href.includes(fragment))) continue;
                seen.add(href);
                const card = a ? (a.closest('li, article, section, div') || a) : null;
                const cardText = ((card && card.innerText) || (a && a.innerText) || '').trim();
                const lines = cardText.split(/\n/).map(x => x.trim()).filter(Boolean);
                const cleaned = lines.filter(x => x && !x.startsWith('@') && !/^(\d{{1,2}}:\d{{2}}|\d{{1,2}}:\d{{2}}:\d{{2}})$/.test(x) && !/^(\d+(\.\d+)?[万亿]?\+?)$/.test(x.replace(/,/g, '')) && x !== '合集');
                const authorLine = lines.find(x => x.startsWith('@')) || '';
                items.push({{
                  href,
                  text: cardText.slice(0, 300),
                  title: (cleaned[0] || lines.find(x => x.length >= 4) || '').trim(),
                  author: authorLine.replace(/^@/, '').trim(),
                }});
                if (items.length >= 20) break;
              }}
              return {{ title, text: text.slice(0, 3000), items, hrefCount: anchors.length }};
            }})()
            """
            )
            or {}
        )
        if page_info.get("items"):
            break
        time.sleep(1)
    title = page_info.get("title", "") or seed.get("title", "")
    text = page_info.get("text", "") or seed.get("text", "")
    classification = classify_search_snapshot(
        {"title": title, "text": text, "items": page_info.get("items", [])}
    )
    if classification["state"] == "risk" or _is_risk_page(title, text, adapter):
        return {
            "success": False,
            "keyword": keyword,
            "count": 0,
            "videos": [],
            "risk_page": True,
            "message": "当前处于验证码/风控页，无法执行搜索结果抓取。",
            "page_title": title,
        }
    items = page_info.get("items", [])
    if classification["state"] == "empty_or_blocked":
        return {
            "success": False,
            "keyword": keyword,
            "count": 0,
            "videos": [],
            "risk_page": True,
            "message": "页面内容为空，疑似被验证码/风控页拦截。",
            "page_title": title,
        }
    videos = []
    requested_limit = min(20, max(1, int(limit or DEFAULT_SEARCH_LIMIT)))
    for item in items[:requested_limit]:
        href = item.get("href", "")
        video_id = _extract_content_id(href, adapter)
        videos.append(
            {
                "id": video_id,
                "kind": adapter.content_kind(href) or adapter.default_content_kind,
                "author_id": _extract_author_id(href, adapter),
                "title": item.get("title") or item.get("text", "")[:80],
                "author": item.get("author", ""),
                "url": href,
                "summary": item.get("text", ""),
            }
        )

    return {
        "success": True,
        "keyword": keyword,
        "count": len(videos),
        "videos": videos,
        "limit": requested_limit,
    }


def get_trending_topics(page, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    adapter.navigate_trending(page)
    page.wait_for_load(20)
    seed = wait_for_meaningful_text(page, timeout=45, min_len=60)
    title = seed.get("title", "") or ""
    text = seed.get("text", "") or ""
    if _is_risk_page(title, text, adapter):
        return {
            "success": False,
            "count": 0,
            "topics": [],
            "risk_page": True,
            "message": "当前处于验证码/风控页，无法抓取热门话题。",
            "page_title": title,
        }

    trending_selector = json.dumps(
        ", ".join(adapter.selectors.trending_node_selectors), ensure_ascii=False
    )
    topic_keywords = json.dumps(
        list(adapter.selectors.trending_topic_keywords), ensure_ascii=False
    )
    data = (
        page.evaluate(
            f"""
        (() => {{
          const title = document.title || '';
          const bodyText = (document.body?.innerText || '').trim().slice(0, 4000);
          const topicKeywords = {topic_keywords};
          const nodes = Array.from(document.querySelectorAll({trending_selector})).slice(0, 800);
          const topics = [];
          const seen = new Set();
          for (const node of nodes) {{
            const txt = (node.innerText || '').trim();
            if (!txt) continue;
            const lines = txt.split(/\n/).map(x => x.trim()).filter(Boolean);
            const name = lines.find(x => /^#?\\S{{2,40}}$/.test(x) && topicKeywords.some(keyword => txt.includes(keyword))) || lines[0] || '';
            if (!name || seen.has(name)) continue;
            seen.add(name);
            topics.push({{ name, summary: lines.slice(0, 4).join(' | ').slice(0, 200) }});
            if (topics.length >= 20) break;
          }}
          return {{ title, text: bodyText, topics }};
        }})()
        """
        )
        or {}
    )
    title = data.get("title", "") or title
    text = data.get("text", "") or text
    if _is_risk_page(title, text, adapter):
        return {
            "success": False,
            "count": 0,
            "topics": [],
            "risk_page": True,
            "message": "当前处于验证码/风控页，无法抓取热门话题。",
            "page_title": title,
        }
    topics = data.get("topics", [])
    return {
        "success": True,
        "count": len(topics),
        "topics": topics,
        "page_title": title,
    }


def get_video_detail(
    page, video_id: str, adapter: PlatformAdapter | None = None
) -> dict:
    adapter = resolve_adapter(adapter)
    content_id, requested_kind = adapter.parse_content_ref(video_id)
    last_detail: dict = {}
    last_seed: dict = {}
    detail_desc_selectors = json.dumps(
        list(adapter.selectors.detail_desc_selectors), ensure_ascii=False
    )
    comment_item_selectors = json.dumps(
        list(adapter.selectors.comment_item_selectors), ensure_ascii=False
    )
    for kind, url in adapter.content_urls(video_id):
        page.navigate(url)
        page.wait_for_load(20)
        seed = wait_for_meaningful_text(page, timeout=45, min_len=40)
        detail_raw = page.evaluate(
            f"""
        (() => {{
          const descSelectors = {detail_desc_selectors};
          let description = '';
          for (const sel of descSelectors) {{
            const el = document.querySelector(sel);
            if (el && (el.innerText || el.textContent)) {{
              description = (el.innerText || el.textContent).trim();
              if (description) break;
            }}
          }}
          const title = document.title || '';
          const comments = [];
          const commentSelectors = {comment_item_selectors};
          for (const sel of commentSelectors) {{
            for (const node of document.querySelectorAll(sel)) {{
              const txt = (node.innerText || '').trim();
              if (txt) comments.push(txt.slice(0, 300));
              if (comments.length >= 20) break;
            }}
            if (comments.length) break;
          }}
          return JSON.stringify({{
            title,
            description,
            comments,
            url: location.href,
            bodyText: (document.body?.innerText || '').slice(0, 1500),
          }});
        }})()
        """
        )
        detail = json.loads(detail_raw) if detail_raw else {}
        detail["title"] = detail.get("title", "") or seed.get("title", "")
        detail["bodyText"] = detail.get("bodyText", "") or seed.get("text", "")
        classification = classify_detail_snapshot(detail, kind)
        if classification["state"] == "risk":
            return {
                "success": False,
                "video_id": content_id,
                "risk_page": True,
                "message": "当前处于验证码/风控页，无法抓取作品详情。",
                "page_title": detail.get("title", ""),
            }
        href = detail.get("url", "") or ""
        body = detail.get("bodyText", "") or ""
        if classification["state"] == "ready":
            return {
                "success": True,
                "video_id": content_id,
                "content_type": kind,
                "video_info": {
                    "title": detail.get("title", ""),
                    "description": detail.get("description", ""),
                    "url": href,
                },
                "comments": [{"text": x} for x in detail.get("comments", [])],
                "raw_excerpt": body,
            }
        last_detail = detail
        last_seed = seed

    return {
        "success": False,
        "video_id": content_id,
        "requested_type": requested_kind,
        "message": "作品不存在、不可见或页面结构已变化。",
        "page_title": last_detail.get("title", "") or last_seed.get("title", ""),
    }
