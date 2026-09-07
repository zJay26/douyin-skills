#!/usr/bin/env python3
"""Exercise real Chrome against a synthetic local page in a temporary profile."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from browser_runtime import Browser, CDPError
from chrome_launcher import launch_chrome


def smoke_browser() -> dict:
    temporary = tempfile.TemporaryDirectory(prefix="douyin-chrome-smoke-")
    with temporary as directory:
        root = Path(directory)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        # Keep the launcher's tracking data in this disposable directory too.
        import chrome_launcher

        previous_state_root = chrome_launcher._STATE_ROOT
        chrome_launcher._STATE_ROOT = root / "runtime"
        process = None
        try:
            process = launch_chrome(
                port=port, headless=True, user_data_dir=str(root / "profile")
            )
            browser = Browser(port=port)
            version = browser.version()
            print("Chrome connected", file=sys.stderr)
            page = browser.new_page()
            markup = """<!doctype html><meta charset="utf-8"><title>Local smoke</title>
                <input id="text"><input id="file" type="file">
                <div id="editor" contenteditable="true"></div>
                <button id="click" onclick="this.dataset.count=String(Number(this.dataset.count||0)+1)">Test</button>"""
            page.navigate("data:text/html;charset=utf-8," + quote(markup))
            page.wait_for_load(5)
            print("Synthetic page loaded", file=sys.stderr)
            if page.evaluate("document.title") != "Local smoke":
                raise RuntimeError("synthetic page did not load")
            text = "中文输入 😀"
            if (
                not page.type_text("#text", text)
                or page.evaluate("document.querySelector('#text').value") != text
            ):
                raise RuntimeError("Unicode form input failed")
            page.evaluate("document.querySelector('#editor').focus()")
            page.insert_text(text)
            if page.evaluate("document.querySelector('#editor').innerText") != text:
                raise RuntimeError("native editor input failed")
            print("Unicode input verified", file=sys.stderr)
            upload = root / "素材.txt"
            upload.write_text("synthetic upload", encoding="utf-8")
            if not page.set_files("#file", [str(upload)]):
                raise RuntimeError("file input failed")
            if (
                page.evaluate("document.querySelector('#file').files[0].name")
                != upload.name
            ):
                raise RuntimeError("Unicode upload path did not round-trip")
            print("File input verified", file=sys.stderr)
            page.click("#click")
            if page.evaluate("document.querySelector('#click').dataset.count") != "1":
                raise RuntimeError("synthetic click was not observed exactly once")
            try:
                page.evaluate("(() => { throw new Error('synthetic exception'); })()")
            except CDPError as error:
                if error.code != "evaluation_failed":
                    raise
            else:
                raise RuntimeError(
                    "JavaScript exception was incorrectly reported as success"
                )
            return {
                "success": True,
                "browser": version["browser"],
                "checks": [
                    "navigation",
                    "unicode_input",
                    "native_editor",
                    "file_upload",
                    "single_click",
                    "javascript_exception",
                ],
                "page_source": "synthetic data URL",
                "used_real_account": False,
            }
        finally:
            if process is not None and process.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                        timeout=10,
                    )
                else:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            chrome_launcher._STATE_ROOT = previous_state_root
            # Windows can retain Crashpad mappings briefly after tree shutdown.
            for attempt in range(10):
                try:
                    temporary.cleanup()
                    break
                except OSError:
                    if attempt == 9:
                        raise
                    time.sleep(0.5)


if __name__ == "__main__":
    try:
        print(json.dumps(smoke_browser(), ensure_ascii=False, indent=2))
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        raise SystemExit(1) from error
