from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from validate_fixtures import main  # noqa: E402


class ValidateFixturesCliTests(unittest.TestCase):
    def test_fixture_id_filter_runs_a_focused_regression(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["--fixture-id", "detail-page-drift"])

        self.assertEqual(result, 0)
        self.assertIn("1 fixtures", output.getvalue())
        self.assertIn("focused selection", output.getvalue())

    def test_unknown_filter_returns_a_distinct_usage_failure(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["--fixture-id", "not-a-real-fixture"])

        self.assertEqual(result, 2)
        self.assertIn("No page-state fixtures", output.getvalue())


if __name__ == "__main__":
    unittest.main()
