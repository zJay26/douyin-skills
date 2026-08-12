from __future__ import annotations

import json
import re
import time

from .page_states import (
    classify_detail_snapshot,
    classify_search_snapshot,
    has_risk_evidence,
)
from .selectors import (
    COMMENT_ITEM_SELECTORS,
    DETAIL_DESC_SELECTORS,
)
from .urls import (
    content_urls,
    jingxuan_url,
    parse_content_ref,
    search_url,
    trending_url,
)
from .waiters import wait_for_meaningful_text

DEFAULT_SEARCH_LIMIT = 7


def _extract_content_id(url: str) -> str:
    m = re.search(r"/(?:video|note)/(\d+)", url)
    return m.group(1) if m else ""


def _extract_author_id(url: str) -> str:
    patterns = [
        r"modal_id=(\d+)",
        r"sec_uid=([^&#]+)",
        r"/user/([^/?&#]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return ""


def _is_risk_page(title: str, text: str) -> bool:
    return has_risk_evidence(title, text)


def list_feeds(page) -> dict:
    page.navigate(jingxuan_url())
    page.wait_for_load(20)
    seed = wait_for_meaningful_text(page, timeout=45, min_len=80)
    title = seed.get("title", "") or ""
    text = seed.get("text", "") or ""
    if _is_risk_page(title, text):
        return {
            "success": False,
            "count": 0,
            "videos": [],
            "risk_page": True,
            "message": "当前处于验证码/风控页，无法抓取首页推荐。",
            "page_title": title,
        }

    page_info = {}
    for _ in range(20):
        raw = page.evaluate(
            "(()=>JSON.stringify({title:document.title||'',text:(document.body?.innerText||'').trim().slice(0,4000),videos:Array.from(document.querySelectorAll('div[data-aweme-id]')).slice(0,20).map(card=>{const id=card.getAttribute('data-aweme-id')||'';const txt=(card.innerText||'').trim();const lines=txt.split(/\\n/).map(x=>x.trim()).filter(Boolean);const author=(lines.find(x=>x.startsWith('@'))||'').replace(/^@/,'');const t=lines.find(x=>/^(\\d{1,2}:\\d{2}|\\d{1,2}:\\d{2}:\\d{2})$/.test(x))||'';const s=lines.find(x=>/^(\\d+(\\.\\d+)?[万亿]?\\+?)$/.test(x.replace(/,/g,'')))||'';const title=lines.find(x=>x&&!x.startsWith('@')&&!x.startsWith('·')&&x!=='/'&&!/^共创$/.test(x)&&!/^(\\d{1,2}:\\d{2}|\\d{1,2}:\\d{2}:\\d{2})$/.test(x)&&!/^(\\d+(\\.\\d+)?[万亿]?\\+?)$/.test(x.replace(/,/g,'')))||'';const img=card.querySelector('img');const timeIdx=lines.findIndex(x=>x.startsWith('@'));return {id,author_id:'',title:title.slice(0,120),author,publish_time:timeIdx>=0?(lines[timeIdx+1]||'').replace(/^·\\s*/,''):'' ,duration:t,interaction_text:s,cover_url:img?(img.src||''):'',url:id?('https://www.douyin.com/video/'+id):'',summary:txt.slice(0,500)};})}))()"
        )
        page_info = json.loads(raw) if raw else {}
        if page_info.get("videos"):
            break
        time.sleep(1)

    title = page_info.get("title", "") or title
    text = page_info.get("text", "") or text
    if _is_risk_page(title, text):
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


def search_videos(page, keyword: str, limit: int = DEFAULT_SEARCH_LIMIT) -> dict:
    page.navigate(search_url(keyword))
    page.wait_for_load(20)
    seed = wait_for_meaningful_text(page, timeout=45, min_len=80)
    if has_risk_evidence(seed.get("title", ""), seed.get("text", "")):
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
    for _ in range(15):
        page_info = (
            page.evaluate(
                r"""
            (() => {
              const title = document.title || '';
              const text = document.body ? document.body.innerText : '';
              const anchors = Array.from(document.querySelectorAll("a[href*='/video/'], a[href*='/note/']"));
              const seen = new Set();
              const items = [];
              for (const a of anchors) {
                const href = a.href || a.getAttribute('href') || '';
                if (seen.has(href) || (!href.includes('/video/') && !href.includes('/note/'))) continue;
                seen.add(href);
                const card = a ? (a.closest('li, article, section, div') || a) : null;
                const cardText = ((card && card.innerText) || (a && a.innerText) || '').trim();
                const lines = cardText.split(/\n/).map(x => x.trim()).filter(Boolean);
                const cleaned = lines.filter(x => x && !x.startsWith('@') && !/^(\d{1,2}:\d{2}|\d{1,2}:\d{2}:\d{2})$/.test(x) && !/^(\d+(\.\d+)?[万亿]?\+?)$/.test(x.replace(/,/g, '')) && x !== '合集');
                const authorLine = lines.find(x => x.startsWith('@')) || '';
                items.push({
                  href,
                  text: cardText.slice(0, 300),
                  title: (cleaned[0] || lines.find(x => x.length >= 4) || '').trim(),
                  author: authorLine.replace(/^@/, '').trim(),
                });
                if (items.length >= 20) break;
              }
              return { title, text: text.slice(0, 3000), items, hrefCount: anchors.length };
            })()
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
    if classification["state"] == "risk":
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
        video_id = _extract_content_id(href)
        videos.append(
            {
                "id": video_id,
                "kind": "note" if "/note/" in href else "video",
                "author_id": _extract_author_id(href),
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


def get_trending_topics(page) -> dict:
    page.navigate(trending_url())
    page.wait_for_load(20)
    seed = wait_for_meaningful_text(page, timeout=45, min_len=60)
    title = seed.get("title", "") or ""
    text = seed.get("text", "") or ""
    if _is_risk_page(title, text):
        return {
            "success": False,
            "count": 0,
            "topics": [],
            "risk_page": True,
            "message": "当前处于验证码/风控页，无法抓取热门话题。",
            "page_title": title,
        }

    data = (
        page.evaluate(
            """
        (() => {
          const title = document.title || '';
          const bodyText = (document.body?.innerText || '').trim().slice(0, 4000);
          const nodes = Array.from(document.querySelectorAll('a, div, li')).slice(0, 800);
          const topics = [];
          const seen = new Set();
          for (const node of nodes) {
            const txt = (node.innerText || '').trim();
            if (!txt) continue;
            const lines = txt.split(/\n/).map(x => x.trim()).filter(Boolean);
            const name = lines.find(x => /^#?\\S{2,40}$/.test(x) && /热|榜|话题|挑战|同城|推荐|音乐|剧情|搞笑|美食|穿搭|旅行|开箱|测评/.test(txt)) || lines[0] || '';
            if (!name || seen.has(name)) continue;
            seen.add(name);
            topics.push({ name, summary: lines.slice(0, 4).join(' | ').slice(0, 200) });
            if (topics.length >= 20) break;
          }
          return { title, text: bodyText, topics };
        })()
        """
        )
        or {}
    )
    title = data.get("title", "") or title
    text = data.get("text", "") or text
    if _is_risk_page(title, text):
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


def get_video_detail(page, video_id: str) -> dict:
    content_id, requested_kind = parse_content_ref(video_id)
    last_detail: dict = {}
    last_seed: dict = {}
    for kind, url in content_urls(video_id):
        page.navigate(url)
        page.wait_for_load(20)
        seed = wait_for_meaningful_text(page, timeout=45, min_len=40)
        detail_raw = page.evaluate(
            f"""
        (() => {{
          const descSelectors = {json.dumps(DETAIL_DESC_SELECTORS)};
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
          const commentSelectors = {json.dumps(COMMENT_ITEM_SELECTORS)};
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
