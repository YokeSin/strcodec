"""(Re)generate the expected-output fixtures used by test_regression.py.

  python .bob/strcodec/tests/make_fixtures.py

Run this ONLY after an intentional change of the generated output (stream.py conventions or the rebuild
script / prelude). The regression test compares byte-for-byte against these files, so regenerating them
without reviewing the diff defeats its purpose.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fixture_ctx as fx  # noqa: E402


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    stream_py = fx.normalized()
    script, warnings = fx.rebuilt()
    fx.EXPECTED_STREAM.write_text(stream_py, encoding="utf-8", newline="\n")
    fx.EXPECTED_REBUILD.write_text(script, encoding="utf-8", newline="\n")
    print("wrote %s  sha256=%s" % (fx.EXPECTED_STREAM.name, sha(stream_py)))
    print("wrote %s  sha256=%s (warnings=%d)" % (fx.EXPECTED_REBUILD.name, sha(script), len(warnings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
