#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter

from douyin.page_states import (
    SUPPORTED_FIXTURE_FLOWS,
    load_fixtures,
    select_fixtures,
    validate_fixture_set,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate synthetic page-state fixtures and focused regressions."
    )
    parser.add_argument(
        "--flow",
        choices=sorted(SUPPORTED_FIXTURE_FLOWS),
        help="validate only fixtures from one workflow",
    )
    parser.add_argument(
        "--fixture-id",
        help="validate one fixture by its stable id",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    all_fixtures = load_fixtures()
    filtered = args.flow is not None or args.fixture_id is not None
    fixtures = select_fixtures(all_fixtures, flow=args.flow, fixture_id=args.fixture_id)
    if not fixtures:
        print("No page-state fixtures matched the requested filter.")
        return 2

    errors = validate_fixture_set(fixtures, require_all_flows=not filtered)
    if errors:
        print("Page-state fixture validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    flows = Counter(fixture["flow"] for fixture in fixtures)
    summary = ", ".join(f"{name}={flows[name]}" for name in sorted(flows))
    scope = "all fixtures" if not filtered else "focused selection"
    print(
        f"Page-state fixture validation passed: {len(fixtures)} fixtures "
        f"({summary}; {scope})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
