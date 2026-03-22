from __future__ import annotations

import time
from pathlib import Path

from .login import RISK_PAGE_KEYWORDS, RISK_STRONG_HINTS

IMAGE_UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload?default-tab=3"


def _wait_until(page, fn: str, timeout: float = 30.0, interval: float = 0.5):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = page.evaluate(fn)
        if last:
            return last
        time.sleep(interval)
    return last


def _js_quote(text: str) -> str:
    return repr(text)


def _page_snapshot(page) -> dict:
    return page.evaluate(
        """
        (() => ({
          href: location.href || '',
          title: document.title || '',
          text: (document.body?.innerText || '').slice(0, 3000)
        }))()
        """
    ) or {}


def _risk_result(page, message: str) -> dict | None:
    state = _page_snapshot(page)
    title = state.get('title', '') or ''
    text = state.get('text', '') or ''
    risk = any(k in title or k in text for k in (RISK_PAGE_KEYWORDS + RISK_STRONG_HINTS))
    if not risk:
        return None
    return {
        'success': False,
        'risk_page': True,
        'message': message,
        'page_title': title,
        'page': state,
    }


def _fill_title_and_desc(page, title: str, desc: str) -> dict:
    title = (title or "").strip()
    return page.evaluate(
        f"""
        (() => {{
          const titleText = {_js_quote(title)};
          const bodyText = {_js_quote(desc)};
          const titleInput = document.querySelector('input[placeholder="添加作品标题"]');
          const editor = document.querySelector('[data-slate-editor="true"]')
            || document.querySelector('.editor-kit-container')
            || document.querySelector('[contenteditable="true"]')
            || document.querySelector('div[role="textbox"]');
          if (!titleInput) return {{ success: false, reason: 'no-title-input' }};
          if (!editor) return {{ success: false, reason: 'no-editor' }};

          const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
          titleInput.scrollIntoView({{ block: 'center' }});
          titleInput.focus();
          if (nativeSetter) nativeSetter.call(titleInput, titleText);
          else titleInput.value = titleText;
          titleInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
          titleInput.dispatchEvent(new Event('change', {{ bubbles: true }}));

          editor.scrollIntoView({{ block: 'center' }});
          editor.focus();
          if (document.execCommand) {{
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
            document.execCommand('insertText', false, bodyText);
          }} else if (editor.isContentEditable) {{
            editor.textContent = bodyText;
          }} else if ('value' in editor) {{
            editor.value = bodyText;
          }} else {{
            editor.textContent = bodyText;
          }}
          editor.dispatchEvent(new InputEvent('input', {{ bubbles: true, inputType: 'insertText', data: bodyText }}));
          editor.dispatchEvent(new Event('change', {{ bubbles: true }}));

          const titleValue = titleInput.value || '';
          const editorText = (editor.innerText || editor.textContent || '').trim();
          return {{
            success: !!titleValue && !!editorText,
            titleValue,
            editorText: editorText.slice(0, 1000),
          }};
        }})()
        """
    )


def fill_publish_image(page, images: list[str], desc: str, title: str = "") -> dict:
    page.navigate(IMAGE_UPLOAD_URL)
    page.wait_for_load(30)

    risk = _risk_result(page, "当前处于验证码/风控页，无法继续填写图文发布表单。")
    if risk:
        return risk

    ok = _wait_until(page, """(() => !!document.querySelector('input[type="file"]'))()""", timeout=20)
    if not ok:
        risk = _risk_result(page, "当前处于验证码/风控页，无法继续填写图文发布表单。")
        if risk:
            return risk
        return {"success": False, "message": "未找到图文上传输入框。"}

    image_paths = [str(Path(x).resolve()) for x in images]
    if not page.set_files('input[type="file"]', image_paths):
        return {"success": False, "message": "图片上传失败。"}

    editor_ready = _wait_until(
        page,
        """
        (() => {
          const hasTitle = !!document.querySelector('input[placeholder="添加作品标题"]');
          const hasEditor = !!document.querySelector('[data-slate-editor="true"], .editor-kit-container, [contenteditable="true"], div[role="textbox"]');
          return hasTitle && hasEditor;
        })()
        """,
        timeout=60,
        interval=1,
    )
    if not editor_ready:
        return {"success": False, "message": "图片已上传，但未等到标题/正文输入区域出现。"}

    fill_result = _fill_title_and_desc(page, title, desc)
    state = page.evaluate(
        """
        (() => ({
          href: location.href,
          title: document.title,
          text: (document.body?.innerText || '').slice(0, 2500),
          titleValue: document.querySelector('input[placeholder="添加作品标题"]')?.value || '',
          editorText: (document.querySelector('[data-slate-editor="true"],.editor-kit-container,[contenteditable="true"],div[role="textbox"]')?.innerText || '').slice(0, 1200)
        }))()
        """
    )
    success = bool(fill_result and fill_result.get("success") and state.get("titleValue") and desc.splitlines()[0] in state.get("editorText", ""))
    return {
        "success": success,
        "status": "filled" if success else "partial",
        "images": image_paths,
        "title": title,
        "desc": desc,
        "fill": fill_result,
        "page": state,
        "message": "图文发布表单已填写，请在浏览器中确认后再执行 click-publish。" if success else "图片已上传，但标题或正文填写失败。",
    }


def select_music(page, preferred: list[str] | None = None) -> dict:
    preferred = [x.strip() for x in (preferred or []) if x and x.strip()]
    if not preferred:
        preferred = [
            "此刻最好的都在身边 (R&B氛围版)",
            "why u(氛围版)",
            "Cloud Rest（春天）",
            "Ambition (凌云志)",
        ]

    opened = page.click('span.action-Q1y01k') or page.click('.container-right-uW7Pj1') or page.click('.container-JngpiB')
    if not opened:
        risk = _risk_result(page, "当前处于验证码/风控页，无法打开音乐面板。")
        if risk:
            return risk
        return {"success": False, "message": "未找到音乐选择入口。"}

    panel_ready = _wait_until(
        page,
        """
        (() => !!Array.from(document.querySelectorAll('.semi-portal')).find(el => {
          const text = el.innerText || '';
          return text.includes('选择音乐') && text.includes('热门榜');
        }))()
        """,
        timeout=15,
        interval=0.5,
    )
    if not panel_ready:
        risk = _risk_result(page, "当前处于验证码/风控页，无法打开音乐面板。")
        if risk:
            return risk
        return {"success": False, "message": "音乐面板未成功打开。"}

    picked = None
    for name in preferred:
        result = page.evaluate(
            f"""
            (() => {{
              const portal = Array.from(document.querySelectorAll('.semi-portal')).find(el => {{
                const text = el.innerText || '';
                return text.includes('选择音乐') && text.includes('热门榜');
              }});
              if (!portal) return {{ success: false, reason: 'no-portal' }};
              const node = Array.from(portal.querySelectorAll('.song-name-oRge4d')).find(el => (el.innerText || '').trim() === {_js_quote(name)});
              if (!node) return {{ success: false, reason: 'no-song' }};
              let row = node;
              for (let i = 0; i < 8 && row; i++) {{
                if (row.querySelector && row.querySelector('button.apply-btn-LUPP0D')) break;
                row = row.parentElement;
              }}
              const btn = row && row.querySelector ? row.querySelector('button.apply-btn-LUPP0D') : null;
              if (!btn) return {{ success: false, reason: 'no-use-button' }};
              btn.click();
              return {{ success: true, picked: {_js_quote(name)} }};
            }})()
            """
        )
        if result and result.get("success"):
            picked = name
            break

    if not picked:
        fallback = page.evaluate(
            """
            (() => {
              const portal = Array.from(document.querySelectorAll('.semi-portal')).find(el => {
                const text = el.innerText || '';
                return text.includes('选择音乐') && text.includes('热门榜');
              });
              if (!portal) return { success: false, reason: 'no-portal' };
              const btn = portal.querySelector('button.apply-btn-LUPP0D');
              if (!btn) return { success: false, reason: 'no-apply-button' };
              const rowText = (btn.parentElement?.innerText || btn.closest('[class]')?.innerText || '').trim();
              btn.click();
              return { success: true, picked: rowText.split('\n')[0] || '热门榜首个可用音乐' };
            })()
            """
        )
        if fallback and fallback.get("success"):
            picked = fallback.get("picked") or '热门榜首个可用音乐'
        else:
            return {"success": False, "message": "音乐面板已打开，但未找到可用目标音乐。", "preferred": preferred}

    applied = _wait_until(
        page,
        f"""
        (() => {{
          const body = document.body?.innerText || '';
          return body.includes({_js_quote(picked)}) && body.includes('修改音乐');
        }})()
        """,
        timeout=15,
        interval=0.5,
    )
    if not applied:
        return {"success": False, "message": "已点击使用，但页面未确认音乐已应用。", "picked": picked}

    state = page.evaluate(
        """
        (() => ({
          text: (document.body?.innerText || '').slice(0, 2500)
        }))()
        """
    )
    return {"success": True, "picked": picked, "page": state}


def validate_publish_state(page, require_topic: bool = False) -> dict:
    script = f"""
    (() => {{
      const body = (document.body && document.body.innerText) || '';
      const titleEl = document.querySelector('input[placeholder="添加作品标题"]');
      const editorEl = document.querySelector('[data-slate-editor="true"], .editor-kit-container, [contenteditable="true"], div[role="textbox"]');
      const title = titleEl ? ((titleEl.value || '').trim()) : '';
      const editorText = editorEl ? (((editorEl.innerText || editorEl.textContent || '')).trim()) : '';
      const hasImage = body.includes('继续添加') || body.includes('编辑图片') || body.includes('已添加4张图片') || body.includes('已添加1张图片') || body.includes('取消上传');
      const hasMusic = body.includes('修改音乐');
      const hasTopic = body.includes('已关联热点') || body.includes('修改热点') || body.includes('关联热点\n#') || body.includes('关联热点\n话题');
      const errors = [];
      if (!hasImage) errors.push('缺少图片');
      if (!title) errors.push('标题为空');
      if (!editorText) errors.push('正文为空');
      if (!hasMusic) errors.push('未选择音乐');
      if ({'true' if require_topic else 'false'} && !hasTopic) errors.push('未关联热点');
      return {{
        success: errors.length === 0,
        requireTopic: {'true' if require_topic else 'false'},
        title: title,
        editorText: editorText.slice(0, 1000),
        hasImage: hasImage,
        hasMusic: hasMusic,
        hasTopic: hasTopic,
        errors: errors,
        text: body.slice(0, 2500)
      }};
    }})()
    """
    state = page.evaluate(script)
    if state:
        return state
    risk = _risk_result(page, "当前处于验证码/风控页，无法读取发布页状态。")
    if risk:
        return risk
    return {"success": False, "errors": ["无法读取发布页状态"]}


def click_publish(page, require_topic: bool = False) -> dict:
    check = validate_publish_state(page, require_topic=require_topic)
    if check.get("risk_page"):
        return check
    allow_fallback_click = check.get("errors") == ["无法读取发布页状态"]
    if not check.get("success") and not allow_fallback_click:
        return {
            "success": False,
            "message": "发布前校验失败",
            "validation": check,
        }

    result = page.evaluate(
        """
        (() => {
          const body = (document.body && document.body.innerText) || '';
          const buttons = Array.from(document.querySelectorAll('button'));
          const btn = buttons.find(el => (el.innerText || '').trim() === '发布');
          if (!btn) return { success: false, message: '未找到底部发布按钮', body: body.slice(0, 2500) };
          btn.scrollIntoView({ block: 'center' });
          btn.click();
          return {
            success: true,
            text: (btn.innerText || '').trim(),
            className: btn.className || '',
            body: body.slice(0, 2500)
          };
        })()
        """
    )
    if result:
        result["validation"] = check
        if allow_fallback_click:
            result["fallback"] = True
    return result or {"success": False, "message": "点击发布失败", "validation": check}
