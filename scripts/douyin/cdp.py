from __future__ import annotations

import json
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
NODE_CLIENT = SCRIPT_DIR / "cdp_client.mjs"


def _run_node(mode: str, payload: dict) -> dict:
    cmd = ["node", str(NODE_CLIENT), mode, json.dumps(payload, ensure_ascii=False)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"node command failed: {mode}")
    return json.loads(proc.stdout)


class Page:
    def __init__(self, host: str, port: int, target_id: str):
        self.host = host
        self.port = port
        self.target_id = target_id

    def navigate(self, url: str) -> None:
        _run_node("navigate", {"host": self.host, "port": self.port, "targetId": self.target_id, "url": url})

    def evaluate(self, expression: str):
        result = _run_node("evaluate", {"host": self.host, "port": self.port, "targetId": self.target_id, "expression": expression})
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
        return bool(result)

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
            {"host": self.host, "port": self.port, "targetId": self.target_id, "key": "Enter", "code": "Enter", "keyCode": 13, "text": "\r"},
        )

    def set_files(self, selector: str, files: list[str]) -> bool:
        result = _run_node(
            "set-file-input-files",
            {"host": self.host, "port": self.port, "targetId": self.target_id, "selector": selector, "files": files},
        )
        return bool(result.get("success"))


class Browser:
    def __init__(self, host: str = "127.0.0.1", port: int = 9222):
        self.host = host
        self.port = port

    def connect(self) -> None:
        _run_node("list", {"host": self.host, "port": self.port})

    def list_pages(self) -> list[dict]:
        result = _run_node("list", {"host": self.host, "port": self.port})
        return result.get("targets", [])

    def get_or_create_page(self) -> Page:
        pages = self.list_pages()
        for target in pages:
            if target.get("type") == "page":
                tid = target.get("targetId") or target.get("id")
                if tid:
                    return Page(self.host, self.port, tid)
        result = _run_node("new-page", {"host": self.host, "port": self.port})
        return Page(self.host, self.port, result["targetId"])

    def get_page_by_target_id(self, target_id: str | None) -> Page | None:
        if not target_id:
            return None
        for target in self.list_pages():
            tid = target.get("targetId") or target.get("id")
            if tid == target_id:
                return Page(self.host, self.port, target_id)
        return None
