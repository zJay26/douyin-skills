from __future__ import annotations

import base64
import binascii
import json
import re
import tempfile
import time
from pathlib import Path

from .page_states import (
    RISK_PAGE_KEYWORDS,
    RISK_STRONG_HINTS,
    classify_login_snapshot,
)
from .selectors import LOGGED_IN_TEXT_HINTS, LOGIN_TEXT_KEYWORDS


def inspect_login_state(page) -> dict:
    script = f"""
    (() => {{
      const bodyText = (document.body && document.body.innerText) || '';
      const title = document.title || '';
      const href = location.href || '';
      const cookies = document.cookie || '';
      const isVisible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
      const visibleTextNodes = Array.from(document.querySelectorAll('button, [role="button"], [role="dialog"], a, span, div')).filter(isVisible);
      const hasLoginKeyword = visibleTextNodes.some(el => {LOGIN_TEXT_KEYWORDS!r}.includes((el.innerText || '').trim()));
      const loggedInHintCount = {LOGGED_IN_TEXT_HINTS!r}.filter(x => bodyText.includes(x) || title.includes(x)).length;
      const riskKeywordCount = {RISK_PAGE_KEYWORDS!r}.filter(x => bodyText.includes(x) || title.includes(x)).length;
      const hasRiskStrongHint = {RISK_STRONG_HINTS!r}.some(x => bodyText.includes(x) || title.includes(x));
      const hasRiskUi = visibleTextNodes.some(el => ['发送短信验证', '接收短信验证码', '重新获取验证码', '拖动滑块', '立即验证'].includes((el.innerText || '').trim()));
      const hasLoginPanel = visibleTextNodes.some(el => {{
        const text = (el.innerText || '').trim();
        const role = el.getAttribute?.('role') || '';
        return (role === 'dialog' || /login/i.test((el.className || '').toString()) || /login/i.test(el.getAttribute?.('data-e2e') || ''))
          && (text.includes('扫码登录') || text.includes('手机号登录') || text.includes('立即登录'));
      }}) || Array.from(document.querySelectorAll('img[alt*="二维码"]')).some(isVisible);
      const hasProfileUi = Array.from(document.querySelectorAll('a[href*="/user/self"], [data-e2e*="user-avatar"], [data-e2e="user-info"]')).some(isVisible);
      const hasAuthCookie = /(?:^|;[ \t]*)(sessionid|sessionid_ss|sid_guard|uid_tt|uid_tt_ss)=/.test(cookies);
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


def check_login_state(page) -> dict:
    info = inspect_login_state(page) or {}
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


def _find_qrcode_data_url(page) -> str | None:
    script = """
    (async () => {
      const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
      const nodes = Array.from(document.querySelectorAll('img[alt*="二维码"], canvas')).filter(visible);
      const node = nodes[0] || null;
      if (!node) return null;
      if (node.tagName === 'CANVAS') return node.toDataURL('image/png');
      if (node.src?.startsWith('data:image')) return node.src;
      if (node.src) {
        try {
          const response = await fetch(node.src, { credentials: 'include' });
          if (!response.ok) return null;
          const blob = await response.blob();
          return await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
          });
        } catch (_error) {
          return null;
        }
      }
      return null;
    })()
    """
    return page.evaluate(script)


def get_qrcode(page) -> dict:
    page.navigate("https://www.douyin.com/")
    page.wait_for_load(20)
    deadline = time.time() + 20
    data_url = None
    while time.time() < deadline:
        data_url = _find_qrcode_data_url(page)
        if data_url:
            break
        time.sleep(1)
    if not data_url:
        state = check_login_state(page)
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


def wait_login(page, timeout_seconds: int = 120) -> dict:
    deadline = time.time() + timeout_seconds
    last_state = {}
    while time.time() < deadline:
        state = check_login_state(page)
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


def send_code(page, phone: str = "") -> dict:
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
    page.navigate("https://www.douyin.com/")
    page.wait_for_load(20)
    if phone:
        page.evaluate(
            f"""
            (() => {{
              const input = document.querySelector('input[placeholder*="手机号"], input[type="tel"]');
              if (!input) return false;
              input.focus();
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
              if (setter) setter.call(input, {json.dumps(phone)});
              else input.value = {json.dumps(phone)};
              input.dispatchEvent(new Event('input', {{bubbles:true}}));
              input.dispatchEvent(new Event('change', {{bubbles:true}}));
              const agreement = Array.from(document.querySelectorAll('label, div, span')).find(el => (el.innerText || '').includes('已阅读并同意'));
              const checkbox = agreement?.querySelector?.('input[type="checkbox"]') || agreement?.closest?.('label')?.querySelector?.('input[type="checkbox"]');
              if (checkbox && !checkbox.checked) checkbox.click();
              return true;
            }})()
            """
        )
    ok = page.evaluate(
        """
        (() => {
          const nodes = Array.from(document.querySelectorAll('button, [role="button"], span, div'));
          const btn = nodes.find(el => ['获取验证码', '发送验证码', '接收短信验证码', '发送短信验证'].includes((el.innerText || '').trim()) && !el.disabled);
          if (!btn) return false;
          btn.click();
          return true;
        })()
        """
    )
    if not ok:
        state = check_login_state(page)
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


def verify_code(page, code: str) -> dict:
    code = str(code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        return {"success": False, "logged_in": False, "error": "验证码必须是 6 位数字"}
    ok = page.evaluate(
        f"""
        (() => {{
          const input = document.querySelector('input[placeholder*="验证码"], input[inputmode="numeric"], input[type="number"]');
          if (!input) return false;
          input.focus();
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
          if (setter) setter.call(input, {json.dumps(code)});
          else input.value = {json.dumps(code)};
          input.dispatchEvent(new Event('input', {{bubbles:true}}));
          input.dispatchEvent(new Event('change', {{bubbles:true}}));
          const nodes = Array.from(document.querySelectorAll('button, [role="button"], span, div'));
          const btn = nodes.find(el => ['登录', '确定', '验证', '提交'].includes((el.innerText || '').trim()) && !el.disabled);
          if (btn) btn.click();
          return true;
        }})()
        """
    )
    if not ok:
        return {"success": False, "logged_in": False, "error": "未找到验证码输入框"}
    time.sleep(3)
    state = check_login_state(page)
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
