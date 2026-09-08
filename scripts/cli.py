#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from account_manager import (
    add_account,
    get_account_port,
    get_default_account,
    get_profile_dir,
    list_accounts,
    remove_account,
    set_default_account,
    update_account_description,
)
from browser_runtime import Browser, CDPError, normalize_host
from chrome_launcher import DEFAULT_PORT, ensure_chrome
from cli_contract import JsonArgumentParser, capabilities_payload
from doctor import run_doctor
from douyin.interact import (
    comment_video,
    favorite_video,
    get_interaction_state,
    like_video,
    share_video,
)
from douyin.login import (
    get_qrcode,
    send_code,
    settle_login_state,
    verify_code,
    wait_login,
)
from douyin.publish import (
    click_publish,
    click_publish_video,
    fill_publish_image,
    fill_publish_video,
    select_music,
    set_video_cover,
    validate_publish_state,
    validate_video_publish_state,
)
from douyin.search import get_trending_topics, get_video_detail, search_videos
from local_state import atomic_write
from platform_adapter import get_default_adapter
from project_metadata import version_payload
from update_install import install, installation_lock
from updates import check as check_updates
from updates import configure as configure_updates
from updates import download as download_update
from updates import notification as update_notification
from updates import start_worker
from updates import status as update_status

_include_update_notification = False


def _wslg_headed_env_exports() -> str:
    return "DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 FORCE_HEADED=1"


def _maybe_switch_to_headed_for_risk(
    args: argparse.Namespace,
    result: dict,
    reason: str,
    adapter,
    *,
    accept_recovered_login: bool = False,
):
    if not isinstance(result, dict) or not result.get("risk_page"):
        return None
    if getattr(args, "target_id", None):
        return {
            **result,
            "action": "needs_user_verification",
            "needs_user_verification": True,
            "message": "指定页面需要人工验证；请在该浏览器中完成验证后重试。",
        }
    if getattr(args, "headed", False):
        page_title = result.get("page_title") or ""
        return {
            **result,
            "action": "needs_user_verification",
            "needs_user_verification": True,
            "message": f"已处于有头模式，请在浏览器中手动完成验证码/身份验证后重试。原因：{reason}",
            "page_title": page_title,
        }
    headed_args = argparse.Namespace(**vars(args))
    headed_args.headed = True
    _browser, page = _connect(headed_args)
    adapter.navigate_home(page)
    page.wait_for_load(20)
    if accept_recovered_login:
        recovered = settle_login_state(page, adapter=adapter)
        if not recovered.get("risk_page"):
            logged_in = bool(recovered.get("logged_in"))
            return {
                **recovered,
                "action": "risk_recovered_after_headed_switch",
                "risk_recovered": True,
                "needs_user_verification": False,
                "message": "切换到可见浏览器后风险状态已消失，当前登录状态已重新确认。"
                if logged_in
                else "切换到可见浏览器后风险状态已消失，但当前尚未确认登录。",
            }
        result = recovered
    body = _risk_or_verify_text(page)
    return {
        **result,
        "action": "switched_to_headed",
        "needs_user_verification": True,
        "message": f"已自动切换到有头模式，请在浏览器中手动完成验证码/身份验证后重试。原因：{reason}。WSLg 环境请显式使用：{_wslg_headed_env_exports()}",
        "page_excerpt": body[:1500],
    }


if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _output(data: dict, exit_code: int = 0) -> None:
    if _include_update_notification:
        notice = update_notification()
        if notice:
            data = {**data, "update_notice": notice}
    print(json.dumps(data, ensure_ascii=False, indent=2))
    raise SystemExit(exit_code)


def _session_tab_file(
    port: int, host: str = "127.0.0.1", profile: str | None = None
) -> Path:
    root = Path(
        os.environ.get("DOUYIN_SKILLS_HOME", Path.home() / ".douyin-skills")
    ).expanduser()
    identity = json.dumps(
        [normalize_host(host), port, profile or ""], ensure_ascii=False
    )
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return root / "runtime" / f"session-{key}.txt"


def _save_session_tab(
    target_id: str, port: int, host: str = "127.0.0.1", profile: str | None = None
) -> None:
    atomic_write(_session_tab_file(port, host, profile), target_id)


def _load_session_tab(
    port: int, host: str = "127.0.0.1", profile: str | None = None
) -> str | None:
    with contextlib.suppress(FileNotFoundError):
        data = (
            _session_tab_file(port, host, profile).read_text(encoding="utf-8").strip()
        )
        return data or None
    return None


def _is_loopback_host(host: str) -> bool:
    try:
        normalize_host(host)
        return True
    except ValueError:
        return False


def _resolve_account(args: argparse.Namespace) -> str | None:
    requested = str(getattr(args, "account", "") or "").strip()
    explicit_port = getattr(args, "port", None)
    if requested:
        account_port = get_account_port(requested)
        if explicit_port is not None and explicit_port != account_port:
            raise ValueError("--account 与其他账号端口的 --port 不能同时使用")
        args.account = requested
        args.port = account_port
        return get_profile_dir(requested)

    selected = get_default_account() if explicit_port is None else ""
    if selected:
        args.account = selected
        args.port = get_account_port(selected)
        return get_profile_dir(selected)

    args.port = explicit_port or DEFAULT_PORT
    return None


def _connect(args: argparse.Namespace):
    if not _is_loopback_host(args.host):
        raise ValueError("出于安全考虑，--host 只允许 localhost、127.0.0.1 或 ::1")
    user_data_dir = _resolve_account(args)
    args.host = normalize_host(args.host)
    browser = Browser(host=args.host, port=args.port)
    explicit_target = getattr(args, "target_id", None)
    if explicit_target:
        page = browser.get_page_by_target_id(explicit_target)
        if page is None:
            raise RuntimeError(
                "指定的 --target-id 不存在或不是页面；请运行 browser-status --include-tabs 核对"
            )
        _save_session_tab(page.target_id, args.port, args.host, user_data_dir)
        return browser, page
    desired_headless = not getattr(args, "headed", False)
    if args.host != "127.0.0.1":
        browser.version()  # Alternate loopback endpoints are attach-only.
    elif not ensure_chrome(
        port=args.port,
        headless=desired_headless,
        user_data_dir=user_data_dir,
        force_mode=bool(getattr(args, "headed", False)),
    ):
        raise RuntimeError("无法启动 Chrome")
    saved = _load_session_tab(args.port, args.host, user_data_dir)
    page = browser.get_page_by_target_id(saved) if saved else None
    if not page:
        if args.command in {
            "set-video-cover",
            "select-music",
            "validate-publish",
            "click-publish",
            "validate-publish-video",
            "click-publish-video",
        }:
            raise RuntimeError(
                "发布会话不存在或已关闭；请先准备发布表单，或用 --target-id 显式选择现有表单"
            )
        page = browser.get_or_create_page()
    _save_session_tab(page.target_id, args.port, args.host, user_data_dir)
    return browser, page


def _risk_or_verify_text(page) -> str:
    text = (
        page.evaluate("(document.body && document.body.innerText || '').slice(0, 3000)")
        or ""
    )
    title = page.evaluate("document.title || ''") or ""
    return f"{title}\n{text}"


def cmd_list_accounts(_args: argparse.Namespace) -> None:
    accounts = list_accounts()
    _output({"success": True, "count": len(accounts), "accounts": accounts})


def cmd_add_account(args: argparse.Namespace) -> None:
    result = add_account(args.name, args.description)
    _output({"success": True, **result})


def cmd_remove_account(args: argparse.Namespace) -> None:
    remove_account(args.name)
    _output({"success": True, "name": args.name})


def cmd_set_default_account(args: argparse.Namespace) -> None:
    set_default_account(args.name)
    _output({"success": True, "default": args.name})


def cmd_update_account(args: argparse.Namespace) -> None:
    update_account_description(args.name, args.description)
    _output({"success": True, "name": args.name, "description": args.description})


def cmd_capabilities(_args: argparse.Namespace) -> None:
    _output(capabilities_payload(build_parser()))


def cmd_browser_status(args: argparse.Namespace) -> None:
    profile = _resolve_account(args)
    args.host = normalize_host(args.host)
    browser = Browser(args.host, args.port)
    base = {"host": args.host, "port": args.port, "account": args.account or None}
    try:
        version = browser.version()
        pages = [
            target for target in browser.list_pages() if target.get("type") == "page"
        ]
    except (OSError, RuntimeError, ValueError) as error:
        _output(
            {
                "success": False,
                **base,
                "connected": False,
                "error": str(error),
                "error_code": getattr(error, "code", "connection_failed"),
            },
            exit_code=2,
        )
    saved = args.target_id or _load_session_tab(args.port, args.host, profile)
    found = any(
        (target.get("id") or target.get("targetId")) == saved for target in pages
    )
    result = {
        **version,
        **base,
        "connected": True,
        "page_count": len(pages),
        "session_target_id": saved,
        "session_target_found": found,
    }
    if args.include_tabs:
        result["tabs"] = [
            {
                "target_id": target.get("id") or target.get("targetId"),
                "title": target.get("title", ""),
                "url": target.get("url", ""),
            }
            for target in pages
        ]
    if args.target_id and not found:
        result.update(
            success=False, error="指定的页面不存在", error_code="target_not_found"
        )
    _output(result, exit_code=0 if result["success"] else 2)


def cmd_doctor(_args: argparse.Namespace) -> None:
    result = run_doctor()
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_version(_args: argparse.Namespace) -> None:
    _output(version_payload())


def cmd_check_update(_args: argparse.Namespace) -> None:
    _output(check_updates())


def cmd_update_status(_args: argparse.Namespace) -> None:
    _output(update_status())


def cmd_update_config(args: argparse.Namespace) -> None:
    result = configure_updates(
        auto_check=None if args.auto_check is None else args.auto_check == "on",
        interval_hours=args.interval_hours,
        download_dir=args.download_dir,
    )
    if result["auto_check"] and args.auto_check == "on":
        start_worker()
    _output(result)


def cmd_download_update(args: argparse.Namespace) -> None:
    _output(download_update(args.version))


def cmd_install_update(args: argparse.Namespace) -> None:
    _output(install(args.version, confirm=args.confirm))


def cmd_check_login(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    adapter.navigate_home(page)
    page.wait_for_load(20)
    state = settle_login_state(page, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args,
        state,
        "检测到验证码/风控页",
        adapter,
        accept_recovered_login=True,
    )
    if switched:
        exit_code = (
            2
            if switched.get("needs_user_verification")
            else 0
            if switched.get("logged_in")
            else 1
        )
        _output(switched, exit_code=exit_code)
    _output(state, exit_code=0 if state.get("logged_in") else 1)


def cmd_get_qrcode(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    if not adapter.is_platform_url(page.evaluate("location.href") or ""):
        adapter.navigate_home(page)
        page.wait_for_load(20)
    result = get_qrcode(page, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "读取登录二维码时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_wait_login(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = wait_login(page, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "等待登录时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("logged_in") else 1)


def cmd_send_code(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = send_code(page, getattr(args, "phone", "") or "", adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "发送验证码时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_verify_code(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = verify_code(page, args.code, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "提交验证码时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("logged_in") else 1)


def cmd_search_videos(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = search_videos(page, args.keyword, limit=args.limit, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "搜索页检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_get_trending_topics(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = get_trending_topics(page, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "热门话题页检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_get_video_detail(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = get_video_detail(page, args.video_id, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "读取作品详情时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_like_video(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = like_video(page, args.video_id, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "点赞时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_favorite_video(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = favorite_video(page, args.video_id, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "收藏时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_comment_video(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = comment_video(page, args.video_id, args.comment, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "评论时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_get_interaction_state(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = get_interaction_state(page, args.video_id, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "读取互动状态时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_share_video(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = share_video(page, args.video_id, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "获取分享链接时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_fill_publish_image(args: argparse.Namespace) -> None:
    desc_path = Path(args.desc_file).expanduser()
    if not desc_path.is_absolute():
        raise ValueError("--desc-file 必须使用绝对路径")
    try:
        desc_path = desc_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"正文文件不存在：{args.desc_file}") from exc
    if not desc_path.is_file():
        raise ValueError(f"正文路径不是文件：{args.desc_file}")
    desc = desc_path.read_text(encoding="utf-8").strip()
    if not desc:
        raise ValueError("正文文件不能为空")
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = fill_publish_image(
        page,
        args.images,
        desc,
        getattr(args, "title", "") or "",
        adapter=adapter,
    )
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "发布页检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_fill_publish_video(args: argparse.Namespace) -> None:
    desc_path = Path(args.desc_file).expanduser()
    if not desc_path.is_absolute():
        raise ValueError("--desc-file 必须使用绝对路径")
    try:
        desc_path = desc_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"作品简介文件不存在：{args.desc_file}") from exc
    if not desc_path.is_file():
        raise ValueError(f"作品简介路径不是文件：{args.desc_file}")
    desc = desc_path.read_text(encoding="utf-8").strip()
    if not desc:
        raise ValueError("作品简介文件不能为空")
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = fill_publish_video(
        page,
        args.video,
        desc,
        args.title,
        cover=getattr(args, "cover", None),
        adapter=adapter,
    )
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "视频发布页检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_set_video_cover(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = set_video_cover(page, args.cover, adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "设置视频封面时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_select_music(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = select_music(page, getattr(args, "names", None), adapter=adapter)
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "选音乐时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_validate_publish(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = validate_publish_state(
        page,
        require_topic=getattr(args, "require_topic", False),
        adapter=adapter,
    )
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "发布校验时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_click_publish(args: argparse.Namespace) -> None:
    if not getattr(args, "confirm", False):
        _output(
            {
                "success": False,
                "error": "click-publish 必须显式传入 --confirm，表示已完成内容与页面复核",
            },
            exit_code=2,
        )
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = click_publish(
        page,
        require_topic=getattr(args, "require_topic", False),
        adapter=adapter,
    )
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "发布前检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_validate_publish_video(args: argparse.Namespace) -> None:
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = validate_video_publish_state(
        page,
        require_topic=getattr(args, "require_topic", False),
        adapter=adapter,
    )
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "视频发布校验时检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_click_publish_video(args: argparse.Namespace) -> None:
    if not getattr(args, "confirm", False):
        _output(
            {
                "success": False,
                "error": "click-publish-video 必须显式传入 --confirm，表示已完成视频、封面、文案与页面复核",
            },
            exit_code=2,
        )
    adapter = get_default_adapter()
    _browser, page = _connect(args)
    result = click_publish_video(
        page,
        require_topic=getattr(args, "require_topic", False),
        adapter=adapter,
    )
    switched = _maybe_switch_to_headed_for_risk(
        args, result, "视频发布前检测到验证码/风控", adapter
    )
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def _valid_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("端口必须是整数") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("端口必须在 1 到 65535 之间")
    return port


def _valid_search_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("搜索数量必须是整数") from exc
    if not 1 <= limit <= 20:
        raise argparse.ArgumentTypeError("搜索数量必须在 1 到 20 之间")
    return limit


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(description="douyin-skills CLI")
    parser.add_argument(
        "--host", default="127.0.0.1", help="本地 Chrome 调试地址（仅允许 loopback）"
    )
    parser.add_argument(
        "--port",
        type=_valid_port,
        default=None,
        help="Chrome 调试端口；不与 --account 同时使用",
    )
    parser.add_argument(
        "--account", default="", help="命名账号；省略时使用已设置的默认账号"
    )
    parser.add_argument(
        "--target-id", help="显式选择现有页面；只连接现有浏览器，不自动启动"
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="需要时强制切换到有头模式；已有可用 Chrome 默认复用",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in [
        "version",
        "capabilities",
        "doctor",
        "check-login",
        "get-qrcode",
        "wait-login",
        "list-accounts",
        "check-update",
        "update-status",
    ]:
        sub.add_parser(name)

    p = sub.add_parser("update-config")
    p.add_argument(
        "--auto-check", choices=("on", "off"), help="开启或关闭自动检查（默认开启）"
    )
    p.add_argument(
        "--interval-hours", type=int, help="检查间隔，1 到 168 小时（默认 6）"
    )
    p.add_argument(
        "--download-dir", help="更新包下载目录；相对路径按当前目录解析后保存"
    )

    p = sub.add_parser("download-update")
    p.add_argument(
        "--version", required=True, help="已查看并选择的稳定版本，例如 v1.7.0"
    )

    p = sub.add_parser("install-update")
    p.add_argument("--version", required=True, help="已查看并选择的稳定版本")
    p.add_argument("--confirm", action="store_true", help="用户确认下载并安装该版本")

    p = sub.add_parser("browser-status")
    p.add_argument(
        "--include-tabs",
        action="store_true",
        help="包含标签页标题和 URL，仅在本地排查时使用",
    )

    p = sub.add_parser("send-code")
    p.add_argument("--phone", default="")

    p = sub.add_parser("verify-code")
    p.add_argument("--code", required=True)

    p = sub.add_parser("add-account")
    p.add_argument("--name", required=True)
    p.add_argument("--description", default="")

    p = sub.add_parser("remove-account")
    p.add_argument("--name", required=True)

    p = sub.add_parser("set-default-account")
    p.add_argument("--name", required=True)

    p = sub.add_parser("update-account")
    p.add_argument("--name", required=True)
    p.add_argument("--description", required=True)

    p = sub.add_parser("search-videos")
    p.add_argument("--keyword", required=True)
    p.add_argument("--limit", type=_valid_search_limit, default=7)

    sub.add_parser("get-trending-topics")

    p = sub.add_parser("get-video-detail")
    p.add_argument("--video-id", required=True)

    p = sub.add_parser("fill-publish-image")
    p.add_argument("--desc-file", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--images", nargs="+", required=True)

    p = sub.add_parser("fill-publish-video")
    p.add_argument("--desc-file", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--video", required=True)
    p.add_argument("--cover")

    p = sub.add_parser("set-video-cover")
    p.add_argument("--cover", required=True)

    p = sub.add_parser("select-music")
    p.add_argument("--names", nargs="*", default=[])

    p = sub.add_parser("validate-publish")
    p.add_argument("--require-topic", action="store_true")

    p = sub.add_parser("click-publish")
    p.add_argument("--require-topic", action="store_true")
    p.add_argument(
        "--confirm",
        action="store_true",
        help="确认已人工复核标题、正文、图片、音乐和页面状态",
    )

    p = sub.add_parser("validate-publish-video")
    p.add_argument("--require-topic", action="store_true")

    p = sub.add_parser("click-publish-video")
    p.add_argument("--require-topic", action="store_true")
    p.add_argument(
        "--confirm",
        action="store_true",
        help="确认已人工复核视频、封面、标题、作品简介和页面状态",
    )

    p = sub.add_parser("like-video")
    p.add_argument("--video-id", required=True)

    p = sub.add_parser("favorite-video")
    p.add_argument("--video-id", required=True)

    p = sub.add_parser("comment-video")
    p.add_argument("--video-id", required=True)
    p.add_argument("--comment", required=True)

    p = sub.add_parser("get-interaction-state")
    p.add_argument("--video-id", required=True)

    p = sub.add_parser("share-video")
    p.add_argument("--video-id", required=True)

    return parser


def main(argv: list[str] | None = None, *, background_updates: bool = False) -> None:
    global _include_update_notification
    _include_update_notification = False
    parser = build_parser()

    args = parser.parse_args(argv)
    if background_updates and args.command not in {
        "version",
        "capabilities",
        "update-status",
        "update-config",
        "check-update",
        "download-update",
        "install-update",
        "list-accounts",
        "add-account",
        "remove-account",
        "set-default-account",
        "update-account",
    }:
        start_worker()
        _include_update_notification = True

    dispatch = {
        "version": cmd_version,
        "check-update": cmd_check_update,
        "update-status": cmd_update_status,
        "update-config": cmd_update_config,
        "download-update": cmd_download_update,
        "install-update": cmd_install_update,
        "capabilities": cmd_capabilities,
        "browser-status": cmd_browser_status,
        "doctor": cmd_doctor,
        "list-accounts": cmd_list_accounts,
        "add-account": cmd_add_account,
        "remove-account": cmd_remove_account,
        "set-default-account": cmd_set_default_account,
        "update-account": cmd_update_account,
        "check-login": cmd_check_login,
        "get-qrcode": cmd_get_qrcode,
        "wait-login": cmd_wait_login,
        "send-code": cmd_send_code,
        "verify-code": cmd_verify_code,
        "search-videos": cmd_search_videos,
        "get-trending-topics": cmd_get_trending_topics,
        "get-video-detail": cmd_get_video_detail,
        "fill-publish-image": cmd_fill_publish_image,
        "fill-publish-video": cmd_fill_publish_video,
        "set-video-cover": cmd_set_video_cover,
        "select-music": cmd_select_music,
        "validate-publish": cmd_validate_publish,
        "click-publish": cmd_click_publish,
        "validate-publish-video": cmd_validate_publish_video,
        "click-publish-video": cmd_click_publish_video,
        "like-video": cmd_like_video,
        "favorite-video": cmd_favorite_video,
        "comment-video": cmd_comment_video,
        "get-interaction-state": cmd_get_interaction_state,
        "share-video": cmd_share_video,
    }
    try:
        with installation_lock():
            dispatch[args.command](args)
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        _output(
            {
                "success": False,
                "error": str(exc),
                "error_type": type(exc).__name__,
                **({"error_code": exc.code} if isinstance(exc, CDPError) else {}),
            },
            exit_code=2,
        )


if __name__ == "__main__":
    main(background_updates=True)
