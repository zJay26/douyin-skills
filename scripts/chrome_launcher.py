#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_PORT = 9222


def has_display() -> bool:
    if os.environ.get("FORCE_HEADED") == "1":
        return True
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return True
    if sys.platform in ("darwin", "win32"):
        return True
    return Path("/tmp/.X11-unix/X0").exists() or Path("/run/user/1000/wayland-0").exists()


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
    for name in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]:
        p = shutil.which(name)
        if p:
            return p
    linux_candidates = [
        str(Path.home() / ".cache" / "ms-playwright" / "chromium-1208" / "chrome-linux64" / "chrome"),
    ]
    linux_candidates.extend(
        str(p)
        for p in sorted((Path.home() / ".cache" / "ms-playwright").glob("chromium-*/chrome-linux64/chrome"), reverse=True)
    )
    for p in linux_candidates:
        if os.path.isfile(p):
            return p
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
        result = subprocess.run(["wslpath", "-w", path], capture_output=True, text=True, check=True)
        converted = result.stdout.strip()
        return converted or path
    except Exception:
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


def _prepare_launch_cmd(chrome: str, port: int, headless: bool, user_data_dir: str) -> list[str]:
    actual_user_data_dir = user_data_dir
    if chrome.lower().endswith(".exe"):
        actual_user_data_dir = _to_windows_path(user_data_dir)
    cmd = [
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={actual_user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
    ]
    if sys.platform.startswith("linux"):
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


def _chrome_cmdline_for_port(port: int) -> str:
    try:
        result = subprocess.run(
            ["bash", "-lc", f"ps -eo args= | grep -- '--remote-debugging-port={port}' | grep -v grep | head -n 1"],
            capture_output=True,
            text=True,
            check=False,
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""


def _is_headless_process_for_port(port: int) -> bool:
    return "--headless" in _chrome_cmdline_for_port(port)


def _kill_process_for_port(port: int) -> None:
    try:
        result = subprocess.run(
            ["bash", "-lc", f"ps -eo pid=,args= | grep -- '--remote-debugging-port={port}' | grep -v grep"],
            capture_output=True,
            text=True,
            check=False,
        )
        pids: list[int] = []
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            pids.append(int(line.split(None, 1)[0]))
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for _ in range(20):
            if not is_port_open(port):
                return
            time.sleep(0.5)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except Exception:
        pass


def launch_chrome(port: int = DEFAULT_PORT, headless: bool = False, user_data_dir: str | None = None) -> subprocess.Popen:
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
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    for _ in range(40):
        if is_port_open(port):
            return proc
        time.sleep(0.5)
    raise RuntimeError(f"Chrome 启动超时: port={port}")


def ensure_chrome(port: int = DEFAULT_PORT, headless: bool = False, user_data_dir: str | None = None) -> bool:
    if is_port_open(port):
        running_headless = _is_headless_process_for_port(port)
        if headless != running_headless:
            _kill_process_for_port(port)
        else:
            return True
    launch_chrome(port=port, headless=headless, user_data_dir=user_data_dir)
    return is_port_open(port)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    ok = ensure_chrome(port=port, headless=not has_display())
    print('{"success": true, "port": %d, "running": %s}' % (port, "true" if ok else "false"))
