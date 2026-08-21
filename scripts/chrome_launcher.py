#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_PORT = 9222
_STATE_ROOT = (
    Path(
        os.environ.get("DOUYIN_SKILLS_HOME", Path.home() / ".douyin-skills")
    ).expanduser()
    / "runtime"
)


def has_display() -> bool:
    if os.environ.get("FORCE_HEADED") == "1":
        return True
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return True
    if sys.platform in ("darwin", "win32"):
        return True
    return (
        Path("/tmp/.X11-unix/X0").exists() or Path("/run/user/1000/wayland-0").exists()
    )


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


def find_chrome() -> str | None:
    env = os.getenv("CHROME_BIN")
    if env and os.path.isfile(env):
        return env
    for name in [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
    ]:
        p = shutil.which(name)
        if p:
            return p
    linux_candidates = [
        str(
            Path.home()
            / ".cache"
            / "ms-playwright"
            / "chromium-1208"
            / "chrome-linux64"
            / "chrome"
        ),
    ]
    linux_candidates.extend(
        str(p)
        for p in sorted(
            (Path.home() / ".cache" / "ms-playwright").glob(
                "chromium-*/chrome-linux64/chrome"
            ),
            reverse=True,
        )
    )
    for p in linux_candidates:
        if os.path.isfile(p):
            return p
    native_candidates: list[Path] = []
    if sys.platform == "win32":
        for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            root = os.environ.get(env_name)
            if root:
                native_candidates.append(
                    Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"
                )
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            native_candidates.append(
                Path(local_app_data) / "Chromium" / "Application" / "chrome.exe"
            )
    elif sys.platform == "darwin":
        native_candidates.extend(
            [
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
            ]
        )
    for path in native_candidates:
        if path.is_file():
            return str(path)
    windows_candidates = [
        "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
        "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    ]
    for p in windows_candidates:
        if os.path.isfile(p):
            return p
    return None


def default_profile_dir(port: int) -> str:
    return str(Path.home() / ".douyin-skills" / "chrome" / f"profile-{port}")


def _to_windows_path(path: str) -> str:
    try:
        result = subprocess.run(
            ["wslpath", "-w", path], capture_output=True, text=True, check=True
        )
        converted = result.stdout.strip()
        return converted or path
    except (OSError, subprocess.SubprocessError):
        return path


def _cleanup_stale_singleton(user_data_dir: str) -> None:
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        path = Path(user_data_dir) / name
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def _prepare_launch_cmd(
    chrome: str, port: int, headless: bool, user_data_dir: str
) -> list[str]:
    actual_user_data_dir = user_data_dir
    if chrome.lower().endswith(".exe"):
        actual_user_data_dir = _to_windows_path(user_data_dir)
    cmd = [
        chrome,
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={actual_user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
    ]
    is_root = bool(getattr(os, "geteuid", lambda: -1)() == 0)
    if sys.platform.startswith("linux") and (
        is_root or os.environ.get("DOUYIN_CHROME_NO_SANDBOX") == "1"
    ):
        cmd.append("--no-sandbox")
    if headless:
        cmd.append("--headless=new")
    return cmd


def _wslg_env() -> dict[str, str]:
    env = os.environ.copy()
    if sys.platform.startswith("linux") and Path("/tmp/.X11-unix/X0").exists():
        env.setdefault("DISPLAY", ":0")
    if sys.platform.startswith("linux") and Path("/run/user/1000/wayland-0").exists():
        env.setdefault("WAYLAND_DISPLAY", "wayland-0")
        env.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")
    return env


def _state_file(port: int) -> Path:
    return _STATE_ROOT / f"chrome-{port}.json"


def _write_runtime_state(
    port: int, pid: int, headless: bool, command: list[str]
) -> None:
    _STATE_ROOT.mkdir(parents=True, exist_ok=True)
    target = _state_file(port)
    temp = target.with_suffix(".tmp")
    temp.write_text(
        json.dumps(
            {
                "pid": pid,
                "port": port,
                "headless": headless,
                "command": command,
                "started_at": time.time(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temp, target)


def _read_runtime_state(port: int) -> dict:
    try:
        data = json.loads(_state_file(port).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def _remove_runtime_state(port: int) -> None:
    with contextlib.suppress(FileNotFoundError):
        _state_file(port).unlink()


def _process_cmdline(pid: int) -> str:
    try:
        if sys.platform.startswith("linux"):
            return (
                (Path("/proc") / str(pid) / "cmdline")
                .read_bytes()
                .replace(b"\0", b" ")
                .decode(errors="replace")
            )
        if sys.platform == "win32":
            command = (
                '$p = Get-CimInstance Win32_Process -Filter "ProcessId = '
                + str(pid)
                + '" -ErrorAction SilentlyContinue; if ($p) { $p.CommandLine }'
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            return (result.stdout or "").strip()
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return (result.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _browser_headless_state(port: int) -> bool | None:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version", timeout=2
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    user_agent = str(data.get("User-Agent", ""))
    browser = str(data.get("Browser", ""))
    if "HeadlessChrome" in user_agent or "HeadlessChrome" in browser:
        return True
    if (
        "Chrome" in user_agent
        or "Chromium" in user_agent
        or "Chrome" in browser
        or "Chromium" in browser
    ):
        return False
    return None


def _stop_tracked_browser(port: int) -> bool:
    state = _read_runtime_state(port)
    try:
        pid = int(state.get("pid", 0))
    except (TypeError, ValueError):
        pid = 0
    if pid <= 0:
        return False
    cmdline = _process_cmdline(pid)
    if f"--remote-debugging-port={port}" not in cmdline:
        _remove_runtime_state(port)
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        _remove_runtime_state(port)
        return not is_port_open(port)
    for _ in range(30):
        if not is_port_open(port):
            _remove_runtime_state(port)
            return True
        time.sleep(0.25)
    return False


def launch_chrome(
    port: int = DEFAULT_PORT, headless: bool = False, user_data_dir: str | None = None
) -> subprocess.Popen:
    chrome = find_chrome()
    if not chrome:
        raise FileNotFoundError("未找到 Chrome/Chromium")
    user_data_dir = user_data_dir or default_profile_dir(port)
    os.makedirs(user_data_dir, exist_ok=True)
    _cleanup_stale_singleton(user_data_dir)
    cmd = _prepare_launch_cmd(chrome, port, headless, user_data_dir)
    env = _wslg_env()
    if not headless and has_display():
        env["FORCE_HEADED"] = "1"
    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
    )
    for _ in range(40):
        if is_port_open(port):
            _write_runtime_state(port, proc.pid, headless, cmd)
            return proc
        time.sleep(0.5)
    with contextlib.suppress(OSError):
        proc.terminate()
    raise RuntimeError(f"Chrome 启动超时: port={port}")


def ensure_chrome(
    port: int = DEFAULT_PORT,
    headless: bool = False,
    user_data_dir: str | None = None,
    *,
    force_mode: bool = False,
) -> bool:
    """Ensure a usable loopback Chrome debugging instance is available.

    An existing local debugging browser owns the user's live session, so it is
    reused even when its headed/headless mode differs from the caller's
    preference.  Callers that explicitly need a mode transition (for example,
    switching to a visible browser for human verification) can set
    ``force_mode``.  Such a transition is allowed only for a browser tracked by
    this launcher.
    """
    if is_port_open(port):
        running_headless = _browser_headless_state(port)
        if running_headless is None:
            raise RuntimeError(
                f"端口 {port} 已被占用，但无法确认是可用的本地 Chrome 调试端口"
            )
        if headless == running_headless or not force_mode:
            return True
        if not _stop_tracked_browser(port):
            raise RuntimeError(
                f"端口 {port} 上的 Chrome 不是由 douyin-skills 启动，无法安全切换浏览器模式；请先手动关闭该调试实例"
            )
    launch_chrome(port=port, headless=headless, user_data_dir=user_data_dir)
    return is_port_open(port)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    ok = ensure_chrome(port=port, headless=not has_display())
    print(
        json.dumps({"success": True, "port": port, "running": ok}, ensure_ascii=False)
    )
