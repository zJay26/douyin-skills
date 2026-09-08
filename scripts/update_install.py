"""Install a verified portable release with staging and a retained backup."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from local_state import file_lock
from project_metadata import PROJECT_VERSION
from updates import config, download, home, tag_name, version_tuple

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "release-manifest.json"


def installation_lock(root: Path = ROOT):
    key = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:24]
    return file_lock(home() / "updates" / f"installation-{key}.lock", timeout=0)


def safe_member(name: str) -> Path:
    path = PurePosixPath(name)
    if (
        not name
        or any(ord(char) < 32 or char in '<>"|?*' for char in name)
        or "\\" in name
        or path.is_absolute()
        or path.as_posix() != name
        or any(
            part in {"", ".", "..", ".git", "node_modules", ".douyin-skills", ".chrome"}
            or ":" in part
            or part.endswith((".", " "))
            or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)
            for part in path.parts
        )
    ):
        raise ValueError(f"不安全的更新文件路径：{name}")
    return Path(*path.parts)


def manifest_data(raw: bytes, version: str) -> dict:
    manifest = json.loads(raw)
    if (
        not isinstance(manifest, dict)
        or manifest.get("version") != version
        or not isinstance(manifest.get("files"), dict)
    ):
        raise ValueError("更新清单无效或版本不匹配")
    files = manifest["files"]
    if not {
        "scripts/cli.py",
        "scripts/project_metadata.py",
        "package.json",
        "package-lock.json",
        "SKILL.md",
    }.issubset(files):
        raise ValueError("更新清单缺少必要运行文件")
    seen = set()
    for name, digest in files.items():
        safe_member(name)
        if (
            name == MANIFEST
            or name.casefold() in seen
            or not isinstance(digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
        ):
            raise ValueError("更新清单包含重复文件或无效哈希")
        seen.add(name.casefold())
    return manifest


def package_files(archive_path: Path, version: str) -> tuple[dict, dict[str, bytes]]:
    prefix = f"douyin-skills-{tag_name(version)}/"
    contents = {}
    size = 0
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for item in archive.infolist():
                if not item.filename.startswith(prefix) or item.is_dir():
                    raise ValueError("更新包包含非预期目录")
                name = item.filename[len(prefix) :]
                safe_member(name)
                mode = item.external_attr >> 16
                if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in {0, stat.S_IFREG}):
                    raise ValueError("更新包不允许链接或特殊文件")
                size += item.file_size
                if size > 256 * 1024 * 1024 or len(contents) >= 10000:
                    raise ValueError("解压后的更新包过大")
                if name in contents:
                    raise ValueError("更新包包含重复文件")
                contents[name] = archive.read(item)
    except zipfile.BadZipFile as error:
        raise ValueError("更新包 ZIP 或 CRC 校验失败") from error
    manifest = manifest_data(contents.get(MANIFEST, b"{}"), version)
    if set(contents) != set(manifest["files"]) | {MANIFEST}:
        raise ValueError("更新包文件与清单不一致")
    for name, digest in manifest["files"].items():
        if hashlib.sha256(contents[name]).hexdigest() != digest:
            raise ValueError(f"更新文件哈希不匹配：{name}")
    for name in ("package.json", "package-lock.json"):
        if json.loads(contents[name]).get("version") != version:
            raise ValueError("更新包内版本元数据不一致")
    return manifest, contents


def preflight(root: Path) -> dict:
    if (root / ".git").exists():
        raise ValueError(
            "Git 安装请通过 Git 或 Skill 管理器更新；可用 download-update 仅下载更新包"
        )
    if not (root / MANIFEST).is_file():
        raise ValueError(
            "仅支持带 release-manifest.json 的正式便携包原地更新；请下载并手动迁移"
        )
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in folders + files:
            candidate = Path(directory) / name
            # Refuse junctions as well as symlinks before copying or replacing trees.
            attributes = getattr(candidate.lstat(), "st_file_attributes", 0)
            if candidate.is_symlink() or attributes & 0x400:
                raise ValueError(f"安装目录含链接或联接点，请手动更新：{candidate}")
    manifest = manifest_data((root / MANIFEST).read_bytes(), PROJECT_VERSION)
    for name, digest in manifest["files"].items():
        path = root / safe_member(name)
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError(f"本地文件已修改或缺失，请保留修改并手动更新：{name}")
    return manifest


def install(version: str, *, confirm: bool, root: Path = ROOT) -> dict:
    if not confirm:
        raise ValueError("只有用户选择更新后才能传入 --confirm；当前安装保持不变")
    version = tag_name(version)[1:]
    if version_tuple(version) <= version_tuple(PROJECT_VERSION):
        raise ValueError("目标版本必须高于当前版本")
    root = root.resolve()
    original = preflight(root)
    directory = Path(config()["download_dir"]).resolve()
    if (
        directory == root
        or root in directory.parents
        or home() == root
        or root in home().parents
    ):
        raise ValueError("原地更新要求下载目录和 DOUYIN_SKILLS_HOME 位于安装目录之外")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise ValueError("安装更新需要 npm，请先安装 Node.js/npm")
    result = download(version)
    manifest, contents = package_files(Path(result["archive"]), version)
    # New release files may not overwrite unrelated local additions.
    for name in contents:
        target = root / safe_member(name)
        if name != MANIFEST and name not in original["files"] and target.exists():
            raise ValueError(f"新版本文件与本地自定义文件冲突：{name}")
    backup = root.with_name(f"{root.name}.backup-{uuid.uuid4().hex[:12]}")
    # Staging and backup remain siblings on the same filesystem for directory renames.
    with tempfile.TemporaryDirectory(
        prefix=f".{root.name}.update-", dir=root.parent
    ) as temporary:
        stage = Path(temporary) / root.name
        shutil.copytree(
            root, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
        for name in set(original["files"]) - set(manifest["files"]):
            (stage / safe_member(name)).unlink()
        for name, data in contents.items():
            destination = stage / safe_member(name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        # Do not execute lifecycle hooks from a downloaded package.
        process = subprocess.run(
            [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
            cwd=stage,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if process.returncode:
            raise RuntimeError(
                "新版依赖安装失败，当前安装保持不变；请检查 npm 网络后重试"
            )
        for command in ("version", "capabilities"):
            process = subprocess.run(
                [sys.executable, str(stage / "scripts" / "cli.py"), command],
                cwd=stage,
                capture_output=True,
                timeout=20,
                check=True,
            )
            payload = json.loads(process.stdout)
            if payload.get("version") != version or payload.get("success") is not True:
                raise ValueError("新版离线 CLI 验证失败，当前安装保持不变")
        # Check again after downloads and dependency setup, before any live mutation.
        preflight(root)
        previous_cwd = Path.cwd()
        try:
            # Windows can hold the process working directory open during a rename.
            if previous_cwd == root or root in previous_cwd.parents:
                os.chdir(root.parent)
            root.rename(backup)
            try:
                stage.rename(root)
            except OSError:
                backup.rename(root)
                raise
        except OSError as error:
            raise RuntimeError(
                f"安装目录切换失败；请关闭占用程序后重试。旧版本备份（如存在）：{backup}"
            ) from error
        finally:
            if previous_cwd.is_dir():
                os.chdir(previous_cwd)
    return {
        **result,
        "installed": True,
        "installation_dir": str(root),
        "backup_dir": str(backup),
        "message": "更新完成，下次调用使用新版本；旧安装已保留为备份。",
    }
