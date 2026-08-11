#!/usr/bin/env python3
"""Build a deterministic, checksum-verifiable douyin-skills release archive."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import tempfile
import time
import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from project_metadata import PROJECT_NAME, PROJECT_VERSION

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
EXCLUDED_PARTS = {
    ".chrome",
    ".douyin-skills",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "env",
    "node_modules",
    "playwright-report",
    "venv",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyd", ".pyo"}


def normalize_version(value: str) -> str:
    match = VERSION_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(
            "version must use stable semantic versioning, for example v1.0.0"
        )
    return ".".join(match.groups())


def safe_relative_path(value: str) -> PurePosixPath:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        path.is_absolute()
        or not path.parts
        or re.fullmatch(r"[A-Za-z]:", path.parts[0]) is not None
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"unsafe archive path: {value}")
    return path


def should_include(value: str) -> bool:
    path = safe_relative_path(value)
    return (
        not EXCLUDED_PARTS.intersection(path.parts)
        and path.suffix.lower() not in EXCLUDED_SUFFIXES
    )


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git ls-files failed: {detail or result.returncode}")
    values = result.stdout.decode("utf-8").split("\0")
    files = sorted(value for value in values if value and should_include(value))
    if not files:
        raise RuntimeError("no tracked project files were found")
    return files


def source_date_epoch(root: Path) -> int:
    configured = os.environ.get("SOURCE_DATE_EPOCH")
    if configured:
        try:
            value = int(configured)
        except ValueError as error:
            raise ValueError("SOURCE_DATE_EPOCH must be an integer") from error
        if value < 0:
            raise ValueError("SOURCE_DATE_EPOCH must not be negative")
        return value

    result = subprocess.run(
        ["git", "-C", str(root), "show", "-s", "--format=%ct", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip().isdigit():
        raise RuntimeError("could not read the current commit timestamp")
    return int(result.stdout.strip())


def _zip_timestamp(epoch: int) -> tuple[int, int, int, int, int, int]:
    earliest_zip_epoch = 315532800  # 1980-01-01T00:00:00Z
    return time.gmtime(max(epoch, earliest_zip_epoch))[:6]


def build_archive(
    root: Path,
    relative_files: Iterable[str],
    output: Path,
    prefix: str,
    epoch: int,
) -> str:
    prefix_path = safe_relative_path(prefix)
    if len(prefix_path.parts) != 1:
        raise ValueError("archive prefix must be one directory name")

    root = root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    timestamp = _zip_timestamp(epoch)
    entries: list[tuple[PurePosixPath, bytes]] = []

    for value in sorted(set(relative_files)):
        relative = safe_relative_path(value)
        if not should_include(relative.as_posix()):
            continue
        candidate = root / Path(*relative.parts)
        if candidate.is_symlink():
            raise ValueError(
                f"symbolic links are not allowed in release archives: {value}"
            )
        source = candidate.resolve()
        try:
            source.relative_to(root)
        except ValueError as error:
            raise ValueError(f"archive source escapes repository: {value}") from error
        if not source.is_file():
            raise FileNotFoundError(f"tracked release file is missing: {value}")
        entries.append((relative, source.read_bytes()))

    if not entries:
        raise ValueError("release archive would be empty")

    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.comment = b""
            for relative, data in entries:
                name = (prefix_path / relative).as_posix()
                info = zipfile.ZipInfo(name, date_time=timestamp)
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.internal_attr = 0
                info.extra = b""
                info.comment = b""
                archive.writestr(info, data)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()

    return hashlib.sha256(output.read_bytes()).hexdigest()


def build_release(root: Path, version: str, output_dir: Path) -> tuple[Path, Path, str]:
    normalized = normalize_version(version)
    if normalized != PROJECT_VERSION:
        raise ValueError(
            f"requested version {normalized} does not match runtime version {PROJECT_VERSION}"
        )
    archive_name = f"{PROJECT_NAME}-v{normalized}.zip"
    output_dir = output_dir.resolve()
    archive_path = output_dir / archive_name
    checksum_path = output_dir / "SHA256SUMS"
    digest = build_archive(
        root=root,
        relative_files=tracked_files(root),
        output=archive_path,
        prefix=f"{PROJECT_NAME}-v{normalized}",
        epoch=source_date_epoch(root),
    )
    checksum_path.write_bytes(f"{digest}  {archive_name}\n".encode("ascii"))
    return archive_path, checksum_path, digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=f"v{PROJECT_VERSION}")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        archive, checksums, digest = build_release(ROOT, args.version, args.output_dir)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(f"Release build failed: {error}")
        return 1
    print(f"Created {archive}")
    print(f"Created {checksums}")
    print(f"SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
