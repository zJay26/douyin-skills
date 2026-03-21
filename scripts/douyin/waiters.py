from __future__ import annotations

import time


def wait_for_meaningful_text(page, timeout: float = 20.0, min_len: int = 40) -> dict:
    deadline = time.time() + timeout
    last = {"title": "", "text": ""}
    while time.time() < deadline:
        data = page.evaluate(
            """
            (() => ({
              title: document.title || '',
              text: (document.body?.innerText || '').trim().slice(0, 5000)
            }))()
            """
        ) or {}
        last = data
        if len((data.get("text") or "").strip()) >= min_len:
            return data
        time.sleep(1)
    return last
