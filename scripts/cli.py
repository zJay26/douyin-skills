#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path

from account_manager import (
    add_account,
    get_account_port,
    get_profile_dir,
    list_accounts,
    remove_account,
    set_default_account,
)
from chrome_launcher import ensure_chrome, has_display
from douyin.cdp import Browser
from douyin.interact import favorite_video, like_video, share_video
from douyin.login import check_login_state, get_qrcode, wait_login, send_code, verify_code
from douyin.publish import click_publish, fill_publish_image, select_music, validate_publish_state
from douyin.search import get_trending_topics, get_video_detail, list_feeds, search_videos


def _wslg_headed_env_exports() -> str:
    return "DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 FORCE_HEADED=1"


def _maybe_switch_to_headed_for_risk(args: argparse.Namespace, result: dict, reason: str):
    if not isinstance(result, dict) or not result.get("risk_page"):
        return None
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
    page.navigate("https://www.douyin.com/")
    page.wait_for_load(20)
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
    print(json.dumps(data, ensure_ascii=False, indent=2))
    raise SystemExit(exit_code)


def _session_tab_file(port: int) -> str:
    return os.path.join(tempfile.gettempdir(), "douyin-skills", f"session_tab_{port}.txt")


def _save_session_tab(target_id: str, port: int) -> None:
    path = _session_tab_file(port)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Path(path).write_text(target_id, encoding="utf-8")


def _load_session_tab(port: int) -> str | None:
    with contextlib.suppress(FileNotFoundError):
        data = Path(_session_tab_file(port)).read_text(encoding="utf-8").strip()
        return data or None
    return None


def _resolve_account(args: argparse.Namespace) -> str | None:
    if not getattr(args, "account", ""):
        return None
    args.port = get_account_port(args.account)
    return get_profile_dir(args.account)


def _connect(args: argparse.Namespace):
    user_data_dir = _resolve_account(args)
    desired_headless = not getattr(args, "headed", False)
    if not ensure_chrome(port=args.port, headless=desired_headless, user_data_dir=user_data_dir):
        _output({"success": False, "error": "无法启动 Chrome"}, exit_code=2)
    browser = Browser(host=args.host, port=args.port)
    browser.connect()
    saved = _load_session_tab(args.port)
    page = browser.get_page_by_target_id(saved) if saved else None
    if not page:
        page = browser.get_or_create_page()
    _save_session_tab(page.target_id, args.port)
    return browser, page


def _risk_or_verify_text(page) -> str:
    text = page.evaluate("(document.body && document.body.innerText || '').slice(0, 3000)") or ""
    title = page.evaluate("document.title || ''") or ""
    return f"{title}\n{text}"


def _switch_to_headed_for_verification(args: argparse.Namespace, reason: str):
    headed_args = argparse.Namespace(**vars(args))
    headed_args.headed = True
    _browser, page = _connect(headed_args)
    page.navigate("https://www.douyin.com/")
    page.wait_for_load(20)
    body = _risk_or_verify_text(page)
    return {
        "success": False,
        "action": "switched_to_headed",
        "needs_user_verification": True,
        "message": f"已切换到有头模式，请在浏览器中手动完成验证码/身份验证后再重试。原因：{reason}",
        "page_excerpt": body[:1500],
    }


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


def cmd_check_login(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    page.navigate("https://www.douyin.com/")
    page.wait_for_load(20)
    state = check_login_state(page)
    if state.get("risk_page") and not getattr(args, "headed", False):
        _output(_switch_to_headed_for_verification(args, "检测到验证码/风控页"), exit_code=2)
    _output(state, exit_code=0 if state.get("logged_in") else 1)


def cmd_get_qrcode(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    if "douyin.com" not in (page.evaluate("location.href") or ""):
        page.navigate("https://www.douyin.com/")
        page.wait_for_load(20)
    result = get_qrcode(page)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_wait_login(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    result = wait_login(page)
    _output(result, exit_code=0 if result.get("logged_in") else 1)


def cmd_send_code(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    result = send_code(page, getattr(args, 'phone', '') or '')
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_verify_code(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    result = verify_code(page, args.code)
    _output(result, exit_code=0 if result.get("logged_in") else 1)


def cmd_list_feeds(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    _output(list_feeds(page))


def cmd_trending_topics(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    _output(get_trending_topics(page))


def cmd_search_videos(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    result = search_videos(page, args.keyword, limit=args.limit)
    switched = _maybe_switch_to_headed_for_risk(args, result, "搜索页检测到验证码/风控")
    if switched:
        _output(switched, exit_code=2)
    _output(result)


def cmd_get_video_detail(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    _output(get_video_detail(page, args.video_id))


def cmd_like_video(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    result = like_video(page, args.video_id)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_favorite_video(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    result = favorite_video(page, args.video_id)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_share_video(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    result = share_video(page, args.video_id)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_fill_publish_image(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    desc = Path(args.desc_file).read_text(encoding="utf-8").strip()
    result = fill_publish_image(page, args.images, desc, getattr(args, "title", "") or "")
    switched = _maybe_switch_to_headed_for_risk(args, result, "发布页检测到验证码/风控")
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_select_music(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    result = select_music(page, getattr(args, "names", None))
    switched = _maybe_switch_to_headed_for_risk(args, result, "选音乐时检测到验证码/风控")
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_validate_publish(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    result = validate_publish_state(page, require_topic=getattr(args, "require_topic", False))
    _output(result, exit_code=0 if result.get("success") else 2)


def cmd_click_publish(args: argparse.Namespace) -> None:
    _browser, page = _connect(args)
    result = click_publish(page, require_topic=getattr(args, "require_topic", False))
    switched = _maybe_switch_to_headed_for_risk(args, result, "发布前检测到验证码/风控")
    if switched:
        _output(switched, exit_code=2)
    _output(result, exit_code=0 if result.get("success") else 2)


def main() -> None:
    parser = argparse.ArgumentParser(description="douyin-skills CLI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9222)
    parser.add_argument("--account", default="")
    parser.add_argument("--headed", action="store_true", help="强制使用有头模式；默认无头运行")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ["check-login", "get-qrcode", "wait-login", "list-accounts"]:
        sub.add_parser(name)

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

    p = sub.add_parser("search-videos")
    p.add_argument("--keyword", required=True)
    p.add_argument("--limit", type=int, default=7)

    p = sub.add_parser("get-video-detail")
    p.add_argument("--video-id", required=True)

    p = sub.add_parser("fill-publish-image")
    p.add_argument("--desc-file", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--images", nargs="+", required=True)

    p = sub.add_parser("select-music")
    p.add_argument("--names", nargs="*", default=[])

    p = sub.add_parser("click-publish")
    p.add_argument("--require-topic", action="store_true")

    p = sub.add_parser("like-video")
    p.add_argument("--video-id", required=True)

    p = sub.add_parser("favorite-video")
    p.add_argument("--video-id", required=True)

    p = sub.add_parser("share-video")
    p.add_argument("--video-id", required=True)

    args = parser.parse_args()

    dispatch = {
        "list-accounts": cmd_list_accounts,
        "add-account": cmd_add_account,
        "remove-account": cmd_remove_account,
        "set-default-account": cmd_set_default_account,
        "check-login": cmd_check_login,
        "get-qrcode": cmd_get_qrcode,
        "wait-login": cmd_wait_login,
        "send-code": cmd_send_code,
        "verify-code": cmd_verify_code,
        "search-videos": cmd_search_videos,
        "get-video-detail": cmd_get_video_detail,
        "fill-publish-image": cmd_fill_publish_image,
        "select-music": cmd_select_music,
        "click-publish": cmd_click_publish,
        "like-video": cmd_like_video,
        "favorite-video": cmd_favorite_video,
        "share-video": cmd_share_video,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
