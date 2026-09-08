#!/usr/bin/env python3
"""Build twice, compare archives and run the packaged offline CLI."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from build_release import ROOT, build_release, safe_relative_path
from project_metadata import PROJECT_NAME, PROJECT_VERSION, version_payload
from update_install import MANIFEST, package_files


def validate_portable_update(packaged: Path, archive: Path, temporary: Path) -> None:
    """Exercise real dependency setup, directory swap and next CLI invocation.

    Only the GitHub download is replaced by the already verified local archive.
    A synthetic older version is confined to the disposable extraction.
    """
    old = temporary / "old-portable"
    shutil.copytree(
        packaged, old, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    metadata = old / "scripts" / "project_metadata.py"
    metadata.write_bytes(
        metadata.read_bytes().replace(
            f'PROJECT_VERSION = "{PROJECT_VERSION}"'.encode(),
            b'PROJECT_VERSION = "0.0.0"',
        )
    )
    for name in ("package.json", "package-lock.json"):
        path = old / name
        data = json.loads(path.read_bytes())
        data["version"] = "0.0.0"
        if name == "package-lock.json":
            data["packages"][""]["version"] = "0.0.0"
        path.write_bytes(json.dumps(data).encode())
    manifest = json.loads((old / MANIFEST).read_bytes())
    manifest["version"] = "0.0.0"
    for name in manifest["files"]:
        manifest["files"][name] = hashlib.sha256((old / name).read_bytes()).hexdigest()
    (old / MANIFEST).write_bytes(json.dumps(manifest).encode())
    (old / "user-note.txt").write_bytes(b"preserve local addition")
    state = temporary / "update-state"
    state.mkdir()
    (state / "accounts.json").write_bytes(b"synthetic account sentinel")
    env = {
        **os.environ,
        "DOUYIN_SKILLS_HOME": str(state),
        "DOUYIN_SKILLS_NO_UPDATE_CHECK": "1",
        "npm_config_offline": "true",
    }
    runner = temporary / "exercise_update.py"
    runner.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path.cwd() / 'scripts'))\n"
        "import update_install as updater\n"
        "updater.download = lambda version: {'success': True, 'archive': sys.argv[1], 'version': version, 'installed': False}\n"
        "print(json.dumps(updater.install(sys.argv[2], confirm=True)))\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(runner), str(archive), PROJECT_VERSION],
        cwd=old,
        env=env,
        capture_output=True,
        timeout=240,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"portable update smoke failed: {result.stderr.decode('utf-8', errors='replace')}"
        )
    installed = json.loads(result.stdout)
    if not installed.get("installed") or not Path(installed["backup_dir"]).is_dir():
        raise ValueError("portable update did not retain a backup")
    if (old / "user-note.txt").read_bytes() != b"preserve local addition" or (
        state / "accounts.json"
    ).read_bytes() != b"synthetic account sentinel":
        raise ValueError("portable update did not preserve local data")
    after = subprocess.run(
        [sys.executable, str(old / "scripts" / "cli.py"), "version"],
        cwd=old,
        env=env,
        capture_output=True,
        timeout=20,
        check=True,
    )
    if json.loads(after.stdout) != version_payload():
        raise ValueError("next CLI invocation does not use the installed version")


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
        package_files(first, PROJECT_VERSION)
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
        validate_portable_update(packaged, first, temporary)
        return {
            "success": True,
            "version": PROJECT_VERSION,
            "sha256": digest,
            "bytes": first.stat().st_size,
            "commands": len(results["capabilities"]["commands"]),
            "portable_update_smoke": True,
        }


if __name__ == "__main__":
    try:
        print(json.dumps(validate_release(), indent=2))
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"success": False, "error": str(error)}))
        raise SystemExit(1) from error
