from __future__ import annotations

import json
import os
from pathlib import Path

_CONFIG_DIR = Path.home() / ".douyin-skills"
_ACCOUNTS_FILE = _CONFIG_DIR / "accounts.json"
_NAMED_PORT_START = 9223


def _load_config() -> dict:
    if not _ACCOUNTS_FILE.exists():
        return {"default": "", "accounts": {}}
    with open(_ACCOUNTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_config(config: dict) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(_ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


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
        for name, info in accounts.items()
    ]


def add_account(name: str, description: str = "") -> dict:
    config = _load_config()
    accounts = config.setdefault("accounts", {})
    if name in accounts:
        raise ValueError(f"账号 '{name}' 已存在")
    existing_ports = {info.get("port", _NAMED_PORT_START) for info in accounts.values()}
    port = max(existing_ports | {_NAMED_PORT_START - 1}) + 1
    accounts[name] = {"description": description, "port": port}
    if not config.get("default"):
        config["default"] = name
    _save_config(config)
    profile_dir = get_profile_dir(name)
    os.makedirs(profile_dir, exist_ok=True)
    return {"name": name, "description": description, "port": port, "profile_dir": profile_dir}


def remove_account(name: str) -> None:
    config = _load_config()
    accounts = config.get("accounts", {})
    if name not in accounts:
        raise ValueError(f"账号 '{name}' 不存在")
    del accounts[name]
    if config.get("default") == name:
        config["default"] = next(iter(accounts), "")
    _save_config(config)


def set_default_account(name: str) -> None:
    config = _load_config()
    accounts = config.get("accounts", {})
    if name not in accounts:
        raise ValueError(f"账号 '{name}' 不存在")
    config["default"] = name
    _save_config(config)


def update_account_description(name: str, description: str) -> None:
    config = _load_config()
    accounts = config.get("accounts", {})
    if name not in accounts:
        raise ValueError(f"账号 '{name}' 不存在")
    accounts[name]["description"] = description
    _save_config(config)


def get_profile_dir(account: str) -> str:
    return str(_CONFIG_DIR / "accounts" / account / "chrome-profile")


def get_account_port(name: str) -> int:
    config = _load_config()
    accounts = config.get("accounts", {})
    if name not in accounts:
        raise ValueError(f"账号 '{name}' 不存在")
    return accounts[name].get("port", _NAMED_PORT_START)
