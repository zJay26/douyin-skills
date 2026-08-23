from __future__ import annotations

import base64
import binascii
import json
import re
import tempfile
import time
from pathlib import Path

from platform_adapter import PlatformAdapter, resolve_adapter

from .page_states import classify_login_snapshot

LOGIN_STATE_SETTLE_TIMEOUT = 8.0
LOGIN_STATE_SETTLE_INTERVAL = 1.0


def inspect_login_state(page, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    selectors = adapter.selectors
    login_keywords = json.dumps(list(selectors.login_text_keywords), ensure_ascii=False)
    login_panel_markers = json.dumps(
        list(selectors.login_panel_markers), ensure_ascii=False
    )
    logged_in_hints = json.dumps(
        list(selectors.logged_in_text_hints), ensure_ascii=False
    )
    risk_keywords = json.dumps(list(adapter.risk_page_keywords), ensure_ascii=False)
    risk_strong_hints = json.dumps(list(adapter.risk_strong_hints), ensure_ascii=False)
    qrcode_selectors = json.dumps(
        ", ".join(selectors.login_qrcode_selectors), ensure_ascii=False
    )
    profile_ui_selectors = json.dumps(
        ", ".join(selectors.profile_ui_selectors), ensure_ascii=False
    )
    auth_cookie_names = json.dumps(
        list(selectors.auth_cookie_names), ensure_ascii=False
    )
    script = f"""
    (() => {{
      const bodyText = (document.body && document.body.innerText) || '';
      const title = document.title || '';
      const href = location.href || '';
      const cookies = document.cookie || '';
      const isVisible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
      const visibleTextNodes = Array.from(document.querySelectorAll('button, [role="button"], [role="dialog"], a, span, div')).filter(isVisible);
      const loginKeywords = {login_keywords};
      const loginPanelMarkers = {login_panel_markers};
      const loggedInHints = {logged_in_hints};
      const riskKeywords = {risk_keywords};
      const riskStrongHints = {risk_strong_hints};
      const hasLoginKeyword = visibleTextNodes.some(el => loginKeywords.includes((el.innerText || '').trim()));
      const loggedInHintCount = loggedInHints.filter(x => bodyText.includes(x) || title.includes(x)).length;
      const riskKeywordCount = riskKeywords.filter(x => bodyText.includes(x) || title.includes(x)).length;
      const hasRiskStrongHint = riskStrongHints.some(x => bodyText.includes(x) || title.includes(x));
      const hasRiskUi = visibleTextNodes.some(el => riskStrongHints.includes((el.innerText || '').trim()));
      const hasLoginPanel = visibleTextNodes.some(el => {{
        const text = (el.innerText || '').trim();
        const role = el.getAttribute?.('role') || '';
        return (role === 'dialog' || /login/i.test((el.className || '').toString()) || /login/i.test(el.getAttribute?.('data-e2e') || ''))
          && loginPanelMarkers.some(marker => text.includes(marker));
      }}) || Array.from(document.querySelectorAll({qrcode_selectors})).some(isVisible);
      const hasProfileUi = Array.from(document.querySelectorAll({profile_ui_selectors})).some(isVisible);
      const authCookieNames = {auth_cookie_names};
      const hasAuthCookie = cookies.split(';').some(cookie => authCookieNames.includes(cookie.trim().split('=', 1)[0]));
      const hasRiskKeyword = hasRiskStrongHint || hasRiskUi || riskKeywordCount >= 2;
      return {{
        title,
        href,
        bodyText: bodyText.slice(0, 5000),
        cookieLength: cookies.length,
        hasLoginKeyword,
        loggedInHintCount,
        hasProfileUi,
        hasAuthCookie,
        hasRiskKeyword,
        hasRiskStrongHint,
        hasRiskUi,
        riskKeywordCount,
        hasLoginPanel,
      }};
    }})()
    """
    return page.evaluate(script) or {}


def check_login_state(page, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    info = inspect_login_state(page, adapter=adapter) or {}
    classification = classify_login_snapshot(info)
    return {
        "success": True,
        "logged_in": classification["logged_in"],
        "risk_page": classification["risk_page"],
        "login_method": "qrcode_or_sms",
        "page": {
            k: info.get(k)
            for k in [
                "title",
                "href",
                "hasLoginKeyword",
                "loggedInHintCount",
                "hasProfileUi",
                "hasAuthCookie",
                "hasRiskKeyword",
                "hasRiskStrongHint",
                "hasRiskUi",
                "riskKeywordCount",
                "hasLoginPanel",
                "cookieLength",
            ]
        },
    }


def settle_login_state(
    page,
    adapter: PlatformAdapter | None = None,
    *,
    timeout_seconds: float = LOGIN_STATE_SETTLE_TIMEOUT,
    interval_seconds: float = LOGIN_STATE_SETTLE_INTERVAL,
) -> dict:
    """Recheck a transient verification interstitial before surfacing a pause.

    Douyin can briefly render a verification interstitial while a reused,
    already-authenticated Chrome tab is navigating. A persistent verification
    page remains a human checkpoint; only a later non-risk state is accepted.
    """
    state = check_login_state(page, adapter=adapter)
    if not state.get("risk_page"):
        return state

    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    attempts = 1
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        time.sleep(min(max(0.0, float(interval_seconds)), remaining))
        state = check_login_state(page, adapter=adapter)
        attempts += 1
        if not state.get("risk_page"):
            if state.get("logged_in"):
                return {
                    **state,
                    "risk_recovered": True,
                    "risk_recheck_count": attempts,
                }
            return state

    return {**state, "risk_recheck_count": attempts}


def _find_qrcode_data_url(page, adapter: PlatformAdapter | None = None) -> str | None:
    adapter = resolve_adapter(adapter)
    qrcode_selectors = ", ".join(adapter.selectors.login_qrcode_selectors)
    script = f"""
    (async () => {{
      const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
      const nodes = Array.from(document.querySelectorAll({json.dumps(qrcode_selectors, ensure_ascii=False)})).filter(visible);
      const node = nodes[0] || null;
      if (!node) return null;
      if (node.tagName === 'CANVAS') return node.toDataURL('image/png');
      if (node.src?.startsWith('data:image')) return node.src;
      if (node.src) {{
        try {{
          const response = await fetch(node.src, {{ credentials: 'include' }});
          if (!response.ok) return null;
          const blob = await response.blob();
          return await new Promise((resolve, reject) => {{
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
          }});
        }} catch (_error) {{
          return null;
        }}
      }}
      return null;
    }})()
    """
    return page.evaluate(script)


def get_qrcode(page, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    adapter.navigate_home(page)
    page.wait_for_load(20)
    deadline = time.time() + 20
    data_url = None
    while time.time() < deadline:
        data_url = _find_qrcode_data_url(page, adapter=adapter)
        if data_url:
            break
        time.sleep(1)
    if not data_url:
        state = check_login_state(page, adapter=adapter)
        if state.get("risk_page"):
            return {
                "success": False,
                "risk_page": True,
                "error": "当前处于验证码/风控页，无法读取登录二维码",
                "state": state,
            }
        return {"success": False, "error": "未找到可读取的登录二维码"}
    out_dir = Path(tempfile.gettempdir()) / "douyin-skills"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "douyin-login-qrcode.png"
    try:
        encoded = data_url.split(",", 1)[1]
        out_path.write_bytes(base64.b64decode(encoded, validate=True))
    except (IndexError, ValueError, binascii.Error) as exc:
        return {"success": False, "error": f"二维码数据无效：{exc}"}
    return {
        "success": True,
        "qrcode_path": str(out_path),
        "qrcode_data_url": data_url,
        "message": "请使用抖音 App 扫码登录",
    }


def wait_login(
    page, timeout_seconds: int = 120, adapter: PlatformAdapter | None = None
) -> dict:
    adapter = resolve_adapter(adapter)
    deadline = time.time() + timeout_seconds
    last_state = {}
    while time.time() < deadline:
        state = check_login_state(page, adapter=adapter)
        last_state = state
        if state.get("risk_page"):
            return {
                "success": False,
                "logged_in": False,
                "risk_page": True,
                "error": "登录过程中出现验证码/风控页",
                "state": state,
            }
        if state.get("logged_in"):
            return {
                "success": True,
                "logged_in": True,
                "message": "登录成功",
                "state": state,
            }
        time.sleep(2)
    return {
        "success": False,
        "logged_in": False,
        "error": "等待登录超时",
        "state": last_state,
    }


def send_code(page, phone: str = "", adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    if phone:
        phone = re.sub(r"[\s-]", "", phone)
        if not re.fullmatch(r"(?:\+?86)?1[3-9]\d{9}", phone):
            return {
                "success": False,
                "status": "failed",
                "message": "手机号格式无效，请输入中国大陆手机号",
            }
        if phone.startswith("+86"):
            phone = phone[3:]
        elif phone.startswith("86") and len(phone) == 13:
            phone = phone[2:]
    adapter.navigate_home(page)
    page.wait_for_load(20)
    if phone:
        page.evaluate(
            f"""
            (() => {{
              const input = document.querySelector(%s);
              if (!input) return false;
              input.focus();
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
              if (setter) setter.call(input, {json.dumps(phone)});
              else input.value = {json.dumps(phone)};
              input.dispatchEvent(new Event('input', {{bubbles:true}}));
              input.dispatchEvent(new Event('change', {{bubbles:true}}));
              const agreement = Array.from(document.querySelectorAll('label, div, span')).find(el => (el.innerText || '').includes(%s));
              const checkbox = agreement?.querySelector?.('input[type="checkbox"]') || agreement?.closest?.('label')?.querySelector?.('input[type="checkbox"]');
              if (checkbox && !checkbox.checked) checkbox.click();
              return true;
            }})()
            """
            % (
                json.dumps(
                    ", ".join(adapter.selectors.phone_input_selectors),
                    ensure_ascii=False,
                ),
                json.dumps(adapter.selectors.agreement_text, ensure_ascii=False),
            )
        )
    ok = page.evaluate(
        f"""
        (() => {{
          const nodes = Array.from(document.querySelectorAll('button, [role="button"], span, div'));
          const btn = nodes.find(el => {json.dumps(list(adapter.selectors.send_code_texts), ensure_ascii=False)}.includes((el.innerText || '').trim()) && !el.disabled);
          if (!btn) return false;
          btn.click();
          return true;
        }})()
        """
    )
    if not ok:
        state = check_login_state(page, adapter=adapter)
        if state.get("risk_page"):
            return {
                "success": False,
                "status": "failed",
                "risk_page": True,
                "message": "当前处于验证码/风控页，无法发送验证码",
                "state": state,
            }
    return {
        "success": bool(ok),
        "status": "code_sent" if ok else "failed",
        "message": "验证码已发送" if ok else "未找到验证码发送入口",
    }


def verify_code(page, code: str, adapter: PlatformAdapter | None = None) -> dict:
    adapter = resolve_adapter(adapter)
    code = str(code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        return {"success": False, "logged_in": False, "error": "验证码必须是 6 位数字"}
    ok = page.evaluate(
        f"""
        (() => {{
          const input = document.querySelector(%s);
          if (!input) return false;
          input.focus();
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
          if (setter) setter.call(input, {json.dumps(code)});
          else input.value = {json.dumps(code)};
          input.dispatchEvent(new Event('input', {{bubbles:true}}));
          input.dispatchEvent(new Event('change', {{bubbles:true}}));
          const nodes = Array.from(document.querySelectorAll('button, [role="button"], span, div'));
          const btn = nodes.find(el => %s.includes((el.innerText || '').trim()) && !el.disabled);
          if (btn) btn.click();
          return true;
        }})()
        """
        % (
            json.dumps(
                ", ".join(adapter.selectors.verification_input_selectors),
                ensure_ascii=False,
            ),
            json.dumps(list(adapter.selectors.submit_code_texts), ensure_ascii=False),
        )
    )
    if not ok:
        return {"success": False, "logged_in": False, "error": "未找到验证码输入框"}
    time.sleep(3)
    state = check_login_state(page, adapter=adapter)
    if state.get("logged_in"):
        return {
            "success": True,
            "logged_in": True,
            "message": "登录成功",
            "state": state,
        }
    return {
        "success": False,
        "logged_in": False,
        "message": "验证码已提交，但尚未确认登录成功",
        "state": state,
    }
