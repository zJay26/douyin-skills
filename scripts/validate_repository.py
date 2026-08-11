#!/usr/bin/env python3
"""Validate repository-facing documentation and release presentation assets."""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from project_metadata import PROJECT_VERSION

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_OWNER = "zJay26"
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HTML_LINK_RE = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']", re.IGNORECASE)
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
REPOSITORY_RE = re.compile(
    r"(?:https://github\.com/|git:)([A-Za-z0-9_.-]+)/douyin-skills(?:\.git)?",
    re.IGNORECASE,
)
TEXT_SUFFIXES = {
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".toml",
    ".yaml",
    ".yml",
}
IGNORED_PARTS = {".git", ".douyin-skills", "dist", "node_modules"}


@dataclass(frozen=True)
class GifMetadata:
    width: int
    height: int
    frames: int
    duration_seconds: float
    loops: bool


def _skip_sub_blocks(data: bytes, offset: int) -> tuple[int, bytes]:
    chunks: list[bytes] = []
    while True:
        if offset >= len(data):
            raise ValueError("truncated GIF sub-block")
        size = data[offset]
        offset += 1
        if size == 0:
            return offset, b"".join(chunks)
        end = offset + size
        if end > len(data):
            raise ValueError("truncated GIF sub-block data")
        chunks.append(data[offset:end])
        offset = end


def parse_gif(path: Path) -> GifMetadata:
    data = path.read_bytes()
    if len(data) < 13 or data[:6] not in {b"GIF87a", b"GIF89a"}:
        raise ValueError("not a valid GIF header")

    width = int.from_bytes(data[6:8], "little")
    height = int.from_bytes(data[8:10], "little")
    packed = data[10]
    offset = 13
    if packed & 0x80:
        offset += 3 * (2 ** ((packed & 0x07) + 1))

    frames = 0
    delays: list[int] = []
    pending_delay = 0
    loops = False

    while offset < len(data):
        marker = data[offset]
        offset += 1
        if marker == 0x3B:
            break
        if marker == 0x21:
            if offset >= len(data):
                raise ValueError("truncated GIF extension")
            label = data[offset]
            offset += 1
            if label == 0xF9:
                if offset + 6 > len(data) or data[offset] != 4:
                    raise ValueError("invalid GIF graphic control extension")
                pending_delay = int.from_bytes(data[offset + 2 : offset + 4], "little")
                offset += 6
            elif label == 0xFF:
                if offset >= len(data):
                    raise ValueError("truncated GIF application extension")
                block_size = data[offset]
                offset += 1
                end = offset + block_size
                if end > len(data):
                    raise ValueError("truncated GIF application identifier")
                identifier = data[offset:end]
                offset, payload = _skip_sub_blocks(data, end)
                if identifier.startswith(b"NETSCAPE") and payload.startswith(b"\x01"):
                    loops = True
            else:
                offset, _ = _skip_sub_blocks(data, offset)
            continue
        if marker == 0x2C:
            if offset + 9 > len(data):
                raise ValueError("truncated GIF image descriptor")
            image_packed = data[offset + 8]
            offset += 9
            if image_packed & 0x80:
                offset += 3 * (2 ** ((image_packed & 0x07) + 1))
            if offset >= len(data):
                raise ValueError("truncated GIF image data")
            offset += 1  # LZW minimum code size
            offset, _ = _skip_sub_blocks(data, offset)
            frames += 1
            delays.append(pending_delay)
            pending_delay = 0
            continue
        raise ValueError(f"unexpected GIF block marker 0x{marker:02x}")

    if frames == 0:
        raise ValueError("GIF contains no image frames")
    return GifMetadata(
        width=width,
        height=height,
        frames=frames,
        duration_seconds=sum(delays) / 100,
        loops=loops,
    )


def _fallback_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and not IGNORED_PARTS.intersection(path.relative_to(root).parts)
    )


def repository_files(root: Path) -> list[Path]:
    if (root / ".git").exists():
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return [root / line for line in result.stdout.splitlines() if line]
    return _fallback_files(root)


def extract_local_links(markdown: str) -> list[tuple[int, str]]:
    matches = list(MARKDOWN_LINK_RE.finditer(markdown))
    matches.extend(HTML_LINK_RE.finditer(markdown))
    links: list[tuple[int, str]] = []
    for match in sorted(matches, key=lambda item: item.start()):
        raw = html.unescape(match.group(1).strip())
        if raw.startswith("<") and ">" in raw:
            raw = raw[1 : raw.index(">")]
        elif " " in raw:
            raw = raw.split(" ", 1)[0]
        parsed = urlsplit(raw)
        if not raw or raw.startswith("#") or parsed.scheme or parsed.netloc:
            continue
        path = unquote(parsed.path)
        if not path:
            continue
        line = markdown.count("\n", 0, match.start()) + 1
        links.append((line, path))
    return links


def contains_cjk(text: str) -> bool:
    return CJK_RE.search(text) is not None


def _check_markdown_links(root: Path, files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in (item for item in files if item.suffix.lower() == ".md"):
        content = path.read_text(encoding="utf-8")
        for line, target_text in extract_local_links(content):
            if target_text.startswith("/"):
                target = root / target_text.lstrip("/")
            else:
                target = path.parent / target_text
            resolved = target.resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(
                    f"{path.relative_to(root)}:{line}: link escapes repository: {target_text}"
                )
                continue
            if not resolved.exists():
                errors.append(
                    f"{path.relative_to(root)}:{line}: missing link target: {target_text}"
                )
    return errors


def _check_repository_owners(root: Path, files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in (item for item in files if item.suffix.lower() in TEXT_SUFFIXES):
        content = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(content.splitlines(), start=1):
            for match in REPOSITORY_RE.finditer(line):
                if match.group(1).lower() != EXPECTED_OWNER.lower():
                    errors.append(
                        f"{path.relative_to(root)}:{line_number}: "
                        f"repository owner must be {EXPECTED_OWNER}, found {match.group(1)}"
                    )
    return errors


def _check_visual_assets(root: Path) -> list[str]:
    errors: list[str] = []
    required = [
        Path("assets/demo.gif"),
        Path("assets/demo/index.html"),
        Path("assets/hero-agent.svg"),
        Path("CHANGELOG.md"),
        Path("docs/RELEASING.md"),
        Path("docs/VALIDATION.md"),
        Path(f"docs/releases/v{PROJECT_VERSION}.md"),
    ]
    for relative in required:
        if not (root / relative).is_file():
            errors.append(f"missing required repository asset: {relative.as_posix()}")

    for relative in [Path("assets/demo/index.html"), Path("assets/hero-agent.svg")]:
        path = root / relative
        if path.is_file() and contains_cjk(path.read_text(encoding="utf-8")):
            errors.append(f"visual asset contains CJK text: {relative.as_posix()}")

    demo_source = root / "assets" / "demo" / "index.html"
    if demo_source.is_file():
        source = demo_source.read_text(encoding="utf-8")
        network_patterns = [
            r"\bfetch\s*\(",
            r"\bXMLHttpRequest\b",
            r"\bnew\s+WebSocket\b",
            r"(?:src|href)=[\"']https?://",
            r"url\(\s*[\"']?https?://",
        ]
        for pattern in network_patterns:
            if re.search(pattern, source, re.IGNORECASE):
                errors.append(f"demo source contains a network primitive: {pattern}")

    gif_path = root / "assets" / "demo.gif"
    if gif_path.is_file():
        try:
            metadata = parse_gif(gif_path)
        except ValueError as error:
            errors.append(f"invalid demo GIF: {error}")
        else:
            if (metadata.width, metadata.height) != (960, 540):
                errors.append(
                    "demo GIF must be 960x540, found "
                    f"{metadata.width}x{metadata.height}"
                )
            if not 30 <= metadata.duration_seconds <= 45:
                errors.append(
                    "demo GIF duration must be 30-45 seconds, found "
                    f"{metadata.duration_seconds:.2f}"
                )
            if metadata.frames < 100:
                errors.append(
                    f"demo GIF must contain at least 100 frames, found {metadata.frames}"
                )
            if not metadata.loops:
                errors.append(
                    "demo GIF must contain an infinite-loop application extension"
                )

    readme = root / "README.md"
    if readme.is_file() and "./assets/demo.gif" not in readme.read_text(
        encoding="utf-8"
    ):
        errors.append("README.md does not embed ./assets/demo.gif")
    return errors


def _check_version_consistency(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in [Path("package.json"), Path("package-lock.json")]:
        path = root / relative
        if not path.is_file():
            errors.append(f"missing package metadata: {relative.as_posix()}")
            continue
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            errors.append(f"invalid {relative.as_posix()}: {error}")
            continue
        if metadata.get("version") != PROJECT_VERSION:
            errors.append(
                f"{relative.as_posix()} version must be {PROJECT_VERSION}, "
                f"found {metadata.get('version')!r}"
            )

    lock_path = root / "package-lock.json"
    if lock_path.is_file():
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            root_package_version = lock.get("packages", {}).get("", {}).get("version")
        except (json.JSONDecodeError, OSError):
            root_package_version = None
        if root_package_version != PROJECT_VERSION:
            errors.append(
                "package-lock.json root package version must be "
                f"{PROJECT_VERSION}, found {root_package_version!r}"
            )

    release_note = root / "docs" / "releases" / f"v{PROJECT_VERSION}.md"
    if not release_note.is_file():
        errors.append(
            f"missing versioned release note: {release_note.relative_to(root)}"
        )
    return errors


def validate_repository(root: Path = ROOT) -> list[str]:
    files = repository_files(root)
    errors = _check_markdown_links(root, files)
    errors.extend(_check_repository_owners(root, files))
    errors.extend(_check_visual_assets(root))
    errors.extend(_check_version_consistency(root))
    return errors


def main() -> int:
    errors = validate_repository()
    if errors:
        print("Repository validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    metadata = parse_gif(ROOT / "assets" / "demo.gif")
    print(
        "Repository validation passed: "
        f"demo={metadata.width}x{metadata.height}, "
        f"{metadata.frames} frames, {metadata.duration_seconds:.2f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
