"""Locate a usable CPython 3.10+ for strcodec (Python mirror of strcodec.cmd's resolution order).

The batch launcher (strcodec.cmd) is the real bootstrap on Windows; this module provides the same
candidate list for diagnostics (`strcodec.cmd python-info`, `status`) and for unit tests, where the
candidate sources and the interpreter check are injectable. Keep the two in sync.

Resolution order (the Python already on the machine first, Modeler's bundled CPython only as a fallback):
  1. STRCODEC_PYTHON environment variable
  2. <tool dir>/python.path (first non-empty, non-# line)
  3. py -3 (Python launcher)   4. python on PATH
  5. SPSS_MODELER_CLEMB_PATH -> <Modeler>/python/python.exe
  6. <ProgramW6432|ProgramFiles|ProgramFiles(x86)>/IBM/SPSS/{Modeler,ModelerServer}/<version>/python/python.exe
     (newest version first; no product version is hard-coded)
Accepted: CPython, version >= 3.10, starts with the isolation flags.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
ISOLATION_FLAGS = ["-I", "-S", "-B", "-X", "utf8"]
CHECK_CODE = "import sys; print(sys.implementation.name, '%d.%d.%d' % sys.version_info[:3])"
MIN_VERSION = (3, 10)
VENDOR_DIRS = ("Modeler", "ModelerServer")
PYTHON_PATH_FILE = "python.path"


@dataclass
class Candidate:
    path: str
    source: str
    exists: bool = False
    ok: bool = False
    detail: str = "not tried"


def _version_key(name: str) -> tuple:
    nums = re.findall(r"\d+", name)
    return tuple(int(n) for n in nums) if nums else (-1,)


def program_roots(env=None) -> list[str]:
    env = os.environ if env is None else env
    roots: list[str] = []
    for var in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        v = env.get(var)
        if v and v not in roots:
            roots.append(v)
    return roots


def modeler_pythons(roots) -> list[tuple[str, str]]:
    """Bundled CPython candidates under each root, newest Modeler version first."""
    out: list[tuple[str, str]] = []
    for root in roots:
        for vendor in VENDOR_DIRS:
            base = Path(root) / "IBM" / "SPSS" / vendor
            try:
                versions = [d for d in base.iterdir() if d.is_dir()]
            except OSError:
                continue
            versions.sort(key=lambda d: _version_key(d.name), reverse=True)
            for d in versions:
                out.append((str(d / "python" / "python.exe"), "modeler_%s_%s" % (vendor, d.name)))
    return out


def read_python_path_file(tool_dir: Path | None = None) -> str | None:
    p = Path(tool_dir or TOOL_DIR) / PYTHON_PATH_FILE
    try:
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                return s
    except OSError:
        return None
    return None


def candidates(env=None, tool_dir: Path | None = None, roots=None, which=shutil.which, run=subprocess.run) -> list[Candidate]:
    env = os.environ if env is None else env
    out: list[Candidate] = []
    if env.get("STRCODEC_PYTHON"):
        out.append(Candidate(env["STRCODEC_PYTHON"], "STRCODEC_PYTHON"))
    p = read_python_path_file(tool_dir)
    if p:
        out.append(Candidate(p, PYTHON_PATH_FILE))
    py = which("py")
    if py:
        try:
            r = run([py, "-3", "-c", "import sys; print(sys.executable)"], capture_output=True, text=True, timeout=20)
            exe = (r.stdout or "").strip()
            if r.returncode == 0 and exe:
                out.append(Candidate(exe, "py_launcher"))
        except Exception:
            pass
    path_py = which("python")
    if path_py:
        out.append(Candidate(path_py, "PATH"))
    # fallbacks: Modeler's bundled CPython (not an IBM-supported use of it)
    clemb = env.get("SPSS_MODELER_CLEMB_PATH")
    if clemb:
        # <Modeler>\bin\clemb.exe -> <Modeler>\python\python.exe (abspath, not resolve(): keep 8.3 short names as given)
        out.append(Candidate(str(Path(os.path.abspath(clemb)).parent.parent / "python" / "python.exe"), "SPSS_MODELER_CLEMB_PATH"))
    for path, src in modeler_pythons(program_roots(env) if roots is None else roots):
        out.append(Candidate(path, src))
    return out


def check(cand: Candidate, run=subprocess.run) -> Candidate:
    """Run the candidate with the isolation flags and verify implementation/version."""
    cand.exists = os.path.isfile(cand.path)
    if not cand.exists:
        cand.detail = "not found"
        return cand
    try:
        r = run([cand.path, *ISOLATION_FLAGS, "-c", CHECK_CODE], capture_output=True, text=True, timeout=30)
    except Exception as e:  # not executable, timeout, ...
        cand.detail = "failed to start: %s" % e
        return cand
    m = re.match(r"(\w+)\s+(\d+)\.(\d+)\.(\d+)", (r.stdout or "").strip())
    if r.returncode != 0 or not m:
        cand.detail = "failed to start (rc=%s)" % r.returncode
        return cand
    impl = m.group(1)
    ver = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
    cand.detail = "%s %d.%d.%d" % (impl, *ver)
    cand.ok = impl == "cpython" and ver >= MIN_VERSION
    if not cand.ok:
        cand.detail += " (need CPython >= %d.%d)" % MIN_VERSION
    return cand


def resolve(run=subprocess.run, **kw) -> tuple[Candidate | None, list[Candidate]]:
    """First candidate that passes `check`; also returns the full list with per-candidate details."""
    cands = candidates(run=run, **kw)
    for c in cands:
        check(c, run=run)
        if c.ok:
            return c, cands
    return None, cands


def describe_current() -> dict:
    f = sys.flags
    return {
        "executable": sys.executable,
        "implementation": sys.implementation.name,
        "version": "%d.%d.%d" % sys.version_info[:3],
        "isolated": bool(getattr(f, "isolated", 0)),
        "no_site": bool(getattr(f, "no_site", 0)),
        "dont_write_bytecode": bool(getattr(f, "dont_write_bytecode", 0)),
        "utf8_mode": bool(getattr(f, "utf8_mode", 0)),
        "selected_by": os.environ.get("STRCODEC_PYTHON_SOURCE") or "direct (not via strcodec.cmd)",
    }


def format_current(d: dict | None = None) -> str:
    d = d or describe_current()
    flags = "".join(k[0].upper() if d[k] else "-" for k in ("isolated", "no_site", "dont_write_bytecode", "utf8_mode"))
    return "python: %s (%s %s, flags=%s [I=isolated S=no site B=no pyc U=utf8], selected_by=%s)" % (
        d["executable"], d["implementation"], d["version"], flags, d["selected_by"])
