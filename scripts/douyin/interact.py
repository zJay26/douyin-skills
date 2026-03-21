from __future__ import annotations

import json
import time

from .login import RISK_PAGE_KEYWORDS
from .selectors import LIKE_BUTTON_SELECTORS
from .urls import note_url, video_url


def _first_clickable(page, selectors: list[str]) -> str | None:
    for selector in selectors:
        found = page.evaluate(f"document.querySelector({json.dumps(selector)}) !== null")
        if found:
            return selector
    return None


def _open_detail(page, item_id: str) -> dict:
    for kind, url in (("video", video_url(item_id)), ("note", note_url(item_id))):
        page.navigate(url)
        page.wait_for_load(20)
        time.sleep(5)
        title = page.evaluate("document.title || ''") or ""
        body = page.evaluate("(document.body && document.body.innerText || '').slice(0, 3000)") or ""
        href = page.evaluate("location.href || ''") or ""
        if any(k in title or k in body for k in RISK_PAGE_KEYWORDS):
            return {"success": False, "risk_page": True, "error": "当前处于验证码/风控页，无法执行互动", "item_id": item_id, "page_title": title, "href": href}
        if "/note/" in href:
            return {"success": True, "kind": "note", "href": href, "title": title, "body": body}
        if kind == "video" and ("不存在" in body or "视频数据加载中" in body or ("收藏" not in body and "分享" not in body and "评论" not in body)):
            continue
        return {"success": True, "kind": kind, "href": href, "title": title, "body": body}
    return {"success": False, "error": "作品详情页不存在或无法访问", "item_id": item_id}


def _click_note_action(page, action: str) -> dict:
    script = f"""
    (() => {{
      const bars = Array.from(document.querySelectorAll('div')).filter(el => {{
        const txt = (el.innerText || '').trim();
        return txt.includes('分享') && el.children.length >= 4 && el.children.length <= 8;
      }});
      const bar = bars.reverse().find(el => Array.from(el.children).some(c => (c.innerText || '').trim().includes('分享')));
      if (!bar) return {{ok:false, reason:'action-bar-not-found'}};
      let target = null;
      if ({json.dumps(action)} === 'like') target = bar.children[0] || null;
      else if ({json.dumps(action)} === 'favorite') target = Array.from(bar.children).find(el => (el.innerText || '').trim().includes('收藏')) || null;
      else if ({json.dumps(action)} === 'share') target = Array.from(bar.children).find(el => (el.innerText || '').trim().includes('分享')) || null;
      if (!target) return {{ok:false, reason:'target-not-found'}};
      target.scrollIntoView({{block:'center'}});
      target.click();
      return {{ok:true, text:(target.innerText||'').trim(), cls:(target.className||'').toString()}};
    }})()
    """
    return page.evaluate(script) or {"ok": False, "reason": "evaluate-failed"}


def _click_text(page, text: str) -> bool:
    return bool(page.evaluate(f"""(() => {{ const wanted = {json.dumps(text)}; const nodes = Array.from(document.querySelectorAll('button, [role=\"button\"], div, span')); const el = nodes.find(x => (x.innerText || '').trim() === wanted) || nodes.find(x => (x.innerText || '').trim().includes(wanted)); if (!el) return false; el.scrollIntoView({{block:'center'}}); el.click(); return true; }})()"""))


def like_video(page, video_id: str) -> dict:
    opened = _open_detail(page, video_id)
    if not opened.get("success"):
        return opened
    selector = _first_clickable(page, LIKE_BUTTON_SELECTORS)
    clicked = page.click(selector) if selector else False
    meta = {"video_id": video_id, "action": "like", "page_kind": opened.get("kind"), "url": opened.get("href")}
    if clicked:
        return {"success": True, **meta, "selector": selector}
    if opened.get("kind") == "note":
        result = _click_note_action(page, "like")
        return {"success": bool(result.get("ok")), **meta, "selector": "note-action-bar:first-child", "detail": result}
    return {"success": False, **meta, "error": "未找到点赞按钮"}


def favorite_video(page, video_id: str) -> dict:
    opened = _open_detail(page, video_id)
    if not opened.get("success"):
        return opened
    if opened.get("kind") == "note":
        result = _click_note_action(page, "favorite")
        return {"success": bool(result.get("ok")), "video_id": video_id, "action": "favorite", "page_kind": opened.get("kind"), "url": opened.get("href"), "selector": "note-action-bar:favorite", "detail": result}
    clicked = _click_text(page, "收藏")
    return {"success": clicked, "video_id": video_id, "action": "favorite", "page_kind": opened.get("kind"), "url": opened.get("href"), "selector": "text:收藏" if clicked else "", "error": "未找到收藏按钮" if not clicked else ""}


def share_video(page, video_id: str) -> dict:
    opened = _open_detail(page, video_id)
    if not opened.get("success"):
        return opened
    result = _click_note_action(page, "share") if opened.get("kind") == "note" else {"ok": _click_text(page, "分享")}
    if not result.get("ok"):
        return {"success": False, "video_id": video_id, "action": "share", "page_kind": opened.get("kind"), "url": opened.get("href"), "error": "未找到分享按钮", "detail": result}
    time.sleep(1)
    copied = _click_text(page, "复制链接")
    return {"success": copied, "video_id": video_id, "action": "share", "page_kind": opened.get("kind"), "url": opened.get("href"), "selector": "text:复制链接" if copied else "", "detail": result, "error": "已打开分享面板，但未找到复制链接" if not copied else ""}
