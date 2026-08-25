from __future__ import annotations

import json
import time
from pathlib import Path

from platform_adapter import PlatformAdapter, resolve_adapter

from .page_states import (
    classify_publish_outcome,
    classify_publish_snapshot,
    classify_video_publish_snapshot,
)

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_VIDEO_SUFFIXES = {
    ".avi",
    ".flv",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg4",
    ".mpg",
    ".ts",
    ".webm",
    ".wmv",
}


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
    return json.dumps(text, ensure_ascii=False)


def _resolve_image_paths(images: list[str]) -> list[str]:
    if not images:
        raise ValueError("至少需要一张图片")
    resolved: list[str] = []
    for raw_path in images:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            raise ValueError(f"图片路径必须是绝对路径：{raw_path}")
        try:
            path = path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(f"图片不存在：{raw_path}") from exc
        if not path.is_file():
            raise ValueError(f"图片路径不是文件：{raw_path}")
        if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
            supported = ", ".join(sorted(SUPPORTED_IMAGE_SUFFIXES))
            raise ValueError(
                f"不支持的图片格式：{path.suffix or '无扩展名'}；支持 {supported}"
            )
        resolved.append(str(path))
    return resolved


def _resolve_video_path(video: str) -> str:
    raw_path = str(video or "").strip()
    if not raw_path:
        raise ValueError("视频路径不能为空")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ValueError(f"视频路径必须是绝对路径：{raw_path}")
    try:
        path = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"视频不存在：{raw_path}") from exc
    if not path.is_file():
        raise ValueError(f"视频路径不是文件：{raw_path}")
    if path.suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_VIDEO_SUFFIXES))
        raise ValueError(
            f"不支持的视频格式：{path.suffix or '无扩展名'}；支持 {supported}"
        )
    return str(path)


def _page_snapshot(page) -> dict:
    return (
        page.evaluate(
            """
        (() => ({
          href: location.href || '',
          title: document.title || '',
          text: (document.body?.innerText || '').slice(0, 3000)
        }))()
        """
        )
        or {}
    )


def _wrong_publish_page_result(
    page,
    adapter: PlatformAdapter,
    require_topic: bool = False,
    state: dict | None = None,
    publish_kind: str = "image",
) -> dict | None:
    state = state or _page_snapshot(page)
    if adapter.is_publish_url(state.get("href", "") or "", kind=publish_kind):
        return None
    label = "视频" if publish_kind == "video" else "图文"
    command = "fill-publish-video" if publish_kind == "video" else "fill-publish-image"
    return {
        "success": False,
        "requireTopic": bool(require_topic),
        "state": "wrong_page",
        "risk_page": False,
        "errors": [f"当前页面不是{label}发布页"],
        "message": f"当前页面不是{label}发布页，请先执行 {command}。",
        "page": state,
    }


def _risk_result(
    page, message: str, adapter: PlatformAdapter | None = None
) -> dict | None:
    adapter = resolve_adapter(adapter)
    state = _page_snapshot(page)
    title = state.get("title", "") or ""
    text = state.get("text", "") or ""
    risk = adapter.is_risk_page(title, text) or any(
        k in title or k in text for k in adapter.risk_strong_hints
    )
    if not risk:
        return None
    return {
        "success": False,
        "risk_page": True,
        "message": message,
        "page_title": title,
        "page": state,
    }


def _fill_title_and_desc(
    page,
    title: str,
    desc: str,
    adapter: PlatformAdapter | None = None,
    title_selector: str | None = None,
    editor_selectors: tuple[str, ...] | None = None,
) -> dict:
    adapter = resolve_adapter(adapter)
    title = (title or "").strip()
    title_selector = json.dumps(
        title_selector or adapter.selectors.publish_title_input_selector,
        ensure_ascii=False,
    )
    editor_selector = json.dumps(
        ",".join(editor_selectors or adapter.selectors.publish_editor_selectors),
        ensure_ascii=False,
    )
    return page.evaluate(
        f"""
        (() => {{
          const titleText = {_js_quote(title)};
          const bodyText = {_js_quote(desc)};
          const titleInput = document.querySelector({title_selector});
          const editor = document.querySelector({editor_selector});
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
          const normalize = value => String(value || '')
            .replace(/\u200b/g, '')
            .replace(/\\r\\n/g, '\\n')
            .trim();
          const titleMatches = normalize(titleValue) === normalize(titleText);
          const editorMatches = normalize(editorText) === normalize(bodyText);
          return {{
            success: titleMatches && editorMatches,
            titleValue,
            editorText: editorText.slice(0, 1000),
            titleMatches,
            editorMatches,
          }};
        }})()
        """
    )


def fill_publish_image(
    page,
    images: list[str],
    desc: str,
    title: str = "",
    adapter: PlatformAdapter | None = None,
) -> dict:
    adapter = resolve_adapter(adapter)
    title = (title or "").strip()
    desc = (desc or "").strip()
    if not title:
        return {"success": False, "message": "标题不能为空。"}
    if not desc:
        return {"success": False, "message": "正文不能为空。"}
    try:
        image_paths = _resolve_image_paths(images)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}

    adapter.navigate_publish_image(page)
    page.wait_for_load(30)

    risk = _risk_result(
        page, "当前处于验证码/风控页，无法继续填写图文发布表单。", adapter
    )
    if risk:
        return risk

    ok = _wait_until(
        page,
        f"""(() => !!document.querySelector({json.dumps(adapter.selectors.publish_file_input_selector)}))()""",
        timeout=20,
    )
    if not ok:
        risk = _risk_result(
            page, "当前处于验证码/风控页，无法继续填写图文发布表单。", adapter
        )
        if risk:
            return risk
        return {"success": False, "message": "未找到图文上传输入框。"}

    if not page.set_files(adapter.selectors.publish_file_input_selector, image_paths):
        return {"success": False, "message": "图片上传失败。"}

    editor_ready = _wait_until(
        page,
        """
        (() => {{
          const hasTitle = !!document.querySelector({});
          const hasEditor = !!document.querySelector({});
          return hasTitle && hasEditor;
        }})()
        """.format(
            json.dumps(
                adapter.selectors.publish_title_input_selector, ensure_ascii=False
            ),
            json.dumps(
                ",".join(adapter.selectors.publish_editor_selectors), ensure_ascii=False
            ),
        ),
        timeout=60,
        interval=1,
    )
    if not editor_ready:
        return {
            "success": False,
            "message": "图片已上传，但未等到标题/正文输入区域出现。",
        }

    fill_result = _fill_title_and_desc(page, title, desc, adapter=adapter)
    image_markers_json = json.dumps(
        list(adapter.selectors.publish_image_markers), ensure_ascii=False
    )
    upload_ready = _wait_until(
        page,
        f"""
        (() => {{
          const body = document.body?.innerText || '';
          const markers = {image_markers_json};
          const marker = markers.find(value => body.includes(value)) || '';
          return marker ? {{ ready: true, marker }} : null;
        }})()
        """,
        timeout=60,
        interval=1,
    )
    state = (
        page.evaluate(
            """
        (() => ({{
          href: location.href,
          title: document.title,
          text: (document.body?.innerText || '').slice(0, 2500),
          titleValue: document.querySelector({})?.value || '',
          editorText: (document.querySelector({})?.innerText || '').slice(0, 1200)
        }}))()
        """.format(
                json.dumps(
                    adapter.selectors.publish_title_input_selector, ensure_ascii=False
                ),
                json.dumps(
                    ",".join(adapter.selectors.publish_editor_selectors),
                    ensure_ascii=False,
                ),
            )
        )
        or {}
    )
    first_line = desc.splitlines()[0]
    success = bool(
        fill_result
        and fill_result.get("success")
        and upload_ready
        and state.get("titleValue")
        and state.get("titleValue") == title
        and first_line in state.get("editorText", "")
    )
    return {
        "success": success,
        "status": "filled" if success else "partial",
        "images": image_paths,
        "title": title,
        "desc": desc,
        "fill": fill_result,
        "upload": upload_ready
        or {"ready": False, "reason": "image-upload-not-confirmed"},
        "page": state,
        "message": "图文发布表单已填写，请在浏览器中确认后再执行 click-publish。"
        if success
        else "图文表单未完整确认：请检查图片上传状态，以及标题/正文是否被页面截断或改写。",
    }


def _video_publish_snapshot(page, adapter: PlatformAdapter) -> dict:
    title_selector = json.dumps(
        adapter.selectors.publish_video_title_input_selector, ensure_ascii=False
    )
    editor_selector = json.dumps(
        ",".join(adapter.selectors.publish_video_editor_selectors),
        ensure_ascii=False,
    )
    file_selector = json.dumps(
        adapter.selectors.publish_video_file_input_selector, ensure_ascii=False
    )
    preview_selector = json.dumps(
        ",".join(adapter.selectors.publish_video_preview_selectors),
        ensure_ascii=False,
    )
    ready_texts = json.dumps(
        list(adapter.selectors.publish_video_ready_texts), ensure_ascii=False
    )
    progress_selector = json.dumps(
        ",".join(adapter.selectors.publish_video_progress_selectors),
        ensure_ascii=False,
    )
    failure_texts = json.dumps(
        list(adapter.selectors.publish_video_failure_texts), ensure_ascii=False
    )
    cover_control_selector = json.dumps(
        adapter.selectors.publish_video_cover_control_selector,
        ensure_ascii=False,
    )
    empty_cover_text = json.dumps(
        adapter.selectors.publish_video_empty_cover_text, ensure_ascii=False
    )
    topic_markers = json.dumps(
        list(adapter.selectors.topic_markers), ensure_ascii=False
    )
    publish_button_text = json.dumps(
        adapter.selectors.publish_button_text, ensure_ascii=False
    )
    return (
        page.evaluate(
            f"""
            (() => {{
              const normalize = value => String(value || '')
                .replace(/\u200b/g, '')
                .replace(/\\r\\n/g, '\\n')
                .trim();
              const body = document.body?.innerText || '';
              const titleEl = document.querySelector({title_selector});
              const editorEl = document.querySelector({editor_selector});
              const fileInputs = Array.from(document.querySelectorAll({file_selector}));
              const fileCount = fileInputs.reduce(
                (count, input) => count + (input.files?.length || 0), 0
              );
              const previews = Array.from(document.querySelectorAll({preview_selector}));
              const preview = previews.find(el => /^https?:\/\//.test(el.currentSrc || el.src || ''));
              const exactLeafText = value => Array.from(document.querySelectorAll('body *')).some(el =>
                (el.innerText || '').trim() === value &&
                !Array.from(el.children).some(child => (child.innerText || '').trim() === value)
              );
              const hasReadyControl = {ready_texts}.some(exactLeafText);
              const progressFound = !!document.querySelector({progress_selector});
              const hasUploadFailure = {failure_texts}.some(exactLeafText);
              const hasVideo = !!preview || (hasReadyControl && !progressFound && !hasUploadFailure);
              const controls = Array.from(document.querySelectorAll({cover_control_selector}));
              const emptyCoverCount = controls.filter(el =>
                (el.innerText || '').split('\\n').map(x => x.trim()).includes({empty_cover_text})
              ).length;
              const publishButton = Array.from(document.querySelectorAll('button')).find(
                el => (el.innerText || '').trim() === {publish_button_text}
              );
              return {{
                href: location.href || '',
                page_title: document.title || '',
                title: normalize(titleEl?.value),
                editorText: normalize(editorEl?.innerText || editorEl?.textContent),
                fileCount,
                hasVideo,
                hasReadyControl,
                progressFound,
                hasUploadFailure,
                videoPreviewUrl: (preview?.currentSrc || preview?.src || '').slice(0, 500),
                uploadInProgress: !hasVideo && (fileCount > 0 || progressFound),
                coverControlCount: controls.length,
                emptyCoverCount,
                hasCover: controls.length > 0 && emptyCoverCount < controls.length,
                hasTopic: {topic_markers}.some(marker => body.includes(marker)),
                publishButtonFound: !!publishButton,
                publishButtonDisabled: !!publishButton && (
                  publishButton.disabled || publishButton.getAttribute('aria-disabled') === 'true'
                ),
                text: body.slice(0, 3500),
              }};
            }})()
            """
        )
        or {}
    )


def set_video_cover(
    page,
    cover: str,
    adapter: PlatformAdapter | None = None,
) -> dict:
    adapter = resolve_adapter(adapter)
    try:
        cover_path = _resolve_image_paths([cover])[0]
    except ValueError as exc:
        return {"success": False, "message": str(exc)}

    wrong_page = _wrong_publish_page_result(
        page, adapter, state=_page_snapshot(page), publish_kind="video"
    )
    if wrong_page:
        return wrong_page
    risk = _risk_result(page, "当前处于验证码/风控页，无法设置视频封面。", adapter)
    if risk:
        return risk

    opened = page.evaluate(
        f"""
        (() => {{
          const controls = Array.from(document.querySelectorAll({json.dumps(adapter.selectors.publish_video_cover_control_selector, ensure_ascii=False)}));
          const target = controls.find(control =>
            (control.innerText || '').split('\\n').map(x => x.trim()).includes({json.dumps(adapter.selectors.publish_video_empty_cover_text, ensure_ascii=False)})
          ) || controls[0];
          if (!target) return {{ success: false, reason: 'no-cover-control' }};
          const exact = Array.from(target.querySelectorAll('*')).find(el =>
            (el.innerText || '').trim() === {json.dumps(adapter.selectors.publish_video_empty_cover_text, ensure_ascii=False)} &&
            !Array.from(el.children).some(child => (child.innerText || '').trim() === {json.dumps(adapter.selectors.publish_video_empty_cover_text, ensure_ascii=False)})
          );
          (exact || target).click();
          return {{ success: true }};
        }})()
        """
    )
    if not isinstance(opened, dict) or not opened.get("success"):
        state = _video_publish_snapshot(page, adapter)
        return {
            "success": False,
            "message": "未找到视频封面设置入口。",
            "page": state,
        }

    dialog_markers = json.dumps(
        list(adapter.selectors.publish_video_cover_dialog_markers),
        ensure_ascii=False,
    )
    dialog_ready = _wait_until(
        page,
        f"""
        (() => {{
          const dialogs = Array.from(document.querySelectorAll('[role="dialog"]'));
          return dialogs.some(dialog => {dialog_markers}.every(marker =>
            (dialog.innerText || '').includes(marker)
          ));
        }})()
        """,
        timeout=20,
        interval=0.5,
    )
    if not dialog_ready:
        return {"success": False, "message": "视频封面编辑器未成功打开。"}

    upload_markers = json.dumps(
        list(adapter.selectors.publish_video_cover_upload_markers),
        ensure_ascii=False,
    )
    marked = page.evaluate(
        f"""
        (() => {{
          const dialog = Array.from(document.querySelectorAll('[role="dialog"]')).find(el =>
            {dialog_markers}.every(marker => (el.innerText || '').includes(marker))
          );
          if (!dialog) return {{ success: false, reason: 'no-cover-dialog' }};
          const input = Array.from(dialog.querySelectorAll('input[type="file"]')).find(el => {{
            let node = el.parentElement;
            for (let depth = 0; node && depth < 6; depth += 1, node = node.parentElement) {{
              const text = node.innerText || '';
              if ({upload_markers}.every(marker => text.includes(marker))) return true;
            }}
            return false;
          }});
          if (!input) return {{ success: false, reason: 'no-cover-file-input' }};
          input.setAttribute('data-douyin-skills-video-cover', 'true');
          return {{ success: true, accept: input.accept || '' }};
        }})()
        """
    )
    if not isinstance(marked, dict) or not marked.get("success"):
        return {
            "success": False,
            "message": "视频封面编辑器中未找到自定义封面上传输入框。",
            "detail": marked or {},
        }
    if not page.set_files('input[data-douyin-skills-video-cover="true"]', [cover_path]):
        return {"success": False, "message": "视频封面上传失败。"}

    cover_loaded = _wait_until(
        page,
        f"""
        (() => {{
          const dialog = Array.from(document.querySelectorAll('[role="dialog"]')).find(el =>
            {dialog_markers}.every(marker => (el.innerText || '').includes(marker))
          );
          if (!dialog) return null;
          const imageReady = Array.from(dialog.querySelectorAll('img')).some(img =>
            /^data:image\//.test(img.src || '')
          );
          const done = Array.from(dialog.querySelectorAll('button')).find(el =>
            (el.innerText || '').trim() === {json.dumps(adapter.selectors.publish_video_cover_done_text, ensure_ascii=False)} &&
            !el.disabled && el.getAttribute('aria-disabled') !== 'true'
          );
          return imageReady && done ? {{ ready: true }} : null;
        }})()
        """,
        timeout=30,
        interval=0.5,
    )
    if not cover_loaded:
        return {
            "success": False,
            "message": "封面文件已选择，但编辑器未确认图片加载完成。",
        }

    completed = page.evaluate(
        f"""
        (() => {{
          const dialog = Array.from(document.querySelectorAll('[role="dialog"]')).find(el =>
            {dialog_markers}.every(marker => (el.innerText || '').includes(marker))
          );
          const button = Array.from(dialog?.querySelectorAll('button') || []).find(el =>
            (el.innerText || '').trim() === {json.dumps(adapter.selectors.publish_video_cover_done_text, ensure_ascii=False)} &&
            !el.disabled && el.getAttribute('aria-disabled') !== 'true'
          );
          if (!button) return {{ success: false }};
          button.click();
          return {{ success: true }};
        }})()
        """
    )
    if not isinstance(completed, dict) or not completed.get("success"):
        return {"success": False, "message": "视频封面编辑器的完成按钮不可用。"}

    skip_text = json.dumps(
        adapter.selectors.publish_video_cover_skip_horizontal_text,
        ensure_ascii=False,
    )
    followup = _wait_until(
        page,
        f"""
        (() => {{
          const skip = Array.from(document.querySelectorAll('button,[role="button"]')).find(el =>
            (el.innerText || '').trim() === {skip_text} && !el.disabled
          );
          const controls = Array.from(document.querySelectorAll({json.dumps(adapter.selectors.publish_video_cover_control_selector, ensure_ascii=False)}));
          const emptyCount = controls.filter(control =>
            (control.innerText || '').split('\\n').map(x => x.trim()).includes({json.dumps(adapter.selectors.publish_video_empty_cover_text, ensure_ascii=False)})
          ).length;
          if (skip) return {{ state: 'needs-horizontal-decision' }};
          if (controls.length && emptyCount < controls.length) return {{ state: 'cover-applied' }};
          return null;
        }})()
        """,
        timeout=15,
        interval=0.5,
    )
    if (
        isinstance(followup, dict)
        and followup.get("state") == "needs-horizontal-decision"
    ):
        page.evaluate(
            f"""
            (() => {{
              const buttons = Array.from(document.querySelectorAll('button,[role="button"]'));
              const button = buttons.find(el =>
                (el.innerText || '').trim() === {skip_text} && !el.disabled
              );
              if (!button) return false;
              button.click();
              return true;
            }})()
            """
        )

    applied = _wait_until(
        page,
        f"""
        (() => {{
          const controls = Array.from(document.querySelectorAll({json.dumps(adapter.selectors.publish_video_cover_control_selector, ensure_ascii=False)}));
          if (!controls.length) return null;
          const emptyCount = controls.filter(control =>
            (control.innerText || '').split('\\n').map(x => x.trim()).includes({json.dumps(adapter.selectors.publish_video_empty_cover_text, ensure_ascii=False)})
          ).length;
          return emptyCount < controls.length ? {{ ready: true, emptyCount, controlCount: controls.length }} : null;
        }})()
        """,
        timeout=20,
        interval=0.5,
    )
    state = _video_publish_snapshot(page, adapter)
    return {
        "success": bool(applied and state.get("hasCover")),
        "status": "set" if applied and state.get("hasCover") else "unconfirmed",
        "cover": cover_path,
        "page": state,
        "message": "视频封面已设置。"
        if applied and state.get("hasCover")
        else "已完成封面编辑，但发布页未确认封面状态。",
    }


def fill_publish_video(
    page,
    video: str,
    desc: str,
    title: str,
    cover: str | None = None,
    adapter: PlatformAdapter | None = None,
) -> dict:
    adapter = resolve_adapter(adapter)
    title = (title or "").strip()
    desc = (desc or "").strip()
    if not title:
        return {"success": False, "message": "标题不能为空。"}
    if not desc:
        return {"success": False, "message": "作品简介不能为空。"}
    try:
        video_path = _resolve_video_path(video)
        cover_path = _resolve_image_paths([cover])[0] if cover else None
    except ValueError as exc:
        return {"success": False, "message": str(exc)}

    adapter.navigate_publish_video(page)
    page.wait_for_load(30)
    risk = _risk_result(
        page, "当前处于验证码/风控页，无法继续填写视频发布表单。", adapter
    )
    if risk:
        return risk

    file_ready = _wait_until(
        page,
        f"""(() => !!document.querySelector({json.dumps(adapter.selectors.publish_video_file_input_selector, ensure_ascii=False)}))()""",
        timeout=20,
    )
    if not file_ready:
        risk = _risk_result(
            page, "当前处于验证码/风控页，无法继续填写视频发布表单。", adapter
        )
        if risk:
            return risk
        return {"success": False, "message": "未找到视频上传输入框。"}
    if not page.set_files(
        adapter.selectors.publish_video_file_input_selector, [video_path]
    ):
        return {"success": False, "message": "视频上传失败。"}

    title_selector = adapter.selectors.publish_video_title_input_selector
    editor_selectors = adapter.selectors.publish_video_editor_selectors
    editor_ready = _wait_until(
        page,
        """
        (() => {{
          const hasTitle = !!document.querySelector({});
          const hasEditor = !!document.querySelector({});
          return hasTitle && hasEditor;
        }})()
        """.format(
            json.dumps(title_selector, ensure_ascii=False),
            json.dumps(",".join(editor_selectors), ensure_ascii=False),
        ),
        timeout=120,
        interval=1,
    )
    if not editor_ready:
        return {
            "success": False,
            "message": "视频已选择，但未等到标题/作品简介输入区域出现。",
            "page": _page_snapshot(page),
        }

    upload_ready = _wait_until(
        page,
        f"""
        (() => {{
          const previews = Array.from(document.querySelectorAll({json.dumps(",".join(adapter.selectors.publish_video_preview_selectors), ensure_ascii=False)}));
          const preview = previews.find(el => /^https?:\/\//.test(el.currentSrc || el.src || ''));
          const exactLeafText = value => Array.from(document.querySelectorAll('body *')).some(el =>
            (el.innerText || '').trim() === value &&
            !Array.from(el.children).some(child => (child.innerText || '').trim() === value)
          );
          const hasReadyControl = {json.dumps(list(adapter.selectors.publish_video_ready_texts), ensure_ascii=False)}.some(exactLeafText);
          const progressFound = !!document.querySelector({json.dumps(",".join(adapter.selectors.publish_video_progress_selectors), ensure_ascii=False)});
          const hasUploadFailure = {json.dumps(list(adapter.selectors.publish_video_failure_texts), ensure_ascii=False)}.some(exactLeafText);
          const ready = !!preview || (hasReadyControl && !progressFound && !hasUploadFailure);
          return ready ? {{
            ready: true,
            evidence: preview ? 'remote-preview' : 'reupload-control',
            previewUrl: (preview?.currentSrc || preview?.src || '').slice(0, 500)
          }} : null;
        }})()
        """,
        timeout=120,
        interval=1,
    )

    fill_result: dict = {}
    if upload_ready:
        for attempt in range(3):
            fill_result = _fill_title_and_desc(
                page,
                title,
                desc,
                adapter=adapter,
                title_selector=title_selector,
                editor_selectors=editor_selectors,
            )
            if fill_result and fill_result.get("success"):
                break
            if attempt < 2:
                time.sleep(1)

    cover_result = None
    if cover_path and upload_ready:
        cover_result = set_video_cover(page, cover_path, adapter=adapter)
    state = _video_publish_snapshot(page, adapter)
    fields_match = bool(
        fill_result
        and fill_result.get("success")
        and state.get("title") == title
        and state.get("editorText") == desc
    )
    cover_ok = bool(state.get("hasCover")) if cover_path else True
    success = bool(fields_match and upload_ready and state.get("hasVideo") and cover_ok)
    needs_cover = success and not state.get("hasCover")
    status = (
        "filled_needs_cover" if needs_cover else ("filled" if success else "partial")
    )
    return {
        "success": success,
        "status": status,
        "video": video_path,
        "cover": cover_path,
        "title": title,
        "desc": desc,
        "fill": fill_result,
        "upload": upload_ready
        or {"ready": False, "reason": "video-upload-not-confirmed"},
        "coverResult": cover_result,
        "page": state,
        "message": (
            "视频发布表单已填写并设置封面，请人工复核后执行 validate-publish-video。"
            if success and state.get("hasCover")
            else "视频发布表单已填写；发布前还需要在页面设置封面。"
            if needs_cover
            else "视频表单未完整确认：请检查上传、封面，以及标题/作品简介是否被页面截断或改写。"
        ),
    }


def select_music(
    page,
    preferred: list[str] | None = None,
    adapter: PlatformAdapter | None = None,
) -> dict:
    adapter = resolve_adapter(adapter)
    wrong_page = _wrong_publish_page_result(page, adapter)
    if wrong_page:
        return wrong_page
    preferred = [x.strip() for x in (preferred or []) if x and x.strip()]
    if not preferred:
        preferred = [
            "此刻最好的都在身边 (R&B氛围版)",
            "why u(氛围版)",
            "Cloud Rest（春天）",
            "Ambition (凌云志)",
        ]

    opened = False
    for selector in adapter.selectors.music_open_selectors:
        if page.click(selector):
            opened = True
            break
    if not opened:
        opened = bool(
            page.evaluate(
                f"""
                (() => {{
                  const candidates = Array.from(document.querySelectorAll('button, [role="button"], span, div'));
                  const target = candidates.find(el => {json.dumps(list(adapter.selectors.music_open_texts), ensure_ascii=False)}.includes((el.innerText || '').trim()));
                  if (!target) return false;
                  target.click();
                  return true;
                }})()
                """
            )
        )
    if not opened:
        risk = _risk_result(page, "当前处于验证码/风控页，无法打开音乐面板。", adapter)
        if risk:
            return risk
        return {"success": False, "message": "未找到音乐选择入口。"}

    panel_ready = _wait_until(
        page,
        f"""
        (() => !!Array.from(document.querySelectorAll({json.dumps(adapter.selectors.music_panel_selector)})).find(el => {{
          const text = el.innerText || '';
          const hasMarkers = {json.dumps(list(adapter.selectors.music_panel_markers), ensure_ascii=False)}.every(marker => text.includes(marker));
          const hasApply = Array.from(el.querySelectorAll('button')).some(button =>
            (button.innerText || '').trim() === {json.dumps(adapter.selectors.music_apply_text, ensure_ascii=False)} && !button.disabled
          );
          return hasMarkers && hasApply;
        }}))()
        """,
        timeout=15,
        interval=0.5,
    )
    if not panel_ready:
        risk = _risk_result(page, "当前处于验证码/风控页，无法打开音乐面板。", adapter)
        if risk:
            return risk
        return {"success": False, "message": "音乐面板未成功打开。"}

    picked = None
    for name in preferred:
        result = page.evaluate(
            f"""
            (() => {{
              const portal = Array.from(document.querySelectorAll({json.dumps(adapter.selectors.music_panel_selector)})).find(el => {{
                const text = el.innerText || '';
                return {json.dumps(list(adapter.selectors.music_panel_markers), ensure_ascii=False)}.every(marker => text.includes(marker));
              }});
              if (!portal) return {{ success: false, reason: 'no-portal' }};
              const node = Array.from(portal.querySelectorAll({json.dumps(",".join(adapter.selectors.music_name_selectors))})).find(el => (el.innerText || '').trim() === {_js_quote(name)});
              if (!node) return {{ success: false, reason: 'no-song' }};
              let row = node;
              for (let i = 0; i < 8 && row; i++) {{
                const buttons = row.querySelectorAll ? Array.from(row.querySelectorAll('button')) : [];
                if ((row.querySelector && row.querySelector({json.dumps(",".join(adapter.selectors.music_apply_selectors))})) || buttons.some(btn => (btn.innerText || '').trim() === {json.dumps(adapter.selectors.music_apply_text)})) break;
                row = row.parentElement;
              }}
              const btn = row && row.querySelector
                ? row.querySelector({json.dumps(",".join(adapter.selectors.music_apply_selectors))}) || Array.from(row.querySelectorAll('button')).find(el => (el.innerText || '').trim() === {json.dumps(adapter.selectors.music_apply_text)})
                : null;
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
            (() => {{
              const portal = Array.from(document.querySelectorAll({})).find(el => {{
                const text = el.innerText || '';
                return {}.every(marker => text.includes(marker));
              }});
              if (!portal) return {{ success: false, reason: 'no-portal' }};
              const nameSelectors = {};
              const applySelectors = {};
              const buttons = Array.from(portal.querySelectorAll(applySelectors)).filter(el =>
                (el.innerText || '').trim() === {} && !el.disabled
              );
              let btn = null;
              let nameNode = null;
              for (const candidate of buttons) {{
                let row = candidate.parentElement;
                for (let depth = 0; row && depth < 8; depth += 1, row = row.parentElement) {{
                  const name = nameSelectors
                    .map(selector => row.querySelector?.(selector))
                    .find(node => (node?.innerText || '').trim());
                  if (!name) continue;
                  btn = candidate;
                  nameNode = name;
                  break;
                }}
                if (nameNode) break;
              }}
              if (!btn || !nameNode) return {{ success: false, reason: 'no-apply-button' }};
              const picked = (nameNode.innerText || '').trim();
              btn.click();
              return {{ success: true, picked: picked || '推荐列表首个可用音乐' }};
            }})()
            """.format(
                json.dumps(adapter.selectors.music_panel_selector, ensure_ascii=False),
                json.dumps(
                    list(adapter.selectors.music_panel_markers), ensure_ascii=False
                ),
                json.dumps(
                    list(adapter.selectors.music_name_selectors),
                    ensure_ascii=False,
                ),
                json.dumps(
                    ",".join(adapter.selectors.music_apply_selectors),
                    ensure_ascii=False,
                ),
                json.dumps(adapter.selectors.music_apply_text, ensure_ascii=False),
            )
        )
        if fallback and fallback.get("success"):
            picked = fallback.get("picked") or "热门榜首个可用音乐"
        else:
            return {
                "success": False,
                "message": "音乐面板已打开，但未找到可用目标音乐。",
                "preferred": preferred,
            }

    applied = _wait_until(
        page,
        f"""
        (() => {{
          const body = document.body?.innerText || '';
          return body.includes({json.dumps(adapter.selectors.selected_music_text, ensure_ascii=False)});
        }})()
        """,
        timeout=15,
        interval=0.5,
    )
    if not applied:
        return {
            "success": False,
            "message": "已点击使用，但页面未确认音乐已应用。",
            "picked": picked,
        }

    state = (
        page.evaluate(
            f"""
        (() => ({{
          text: (document.body?.innerText || '').slice(0, 2500),
          selectedMusic: (() => {{
            const body = document.body?.innerText || '';
            const marker = body.indexOf({json.dumps(adapter.selectors.selected_music_text, ensure_ascii=False)});
            if (marker < 0) return '';
            const lines = body.slice(Math.max(0, marker - 160), marker)
              .split('\\n').map(x => x.trim()).filter(Boolean);
            const last = lines.at(-1) || '';
            return /^\\d{{1,2}}:\\d{{2}}$/.test(last)
              ? (lines.at(-2) || '')
              : last;
          }})()
        }}))()
        """
        )
        or {}
    )
    return {
        "success": True,
        "picked": state.get("selectedMusic") or picked,
        "requested": preferred,
        "page": state,
    }


def validate_publish_state(
    page,
    require_topic: bool = False,
    adapter: PlatformAdapter | None = None,
) -> dict:
    adapter = resolve_adapter(adapter)
    title_selector = json.dumps(
        adapter.selectors.publish_title_input_selector, ensure_ascii=False
    )
    editor_selector = json.dumps(
        ",".join(adapter.selectors.publish_editor_selectors), ensure_ascii=False
    )
    file_selector = json.dumps(
        adapter.selectors.publish_file_input_selector, ensure_ascii=False
    )
    image_markers = json.dumps(
        list(adapter.selectors.publish_image_markers), ensure_ascii=False
    )
    topic_markers = json.dumps(
        list(adapter.selectors.topic_markers), ensure_ascii=False
    )
    selected_music_text = json.dumps(
        adapter.selectors.selected_music_text, ensure_ascii=False
    )
    script = f"""
    (() => {{
      const body = (document.body && document.body.innerText) || '';
      const titleEl = document.querySelector({title_selector});
      const editorEl = document.querySelector({editor_selector});
      const title = titleEl ? ((titleEl.value || '').trim()) : '';
      const editorText = editorEl ? (((editorEl.innerText || editorEl.textContent || '')).trim()) : '';
      const fileCount = Array.from(document.querySelectorAll({file_selector})).reduce((count, input) => count + (input.files?.length || 0), 0);
      const hasImage = {image_markers}.some(marker => body.includes(marker));
      const uploadInProgress = fileCount > 0 && !hasImage;
      const hasMusic = body.includes({selected_music_text});
      const hasTopic = {topic_markers}.some(marker => body.includes(marker));
      const errors = [];
      if (!hasImage) errors.push('缺少图片');
      if (!title) errors.push('标题为空');
      if (!editorText) errors.push('正文为空');
      if (!hasMusic) errors.push('未选择音乐');
      if ({"true" if require_topic else "false"} && !hasTopic) errors.push('未关联热点');
      return {{
        success: errors.length === 0,
        requireTopic: {"true" if require_topic else "false"},
        title: title,
        editorText: editorText.slice(0, 1000),
        href: location.href || '',
        page_title: document.title || '',
        fileCount: fileCount,
        hasImage: hasImage,
        uploadInProgress: uploadInProgress,
        hasMusic: hasMusic,
        hasTopic: hasTopic,
        errors: errors,
        text: body.slice(0, 2500)
      }};
    }})()
    """
    state = page.evaluate(script)
    if isinstance(state, dict) and state:
        page_title = state.get("page_title", "") or ""
        page_text = state.get("text", "") or ""
        is_risk = adapter.is_risk_page(page_title, page_text) or any(
            hint in page_title or hint in page_text
            for hint in adapter.risk_strong_hints
        )
        if is_risk:
            return {
                "success": False,
                "risk_page": True,
                "message": "当前处于验证码/风控页，无法读取发布页状态。",
                "page_title": page_title,
                "page": {
                    "href": state.get("href", ""),
                    "title": page_title,
                    "text": page_text,
                },
            }
        wrong_page = _wrong_publish_page_result(
            page, adapter, require_topic, state=state
        )
        if wrong_page:
            wrong_page["page"] = {
                "href": state.get("href", ""),
                "page_title": state.get("page_title", ""),
                "text": state.get("text", ""),
            }
            return wrong_page
        return classify_publish_snapshot(state, require_topic=require_topic)
    return {"success": False, "errors": ["无法读取发布页状态"]}


def validate_video_publish_state(
    page,
    require_topic: bool = False,
    adapter: PlatformAdapter | None = None,
) -> dict:
    adapter = resolve_adapter(adapter)
    state = _video_publish_snapshot(page, adapter)
    if state:
        page_title = state.get("page_title", "") or ""
        page_text = state.get("text", "") or ""
        is_risk = adapter.is_risk_page(page_title, page_text) or any(
            hint in page_title or hint in page_text
            for hint in adapter.risk_strong_hints
        )
        if is_risk:
            return {
                "success": False,
                "risk_page": True,
                "message": "当前处于验证码/风控页，无法读取视频发布页状态。",
                "page_title": page_title,
                "page": {
                    "href": state.get("href", ""),
                    "title": page_title,
                    "text": page_text,
                },
            }
        wrong_page = _wrong_publish_page_result(
            page,
            adapter,
            require_topic,
            state=state,
            publish_kind="video",
        )
        if wrong_page:
            wrong_page["page"] = {
                "href": state.get("href", ""),
                "page_title": state.get("page_title", ""),
                "text": state.get("text", ""),
            }
            return wrong_page
        return classify_video_publish_snapshot(state, require_topic=require_topic)
    return {"success": False, "errors": ["无法读取视频发布页状态"]}


def click_publish(
    page,
    require_topic: bool = False,
    adapter: PlatformAdapter | None = None,
) -> dict:
    adapter = resolve_adapter(adapter)
    check = validate_publish_state(page, require_topic=require_topic, adapter=adapter)
    return _click_publish_after_validation(page, check, adapter)


def click_publish_video(
    page,
    require_topic: bool = False,
    adapter: PlatformAdapter | None = None,
) -> dict:
    adapter = resolve_adapter(adapter)
    check = validate_video_publish_state(
        page, require_topic=require_topic, adapter=adapter
    )
    return _click_publish_after_validation(page, check, adapter)


def _click_publish_after_validation(
    page,
    check: dict,
    adapter: PlatformAdapter,
) -> dict:
    if check.get("risk_page"):
        return check
    if not check.get("success"):
        return {
            "success": False,
            "message": "发布前校验失败",
            "validation": check,
        }

    result = (
        page.evaluate(
            f"""
        (() => {{
          const body = (document.body && document.body.innerText) || '';
          const buttons = Array.from(document.querySelectorAll('button'));
          const btn = buttons.find(el => (el.innerText || '').trim() === {json.dumps(adapter.selectors.publish_button_text, ensure_ascii=False)});
          if (!btn) return {{ clicked: false, message: '未找到底部发布按钮', body: body.slice(0, 2500) }};
          if (btn.disabled || btn.getAttribute('aria-disabled') === 'true') {{
            return {{ clicked: false, message: '发布按钮当前不可用', body: body.slice(0, 2500) }};
          }}
          btn.scrollIntoView({{ block: 'center' }});
          btn.click();
          return {{
            clicked: true,
            text: (btn.innerText || '').trim(),
            className: btn.className || '',
            hrefBefore: location.href || ''
          }};
        }})()
        """
        )
        or {}
    )
    if not result.get("clicked"):
        return {
            "success": False,
            "message": result.get("message") or "点击发布失败",
            "validation": check,
            "click": result,
        }

    confirmation = _wait_until(
        page,
        f"""
        (() => {{
          const body = document.body?.innerText || '';
          const href = location.href || '';
          const confirmed = {json.dumps(list(adapter.selectors.publish_success_texts), ensure_ascii=False)}.some(marker => body.includes(marker)) || href.includes({json.dumps(adapter.selectors.publish_success_path_fragment, ensure_ascii=False)});
          return confirmed ? {{ confirmed: true, href, text: body.slice(0, 1200) }} : null;
        }})()
        """,
        timeout=20,
        interval=1,
    )
    outcome = classify_publish_outcome(True, confirmation)
    if outcome["status"] == "publish_confirmed":
        return {
            "success": True,
            **outcome,
            "message": "页面已确认发布成功。",
            "validation": check,
            "click": result,
            "confirmation": confirmation,
        }

    return {
        "success": True,
        **outcome,
        "message": "已点击发布，但页面尚未给出明确成功信号。不要自动重试，请先到作品管理确认，避免重复发布。",
        "validation": check,
        "click": result,
        "page": _page_snapshot(page),
    }
