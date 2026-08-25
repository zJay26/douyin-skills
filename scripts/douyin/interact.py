from __future__ import annotations

import json
import time

from platform_adapter import PlatformAdapter, resolve_adapter

ACTION_STATE_TIMEOUT = 3.0
ACTION_STATE_INTERVAL = 0.4


def _first_clickable(page, selectors: list[str]) -> str | None:
    for selector in selectors:
        found = page.evaluate(
            f"document.querySelector({json.dumps(selector)}) !== null"
        )
        if found:
            return selector
    return None


def _read_action_state(page, selector: str, active_texts: tuple[str, ...] = ()) -> dict:
    return _read_action_state_with_styles(page, selector, active_texts, ())


def _read_action_state_with_styles(
    page,
    selector: str,
    active_texts: tuple[str, ...] = (),
    active_style_tokens: tuple[str, ...] = (),
    active_state_tokens: tuple[str, ...] = (),
    inactive_state_tokens: tuple[str, ...] = (),
) -> dict:
    active_texts_json = json.dumps(list(active_texts), ensure_ascii=False)
    active_style_tokens_json = json.dumps(list(active_style_tokens), ensure_ascii=False)
    active_state_tokens_json = json.dumps(list(active_state_tokens), ensure_ascii=False)
    inactive_state_tokens_json = json.dumps(
        list(inactive_state_tokens), ensure_ascii=False
    )
    selector_json = json.dumps(selector, ensure_ascii=False)
    return page.evaluate(
        f"""
        (() => {{
          const root = document.querySelector({selector_json});
          if (!root) return {{state:'missing', confidence:'none', selector:{selector_json}}};
          const nodes = [root, ...root.querySelectorAll('*')];
          const values = ['aria-pressed', 'aria-checked', 'data-selected', 'data-checked', 'data-active']
            .map(name => root.getAttribute(name))
            .filter(value => value !== null)
            .map(value => String(value).toLowerCase());
          const labels = nodes.map(el => [
            el.innerText || '',
            el.getAttribute?.('aria-label') || '',
            el.getAttribute?.('title') || ''
          ].join(' ')).join(' ').trim();
          const activeTexts = {active_texts_json};
          const activeStyleTokens = {active_style_tokens_json};
          const activeStateTokens = {active_state_tokens_json}
            .map(value => String(value).toLowerCase());
          const inactiveStateTokens = {inactive_state_tokens_json}
            .map(value => String(value).toLowerCase());
          const dataE2eState = String(root.getAttribute('data-e2e-state') || '')
            .toLowerCase();
          const attributeActive = activeStateTokens.includes(dataE2eState);
          const attributeInactive = inactiveStateTokens.includes(dataE2eState);
          const explicitTrue = values.some(value => ['true', '1', 'yes'].includes(value));
          const explicitFalse = values.some(value => ['false', '0', 'no'].includes(value));
          const activeText = activeTexts.some(text => text && labels.includes(text));
          const activeClass = nodes.some(el =>
            /(^|[-_\\s])(active|selected|checked|liked|favorited|collected)([-_\\s]|$)/i
              .test(String(el.className || ''))
          );
          const classes = [...new Set(nodes
            .map(el => String(el.className || '').trim())
            .filter(Boolean))].join(' ').slice(0, 500);
          const colors = [...new Set(nodes.flatMap(el => {{
            const style = getComputedStyle(el);
            return [style.color, style.fill, style.stroke].filter(Boolean);
          }}))].slice(0, 20);
          const activeStyle = activeStyleTokens.some(token =>
            colors.some(color => color.toLowerCase().includes(token.toLowerCase()))
          );
          const highActive = attributeActive || explicitTrue || activeText || activeStyle;
          const highInactive = attributeInactive || explicitFalse;
          const evidenceConflict = highActive && highInactive;
          const state = evidenceConflict
            ? 'unknown'
            : highActive
              ? 'active'
              : highInactive
                ? 'inactive'
                : activeClass
                  ? 'active'
                  : 'unknown';
          const confidence = evidenceConflict
            ? 'none'
            : highActive || highInactive
              ? 'high'
              : activeClass
                ? 'low'
                : 'none';
          return {{
            state,
            confidence,
            selector: {selector_json},
            ariaPressed: root.getAttribute('aria-pressed') || '',
            ariaChecked: root.getAttribute('aria-checked') || '',
            dataSelected: root.getAttribute('data-selected') || '',
            dataE2eState,
            label: labels.slice(0, 300),
            classes,
            colors,
            activeStyle,
            attributeActive,
            attributeInactive,
            evidenceConflict
          }};
        }})()
        """
    ) or {"state": "unknown", "confidence": "none", "selector": selector}


def _wait_for_active_action(
    page,
    selector: str,
    active_texts: tuple[str, ...] = (),
    active_style_tokens: tuple[str, ...] = (),
    active_state_tokens: tuple[str, ...] = (),
    inactive_state_tokens: tuple[str, ...] = (),
    *,
    timeout_seconds: float = ACTION_STATE_TIMEOUT,
) -> dict:
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    state = _read_action_state_with_styles(
        page,
        selector,
        active_texts,
        active_style_tokens,
        active_state_tokens,
        inactive_state_tokens,
    )
    while time.monotonic() < deadline:
        if state.get("state") == "active" and state.get("confidence") == "high":
            return state
        remaining = deadline - time.monotonic()
        time.sleep(min(ACTION_STATE_INTERVAL, max(0.0, remaining)))
        state = _read_action_state_with_styles(
            page,
            selector,
            active_texts,
            active_style_tokens,
            active_state_tokens,
            inactive_state_tokens,
        )
    return state


def _ensure_action_active(
    page,
    selector: str,
    active_texts: tuple[str, ...] = (),
    active_style_tokens: tuple[str, ...] = (),
    active_state_tokens: tuple[str, ...] = (),
    inactive_state_tokens: tuple[str, ...] = (),
) -> dict:
    before = _read_action_state_with_styles(
        page,
        selector,
        active_texts,
        active_style_tokens,
        active_state_tokens,
        inactive_state_tokens,
    )
    if before.get("state") == "active" and before.get("confidence") == "high":
        return {
            "success": True,
            "clicked": False,
            "state": "active",
            "state_verified": True,
            "before": before,
            "after": before,
        }
    if before.get("state") != "inactive" or before.get("confidence") != "high":
        return {
            "success": False,
            "clicked": False,
            "state": before.get("state", "unknown"),
            "state_verified": False,
            "blocked_reason": "interaction_state_unverified",
            "before": before,
            "after": before,
        }
    clicked = page.click(selector)
    if not clicked:
        return {
            "success": False,
            "clicked": False,
            "state": "unknown",
            "state_verified": False,
            "before": before,
            "after": {"state": "unknown", "confidence": "none"},
        }
    after = _wait_for_active_action(
        page,
        selector,
        active_texts,
        active_style_tokens,
        active_state_tokens,
        inactive_state_tokens,
    )
    return {
        "success": True,
        "clicked": True,
        "state": after.get("state", "unknown"),
        "state_verified": after.get("state") == "active"
        and after.get("confidence") == "high",
        "before": before,
        "after": after,
    }


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


def _prepare_comment(
    page, comment: str, adapter: PlatformAdapter | None = None
) -> dict:
    adapter = resolve_adapter(adapter)
    selectors = json.dumps(
        list(adapter.selectors.comment_input_selectors), ensure_ascii=False
    )
    comment_json = json.dumps(comment, ensure_ascii=False)
    probe_script = f"""
            (() => {{
              const selectors = {selectors};
              const text = {comment_json};
              const visible = el => {{
                if (!el || !(el.offsetWidth || el.offsetHeight || el.getClientRects().length)) return false;
                const style = getComputedStyle(el);
                return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) > 0;
              }};
              const normalize = value => String(value || '')
                .replace(/\u00a0/g, ' ')
                .replace(/\\r\\n/g, '\\n')
                .trim();
              const commentish = el => {{
                const parts = [];
                let node = el;
                for (let depth = 0; node && depth < 7; depth += 1, node = node.parentElement) {{
                  parts.push([
                    node.getAttribute?.('placeholder') || '',
                    node.getAttribute?.('aria-label') || '',
                    node.getAttribute?.('data-placeholder') || '',
                    node.getAttribute?.('data-e2e') || '',
                    String(node.className || ''),
                    depth <= 2 ? (node.innerText || '') : ''
                  ].join(' '));
                }}
                return /评论|comment/i.test(parts.join(' '));
              }};
              const findInput = () => {{
                for (const selector of selectors) {{
                  for (const el of document.querySelectorAll(selector)) {{
                    const generic = selector === '[contenteditable="true"]'
                      || selector === '[role="textbox"]'
                      || selector === '[role="combobox"]';
                    if (visible(el) && !el.disabled && el.getAttribute('aria-disabled') !== 'true' && (!generic || commentish(el))) return el;
                  }}
                }}
                return null;
              }};
              const input = findInput();
              if (!input) {{
                const candidates = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"], [role="textbox"]'))
                  .slice(0, 20)
                  .map(el => ({{
                    tag: el.tagName,
                    placeholder: el.getAttribute('placeholder') || '',
                    ariaLabel: el.getAttribute('aria-label') || '',
                    dataPlaceholder: el.getAttribute('data-placeholder') || '',
                    role: el.getAttribute('role') || '',
                    contentEditable: el.getAttribute('contenteditable') || '',
                    visible: visible(el),
                    className: String(el.className || '').slice(0, 160),
                    parentText: (el.parentElement?.innerText || '').trim().slice(0, 160)
                  }}));
                return {{ok:false, reason:'comment-input-not-found', candidates}};
              }}
              input.scrollIntoView({{block:'center'}});
              input.focus();
              const current = normalize(input.isContentEditable
                ? (input.innerText || input.textContent || '')
                : (input.value || ''));
              if (current === normalize(text)) {{
                return {{ok:true, current:current.slice(0, 500), inputFound:true}};
              }}
              if (current) {{
                return {{
                  ok:false,
                  reason:'comment-input-not-empty',
                  current:current.slice(0, 500),
                  inputFound:true
                }};
              }}
              return {{
                ok:false,
                reason:'comment-text-missing',
                current:'',
                inputFound:true,
                editor:input.isContentEditable ? 'contenteditable' : input.tagName.toLowerCase()
              }};
            }})()
            """

    prepared = page.evaluate(probe_script) or {
        "ok": False,
        "reason": "evaluate-failed",
    }
    if prepared.get("ok") or prepared.get("reason") != "comment-text-missing":
        return prepared

    insert_text = getattr(page, "insert_text", None)
    if not callable(insert_text) or not bool(insert_text(comment)):
        return {
            **prepared,
            "ok": False,
            "reason": "comment-native-input-failed",
        }

    verified = prepared
    for _ in range(10):
        time.sleep(0.2)
        verified = page.evaluate(probe_script) or {
            "ok": False,
            "reason": "evaluate-failed",
        }
        if verified.get("ok"):
            return {**verified, "nativeInput": True}
        if verified.get("reason") == "comment-input-not-empty":
            break
    return {
        **verified,
        "ok": False,
        "reason": "comment-text-not-applied",
        "nativeInput": True,
    }


def _open_comment_composer(page, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    action_selectors = json.dumps(
        list(adapter.selectors.comment_action_selectors), ensure_ascii=False
    )
    action_texts = json.dumps(
        list(adapter.selectors.comment_composer_texts), ensure_ascii=False
    )
    return page.evaluate(
        f"""
            (() => {{
              const actionSelectors = {action_selectors};
              const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
              for (const selector of actionSelectors) {{
                const target = Array.from(document.querySelectorAll(selector))
                  .find(el => visible(el) && !el.disabled && el.getAttribute('aria-disabled') !== 'true');
                if (target) {{
                  target.scrollIntoView({{block:'center'}});
                  const rect = target.getBoundingClientRect();
                  const hit = document.elementFromPoint(
                    rect.left + rect.width / 2,
                    rect.top + rect.height / 2
                  ) || target;
                  hit.click();
                  return {{
                    ok:true,
                    text:(target.innerText || target.getAttribute('aria-label') || '').trim(),
                    selector,
                    hitClass:String(hit.className || '').slice(0, 160)
                  }};
                }}
              }}
              const wanted = {action_texts};
              const candidates = Array.from(document.querySelectorAll('button, [role="button"], a, div, span'))
                .filter(el => visible(el) && !el.disabled && el.getAttribute('aria-disabled') !== 'true')
                .map(el => ({{el, label:(el.innerText || el.getAttribute('aria-label') || '').trim()}}))
                .filter(item => item.label.length <= 40 && wanted.some(text => item.label === text || item.label.includes(text)));
              const rank = label => {{
                const exact = wanted.indexOf(label);
                return exact >= 0 ? exact : 100 + wanted.findIndex(text => label.includes(text));
              }};
              const depth = el => {{
                let value = 0;
                for (let node = el; node; node = node.parentElement) value += 1;
                return value;
              }};
              const target = candidates.sort((a, b) =>
                rank(a.label) - rank(b.label)
                  || a.label.length - b.label.length
                  || depth(b.el) - depth(a.el)
              )[0]?.el;
              if (!target) return {{ok:false, reason:'comment-action-not-found'}};
              target.scrollIntoView({{block:'center'}});
              const rect = target.getBoundingClientRect();
              const hit = document.elementFromPoint(
                rect.left + rect.width / 2,
                rect.top + rect.height / 2
              ) || target;
              hit.click();
              return {{
                ok:true,
                text:(target.innerText || target.getAttribute('aria-label') || '').trim(),
                hitClass:String(hit.className || '').slice(0, 160)
              }};
            }})()
            """
    ) or {"ok": False, "reason": "evaluate-failed"}


def _submit_comment(page, comment: str, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    input_selectors = json.dumps(
        list(adapter.selectors.comment_input_selectors), ensure_ascii=False
    )
    submit_selectors = json.dumps(
        list(adapter.selectors.comment_submit_selectors), ensure_ascii=False
    )
    submit_texts = json.dumps(
        list(adapter.selectors.comment_submit_texts), ensure_ascii=False
    )
    comment_json = json.dumps(comment, ensure_ascii=False)
    return page.evaluate(
        f"""
            (() => {{
              const inputSelectors = {input_selectors};
              const submitSelectors = {submit_selectors};
              const submitTexts = {submit_texts};
              const text = {comment_json};
              const visible = el => {{
                if (!el || !(el.offsetWidth || el.offsetHeight || el.getClientRects().length)) return false;
                const style = getComputedStyle(el);
                return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) > 0;
              }};
              const commentish = el => {{
                const parts = [];
                let node = el;
                for (let depth = 0; node && depth < 7; depth += 1, node = node.parentElement) {{
                  parts.push([
                    node.getAttribute?.('placeholder') || '',
                    node.getAttribute?.('aria-label') || '',
                    node.getAttribute?.('data-placeholder') || '',
                    node.getAttribute?.('data-e2e') || '',
                    String(node.className || ''),
                    depth <= 2 ? (node.innerText || '') : ''
                  ].join(' '));
                }}
                return /评论|comment/i.test(parts.join(' '));
              }};
              const findInput = () => {{
                for (const selector of inputSelectors) {{
                  for (const el of document.querySelectorAll(selector)) {{
                    const generic = selector === '[contenteditable="true"]'
                      || selector === '[role="textbox"]'
                      || selector === '[role="combobox"]';
                    if (visible(el) && !el.disabled && el.getAttribute('aria-disabled') !== 'true' && (!generic || commentish(el))) return el;
                  }}
                }}
                return null;
              }};
              const input = findInput();
              if (!input) return {{ok:false, reason:'comment-input-not-found'}};
              const current = input.isContentEditable
                ? (input.innerText || input.textContent || '')
                : (input.value || '');
              if (current !== text) return {{ok:false, reason:'comment-text-not-present'}};
              const candidates = [];
              const seen = new Set();
              let root = input;
              for (let depth = 0; root && depth < 7; depth += 1, root = root.parentElement) {{
                for (const selector of submitSelectors) {{
                  for (const el of root.querySelectorAll(selector)) {{
                    if (!seen.has(el)) {{ seen.add(el); candidates.push(el); }}
                  }}
                }}
                for (const el of root.querySelectorAll('button, [role="button"], input[type="submit"]')) {{
                  if (!seen.has(el)) {{ seen.add(el); candidates.push(el); }}
                }}
              }}
              const target = candidates.find(el => {{
                if (!visible(el) || el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
                const style = getComputedStyle(el);
                if (style.pointerEvents === 'none' || Number(style.opacity || 1) < 0.5) return false;
                if (submitSelectors.some(selector => el.matches(selector))) return true;
                const label = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
                return submitTexts.some(wanted => label === wanted || label.includes(wanted));
              }});
              if (!target) return {{ok:false, reason:'comment-submit-not-found'}};
              target.scrollIntoView({{block:'center'}});
              target.click();
              return {{
                ok:true,
                text:(target.innerText || target.value || target.getAttribute('aria-label') || '').trim(),
                selector:submitSelectors.find(selector => target.matches(selector)) || '',
                className:String(target.className || '').slice(0, 160)
              }};
            }})()
            """
    ) or {"ok": False, "reason": "evaluate-failed"}


def _comment_match_count(
    page, comment: str, adapter: PlatformAdapter | None = None
) -> int:
    adapter = resolve_adapter(adapter)
    item_selectors = json.dumps(
        list(adapter.selectors.comment_item_selectors), ensure_ascii=False
    )
    comment_json = json.dumps(comment, ensure_ascii=False)
    result = page.evaluate(
        f"""
            (() => {{
              const itemSelectors = {item_selectors};
              const text = {comment_json};
              const normalize = value => String(value || '').replace(/\\s+/g, ' ').trim();
              const wanted = normalize(text);
              const items = new Set();
              for (const selector of itemSelectors) {{
                for (const el of document.querySelectorAll(selector)) items.add(el);
              }}
              return Array.from(items).filter(el =>
                wanted && normalize(el.innerText || el.textContent || '').includes(wanted)
              ).length;
            }})()
            """
    )
    return max(0, int(result or 0))


def _comment_is_visible(
    page,
    comment: str,
    adapter: PlatformAdapter | None = None,
    *,
    previous_count: int = 0,
) -> bool:
    return _comment_match_count(page, comment, adapter=adapter) > previous_count


def like_video(page, video_id: str, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    opened = _open_detail(page, video_id, adapter=adapter)
    if not opened.get("success"):
        return opened
    selector = _first_clickable(page, adapter.selectors.like_button_selectors)
    content_id, _kind = adapter.parse_content_ref(video_id)
    meta = {
        "video_id": content_id,
        "action": "like",
        "page_kind": opened.get("kind"),
        "url": opened.get("href"),
    }
    interaction = (
        _ensure_action_active(
            page,
            selector,
            adapter.selectors.like_active_texts,
            adapter.selectors.like_active_style_tokens,
            adapter.selectors.like_active_state_tokens,
            adapter.selectors.like_inactive_state_tokens,
        )
        if selector
        else None
    )
    if interaction and interaction.get("success"):
        confirmed = bool(interaction.get("state_verified"))
        already_active = not bool(interaction.get("clicked"))
        return {
            "success": True,
            **meta,
            "selector": selector,
            "clicked": interaction.get("clicked", True),
            "state": "already_active"
            if already_active
            else interaction.get("state", "unknown"),
            "state_verified": interaction.get("state_verified", False),
            "detail": interaction,
            "message": (
                "点赞状态已确认，未重复点击。"
                if confirmed and already_active
                else "已点击点赞并确认状态已激活。"
                if confirmed
                else "已点击点赞按钮，但最终状态未确认；不要自动重复点击。"
            ),
        }
    if interaction and interaction.get("blocked_reason"):
        return {
            "success": False,
            **meta,
            "selector": selector,
            "clicked": False,
            "state": interaction.get("state", "unknown"),
            "state_verified": False,
            "blocked_reason": interaction.get("blocked_reason"),
            "detail": interaction,
            "error": "点赞状态无法可靠判定，未执行点击",
            "message": "点赞状态证据不足，已安全停止且未点击按钮。",
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
    return {
        "success": False,
        **meta,
        "selector": selector or "",
        "clicked": False,
        "state": interaction.get("state", "missing") if interaction else "missing",
        "state_verified": False,
        "detail": interaction,
        "error": "点赞按钮不可用" if selector else "未找到点赞按钮",
    }


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
    selector = _first_clickable(page, adapter.selectors.favorite_button_selectors)
    interaction = (
        _ensure_action_active(
            page,
            selector,
            adapter.selectors.favorite_active_texts,
            adapter.selectors.favorite_active_style_tokens,
            adapter.selectors.favorite_active_state_tokens,
            adapter.selectors.favorite_inactive_state_tokens,
        )
        if selector
        else None
    )
    if interaction and interaction.get("success"):
        confirmed = bool(interaction.get("state_verified"))
        already_active = not bool(interaction.get("clicked"))
        return {
            "success": True,
            "video_id": content_id,
            "action": "favorite",
            "page_kind": opened.get("kind"),
            "url": opened.get("href"),
            "selector": selector,
            "clicked": interaction.get("clicked", True),
            "state": "already_active"
            if already_active
            else interaction.get("state", "unknown"),
            "state_verified": interaction.get("state_verified", False),
            "detail": interaction,
            "message": "收藏状态已确认，未重复点击。"
            if confirmed and already_active
            else "已点击收藏并确认状态已激活。"
            if confirmed
            else "已点击收藏按钮，但最终状态未确认；不要自动重复点击。",
        }
    if interaction and interaction.get("blocked_reason"):
        return {
            "success": False,
            "video_id": content_id,
            "action": "favorite",
            "page_kind": opened.get("kind"),
            "url": opened.get("href"),
            "selector": selector,
            "clicked": False,
            "state": interaction.get("state", "unknown"),
            "state_verified": False,
            "blocked_reason": interaction.get("blocked_reason"),
            "detail": interaction,
            "error": "收藏状态无法可靠判定，未执行点击",
            "message": "收藏状态证据不足，已安全停止且未点击按钮。",
        }
    return {
        "success": False,
        "video_id": content_id,
        "action": "favorite",
        "page_kind": opened.get("kind"),
        "url": opened.get("href"),
        "selector": selector or "",
        "clicked": False,
        "state": interaction.get("state", "missing") if interaction else "missing",
        "state_verified": False,
        "detail": interaction,
        "error": "收藏按钮不可用" if selector else "未找到收藏按钮",
        "message": "收藏按钮不可用。" if selector else "未找到收藏按钮。",
    }


def get_interaction_state(
    page, video_id: str, adapter: PlatformAdapter | None = None
) -> dict:
    """Read like/favorite state without clicking either toggle."""
    adapter = resolve_adapter(adapter)
    opened = _open_detail(page, video_id, adapter=adapter)
    if not opened.get("success"):
        return opened
    content_id, _kind = adapter.parse_content_ref(video_id)
    if opened.get("kind") == "note":
        return {
            "success": True,
            "video_id": content_id,
            "page_kind": "note",
            "url": opened.get("href"),
            "states": {
                "like": {"state": "unknown", "state_verified": False},
                "favorite": {"state": "unknown", "state_verified": False},
            },
            "message": "图文操作栏未提供可稳定读取的点赞/收藏状态。",
        }
    actions = {
        "like": (
            adapter.selectors.like_button_selectors,
            adapter.selectors.like_active_texts,
            adapter.selectors.like_active_style_tokens,
            adapter.selectors.like_active_state_tokens,
            adapter.selectors.like_inactive_state_tokens,
        ),
        "favorite": (
            adapter.selectors.favorite_button_selectors,
            adapter.selectors.favorite_active_texts,
            adapter.selectors.favorite_active_style_tokens,
            adapter.selectors.favorite_active_state_tokens,
            adapter.selectors.favorite_inactive_state_tokens,
        ),
    }
    states = {}
    for name, (
        selectors,
        active_texts,
        active_style_tokens,
        active_state_tokens,
        inactive_state_tokens,
    ) in actions.items():
        selector = _first_clickable(page, selectors)
        snapshot = (
            _read_action_state_with_styles(
                page,
                selector,
                active_texts,
                active_style_tokens,
                active_state_tokens,
                inactive_state_tokens,
            )
            if selector
            else {"state": "missing", "confidence": "none"}
        )
        states[name] = {
            "selector": selector or "",
            **snapshot,
            "state_verified": snapshot.get("state") in {"active", "inactive"}
            and snapshot.get("confidence") == "high",
        }
    return {
        "success": True,
        "video_id": content_id,
        "page_kind": opened.get("kind"),
        "url": opened.get("href"),
        "states": states,
        "message": "已读取点赞/收藏当前状态，未执行点击。",
    }


def comment_video(
    page,
    video_id: str,
    comment: str,
    adapter: PlatformAdapter | None = None,
) -> dict:
    adapter = resolve_adapter(adapter)
    content_id, _kind = adapter.parse_content_ref(video_id)
    comment = str(comment or "").strip()
    meta = {
        "video_id": content_id,
        "action": "comment",
        "comment": comment,
    }
    if not comment:
        return {
            "success": False,
            **meta,
            "state": "invalid_comment",
            "state_verified": False,
            "error": "评论内容不能为空",
        }
    opened = _open_detail(page, video_id, adapter=adapter)
    if not opened.get("success"):
        return {**opened, **meta}
    result_base = {
        **meta,
        "page_kind": opened.get("kind"),
        "url": opened.get("href"),
    }
    prepared = _prepare_comment(page, comment, adapter=adapter)
    initial_prepared = prepared
    composer = None
    if not prepared.get("ok") and prepared.get("reason") == "comment-input-not-found":
        composer = _open_comment_composer(page, adapter=adapter)
        if composer.get("ok"):
            for _ in range(8):
                time.sleep(0.5)
                prepared = _prepare_comment(page, comment, adapter=adapter)
                if prepared.get("ok") or prepared.get("reason") not in {
                    "comment-input-not-found",
                    "evaluate-failed",
                }:
                    break
    if not prepared.get("ok"):
        reason = prepared.get("reason") or "comment-input-not-found"
        if reason == "comment-input-not-empty":
            state = "comment_input_not_empty"
            message = "评论框中已有其他草稿，已保留原内容且未发送评论。"
        elif reason in {
            "comment-native-input-failed",
            "comment-text-not-applied",
        }:
            state = "comment_text_not_applied"
            message = "已找到评论框，但未能确认文本已由页面编辑器接收，未发送评论。"
        else:
            state = "comment_input_not_found"
            message = "未找到可用的评论输入框，未发送评论。"
        return {
            "success": False,
            **result_base,
            "state": state,
            "state_verified": False,
            "detail": {
                "initial": initial_prepared,
                "composer": composer,
                "retry": prepared if composer and composer.get("ok") else None,
            },
            "message": message,
        }
    time.sleep(0.5)
    previous_match_count = _comment_match_count(page, comment, adapter=adapter)
    submitted = _submit_comment(page, comment, adapter=adapter)
    if not submitted.get("ok"):
        return {
            "success": False,
            **result_base,
            "state": "comment_submit_not_found",
            "state_verified": False,
            "typed": True,
            "detail": submitted,
            "message": "已填写评论，但未找到可确认的发送控件，未发送评论。",
        }
    for _ in range(5):
        time.sleep(1)
        if _comment_is_visible(
            page,
            comment,
            adapter=adapter,
            previous_count=previous_match_count,
        ):
            return {
                "success": True,
                **result_base,
                "state": "comment_confirmed",
                "state_verified": True,
                "typed": True,
                "detail": {
                    **submitted,
                    "previous_match_count": previous_match_count,
                },
                "message": "评论已发送并在评论区出现。",
            }
    return {
        "success": True,
        **result_base,
        "state": "comment_clicked_unconfirmed",
        "state_verified": False,
        "typed": True,
        "detail": {
            **submitted,
            "previous_match_count": previous_match_count,
        },
        "message": "已点击评论发送控件，但未稳定确认评论已出现在评论区；不要自动重试。",
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
