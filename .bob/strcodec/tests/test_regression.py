"""Regression tests: generated stream.py / rebuild script must stay byte-for-byte identical to the fixtures.

If a change of the output is intentional, review the diff and regenerate with tests/make_fixtures.py.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fixture_ctx as fx  # noqa: E402


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@unittest.skipUnless(fx.EXPECTED_STREAM.exists() and fx.EXPECTED_REBUILD.exists(),
                     "fixtures missing: run tests/make_fixtures.py")
class RegressionTests(unittest.TestCase):
    def test_stream_py_identical(self):
        self.assertEqual(fx.normalized(), _read(fx.EXPECTED_STREAM))

    def test_rebuild_script_identical(self):
        script, warnings = fx.rebuilt()
        self.assertEqual(warnings, [])
        self.assertEqual(script, _read(fx.EXPECTED_REBUILD))

    def test_rebuild_from_expected_stream_py(self):
        # the fixture stream.py itself must round-trip through build_rebuild to the same script
        script, _ = fx.transform.build_rebuild(_read(fx.EXPECTED_STREAM), fx.ctx())
        self.assertEqual(script, _read(fx.EXPECTED_REBUILD))


if __name__ == "__main__":
    unittest.main()
