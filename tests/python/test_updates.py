from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import cli
import update_install as installer
import updates
from project_metadata import PROJECT_VERSION


def release_payload(version="9.0.0"):
    tag = f"v{version}"
    return {
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
        "body": "New release",
        "assets": [
            {
                "name": name,
                "state": "uploaded",
                "browser_download_url": f"{updates.RELEASES}/download/{tag}/{name}",
            }
            for name in (f"douyin-skills-{tag}.zip", "SHA256SUMS")
        ],
    }


def write_package(root: Path, version: str, extra=None) -> dict:
    files = {
        "scripts/cli.py": b"# synthetic CLI\n",
        "scripts/project_metadata.py": f'PROJECT_VERSION = "{version}"\n'.encode(),
        "package.json": json.dumps({"version": version}).encode(),
        "package-lock.json": json.dumps({"version": version}).encode(),
        "SKILL.md": b"# synthetic skill\n",
        **(extra or {}),
    }
    manifest = {
        "version": version,
        "files": {
            name: hashlib.sha256(data).hexdigest() for name, data in files.items()
        },
    }
    files[installer.MANIFEST] = json.dumps(manifest).encode()
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return files


class UpdateTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = mock.patch.dict(
            os.environ,
            {
                "DOUYIN_SKILLS_HOME": str(self.root / "state"),
                "DOUYIN_SKILLS_NO_UPDATE_CHECK": "0",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_cli(self, args, **kwargs):
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            self.assertRaises(SystemExit) as result,
        ):
            cli.main(args, **kwargs)
        return result.exception.code, json.loads(output.getvalue())


class UpdateTests(UpdateTestCase):
    def test_defaults_config_persistence_and_unicode_download_directory(self):
        self.assertEqual(updates.config()["interval_hours"], 6)
        self.assertTrue(updates.config()["auto_check"])
        directory = self.root / "下载 包"
        updates.configure(
            auto_check=False, interval_hours=12, download_dir=str(directory)
        )
        self.assertTrue(directory.is_dir())
        self.assertEqual(
            updates.config(),
            {
                "auto_check": False,
                "interval_hours": 12,
                "download_dir": str(directory.resolve()),
            },
        )
        with mock.patch.object(updates.subprocess, "Popen") as popen:
            updates.start_worker()
            popen.assert_not_called()

    def test_invalid_settings_preserve_saved_config(self):
        updates.configure(auto_check=False)
        before = updates.state_path("config.json").read_bytes()
        for kwargs in (
            {"interval_hours": 0},
            {"interval_hours": 169},
            {"interval_hours": True},
            {"auto_check": "yes"},
            {"download_dir": " "},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                updates.configure(**kwargs)
            self.assertEqual(before, updates.state_path("config.json").read_bytes())

    def test_corrupt_config_is_preserved_and_does_not_block_normal_output(self):
        updates.state_path("config.json").parent.mkdir(parents=True)
        updates.state_path("config.json").write_text("{broken", encoding="utf-8")
        with mock.patch.object(updates.subprocess, "Popen") as popen:
            updates.start_worker()
            popen.assert_not_called()
        self.assertIsNone(updates.notification())
        self.assertEqual(updates.state_path("config.json").read_text(), "{broken")

    def test_six_hour_boundary_restart_clock_rollback_and_interval_change(self):
        settings = updates.config()
        state = {"last_attempt_at": 10000}
        self.assertFalse(updates.is_due(state, settings, 10000 + 21599))
        self.assertTrue(updates.is_due(state, settings, 10000 + 21600))
        self.assertTrue(updates.is_due(state, settings, 9999))
        self.assertTrue(updates.is_due({}, settings, 10000))
        self.assertTrue(updates.is_due(state, {**settings, "interval_hours": 1}, 13600))

    def test_checks_cache_and_failed_attempts_are_throttled(self):
        with mock.patch.object(
            updates, "release_info", return_value={"version": "9.0.0"}
        ) as fetch:
            result = updates.check(force=False)
            self.assertTrue(result["update_available"])
            updates.check(force=False)
            self.assertEqual(fetch.call_count, 1)
            updates.check(force=True)
            self.assertEqual(fetch.call_count, 2)
        with mock.patch.object(
            updates, "release_info", side_effect=RuntimeError("offline")
        ) as fetch:
            with self.assertRaisesRegex(RuntimeError, "offline"):
                updates.check(force=True)
            updates.check(force=False)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(updates.status()["last_error"], "offline")
            self.assertTrue(updates.status()["update_available"])

    def test_disabled_automatic_checks_allow_explicit_check(self):
        updates.configure(auto_check=False)
        with mock.patch.object(
            updates, "release_info", return_value={"version": "9.0.0"}
        ) as fetch:
            updates.check(force=False)
            fetch.assert_not_called()
            updates.check(force=True)
            fetch.assert_called_once()
        self.assertIsNone(updates.notification())

    def test_stable_version_comparison_rejects_prereleases_and_paths(self):
        self.assertGreater(
            updates.version_tuple("v1.10.0"), updates.version_tuple("1.9.0")
        )
        for version in ("v1.0.0-rc1", "1.0", "01.1.0", "../../file", "latest"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                updates.version_tuple(version)
        with mock.patch.object(updates, "release_info") as fetch:
            with self.assertRaises(ValueError):
                updates.download(PROJECT_VERSION)
            fetch.assert_not_called()

    def test_only_complete_stable_official_release_assets_are_accepted(self):
        payload = release_payload()
        with mock.patch.object(
            updates, "fetch_bytes", return_value=json.dumps(payload).encode()
        ):
            self.assertEqual(updates.release_info()["version"], "9.0.0")
        for field in ("draft", "prerelease"):
            with (
                mock.patch.object(
                    updates,
                    "fetch_bytes",
                    return_value=json.dumps({**payload, field: True}).encode(),
                ),
                self.assertRaises(ValueError),
            ):
                updates.release_info()
        payload["assets"][0]["browser_download_url"] = (
            "https://example.test/malware.zip"
        )
        with (
            mock.patch.object(
                updates, "fetch_bytes", return_value=json.dumps(payload).encode()
            ),
            self.assertRaises(ValueError),
        ):
            updates.release_info()

    def test_redirects_refuse_downgrade_and_non_github_hosts(self):
        handler = updates.SafeRedirect()
        for url in (
            "http://github.com/file",
            "https://evil.test/file",
            "https://github.com.evil.test/file",
            "https://user@github.com/file",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                handler.redirect_request(None, None, 302, "", {}, url)

    def test_verified_download_and_partial_cleanup_preserve_existing_archive(self):
        payload = release_payload()
        with mock.patch.object(
            updates, "fetch_bytes", return_value=json.dumps(payload).encode()
        ):
            release = updates.release_info()
        data = b"synthetic archive"
        digest = hashlib.sha256(data).hexdigest()
        checksum = f"{digest}  {release['archive_name']}\n".encode()
        with (
            mock.patch.object(updates, "release_info", return_value=release),
            mock.patch.object(updates, "fetch_bytes", return_value=checksum),
            mock.patch.object(
                updates,
                "fetch",
                side_effect=lambda url, stream, limit: stream.write(data),
            ),
        ):
            result = updates.download("9.0.0")
            archive = Path(result["archive"])
            self.assertEqual(archive.read_bytes(), data)
            self.assertFalse(result["installed"])
        with (
            mock.patch.object(updates, "release_info", return_value=release),
            mock.patch.object(updates, "fetch_bytes", return_value=checksum),
            mock.patch.object(
                updates,
                "fetch",
                side_effect=lambda url, stream, limit: stream.write(b"tampered"),
            ),
            self.assertRaisesRegex(ValueError, "SHA-256"),
        ):
            updates.download("9.0.0")
        self.assertEqual(archive.read_bytes(), data)
        self.assertEqual(list(archive.parent.glob("*.part")), [])

    def test_offline_cli_and_missing_confirmation_never_start_worker_or_download(self):
        with (
            mock.patch.object(cli, "start_worker") as worker,
            mock.patch.object(updates, "fetch") as fetch,
            mock.patch.object(cli, "_connect") as browser,
        ):
            for command in ("version", "capabilities", "update-status"):
                code, result = self.run_cli([command], background_updates=True)
                self.assertEqual(code, 0)
                self.assertNotIn("update_notice", result)
            code, result = self.run_cli(
                ["install-update", "--version", "9.0.0"], background_updates=True
            )
            self.assertEqual(code, 2)
            self.assertIn("--confirm", result["error"])
            worker.assert_not_called()
            fetch.assert_not_called()
            browser.assert_not_called()

    def test_notice_preserves_command_success_and_exit_code(self):
        updates.write_json(
            updates.state_path("state.json"),
            {
                "release": {
                    "version": "9.0.0",
                    "tag": "v9.0.0",
                    "release_url": "https://github.com/zJay26/douyin-skills/releases/tag/v9.0.0",
                }
            },
        )
        with (
            mock.patch.object(cli, "start_worker"),
            mock.patch.object(
                cli,
                "run_doctor",
                return_value={"success": False, "required_failures": ["test"]},
            ),
        ):
            code, result = self.run_cli(["doctor"], background_updates=True)
        self.assertEqual(code, 2)
        self.assertFalse(result["success"])
        self.assertTrue(result["update_notice"]["requires_confirmation"])

    def test_worker_singleton_and_launch_is_detached(self):
        with (
            updates.file_lock(updates.state_path("worker.lock"), timeout=0),
            mock.patch.object(updates.subprocess, "Popen") as popen,
        ):
            updates.start_worker()
            popen.assert_not_called()
        with mock.patch.object(updates.subprocess, "Popen") as popen:
            updates.start_worker()
            updates.start_worker()
            popen.assert_called_once()
            self.assertEqual(popen.call_args.kwargs["stdout"], subprocess.DEVNULL)
            self.assertEqual(
                popen.call_args.kwargs["env"]["DOUYIN_SKILLS_HOME"], str(updates.home())
            )

    def test_worker_checks_then_exits_after_switch_is_disabled(self):
        with (
            mock.patch.object(updates, "check") as check,
            mock.patch.object(
                updates.time,
                "sleep",
                side_effect=lambda seconds: updates.configure(auto_check=False),
            ),
        ):
            updates.worker()
        check.assert_called_once_with(force=False)

    def test_installation_lock_prevents_simultaneous_update(self):
        with installer.installation_lock():
            code, payload = self.run_cli(["version"])
        self.assertEqual(code, 2)
        self.assertEqual(payload["error_type"], "RuntimeError")


class InstallTests(UpdateTestCase):
    def setUp(self):
        super().setUp()
        self.installation = self.root / "portable"
        self.old = write_package(
            self.installation, PROJECT_VERSION, {"obsolete.txt": b"old"}
        )
        new = write_package(self.root / "new", "9.0.0", {"new.txt": b"new"})
        self.archive = self.root / "new.zip"
        with zipfile.ZipFile(self.archive, "w") as archive:
            for name, data in new.items():
                archive.writestr(f"douyin-skills-v9.0.0/{name}", data)
        self.download = mock.patch.object(
            installer,
            "download",
            return_value={
                "success": True,
                "archive": str(self.archive),
                "version": "9.0.0",
                "installed": False,
            },
        )
        self.download_mock = self.download.start()
        self.addCleanup(self.download.stop)
        self.npm = mock.patch.object(installer.shutil, "which", return_value="npm")
        self.npm.start()
        self.addCleanup(self.npm.stop)

    def install(self):
        return installer.install("9.0.0", confirm=True, root=self.installation)

    def test_no_consent_or_git_checkout_or_modified_files_never_download(self):
        with self.assertRaises(ValueError):
            installer.install("9.0.0", confirm=False, root=self.installation)
        (self.installation / ".git").write_text("worktree")
        with self.assertRaisesRegex(ValueError, "Git"):
            self.install()
        (self.installation / ".git").unlink()
        (self.installation / "SKILL.md").write_text("my changes")
        with self.assertRaisesRegex(ValueError, "本地文件"):
            self.install()
        self.download_mock.assert_not_called()

    def test_bad_archive_hash_and_unsafe_members_are_rejected(self):
        for name in (
            "../outside",
            "C:/outside",
            "a\\b",
            "a/./b",
            "CON.txt",
            "foo:bar",
            "a/../b",
            "node_modules/package.js",
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                installer.safe_member(name)
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.writestr("douyin-skills-v9.0.0/unlisted.txt", b"extra")
        with self.assertRaisesRegex(ValueError, "清单"):
            installer.package_files(self.archive, "9.0.0")

    def test_download_dir_inside_installation_is_rejected(self):
        updates.configure(download_dir=str(self.installation / "downloads"))
        with self.assertRaisesRegex(ValueError, "之外"):
            self.install()
        self.download_mock.assert_not_called()

    def test_dependency_failure_keeps_current_installation(self):
        with (
            mock.patch.object(
                installer.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 1),
            ),
            self.assertRaisesRegex(RuntimeError, "依赖安装失败"),
        ):
            self.install()
        self.assertEqual((self.installation / "obsolete.txt").read_bytes(), b"old")
        self.assertFalse((self.installation / "new.txt").exists())

    def test_install_preserves_local_files_profiles_and_retains_backup(self):
        (self.installation / "my-notes.txt").write_text("keep")
        profile = updates.home() / "profiles" / "Cookies"
        profile.parent.mkdir(parents=True)
        profile.write_text("private synthetic data")
        with mock.patch.object(
            installer.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                [], 0, b'{"success":true,"version":"9.0.0"}'
            ),
        ):
            result = self.install()
        self.assertTrue(result["installed"])
        self.assertEqual((self.installation / "my-notes.txt").read_text(), "keep")
        self.assertEqual((self.installation / "new.txt").read_bytes(), b"new")
        self.assertFalse((self.installation / "obsolete.txt").exists())
        self.assertEqual(profile.read_text(), "private synthetic data")
        self.assertEqual(
            (Path(result["backup_dir"]) / "obsolete.txt").read_bytes(), b"old"
        )

    def test_failed_directory_swap_restores_old_installation(self):
        rename = Path.rename

        def fail_stage(path, target):
            if ".update-" in str(path):
                raise PermissionError("synthetic busy directory")
            return rename(path, target)

        with (
            mock.patch.object(
                installer.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    [], 0, b'{"success":true,"version":"9.0.0"}'
                ),
            ),
            mock.patch.object(Path, "rename", fail_stage),
            self.assertRaisesRegex(RuntimeError, "切换失败"),
        ):
            self.install()
        self.assertEqual((self.installation / "obsolete.txt").read_bytes(), b"old")
        self.assertFalse((self.installation / "new.txt").exists())


if __name__ == "__main__":
    unittest.main()
