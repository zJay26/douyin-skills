"""Optional release checks and verified downloads; never install in the worker."""

from __future__ import annotations

import contextlib
import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from local_state import atomic_write, file_lock
from project_metadata import PROJECT_VERSION

REPOSITORY = "zJay26/douyin-skills"
API = f"https://api.github.com/repos/{REPOSITORY}/releases"
RELEASES = f"https://github.com/{REPOSITORY}/releases"
INTERVAL_SECONDS = 6 * 60 * 60
VERSION_RE = re.compile(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
ERRORS = (OSError, RuntimeError, ValueError, TypeError)


def home() -> Path:
    return (
        Path(os.environ.get("DOUYIN_SKILLS_HOME", Path.home() / ".douyin-skills"))
        .expanduser()
        .resolve()
    )


def state_path(name: str) -> Path:
    return home() / "updates" / name


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"配置必须是 JSON 对象：{path}")
    return value


def write_json(path: Path, value: dict) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2))


def version_tuple(value: str) -> tuple[int, ...]:
    if not isinstance(value, str):
        raise ValueError("更新版本必须是字符串")
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ValueError("更新版本必须是稳定版本，例如 v1.6.0")
    return tuple(int(part) for part in match.groups())


def tag_name(value: str) -> str:
    return "v" + ".".join(str(part) for part in version_tuple(value))


def config() -> dict:
    saved = read_json(state_path("config.json"))
    result = {
        "auto_check": saved.get("auto_check", True),
        "interval_hours": saved.get("interval_hours", 6),
        "download_dir": saved.get("download_dir", str(home() / "downloads")),
    }
    if type(result["auto_check"]) is not bool:
        raise ValueError("auto_check 必须是布尔值")
    if (
        type(result["interval_hours"]) is not int
        or not 1 <= result["interval_hours"] <= 168
    ):
        raise ValueError("interval_hours 必须是 1 到 168 的整数")
    directory = result["download_dir"]
    if not isinstance(directory, str) or not directory.strip():
        raise ValueError("download_dir 必须是非空目录路径")
    if not Path(directory).is_absolute():
        raise ValueError("保存的下载目录必须是绝对路径")
    return result


def configure(*, auto_check=None, interval_hours=None, download_dir=None) -> dict:
    with file_lock(state_path("config.lock")):
        current = config()
        if auto_check is not None:
            if type(auto_check) is not bool:
                raise ValueError("auto_check 必须是布尔值")
            current["auto_check"] = auto_check
        if interval_hours is not None:
            if type(interval_hours) is not int or not 1 <= interval_hours <= 168:
                raise ValueError("检查间隔必须是 1 到 168 小时")
            current["interval_hours"] = interval_hours
        if download_dir is not None:
            if not str(download_dir).strip():
                raise ValueError("下载目录不能为空")
            directory = Path(download_dir).expanduser().resolve()
            directory.mkdir(parents=True, exist_ok=True)
            # Verify writability without leaving a file or replacing user data.
            with tempfile.TemporaryFile(dir=directory):
                pass
            current["download_dir"] = str(directory)
        write_json(state_path("config.json"), current)
    return {"success": True, **current}


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if (
            parsed.scheme != "https"
            or parsed.hostname
            not in {
                "api.github.com",
                "github.com",
                "release-assets.githubusercontent.com",
                "objects.githubusercontent.com",
            }
            or parsed.username
            or parsed.password
            or parsed.port not in {None, 443}
        ):
            raise ValueError("更新下载重定向到了非 GitHub HTTPS 地址")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str, stream, limit: int) -> None:
    """Bound response size, socket timeout and total transfer duration."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"douyin-skills/{PROJECT_VERSION}",
            "Accept": "application/vnd.github+json"
            if url.startswith(API)
            else "application/octet-stream",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
    opener = urllib.request.build_opener(SafeRedirect())
    deadline = time.monotonic() + 180
    try:
        with opener.open(request, timeout=15) as response:
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit or time.monotonic() > deadline:
                    raise ValueError("更新响应过大或下载超时")
                stream.write(chunk)
    except urllib.error.HTTPError as error:
        # Never persist a signed redirect URL or authorization material.
        raise RuntimeError(
            f"GitHub 更新请求失败（HTTP {error.code}），请稍后重试"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError("无法连接 GitHub 更新服务，请检查网络后重试") from error
    except http.client.HTTPException as error:
        raise RuntimeError("GitHub 更新响应中断，请稍后重试") from error


def fetch_bytes(url: str, limit: int = 2 * 1024 * 1024) -> bytes:
    import io

    buffer = io.BytesIO()
    fetch(url, buffer, limit)
    return buffer.getvalue()


def release_info(version: str | None = None) -> dict:
    requested = tag_name(version) if version else None
    url = f"{API}/tags/{requested}" if requested else f"{API}/latest"
    release = json.loads(fetch_bytes(url))
    if (
        not isinstance(release, dict)
        or release.get("draft") is not False
        or release.get("prerelease") is not False
    ):
        raise ValueError("更新服务未返回正式稳定 Release")
    tag = tag_name(release.get("tag_name", ""))
    if release["tag_name"] != tag or (requested and tag != requested):
        raise ValueError("Release 版本与请求不匹配")
    archive_name = f"douyin-skills-{tag}.zip"
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("Release 资产列表无效")
    for name in (archive_name, "SHA256SUMS"):
        matches = [
            asset
            for asset in assets
            if isinstance(asset, dict) and asset.get("name") == name
        ]
        expected = f"{RELEASES}/download/{tag}/{name}"
        if (
            len(matches) != 1
            or matches[0].get("browser_download_url") != expected
            or matches[0].get("state") != "uploaded"
        ):
            raise ValueError(f"Release 缺少完整的官方更新资产：{name}")
    return {
        "version": tag[1:],
        "tag": tag,
        "release_url": f"{RELEASES}/tag/{tag}",
        "archive_name": archive_name,
        "archive_url": f"{RELEASES}/download/{tag}/{archive_name}",
        "checksum_url": f"{RELEASES}/download/{tag}/SHA256SUMS",
        "notes": str(release.get("body") or "")[:20000],
    }


def is_due(state: dict, settings: dict, now: float) -> bool:
    last = state.get("last_attempt_at", 0)
    if not isinstance(last, (int, float)):
        return True
    return not last or now < last or now - last >= settings["interval_hours"] * 3600


def check(*, force: bool = True) -> dict:
    with file_lock(state_path("check.lock"), timeout=0):
        settings = config()
        state = read_json(state_path("state.json"))
        now = time.time()
        if not force and (
            not settings["auto_check"] or not is_due(state, settings, now)
        ):
            return status()
        state["last_attempt_at"] = now
        # Persist attempts before networking, including failures/crashes: no retry storm.
        write_json(state_path("state.json"), state)
        try:
            release = release_info()
        except ERRORS as error:
            state["last_error"] = str(error)
            write_json(state_path("state.json"), state)
            raise
        state.update(release=release, last_checked_at=time.time(), last_error=None)
        write_json(state_path("state.json"), state)
    return status()


def status() -> dict:
    settings = config()
    state = read_json(state_path("state.json"))
    release = state.get("release") or {}
    if not isinstance(release, dict) or (release and not release.get("version")):
        raise ValueError("本地更新状态无效，请运行 check-update 刷新")
    available = bool(release) and version_tuple(release["version"]) > version_tuple(
        PROJECT_VERSION
    )
    last = state.get("last_attempt_at")
    return {
        "success": True,
        "current_version": PROJECT_VERSION,
        **settings,
        "update_available": available,
        "release": release or None,
        "last_attempt_at": last,
        "last_checked_at": state.get("last_checked_at"),
        "last_error": state.get("last_error"),
        "next_check_at": last + settings["interval_hours"] * 3600
        if settings["auto_check"] and isinstance(last, (int, float))
        else None,
        "requires_confirmation": True,
    }


def notification() -> dict | None:
    if os.environ.get("DOUYIN_SKILLS_NO_UPDATE_CHECK") == "1":
        return None
    with contextlib.suppress(*ERRORS):
        info = status()
        if info["auto_check"] and info["update_available"]:
            release = info["release"]
            tag = tag_name(release["version"])
            return {
                "current_version": PROJECT_VERSION,
                "latest_version": release["version"],
                "release_url": f"{RELEASES}/tag/{tag}",
                "requires_confirmation": True,
                "message": "发现新版本，可选择更新或继续使用当前版本。",
                "download_command": f"download-update --version {tag}",
                "install_command": f"install-update --version {tag} --confirm",
            }
    return None


def download(version: str) -> dict:
    tag = tag_name(version)
    if version_tuple(tag) <= version_tuple(PROJECT_VERSION):
        raise ValueError("目标版本必须高于当前版本；不会降级或重复更新")
    release = release_info(tag)
    directory = Path(config()["download_dir"]) / tag
    directory.mkdir(parents=True, exist_ok=True)
    with file_lock(directory / ".download.lock"):
        checksum_bytes = fetch_bytes(release["checksum_url"], 64 * 1024)
        matches = re.findall(
            r"^([a-fA-F0-9]{64})  " + re.escape(release["archive_name"]) + r"\r?$",
            checksum_bytes.decode("ascii"),
            re.MULTILINE,
        )
        if len(matches) != 1:
            raise ValueError("SHA256SUMS 缺少唯一匹配的更新包校验值")
        expected = matches[0].lower()
        destination = directory / release["archive_name"]
        descriptor, name = tempfile.mkstemp(
            prefix=".download-", suffix=".part", dir=directory
        )
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                fetch(release["archive_url"], stream, MAX_ARCHIVE_BYTES)
            digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
            if digest != expected:
                raise ValueError("更新包 SHA-256 校验失败，已拒绝使用")
            os.replace(temporary, destination)
            atomic_write(directory / "SHA256SUMS", checksum_bytes.decode("ascii"))
        finally:
            temporary.unlink(missing_ok=True)
    return {
        "success": True,
        "version": tag[1:],
        "archive": str(destination),
        "sha256": expected,
        "installed": False,
    }


def start_worker() -> None:
    if os.environ.get("DOUYIN_SKILLS_NO_UPDATE_CHECK") == "1":
        return
    with contextlib.suppress(*ERRORS):
        if not config()["auto_check"]:
            return
        with file_lock(state_path("launch.lock"), timeout=0):
            # A live worker holds this OS lock for its entire lifetime.
            try:
                with file_lock(state_path("worker.lock"), timeout=0):
                    pass
            except RuntimeError:
                return
            launched = read_json(state_path("launch.json")).get("at", 0)
            if 0 <= time.time() - launched < 30:
                return
            env = os.environ.copy()
            env["DOUYIN_SKILLS_HOME"] = str(home())
            options = (
                {
                    "creationflags": subprocess.CREATE_NO_WINDOW
                    | subprocess.DETACHED_PROCESS
                }
                if os.name == "nt"
                else {"start_new_session": True}
            )
            subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--worker"],
                cwd=home(),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                **options,
            )
            write_json(state_path("launch.json"), {"at": time.time()})


def worker() -> None:
    with file_lock(state_path("worker.lock"), timeout=0):
        while config()["auto_check"]:
            with contextlib.suppress(*ERRORS):
                check(force=False)
            # Read switches frequently; HTTP requests already in progress may finish.
            time.sleep(5)


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        raise SystemExit("Use scripts/cli.py for update commands")
    with contextlib.suppress(*ERRORS):
        worker()
