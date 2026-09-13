"""Unit tests for the interpreter resolution mirror (pyfind.py). No real Program Files needed."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pyfind  # noqa: E402


def fake_run_factory(table):
    """table: {path -> (returncode, stdout)}; anything else 'fails to start'."""
    def run(cmd, **kw):
        exe = cmd[0]
        if exe in table:
            rc, out = table[exe]
            return subprocess.CompletedProcess(cmd, rc, stdout=out, stderr="")
        raise OSError("cannot start %s" % exe)
    return run


def touch(p: Path) -> str:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"")
    return str(p)


class ResolutionOrderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Program Files"          # space in path on purpose
        self.tool = Path(self.tmp.name) / "tool dir"
        self.tool.mkdir()
        self.m185 = touch(self.root / "IBM" / "SPSS" / "Modeler" / "18.5" / "python" / "python.exe")
        self.m190 = touch(self.root / "IBM" / "SPSS" / "Modeler" / "19.0" / "python" / "python.exe")
        self.srv = touch(self.root / "IBM" / "SPSS" / "ModelerServer" / "19.0" / "python" / "python.exe")
        self.env_py = touch(Path(self.tmp.name) / "my python" / "python.exe")
        self.old_py = touch(Path(self.tmp.name) / "old" / "python.exe")
        self.good = {self.m185: (0, "cpython 3.10.7\n"), self.m190: (0, "cpython 3.10.7\n"),
                     self.srv: (0, "cpython 3.10.7\n"), self.env_py: (0, "cpython 3.12.1\n"),
                     self.old_py: (0, "cpython 3.9.13\n")}

    def tearDown(self):
        self.tmp.cleanup()

    def cands(self, env, **kw):
        return pyfind.candidates(env=env, tool_dir=self.tool, roots=[str(self.root)], which=lambda n: None, **kw)

    def test_modeler_newest_first_no_hardcoded_version(self):
        c = self.cands({})  # nothing on PATH: only the bundled fallbacks remain
        self.assertEqual([x.source for x in c], ["modeler_Modeler_19.0", "modeler_Modeler_18.5", "modeler_ModelerServer_19.0"])
        self.assertEqual(c[0].path, self.m190)

    def test_path_python_before_bundled(self):
        # the Python already on the machine (py launcher, then PATH) wins over Modeler's bundled CPython
        py = touch(Path(self.tmp.name) / "launcher" / "py.exe")
        which = lambda n: {"py": py, "python": self.env_py}.get(n)  # noqa: E731
        run = fake_run_factory({py: (0, self.env_py + "\n")})
        clemb = self.root / "IBM" / "SPSS" / "Modeler" / "18.5" / "bin" / "clemb.exe"
        c = pyfind.candidates(env={"SPSS_MODELER_CLEMB_PATH": str(clemb)}, tool_dir=self.tool, roots=[str(self.root)],
                              which=which, run=run)
        self.assertEqual([x.source for x in c], ["py_launcher", "PATH", "SPSS_MODELER_CLEMB_PATH", "modeler_Modeler_19.0",
                                                 "modeler_Modeler_18.5", "modeler_ModelerServer_19.0"])
        self.assertEqual(c[0].path, self.env_py)

    def test_explicit_setting_beats_path_python(self):
        which = lambda n: {"python": self.env_py}.get(n)  # noqa: E731
        (self.tool / "python.path").write_text(self.m185 + "\n", encoding="utf-8")
        c = pyfind.candidates(env={"STRCODEC_PYTHON": self.m190}, tool_dir=self.tool, roots=[str(self.root)], which=which)
        self.assertEqual([x.source for x in c][:3], ["STRCODEC_PYTHON", "python.path", "PATH"])

    def test_env_var_first(self):
        c = self.cands({"STRCODEC_PYTHON": self.env_py})
        self.assertEqual(c[0].source, "STRCODEC_PYTHON")
        self.assertEqual(c[0].path, self.env_py)

    def test_python_path_file(self):
        (self.tool / "python.path").write_text("# comment\n\n%s\n" % self.env_py, encoding="utf-8")
        c = self.cands({})
        self.assertEqual(c[0].source, "python.path")
        self.assertEqual(c[0].path, self.env_py)

    def test_clemb_path_derived(self):
        clemb = self.root / "IBM" / "SPSS" / "Modeler" / "18.5" / "bin" / "clemb.exe"
        c = self.cands({"SPSS_MODELER_CLEMB_PATH": str(clemb)})
        self.assertEqual(c[0].source, "SPSS_MODELER_CLEMB_PATH")
        self.assertEqual(os.path.normcase(c[0].path), os.path.normcase(self.m185))

    def test_resolve_picks_first_ok_with_spaces(self):
        chosen, all_ = pyfind.resolve(run=fake_run_factory(self.good), env={"STRCODEC_PYTHON": self.env_py},
                                      tool_dir=self.tool, roots=[str(self.root)], which=lambda n: None)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.path, self.env_py)
        self.assertIn(" ", chosen.path)
        self.assertEqual(chosen.detail, "cpython 3.12.1")

    def test_old_version_rejected_then_fallback(self):
        chosen, all_ = pyfind.resolve(run=fake_run_factory(self.good), env={"STRCODEC_PYTHON": self.old_py},
                                      tool_dir=self.tool, roots=[str(self.root)], which=lambda n: None)
        self.assertEqual(all_[0].ok, False)
        self.assertIn("need CPython >= 3.10", all_[0].detail)
        self.assertEqual(chosen.path, self.m190)

    def test_missing_and_unrunnable(self):
        table = {self.m190: (1, "")}  # starts but fails; others cannot start / do not exist
        chosen, all_ = pyfind.resolve(run=fake_run_factory(table), env={"STRCODEC_PYTHON": str(self.root / "nope.exe")},
                                      tool_dir=self.tool, roots=[str(self.root)], which=lambda n: None)
        self.assertIsNone(chosen)
        self.assertEqual(all_[0].detail, "not found")
        self.assertTrue(all_[1].detail.startswith("failed to start"))

    def test_non_cpython_rejected(self):
        table = {self.m190: (0, "pypy 3.10.0\n"), self.m185: (0, "cpython 3.10.7\n")}
        chosen, _ = pyfind.resolve(run=fake_run_factory(table), env={}, tool_dir=self.tool, roots=[str(self.root)],
                                   which=lambda n: None)
        self.assertEqual(chosen.path, self.m185)

    def test_version_key(self):
        self.assertGreater(pyfind._version_key("19.0"), pyfind._version_key("18.5"))
        self.assertGreater(pyfind._version_key("20.0"), pyfind._version_key("19.0"))
        self.assertGreater(pyfind._version_key("18.5"), pyfind._version_key("ext"))


class CurrentInterpreterTests(unittest.TestCase):
    def test_check_real_interpreter(self):
        c = pyfind.check(pyfind.Candidate(sys.executable, "self"))
        self.assertTrue(c.exists)
        self.assertTrue(c.ok, c.detail)

    def test_describe_current(self):
        d = pyfind.describe_current()
        self.assertEqual(d["executable"], sys.executable)
        self.assertIn("python:", pyfind.format_current(d))


if __name__ == "__main__":
    unittest.main()
