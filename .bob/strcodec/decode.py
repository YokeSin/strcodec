"""Decode a .str into <stem>.strcode/ (generated_raw.py, structure.json, stream.py, summary.md, *.nod, meta.json)."""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import summarize
import transform
from clemb_runner import parse_sentinel, run_jython
from common import (TOOL_DIR, log, now_iso, pid_alive, read_json, read_text, sha256_file, sha256_text, stamp,
                    strcode_dir_for, to_posix, write_json, write_text)

RESULT_MARK = "===STRCODEC_RESULT==="
ERROR_MARK = "===STRCODEC_ERROR==="
GENERATED_ARTIFACTS = ("generated_raw.py", "structure.json", "_extract.log")
GENERATED_DIRS = ("nuggets", "supernodes", "opaque")


class DecodeError(Exception):
    pass


class DirLock:
    def __init__(self, out_dir: Path, wait_sec: int = 120, stale_sec: int = 900):
        self.path = out_dir / ".lock"
        self.wait_sec = wait_sec
        self.stale_sec = stale_sec

    def __enter__(self):
        deadline = time.time() + self.wait_sec
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                    owner = int((self.path.read_text(encoding="utf-8", errors="ignore").strip() or "0"))
                except (FileNotFoundError, ValueError):
                    continue
                if age > self.stale_sec or (owner and not pid_alive(owner)):
                    # stale (old, or the owning process is gone, e.g. a killed background prewarm)
                    try:
                        self.path.unlink()
                    except OSError:
                        pass
                    continue
                if time.time() > deadline:
                    raise DecodeError("timed out waiting for another decode of the same stream (%s)" % self.path)
                time.sleep(2)

    def __exit__(self, *exc):
        try:
            self.path.unlink()
        except OSError:
            pass


def meta_path(out_dir: Path) -> Path:
    return out_dir / "meta.json"


def is_cache_valid(str_path: Path, out_dir: Path, cfg: dict, sha: str | None = None) -> bool:
    """Cached decode usable: meta/summary/stream.py/structure.json present, same tool version and .str sha256,
    and every .nod file that the decode saved (structure.json `nod`) still exists."""
    mp = meta_path(out_dir)
    for req in (mp, out_dir / "summary.md", out_dir / "stream.py", out_dir / "structure.json"):
        if not req.exists():
            return False
    try:
        meta = read_json(mp)
    except Exception:
        return False
    if meta.get("tool_version") != cfg.get("tool_version"):
        return False
    sha = sha or sha256_file(str_path)
    if meta.get("sha256") != sha:
        return False
    try:
        for nod in referenced_nods(read_json(out_dir / "structure.json")):
            if not (out_dir / nod).is_file():
                return False
    except Exception:
        return False
    return True


def referenced_nods(structure: dict) -> list[str]:
    out: list[str] = []

    def walk(nodes):
        for n in nodes or []:
            if n.get("nod"):
                out.append(str(n["nod"]))
            if n.get("children"):
                walk(n["children"].get("nodes"))
    walk(structure.get("nodes"))
    return out


def _cached_result(str_path: Path, out_dir: Path) -> dict:
    return {"dir": out_dir, "cached": True, "summary_path": out_dir / "summary.md",
            "stream_py": out_dir / "stream.py", "meta": read_json(meta_path(out_dir))}


def decode_stream(str_path: Path | str, cfg: dict, force: bool = False, root: Path | None = None) -> dict:
    str_path = Path(str_path).resolve()
    if not str_path.is_file() or str_path.suffix.lower() != ".str":
        raise DecodeError("not a .str file: %s" % str_path)
    out_dir = strcode_dir_for(str_path)
    root = Path(root or Path.cwd())
    sha = sha256_file(str_path)
    if not force and is_cache_valid(str_path, out_dir, cfg, sha):
        return _cached_result(str_path, out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with DirLock(out_dir, int(cfg.get("lock_wait_sec", 120))):
        if not force and is_cache_valid(str_path, out_dir, cfg, sha):
            return _cached_result(str_path, out_dir)
        return _decode_locked(str_path, out_dir, cfg, root, sha)


def _backup_edited_stream_py(out_dir: Path) -> str | None:
    sp = out_dir / "stream.py"
    mp = meta_path(out_dir)
    if not sp.exists() or not mp.exists():
        return None
    try:
        old_meta = read_json(mp)
        if sha256_text(read_text(sp)) != old_meta.get("stream_py_sha256"):
            bak = out_dir / ("stream.py.bak-" + stamp())
            shutil.copy2(sp, bak)
            return to_posix(bak)
    except Exception:
        return None
    return None


def _clean(out_dir: Path) -> None:
    for d in GENERATED_DIRS:
        p = out_dir / d
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    for f in GENERATED_ARTIFACTS:
        p = out_dir / f
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


def _normalize_children(out_dir: Path, nodes: list, cfg: dict, header: dict, prefix: str = "") -> None:
    for n in nodes:
        child = n.get("children")
        if not child or not n.get("var"):
            continue
        code_file = out_dir / child.get("code_file", "")
        if not code_file.exists():
            continue
        parsed = transform.parse_generated(read_text(code_file))
        text = transform.normalize(parsed, child, cfg, header, read_only=True)
        write_text(out_dir / "supernodes" / (prefix + n["var"]) / "stream.py", text)
        _normalize_children(out_dir, child.get("nodes", []), cfg, header, prefix + n["var"] + "/supernodes/")


def _decode_locked(str_path: Path, out_dir: Path, cfg: dict, root: Path, sha: str) -> dict:
    t0 = time.time()
    backup = _backup_edited_stream_py(out_dir)
    _clean(out_dir)
    template = read_text(TOOL_DIR / "jython" / "extract_stream.py")
    params = {"STR_PATH": to_posix(str_path), "OUT_DIR": to_posix(out_dir), "TOOL_VERSION": cfg["tool_version"]}
    log("decode start: %s" % str_path)
    res = run_jython(template, workdir=out_dir, params=params, log_path=out_dir / "_extract.log",
                     timeout=int(cfg.get("clemb_timeout_sec", 600)), cfg=cfg, tag="extract")
    sentinel = parse_sentinel(res.combined, RESULT_MARK)
    if sentinel is None or not (out_dir / "structure.json").exists():
        err = ""
        for line in res.combined.splitlines():
            if line.strip().startswith(ERROR_MARK):
                err = line.strip()
        raise DecodeError("clemb extraction failed (rc=%s). %s\n--- clemb output tail ---\n%s" % (
            res.returncode, err, res.tail(40)))

    structure = read_json(out_dir / "structure.json")
    raw = read_text(out_dir / structure.get("code_file", "generated_raw.py"))
    parsed = transform.parse_generated(raw)
    header = {
        "source_path": to_posix(str_path), "sha256": sha, "decoded_at": now_iso(),
        "tool_version": cfg["tool_version"], "modeler_version": structure.get("modeler_version", "?"),
    }
    stream_py = transform.normalize(parsed, structure, cfg, header)
    write_text(out_dir / "stream.py", stream_py)
    _normalize_children(out_dir, structure.get("nodes", []), cfg, header)

    meta = {
        "tool_version": cfg["tool_version"],
        "source_path": to_posix(str_path),
        "source_name": str_path.name,
        "sha256": sha,
        "size": str_path.stat().st_size,
        "source_mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(str_path.stat().st_mtime)),
        "decoded_at": header["decoded_at"],
        "modeler_version": structure.get("modeler_version", "?"),
        "nodes": len(structure.get("nodes", [])),
        "links": len(structure.get("links", [])),
        "node_types": sorted(n.get("type", "?") for n in structure.get("nodes", [])),
        "nuggets": [n.get("var") for n in structure.get("nodes", []) if n.get("kind") == "applier"],
        "supernodes": [n.get("var") for n in structure.get("nodes", []) if n.get("kind") == "supernode"],
        "stream_py_sha256": sha256_text(stream_py),
        "stream_py_lines": stream_py.count("\n"),
        "generated_raw_lines": raw.count("\n"),
        "extract_elapsed_ms": sentinel.get("elapsed_ms"),
        "clemb_elapsed_sec": round(res.elapsed, 1),
        "backup_of_edited_stream_py": backup,
    }
    summary = summarize.build_summary(structure, parsed, meta, cfg, str_path, out_dir, root)
    write_text(out_dir / "summary.md", summary)
    write_json(meta_path(out_dir), meta)
    write_text(out_dir / "README.md", _readme(str_path, meta))
    log("decode done: %s nodes=%s links=%s in %.1fs" % (str_path.name, meta["nodes"], meta["links"], time.time() - t0))
    return {"dir": out_dir, "cached": False, "summary_path": out_dir / "summary.md",
            "stream_py": out_dir / "stream.py", "meta": meta, "backup": backup}


def _readme(str_path: Path, meta: dict) -> str:
    return "\n".join([
        "# %s.strcode/" % str_path.stem,
        "",
        "Decoded form of `%s` (generated by strcodec; regenerate with `python .bob/strcodec/strcodec.py decode --force`)." % str_path.name,
        "",
        "| file | purpose |",
        "|---|---|",
        "| summary.md | compact digest injected into the agent context (nodes, flow, paths, models, CLEM) |",
        "| stream.py | canonical editable Jython (one block per node, links at the end). Edit this, then `strcodec.py rebuild` |",
        "| structure.json | machine-readable nodes/links/stream info (ids, kinds, positions, modified property names) |",
        "| generated_raw.py | verbatim JythonGenerator output (reference only; contains `null`, not runnable) |",
        "| nuggets/*.nod | model nuggets saved with saveNodeToFile; transplanted by rebuild (no retraining needed) |",
        "| supernodes/*.nod, supernodes/<var>/stream.py | supernodes (transplanted whole; contents decoded read-only) |",
        "| rebuild/ | generated rebuild scripts, logs, result json and reports |",
        "| meta.json | cache key (sha256 of the .str, tool version) and statistics |",
        "",
        "Binary files (.str, .nod) must not be read as text.",
        "",
    ])
