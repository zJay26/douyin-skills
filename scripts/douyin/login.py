from __future__ import annotations

import base64
import os
import tempfile
import time
from pathlib import Path

from .selectors import LOGGED_IN_TEXT_HINTS, LOGIN_TEXT_KEYWORDS

RISK_PAGE_KEYWORDS = ["验证码", "安全验证", "风险提示", "身份验证"]
RISK_STRONG_HINTS = ["请完成验证", "请进行验证", "拖动滑块", "点击按钮进行验证", "短信验证码", "发送短信验证", "接收短信验证码"]


def inspect_login_state(page) -> dict:
    script = f"""
    (() => {{
      const bodyText = (document.body && document.body.innerText) || '';
      const title = document.title || '';
      const href = location.href || '';
      const cookies = document.cookie || '';
      const hasLoginKeyword = {LOGIN_TEXT_KEYWORDS!r}.some(x => bodyText.includes(x) || title.includes(x));
      const hasLoggedInHint = {LOGGED_IN_TEXT_HINTS!r}.some(x => bodyText.includes(x) || title.includes(x));
      const riskKeywordCount = {RISK_PAGE_KEYWORDS!r}.filter(x => bodyText.includes(x) || title.includes(x)).length;
      const hasRiskStrongHint = {RISK_STRONG_HINTS!r}.some(x => bodyText.includes(x) || title.includes(x));
      const hasRiskUi = !!Array.from(document.querySelectorAll('button, div, span')).find(el => ['发送短信验证', '接收短信验证码', '重新获取验证码', '拖动滑块', '立即验证'].includes((el.innerText || '').trim()));
      const hasLoginPanel = !!document.querySelector('[class*="login"], [data-e2e*="login"], img[alt*="二维码"]');
      const hasRiskKeyword = hasRiskStrongHint || hasRiskUi || riskKeywordCount >= 2;
      return {{
        title,
        href,
        bodyText: bodyText.slice(0, 5000),
        cookieLength: cookies.length,
        hasLoginKeyword,
        hasLoggedInHint,
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
    body_text = info.get("bodyText", "") or ""
    href = info.get("href", "") or ""
    risk_page = bool(info.get("hasRiskKeyword"))
    has_login_panel = bool(info.get("hasLoginPanel"))
    logged_in_markers = bool(info.get("hasLoggedInHint")) or any(x in body_text for x in ["投稿", "私信", "通知", "客户端"])
    cookie_based = info.get("cookieLength", 0) > 50 and not info.get("hasLoginKeyword")
    page_based = any(x in href for x in ["/jingxuan", "/search/", "/video/", "/note/", "/user/"]) and not has_login_panel
    logged_in = not risk_page and (logged_in_markers or cookie_based or page_based)
    return {
        "success": True,
        "logged_in": logged_in,
        "risk_page": risk_page,
        "login_method": "qrcode" if os.environ.get("DISPLAY") else "both",
        "page": {k: info.get(k) for k in ["title", "href", "hasLoginKeyword", "hasLoggedInHint", "hasRiskKeyword", "hasRiskStrongHint", "hasRiskUi", "riskKeywordCount", "hasLoginPanel", "cookieLength"]},
    }


def _find_qrcode_data_url(page) -> str | None:
    script = """
    (() => {
      const img = document.querySelector('img[alt*="二维码"], img[src^="data:image"], canvas');
      if (!img) return null;
      if (img.tagName === 'IMG') return img.src || null;
      if (img.tagName === 'CANVAS') return img.toDataURL('image/png');
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
        return {"success": False, "error": "未找到二维码"}
    out_dir = Path(tempfile.gettempdir()) / "douyin-skills"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "douyin-login-qrcode.png"
    if data_url.startswith("data:image"):
        encoded = data_url.split(",", 1)[1]
        out_path.write_bytes(base64.b64decode(encoded))
    return {"success": True, "qrcode_path": str(out_path), "qrcode_data_url": data_url, "message": "请使用抖音 App 扫码登录"}


def wait_login(page, timeout_seconds: int = 120) -> dict:
    deadline = time.time() + timeout_seconds
    last_state = {}
    while time.time() < deadline:
        state = check_login_state(page)
        last_state = state
        if state.get("logged_in"):
            return {"success": True, "logged_in": True, "message": "登录成功", "state": state}
        time.sleep(2)
    return {"success": False, "logged_in": False, "error": "等待登录超时", "state": last_state}


def send_code(page, phone: str = "") -> dict:
    page.navigate("https://www.douyin.com/")
    page.wait_for_load(20)
    if phone:
        page.evaluate(
            f"""
            (() => {{
              const input = document.querySelector('input[type="text"], input[type="tel"]');
              if (!input) return false;
              input.focus();
              input.value = {phone!r};
              input.dispatchEvent(new Event('input', {{bubbles:true}}));
              input.dispatchEvent(new Event('change', {{bubbles:true}}));
              return true;
            }})()
            """
        )
    ok = page.evaluate(
        """
        (() => {
          const nodes = Array.from(document.querySelectorAll('button, span, div'));
          const btn = nodes.find(el => ['获取验证码', '发送验证码', '接收短信验证码', '发送短信验证'].some(t => (el.innerText || '').includes(t)));
          if (!btn) return false;
          btn.click();
          return true;
        })()
        """
    )
    return {"success": bool(ok), "status": "code_sent" if ok else "failed", "message": "验证码已发送" if ok else "未找到验证码发送入口"}


def verify_code(page, code: str) -> dict:
    ok = page.evaluate(
        f"""
        (() => {{
          const input = document.querySelector('input[type="text"], input[type="tel"], input[type="number"]');
          if (!input) return false;
          input.focus();
          input.value = {code!r};
          input.dispatchEvent(new Event('input', {{bubbles:true}}));
          input.dispatchEvent(new Event('change', {{bubbles:true}}));
          const nodes = Array.from(document.querySelectorAll('button, span, div'));
          const btn = nodes.find(el => ['登录', '确定', '验证', '提交'].some(t => (el.innerText || '').includes(t)));
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
        return {"success": True, "logged_in": True, "message": "登录成功", "state": state}
    return {"success": False, "logged_in": False, "message": "验证码已提交，但尚未确认登录成功", "state": state}
