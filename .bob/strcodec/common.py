"""Shared helpers for strcodec (CPython 3.10+, standard library only)."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
LOG_DIR = TOOL_DIR / "logs"
# How users/agents should invoke the CLI (the launcher finds a CPython 3.10+: PATH first, Modeler's bundled one as fallback).
CLI_HINT = r".bob\strcodec\strcodec.cmd"

DEFAULT_CONFIG = {
    "tool_version": "0.3.1",
    "chunk_statements": 40,
    "chunk_max_chars": 20000,
    "big_literal_chars": 4000,
    "summary_max_lines": 300,
    "prewarm": True,
    "prewarm_max_files": 10,
    "guard_read": True,
    "max_prompt_files": 3,
    "clemb_timeout_sec": 600,
    "clemb_path": None,
    "ignore_dirs": [".git", "node_modules", ".venv", "venv", "__pycache__", ".bob", ".claude"],
    "max_scan_files": 500,
    "max_scan_depth": 8,
    "output_suffix": "_rebuilt",
    "lock_wait_sec": 120,
}


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    p = TOOL_DIR / "config.json"
    if p.exists():
        try:
            cfg.update(json.loads(p.read_text(encoding="utf-8-sig")))
        except Exception as e:  # pragma: no cover - defensive
            log(f"config.json unreadable, using defaults: {e}")
    return cfg


def setup_utf8_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def now_iso() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def log(msg: str, name: str = "strcodec.log") -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / name, "a", encoding="utf-8") as f:
            f.write(f"{now_iso()} [{os.getpid()}] {msg}\n")
    except Exception:
        pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path | str) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


def write_text(path: Path | str, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read_json(path: Path | str):
    return json.loads(read_text(path))


def write_json(path: Path | str, obj) -> None:
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def to_posix(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def strcode_dir_for(str_path: Path) -> Path:
    """x.str -> x.strcode (sidecar directory next to the stream)."""
    str_path = Path(str_path)
    return str_path.with_name(str_path.stem + ".strcode")


def rel_to(path: Path | str, root: Path | str) -> str:
    try:
        return to_posix(Path(path).resolve().relative_to(Path(root).resolve()))
    except Exception:
        return to_posix(Path(path))


def python_args() -> list[str]:
    """Isolation flags the current interpreter was started with (so child processes inherit them)."""
    f = sys.flags
    args: list[str] = []
    if getattr(f, "isolated", 0):
        args.append("-I")
    if getattr(f, "no_site", 0):
        args.append("-S")
    if getattr(f, "dont_write_bytecode", 0):
        args.append("-B")
    if getattr(f, "utf8_mode", 0):
        args += ["-X", "utf8"]
    return args


def python_cmd_prefix() -> list[str]:
    """`[sys.executable, <same flags>]` - never switch to a different Python for background work."""
    return [sys.executable] + python_args()


def pid_alive(pid: int) -> bool:
    """True if a process with this pid exists (Windows: OpenProcess; never uses os.kill, which terminates on Windows)."""
    try:
        if os.name == "nt":
            import ctypes
            k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            h = k32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
            k32.CloseHandle(h)
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def spawn_detached(cmd: list[str], cwd: Path) -> "subprocess.Popen":
    """Start a background process that survives the caller (hook) exiting: detached, new process group,
    no window, and (when allowed) broken away from the caller's job object."""
    import subprocess
    kwargs = dict(cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                  close_fds=True)
    if os.name != "nt":
        return subprocess.Popen(cmd, start_new_session=True, **kwargs)
    base = (subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    breakaway = 0x01000000  # CREATE_BREAKAWAY_FROM_JOB
    try:
        return subprocess.Popen(cmd, creationflags=base | breakaway, **kwargs)
    except OSError:
        return subprocess.Popen(cmd, creationflags=base, **kwargs)


def find_str_files(root: Path, cfg: dict) -> list[Path]:
    """Find *.str files under root (pruned; never descends into *.strcode dirs)."""
    root = Path(root)
    ignore = set(cfg.get("ignore_dirs", []))
    max_files = int(cfg.get("max_scan_files", 500))
    max_depth = int(cfg.get("max_scan_depth", 8))
    found: list[Path] = []
    root_depth = len(root.resolve().parts)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = len(Path(dirpath).resolve().parts) - root_depth
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in ignore and not d.lower().endswith(".strcode") and not d.startswith(".")
        )
        if depth >= max_depth:
            dirnames[:] = []
        names_low = {fn.lower() for fn in filenames}
        suffix = str(cfg.get("output_suffix", "_rebuilt")).lower()
        for fn in sorted(filenames):
            if fn.lower().endswith(".str"):
                stem = fn[:-4].lower()
                # X_rebuilt.str next to X.str is strcodec's own output, not a workspace stream
                if suffix and stem.endswith(suffix) and (stem[: -len(suffix)] + ".str") in names_low:
                    continue
                found.append(Path(dirpath) / fn)
                if len(found) >= max_files:
                    return found
    return found
