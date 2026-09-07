"""Machine-readable command discovery derived from the actual CLI parser."""

from __future__ import annotations

import argparse
import json

from project_metadata import version_payload

COMMAND_EFFECTS = {
    **dict.fromkeys(("version", "capabilities", "doctor", "list-accounts"), "offline"),
    **dict.fromkeys(
        ("add-account", "remove-account", "set-default-account", "update-account"),
        "local_config",
    ),
    **dict.fromkeys(
        (
            "browser-status",
            "check-login",
            "wait-login",
            "get-trending-topics",
            "search-videos",
            "get-video-detail",
            "get-interaction-state",
            "validate-publish",
            "validate-publish-video",
            "share-video",
        ),
        "browser_read",
    ),
    **dict.fromkeys(
        (
            "get-qrcode",
            "fill-publish-image",
            "fill-publish-video",
            "set-video-cover",
            "select-music",
        ),
        "browser_form",
    ),
    **dict.fromkeys(
        (
            "send-code",
            "verify-code",
            "like-video",
            "favorite-video",
            "comment-video",
            "click-publish",
            "click-publish-video",
        ),
        "remote_write",
    ),
}


class JsonArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> None:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": message,
                    "error_type": "ArgumentError",
                    "error_code": "invalid_arguments",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(2)


def _arguments(parser: argparse.ArgumentParser) -> list[dict]:
    result = []
    for action in parser._actions:
        if not action.option_strings or action.dest == "help":
            continue
        kind = "boolean" if action.nargs == 0 else "string"
        if action.dest in {"port", "limit"}:
            kind = "integer"
        option = {
            "flags": action.option_strings,
            "name": action.dest,
            "required": action.required,
            "type": kind,
            "default": action.default,
        }
        if action.nargs in {"*", "+"}:
            option.update(
                type="array", items="string", min_items=int(action.nargs == "+")
            )
        if action.choices is not None:
            option["choices"] = list(action.choices)
        if action.dest in {"port", "limit"}:
            option.update(minimum=1, maximum=65535 if action.dest == "port" else 20)
        result.append(option)
    return result


def capabilities_payload(parser: argparse.ArgumentParser) -> dict:
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    commands = []
    for name, command in subparsers.choices.items():
        effect = COMMAND_EFFECTS[name]
        commands.append(
            {
                "name": name,
                "effect": effect,
                "requires_browser": effect.startswith("browser_")
                or effect == "remote_write",
                "requires_confirmation": name
                in {"click-publish", "click-publish-video"},
                "retry_policy": "never_automatically"
                if effect == "remote_write"
                else "inspect_result",
                "arguments": _arguments(command),
            }
        )
    return {
        **version_payload(),
        "platform": "douyin",
        "global_options_position": "before_command",
        "global_options": _arguments(parser),
        "commands": commands,
    }
