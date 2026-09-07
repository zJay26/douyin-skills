#!/usr/bin/env python3
"""Build twice, compare archives and run the packaged offline CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from build_release import ROOT, build_release, safe_relative_path
from project_metadata import PROJECT_NAME, PROJECT_VERSION, version_payload


def validate_release(root: Path = ROOT) -> dict:
    with tempfile.TemporaryDirectory(prefix="douyin-release-") as directory:
        temporary = Path(directory)
        first, checksums, digest = build_release(
            root, PROJECT_VERSION, temporary / "first"
        )
        second, _, second_digest = build_release(
            root, PROJECT_VERSION, temporary / "second"
        )
        if digest != second_digest or first.read_bytes() != second.read_bytes():
            raise ValueError("release archives are not byte-identical")
        if checksums.read_text(encoding="ascii") != f"{digest}  {first.name}\n":
            raise ValueError("release checksum does not match the archive")
        prefix = f"{PROJECT_NAME}-v{PROJECT_VERSION}"
        extraction = temporary / "extracted"
        with zipfile.ZipFile(first) as archive:
            if archive.testzip() is not None:
                raise ValueError("release archive CRC check failed")
            for member in archive.namelist():
                if safe_relative_path(member).parts[0] != prefix:
                    raise ValueError(
                        "release member is outside the versioned directory"
                    )
            archive.extractall(extraction)
        packaged = extraction / prefix
        results = {}
        for command in ("version", "capabilities"):
            process = subprocess.run(
                [sys.executable, str(packaged / "scripts" / "cli.py"), command],
                cwd=packaged,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=15,
                check=True,
            )
            results[command] = json.loads(process.stdout)
        if results["version"] != version_payload():
            raise ValueError("packaged CLI version does not match source metadata")
        if not results["capabilities"].get("commands"):
            raise ValueError("packaged CLI is missing command discovery")
        return {
            "success": True,
            "version": PROJECT_VERSION,
            "sha256": digest,
            "bytes": first.stat().st_size,
            "commands": len(results["capabilities"]["commands"]),
        }


if __name__ == "__main__":
    try:
        print(json.dumps(validate_release(), indent=2))
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"success": False, "error": str(error)}))
        raise SystemExit(1) from error
