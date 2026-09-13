"""Smoke tests for the Windows launcher (strcodec.cmd): interpreter selection and the three hook entry points.

Skipped on non-Windows, and when no CPython 3.10+ can be resolved by the launcher on this machine.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
LAUNCHER = TOOL / "strcodec.cmd"


def run_launcher(args, payload: bytes | None = None, cwd=None, env=None):
    return subprocess.run([str(LAUNCHER)] + args, input=payload, capture_output=True, cwd=str(cwd or TOOL),
                          env=env, timeout=120)


def launcher_usable() -> bool:
    if os.name != "nt" or not LAUNCHER.exists():
        return False
    try:
        return run_launcher(["--which"]).returncode == 0
    except Exception:
        return False


@unittest.skipUnless(launcher_usable(), "strcodec.cmd not usable here (non-Windows or no CPython 3.10+ found)")
class LauncherTests(unittest.TestCase):
    def test_which_prints_interpreter(self):
        r = run_launcher(["--which"])
        out = r.stdout.decode("utf-8", "replace").splitlines()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out[0].lower().endswith("python.exe"), out)
        self.assertTrue(out[1].startswith("source="), out)
        self.assertIn("CPython", out[2])

    def test_explicit_interpreter_env_var_is_honoured(self):
        env = dict(os.environ, STRCODEC_PYTHON=sys.executable)
        r = run_launcher(["--which"], env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.path.normcase(r.stdout.decode("utf-8", "replace").splitlines()[0].strip()),
                         os.path.normcase(sys.executable))

    def test_bad_explicit_interpreter_falls_back(self):
        env = dict(os.environ, STRCODEC_PYTHON=r"C:\does not exist\python.exe")
        r = run_launcher(["--which"], env=env)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_status_reports_python(self):
        r = run_launcher(["status", "--root", str(HERE)])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(b"python:", r.stdout)
        self.assertIn(b"selected_by=", r.stdout)

    def test_hook_guard_read_blocks_str(self):
        payload = json.dumps({"event": "PreToolUse", "tool": "read_file", "input": {"path": "x/y.str"}}).encode()
        r = run_launcher(["hook", "guard-read"], payload=payload)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn(b"strcodec", r.stderr)

    def test_hook_prompt_no_str(self):
        payload = json.dumps({"event": "UserPromptSubmit", "prompt": "hello"}).encode()
        r = run_launcher(["hook", "prompt"], payload=payload)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, b"")

    def test_hook_session_start_empty_workspace(self):
        payload = json.dumps({"event": "SessionStart", "session_id": "x"}).encode()
        r = run_launcher(["hook", "session-start"], payload=payload, cwd=HERE / "fixtures")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, b"")  # no .str files under fixtures/


if __name__ == "__main__":
    unittest.main()
