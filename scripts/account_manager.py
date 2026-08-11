from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path

_CONFIG_DIR = Path(
    os.environ.get("DOUYIN_SKILLS_HOME", Path.home() / ".douyin-skills")
).expanduser()
_ACCOUNTS_FILE = _CONFIG_DIR / "accounts.json"
_NAMED_PORT_START = 9223


def _validate_account_name(name: str) -> str:
    name = str(name or "").strip()
    if not name:
        raise ValueError("账号名称不能为空")
    if len(name) > 64:
        raise ValueError("账号名称不能超过 64 个字符")
    if name in {".", ".."} or any(ch in name for ch in ("/", "\\")):
        raise ValueError("账号名称不能包含路径分隔符")
    if any(ord(ch) < 32 for ch in name):
        raise ValueError("账号名称不能包含控制字符")
    return name


def _normalise_config(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise TypeError("账号配置格式无效：顶层必须是对象")

    raw_accounts = raw.get("accounts", {})
    if not isinstance(raw_accounts, dict):
        raise TypeError("账号配置格式无效：accounts 必须是对象")

    accounts: dict[str, dict] = {}
    for raw_name, raw_info in raw_accounts.items():
        name = _validate_account_name(str(raw_name))
        if not isinstance(raw_info, dict):
            raise TypeError(f"账号 '{name}' 的配置格式无效")
        port = raw_info.get("port", _NAMED_PORT_START)
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 1 <= port <= 65535
        ):
            raise ValueError(f"账号 '{name}' 的端口无效")
        accounts[name] = {
            "description": str(raw_info.get("description", "")),
            "port": port,
        }

    default = str(raw.get("default", "") or "")
    if default and default not in accounts:
        default = ""
    return {"default": default, "accounts": accounts}


def _load_config() -> dict:
    if not _ACCOUNTS_FILE.exists():
        return {"default": "", "accounts": {}}
    try:
        with open(_ACCOUNTS_FILE, encoding="utf-8") as f:
            return _normalise_config(json.load(f))
    except json.JSONDecodeError as exc:
        raise ValueError(f"账号配置已损坏：{_ACCOUNTS_FILE}") from exc


def _save_config(config: dict) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = _normalise_config(config)
    temp_file = _ACCOUNTS_FILE.with_suffix(f".json.{os.getpid()}.tmp")
    with open(temp_file, "w", encoding="utf-8", newline="\n") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_file, _ACCOUNTS_FILE)
    with contextlib.suppress(OSError):
        _ACCOUNTS_FILE.chmod(0o600)


def list_accounts() -> list[dict]:
    config = _load_config()
    default = config.get("default", "")
    accounts = config.get("accounts", {})
    return [
        {
            "name": name,
            "description": info.get("description", ""),
            "is_default": name == default,
            "profile_dir": get_profile_dir(name),
            "port": info.get("port", _NAMED_PORT_START),
        }
        for name, info in sorted(
            accounts.items(),
            key=lambda item: (item[1].get("port", _NAMED_PORT_START), item[0]),
        )
    ]


def add_account(name: str, description: str = "") -> dict:
    name = _validate_account_name(name)
    config = _load_config()
    accounts = config.setdefault("accounts", {})
    if any(existing.casefold() == name.casefold() for existing in accounts):
        raise ValueError(f"账号 '{name}' 已存在")
    existing_ports = {info.get("port", _NAMED_PORT_START) for info in accounts.values()}
    port = next(
        (
            candidate
            for candidate in range(_NAMED_PORT_START, 65536)
            if candidate not in existing_ports
        ),
        None,
    )
    if port is None:
        raise ValueError("没有可用的本地调试端口")
    accounts[name] = {"description": description, "port": port}
    if not config.get("default"):
        config["default"] = name
    _save_config(config)
    profile_dir = get_profile_dir(name)
    os.makedirs(profile_dir, exist_ok=True)
    return {
        "name": name,
        "description": description,
        "port": port,
        "profile_dir": profile_dir,
    }


def remove_account(name: str) -> None:
    name = _validate_account_name(name)
    config = _load_config()
    accounts = config.get("accounts", {})
    if name not in accounts:
        raise ValueError(f"账号 '{name}' 不存在")
    del accounts[name]
    if config.get("default") == name:
        config["default"] = next(iter(accounts), "")
    _save_config(config)


def set_default_account(name: str) -> None:
    name = _validate_account_name(name)
    config = _load_config()
    accounts = config.get("accounts", {})
    if name not in accounts:
        raise ValueError(f"账号 '{name}' 不存在")
    config["default"] = name
    _save_config(config)


def update_account_description(name: str, description: str) -> None:
    name = _validate_account_name(name)
    config = _load_config()
    accounts = config.get("accounts", {})
    if name not in accounts:
        raise ValueError(f"账号 '{name}' 不存在")
    accounts[name]["description"] = description
    _save_config(config)


def get_profile_dir(account: str) -> str:
    account = _validate_account_name(account)
    return str(_CONFIG_DIR / "accounts" / account / "chrome-profile")


def get_account_port(name: str) -> int:
    name = _validate_account_name(name)
    config = _load_config()
    accounts = config.get("accounts", {})
    if name not in accounts:
        raise ValueError(f"账号 '{name}' 不存在")
    return accounts[name].get("port", _NAMED_PORT_START)


def get_default_account() -> str:
    return str(_load_config().get("default", "") or "")
