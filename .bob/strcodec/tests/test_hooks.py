"""Unit tests for hook helpers (no clemb needed)."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
sys.path.insert(0, str(TOOL))

from common import load_config  # noqa: E402
from hooks.hook_prompt import STR_TOKEN_RE, candidates  # noqa: E402


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "sub dir").mkdir()
        (self.root / "a.str").write_bytes(b"\x00")
        (self.root / "sub dir" / "b.str").write_bytes(b"\x00")
        self.cfg = load_config()

    def tearDown(self):
        self.tmp.cleanup()

    def test_mention_forms(self):
        p = "@/a.str を説明して。 %s も同じ" % (self.root / "sub dir" / "b.str")
        found = candidates(p, self.root, self.cfg)
        names = sorted(f.name for f in found)
        self.assertEqual(names, ["a.str", "b.str"])

    def test_basename_only(self):
        found = candidates("b.str の中身は？", self.root, self.cfg)
        self.assertEqual([f.name for f in found], ["b.str"])

    def test_no_match(self):
        self.assertEqual(candidates("hello", self.root, self.cfg), [])
        self.assertEqual(candidates("missing.str", self.root, self.cfg), [])

    def test_token_regex(self):
        self.assertEqual(STR_TOKEN_RE.search("see C:/x/y.str now").group(1), "C:/x/y.str")
        self.assertIsNone(STR_TOKEN_RE.search("string.strip()"))


class GuardHookTests(unittest.TestCase):
    def run_hook(self, payload: dict) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(TOOL / "hooks" / "hook_guard_read.py")],
                              input=json.dumps(payload).encode("utf-8"), capture_output=True, cwd=str(TOOL))

    def test_blocks_str(self):
        r = self.run_hook({"event": "PreToolUse", "tool": "read_file", "input": {"path": "x/campaign_response.str"}})
        self.assertEqual(r.returncode, 2)
        self.assertIn(b"strcodec", r.stderr)

    def test_allows_text(self):
        r = self.run_hook({"event": "PreToolUse", "tool": "read_file", "input": {"path": "x/README.md"}})
        self.assertEqual(r.returncode, 0)

    def test_other_tool(self):
        r = self.run_hook({"event": "PreToolUse", "tool": "write_file", "input": {"path": "x/a.str"}})
        self.assertEqual(r.returncode, 0)


class PromptHookTests(unittest.TestCase):
    def test_malformed_json_does_not_block(self):
        r = subprocess.run([sys.executable, str(TOOL / "hooks" / "hook_prompt.py")], input=b"{not json",
                           capture_output=True, cwd=str(TOOL))
        self.assertEqual(r.returncode, 0)

    def test_prompt_without_str(self):
        r = subprocess.run([sys.executable, str(TOOL / "hooks" / "hook_prompt.py")],
                           input=json.dumps({"prompt": "hello"}).encode(), capture_output=True, cwd=str(TOOL))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, b"")


if __name__ == "__main__":
    unittest.main()
