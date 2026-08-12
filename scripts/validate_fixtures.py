#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter

from douyin.page_states import load_fixtures, validate_fixture_set


def main() -> int:
    fixtures = load_fixtures()
    errors = validate_fixture_set(fixtures)
    if errors:
        print("Page-state fixture validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    flows = Counter(fixture["flow"] for fixture in fixtures)
    summary = ", ".join(f"{name}={flows[name]}" for name in sorted(flows))
    print(f"Page-state fixture validation passed: {len(fixtures)} fixtures ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
