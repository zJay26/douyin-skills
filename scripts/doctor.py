from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from account_manager import list_accounts
from chrome_launcher import find_chrome, has_display

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _command_version(command: str, *args: str) -> tuple[bool, str]:
    executable = shutil.which(command)
    if not executable:
        return False, "未找到"
    try:
        result = subprocess.run(
            [executable, *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    output = (result.stdout or result.stderr or "").strip().splitlines()
    detail = output[0] if output else f"退出码 {result.returncode}"
    return result.returncode == 0, detail


def _check_ws() -> tuple[bool, str]:
    node = shutil.which("node")
    if not node:
        return False, "Node.js 未安装"
    try:
        result = subprocess.run(
            [
                node,
                "--input-type=module",
                "-e",
                "import('ws').then(() => console.log('ws available'))",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if result.returncode == 0:
        return True, (result.stdout or "ws available").strip()
    return False, "未安装；请在 Skill 根目录运行 npm install"


def run_doctor() -> dict:
    node_ok, node_detail = _command_version("node", "--version")
    npm_ok, npm_detail = _command_version("npm", "--version")
    ws_ok, ws_detail = _check_ws()
    chrome = find_chrome()

    checks = [
        {
            "name": "python",
            "ok": sys.version_info >= (3, 9),
            "required": True,
            "detail": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        },
        {"name": "node", "ok": node_ok, "required": True, "detail": node_detail},
        {"name": "npm", "ok": npm_ok, "required": False, "detail": npm_detail},
        {"name": "ws", "ok": ws_ok, "required": True, "detail": ws_detail},
        {
            "name": "chrome",
            "ok": bool(chrome),
            "required": True,
            "detail": chrome or "未找到 Chrome/Chromium",
        },
        {
            "name": "display",
            "ok": has_display(),
            "required": False,
            "detail": "可在风控时切换到有头模式"
            if has_display()
            else "无图形环境；遇到验证码时需要可见桌面",
        },
    ]
    required_failures = [
        check["name"] for check in checks if check["required"] and not check["ok"]
    ]
    accounts = list_accounts()
    return {
        "success": not required_failures,
        "checks": checks,
        "required_failures": required_failures,
        "accounts": {"count": len(accounts), "items": accounts},
        "project_root": str(PROJECT_ROOT),
        "message": "运行环境已就绪"
        if not required_failures
        else "运行环境尚未就绪，请处理 required_failures",
    }
