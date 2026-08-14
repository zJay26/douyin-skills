"""Single source of truth for runtime and result-contract versions."""

from __future__ import annotations

PROJECT_NAME = "douyin-skills"
PROJECT_VERSION = "1.1.0"
RESULT_CONTRACT_VERSION = "1.0"


def version_payload() -> dict[str, str | bool]:
    return {
        "success": True,
        "project": PROJECT_NAME,
        "version": PROJECT_VERSION,
        "result_contract_version": RESULT_CONTRACT_VERSION,
    }
