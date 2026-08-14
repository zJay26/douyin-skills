from __future__ import annotations

import json
import time

from platform_adapter import PlatformAdapter, resolve_adapter


def _first_clickable(page, selectors: list[str]) -> str | None:
    for selector in selectors:
        found = page.evaluate(
            f"document.querySelector({json.dumps(selector)}) !== null"
        )
        if found:
            return selector
    return None


def _open_detail(page, item_id: str, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    normalized_id, _requested_kind = adapter.parse_content_ref(item_id)
    for kind, url in adapter.content_urls(item_id):
        page.navigate(url)
        page.wait_for_load(20)
        time.sleep(5)
        title = page.evaluate("document.title || ''") or ""
        body = (
            page.evaluate(
                "(document.body && document.body.innerText || '').slice(0, 3000)"
            )
            or ""
        )
        href = page.evaluate("location.href || ''") or ""
        if adapter.is_risk_page(title, body):
            return {
                "success": False,
                "risk_page": True,
                "error": "当前处于验证码/风控页，无法执行互动",
                "item_id": normalized_id,
                "page_title": title,
                "href": href,
            }
        if adapter.content_kind(href) == "note":
            return {
                "success": True,
                "kind": "note",
                "href": href,
                "title": title,
                "body": body,
            }
        if kind == "video" and (
            any(marker in body for marker in adapter.inaccessible_content_markers)
            or (
                adapter.selectors.favorite_action_text not in body
                and adapter.selectors.share_action_text not in body
                and adapter.selectors.comment_action_text not in body
            )
        ):
            continue
        return {
            "success": True,
            "kind": kind,
            "href": href,
            "title": title,
            "body": body,
        }
    return {
        "success": False,
        "error": "作品详情页不存在或无法访问",
        "item_id": normalized_id,
    }


def _click_note_action(
    page, action: str, adapter: PlatformAdapter | None = None
) -> dict:
    adapter = resolve_adapter(adapter)
    action_texts = {
        "like": adapter.selectors.like_action_text,
        "favorite": adapter.selectors.favorite_action_text,
        "share": adapter.selectors.share_action_text,
    }
    action_text = json.dumps(action_texts.get(action, ""), ensure_ascii=False)
    marker = json.dumps(adapter.selectors.note_action_bar_marker, ensure_ascii=False)
    script = f"""
    (() => {{
      const bars = Array.from(document.querySelectorAll('div')).filter(el => {{
        const txt = (el.innerText || '').trim();
        return txt.includes({marker}) && el.children.length >= 4 && el.children.length <= 8;
      }});
      const bar = bars.reverse().find(el => Array.from(el.children).some(c => (c.innerText || '').trim().includes({marker})));
      if (!bar) return {{ok:false, reason:'action-bar-not-found'}};
      const target = {json.dumps(action)} === 'like'
        ? bar.children[0] || null
        : Array.from(bar.children).find(el => (el.innerText || '').trim().includes({action_text})) || null;
      if (!target) return {{ok:false, reason:'target-not-found'}};
      target.scrollIntoView({{block:'center'}});
      target.click();
      return {{ok:true, text:(target.innerText||'').trim(), cls:(target.className||'').toString()}};
    }})()
    """
    return page.evaluate(script) or {"ok": False, "reason": "evaluate-failed"}


def _click_text(page, text: str) -> bool:
    return bool(
        page.evaluate(
            f"""(() => {{ const wanted = {json.dumps(text)}; const nodes = Array.from(document.querySelectorAll('button, [role=\"button\"], div, span')); const el = nodes.find(x => (x.innerText || '').trim() === wanted) || nodes.find(x => (x.innerText || '').trim().includes(wanted)); if (!el) return false; el.scrollIntoView({{block:'center'}}); el.click(); return true; }})()"""
        )
    )


def like_video(page, video_id: str, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    opened = _open_detail(page, video_id, adapter=adapter)
    if not opened.get("success"):
        return opened
    selector = _first_clickable(page, adapter.selectors.like_button_selectors)
    clicked = page.click(selector) if selector else False
    content_id, _kind = adapter.parse_content_ref(video_id)
    meta = {
        "video_id": content_id,
        "action": "like",
        "page_kind": opened.get("kind"),
        "url": opened.get("href"),
    }
    if clicked:
        return {
            "success": True,
            **meta,
            "selector": selector,
            "state_verified": False,
            "message": "已点击点赞按钮，但当前页面未提供可稳定读取的最终状态；不要自动重复点击。",
        }
    if opened.get("kind") == "note":
        result = _click_note_action(page, "like", adapter=adapter)
        return {
            "success": bool(result.get("ok")),
            **meta,
            "selector": "note-action-bar:first-child",
            "detail": result,
            "state_verified": False,
            "message": "已点击点赞区域，但当前页面未提供可稳定读取的最终状态；不要自动重复点击。"
            if result.get("ok")
            else "未找到可用的点赞区域。",
        }
    return {"success": False, **meta, "error": "未找到点赞按钮"}


def favorite_video(page, video_id: str, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    opened = _open_detail(page, video_id, adapter=adapter)
    if not opened.get("success"):
        return opened
    content_id, _kind = adapter.parse_content_ref(video_id)
    if opened.get("kind") == "note":
        result = _click_note_action(page, "favorite", adapter=adapter)
        return {
            "success": bool(result.get("ok")),
            "video_id": content_id,
            "action": "favorite",
            "page_kind": opened.get("kind"),
            "url": opened.get("href"),
            "selector": "note-action-bar:favorite",
            "detail": result,
            "state_verified": False,
            "message": "已点击收藏区域，但当前页面未提供可稳定读取的最终状态；不要自动重复点击。"
            if result.get("ok")
            else "未找到可用的收藏区域。",
        }
    clicked = _click_text(page, adapter.selectors.favorite_action_text)
    return {
        "success": clicked,
        "video_id": content_id,
        "action": "favorite",
        "page_kind": opened.get("kind"),
        "url": opened.get("href"),
        "selector": f"text:{adapter.selectors.favorite_action_text}" if clicked else "",
        "state_verified": False,
        "message": "已点击收藏按钮，但当前页面未提供可稳定读取的最终状态；不要自动重复点击。"
        if clicked
        else "未找到收藏按钮。",
        "error": "未找到收藏按钮" if not clicked else "",
    }


def share_video(page, video_id: str, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    opened = _open_detail(page, video_id, adapter=adapter)
    if not opened.get("success"):
        return opened
    content_id, _kind = adapter.parse_content_ref(video_id)
    share_url = opened.get("href") or ""
    result = (
        _click_note_action(page, "share", adapter=adapter)
        if opened.get("kind") == "note"
        else {"ok": _click_text(page, adapter.selectors.share_action_text)}
    )
    if not result.get("ok"):
        return {
            "success": bool(share_url),
            "video_id": content_id,
            "action": "share",
            "page_kind": opened.get("kind"),
            "url": share_url,
            "share_url": share_url,
            "copied_to_clipboard": False,
            "message": "已返回公开作品链接，但未能打开页面分享面板。",
            "detail": result,
        }
    time.sleep(1)
    copied = _click_text(page, adapter.selectors.copy_link_text)
    return {
        "success": bool(share_url),
        "video_id": content_id,
        "action": "share",
        "page_kind": opened.get("kind"),
        "url": share_url,
        "share_url": share_url,
        "copied_to_clipboard": copied,
        "selector": f"text:{adapter.selectors.copy_link_text}" if copied else "",
        "detail": result,
        "message": "已复制并返回公开作品链接。"
        if copied
        else "已返回公开作品链接；当前环境未确认写入剪贴板。",
    }
