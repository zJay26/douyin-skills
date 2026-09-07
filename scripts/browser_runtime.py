from __future__ import annotations

import ipaddress
import json
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
NODE_CLIENT = SCRIPT_DIR / "cdp_client.mjs"


class CDPError(RuntimeError):
    def __init__(self, message: str, code: str = "bridge_error"):
        super().__init__(message)
        self.code = code


def normalize_host(host: str) -> str:
    host = host.strip().lower()
    if host == "localhost":
        return "127.0.0.1"
    try:
        address = ipaddress.ip_address(host)
    except ValueError as error:
        raise ValueError("CDP 地址必须是 loopback 地址") from error
    if not address.is_loopback:
        raise ValueError("CDP 地址必须是 loopback 地址")
    return str(address)


def _run_node(mode: str, payload: dict) -> dict:
    payload = {**payload, "host": normalize_host(payload.get("host", "127.0.0.1"))}
    port = payload.get("port", 9222)
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("CDP 端口必须在 1 到 65535 之间")
    # Stdin avoids Windows command-line limits and keeps text out of process args.
    cmd = ["node", str(NODE_CLIENT), mode, "-"]
    try:
        proc = subprocess.run(
            cmd,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=45,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 Node.js；请先安装 Node.js 18 或更高版本") from exc
    except subprocess.TimeoutExpired as exc:
        raise CDPError(f"CDP 命令超时: {mode}", "timeout") from exc
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CDPError(
            proc.stderr.strip() or f"CDP 命令返回了无效 JSON: {mode}",
            "invalid_response",
        ) from exc
    if not isinstance(result, dict):
        raise CDPError(f"CDP 命令返回格式无效: {mode}", "invalid_response")
    if proc.returncode != 0 or result.get("success") is not True:
        raise CDPError(
            result.get("error") or f"CDP 命令失败: {mode}",
            result.get("error_code") or "bridge_error",
        )
    return result


class Page:
    def __init__(self, host: str, port: int, target_id: str):
        self.host = host
        self.port = port
        self.target_id = target_id

    def navigate(self, url: str) -> None:
        _run_node(
            "navigate",
            {
                "host": self.host,
                "port": self.port,
                "targetId": self.target_id,
                "url": url,
            },
        )

    def evaluate(self, expression: str):
        result = _run_node(
            "evaluate",
            {
                "host": self.host,
                "port": self.port,
                "targetId": self.target_id,
                "expression": expression,
            },
        )
        return result.get("value")

    def click(self, selector: str) -> bool:
        result = self.evaluate(
            f"""
            (() => {{
              const el = document.querySelector({json.dumps(selector)});
              if (!el) return false;
              el.scrollIntoView({{block:'center'}});
              el.click();
              return true;
            }})()
            """
        )
        if not isinstance(result, bool):
            raise CDPError("点击指令未返回明确执行结果", "invalid_response")
        return result

    def type_text(self, selector: str, text: str) -> bool:
        result = self.evaluate(
            f"""
            (() => {{
              const el = document.querySelector({json.dumps(selector)});
              if (!el) return false;
              el.focus();
              if ('value' in el) {{
                el.value = {json.dumps(text)};
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                return true;
              }}
              if (el.isContentEditable) {{
                el.innerText = {json.dumps(text)};
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                return true;
              }}
              return false;
            }})()
            """
        )
        return bool(result)

    def wait_for_load(self, seconds: int = 10) -> None:
        self.evaluate(
            f"""
            new Promise(resolve => {{
              if (document.readyState === 'complete') return resolve(true);
              const timeout = setTimeout(() => resolve(false), {seconds * 1000});
              window.addEventListener('load', () => {{ clearTimeout(timeout); resolve(true); }}, {{once:true}});
            }})
            """
        )

    def press_enter(self) -> None:
        _run_node(
            "keypress",
            {
                "host": self.host,
                "port": self.port,
                "targetId": self.target_id,
                "key": "Enter",
                "code": "Enter",
                "keyCode": 13,
                "text": "\r",
            },
        )

    def insert_text(self, text: str) -> bool:
        """Insert text into the focused editor through Chrome's input domain."""
        result = _run_node(
            "insert-text",
            {
                "host": self.host,
                "port": self.port,
                "targetId": self.target_id,
                "text": text,
            },
        )
        return bool(result.get("success"))

    def set_files(self, selector: str, files: list[str]) -> bool:
        result = _run_node(
            "set-file-input-files",
            {
                "host": self.host,
                "port": self.port,
                "targetId": self.target_id,
                "selector": selector,
                "files": files,
            },
        )
        return bool(result.get("success"))


class Browser:
    def __init__(self, host: str = "127.0.0.1", port: int = 9222):
        self.host = normalize_host(host)
        self.port = port

    def connect(self) -> None:
        _run_node("list", {"host": self.host, "port": self.port})

    def list_pages(self) -> list[dict]:
        result = _run_node("list", {"host": self.host, "port": self.port})
        return result.get("targets", [])

    def version(self) -> dict:
        return _run_node("version", {"host": self.host, "port": self.port})

    def get_or_create_page(self) -> Page:
        """Create a dedicated page when the caller has no saved target."""
        return self.new_page()

    def new_page(self) -> Page:
        result = _run_node("new-page", {"host": self.host, "port": self.port})
        return Page(self.host, self.port, result["targetId"])

    def get_page_by_target_id(self, target_id: str | None) -> Page | None:
        if not target_id:
            return None
        for target in self.list_pages():
            tid = target.get("targetId") or target.get("id")
            if tid == target_id and target.get("type") == "page":
                return Page(self.host, self.port, target_id)
        return None
