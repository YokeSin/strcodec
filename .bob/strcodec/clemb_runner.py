"""Run Jython scripts with SPSS Modeler's clemb.exe (same conventions as spss-clemb-mcp)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from common import log, to_posix

DEFAULT_CLEMB = r"C:\Program Files\IBM\SPSS\Modeler\19.0\bin\clemb.exe"
JAVA_OPTS = "-Dfile.encoding=UTF-8 -Dclient.encoding.override=UTF-8 -Dsun.jnu.encoding=UTF-8"
CODING_RE = re.compile(r"^[ \t\f]*#.*?coding[:=][ \t]*([-\w.]+)")


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    log_text: str
    elapsed: float
    script_path: str
    command: list = field(default_factory=list)

    @property
    def combined(self) -> str:
        return "\n".join(x for x in (self.stdout, self.stderr, self.log_text) if x)

    def tail(self, n: int = 40) -> str:
        lines = [ln for ln in self.combined.splitlines() if ln.strip()]
        return "\n".join(lines[-n:])


def find_clemb(cfg: dict | None = None) -> str:
    cfg = cfg or {}
    candidates: list[str | None] = [cfg.get("clemb_path"), os.environ.get("SPSS_MODELER_CLEMB_PATH")]
    for cfgfile in (
        Path.home() / ".spss-modeler-clemb" / "config.json",
        Path.home() / ".mcp-servers" / "spss-clemb-mcp" / "config.json",
    ):
        try:
            if cfgfile.exists():
                candidates.append(json.loads(cfgfile.read_text(encoding="utf-8-sig")).get("clemb_path"))
        except Exception:
            pass
    candidates.append(DEFAULT_CLEMB)
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    raise FileNotFoundError(
        "clemb.exe not found. Set SPSS_MODELER_CLEMB_PATH or 'clemb_path' in .bob/strcodec/config.json"
    )


def jy_literal(value) -> str:
    """Python/Jython unicode literal for a string value (safe for backslashes/quotes/non-ASCII)."""
    return "u" + json.dumps(str(value), ensure_ascii=False)


def strip_coding_declaration(text: str) -> str:
    """clemb compiles scripts from a unicode string; a coding declaration is a SyntaxError there."""
    lines = text.split("\n")
    for i in range(min(2, len(lines))):
        if CODING_RE.match(lines[i]):
            lines[i] = "# (coding declaration removed by strcodec)"
    return "\n".join(lines)


def _env() -> dict:
    env = os.environ.copy()
    env["JAVA_TOOL_OPTIONS"] = JAVA_OPTS
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _creationflags() -> int:
    # never pop up a console window (hooks / background prewarm run without a visible console)
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _run(cmd: list[str], workdir: Path, timeout: int, log_path: Path | None, script_path: str) -> RunResult:
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True, timeout=timeout, env=_env(),
                              creationflags=_creationflags())
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = -1, e.stdout or b"", (e.stderr or b"") + f"\n[strcodec] clemb timed out after {timeout}s".encode()
    elapsed = time.time() - t0
    stdout = out.decode("utf-8", "replace") if isinstance(out, bytes) else str(out)
    stderr = err.decode("utf-8", "replace") if isinstance(err, bytes) else str(err)
    log_text = ""
    if log_path and Path(log_path).exists():
        try:
            log_text = Path(log_path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            log_text = ""
    log(f"clemb rc={rc} elapsed={elapsed:.1f}s script={script_path}")
    return RunResult(rc, stdout, stderr, log_text, elapsed, script_path, cmd)


def run_jython(
    script_text: str,
    workdir: Path,
    params: dict | None = None,
    log_path: Path | None = None,
    timeout: int = 600,
    cfg: dict | None = None,
    keep_temp: bool = False,
    tag: str = "tmp",
) -> RunResult:
    """Write script (with `NAME = u"value"` parameter lines prepended) to a temp file and run it."""
    clemb = find_clemb(cfg)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    header = "".join(f"{k} = {jy_literal(v)}\n" for k, v in (params or {}).items())
    body = strip_coding_declaration(script_text)
    tmp = workdir / f"_strcodec_{tag}_{os.getpid()}_{int(time.time() * 1000)}.py"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + ("\n" if header else "") + body)
    cmd = [clemb, "-script", str(tmp), "-execute"]
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-log", str(log_path)]
    try:
        return _run(cmd, workdir, timeout, log_path, to_posix(tmp))
    finally:
        if not keep_temp:
            try:
                tmp.unlink()
            except OSError:
                pass


def run_script_file(
    script_path: Path,
    workdir: Path,
    log_path: Path | None = None,
    timeout: int = 600,
    cfg: dict | None = None,
) -> RunResult:
    """Run an existing Jython script file as-is (used for generated rebuild scripts)."""
    clemb = find_clemb(cfg)
    cmd = [clemb, "-script", str(script_path), "-execute"]
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-log", str(log_path)]
    return _run(cmd, Path(workdir), timeout, log_path, to_posix(script_path))


def parse_sentinel(text: str, marker: str) -> dict | None:
    """Find the last `===MARKER=== {json}` line in clemb output."""
    found = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(marker):
            payload = line[len(marker):].strip()
            try:
                found = json.loads(payload)
            except json.JSONDecodeError:
                continue
    return found
