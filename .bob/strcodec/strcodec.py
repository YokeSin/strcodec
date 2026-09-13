"""strcodec - SPSS Modeler .str <-> Jython codec CLI.

  decode      <file.str> [--force] [--quiet] [--json] [--max-lines N]
  rebuild     <file.str | dir.strcode> [--out X.str] [--retrain] [--map OLD=NEW ...] [--no-validate] [--run]
              [--coding-header] [--allow-stale] [--allow-issues]
  report      <file.str | dir.strcode> [--allow-issues]
  verify      <a.str> <b.str> [--force] [--strict]
  prewarm     [--background] [--max N] [--root DIR]
  status      [--root DIR]
  python-info                      (which CPython is used / would be used, and why)
  hook        <prompt | session-start | guard-read>   (entry points for the Bob lifecycle hooks)

Run through the launcher so that the same CPython 3.10+ is used every time (the one on PATH, i.e. the one
spss-clemb-mcp uses; IBM SPSS Modeler's bundled CPython only as a fallback):   .bob\\strcodec\\strcodec.cmd <command> ...
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (CLI_HINT, TOOL_DIR, find_str_files, load_config, log, python_cmd_prefix, read_json, read_text,  # noqa: E402
                    rel_to, setup_utf8_stdio, spawn_detached, strcode_dir_for, to_posix, write_text)


def cmd_decode(a) -> int:
    from decode import DecodeError, decode_stream
    cfg = load_config()
    try:
        r = decode_stream(a.path, cfg, force=a.force)
    except DecodeError as e:
        print("[strcodec] decode failed: %s" % e, file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps({"dir": to_posix(r["dir"]), "cached": r["cached"], "meta": r["meta"]}, ensure_ascii=False, indent=1))
    elif not a.quiet:
        text = read_text(r["summary_path"])
        if a.max_lines:
            lines = text.splitlines()
            if len(lines) > a.max_lines:
                text = "\n".join(lines[: a.max_lines]) + "\n... (truncated; full text: %s)\n" % to_posix(r["summary_path"])
        print(text, end="")
    if r.get("backup"):
        print("[strcodec] note: your edited stream.py was backed up to %s" % r["backup"], file=sys.stderr)
    return 0


def _parse_map(items) -> list[tuple[str, str]]:
    out = []
    for it in items or []:
        if "=" not in it:
            raise SystemExit("--map expects OLD=NEW, got: %s" % it)
        old, new = it.split("=", 1)
        out.append((old.replace("\\", "/"), new.replace("\\", "/")))
    return out


def cmd_rebuild(a) -> int:
    import rebuild
    cfg = load_config()
    if a.coding_header and a.run:
        print("[strcodec] --coding-header is for the Modeler GUI only: clemb rejects a coding declaration, "
              "so it cannot be combined with --run", file=sys.stderr)
        return 2
    try:
        prep = rebuild.prepare(a.target, cfg, out=a.out, retrain=a.retrain, path_map=_parse_map(a.map),
                               validate=not a.no_validate, coding_header=a.coding_header, allow_stale=a.allow_stale)
    except rebuild.RebuildError as e:
        print("[strcodec] rebuild failed: %s" % e, file=sys.stderr)
        return 1
    if not a.run:
        if a.json:
            print(json.dumps({k: to_posix(v) if isinstance(v, Path) else v for k, v in prep.items()}, ensure_ascii=False, indent=1))
        else:
            print("[strcodec] rebuild script generated: %s (%d lines)" % (to_posix(prep["script"]), prep["script_lines"]))
            print("[strcodec] output stream will be: %s" % to_posix(prep["out_str"]))
            for w in prep["warnings"]:
                print("[strcodec] warning: %s" % w)
            print("[strcodec] run it with:  %s" % rebuild.mcp_hint(prep))
            print("[strcodec] then:  %s report \"%s\"" % (CLI_HINT, to_posix(prep["strcode_dir"])))
        return 0
    res = rebuild.run(prep, cfg)
    print(res["report_text"], end="")
    return _rebuild_exit(rebuild.classify(res["result"]), a.allow_issues)


def _rebuild_exit(c: dict, allow_issues: bool) -> int:
    """exit 0 only for STATUS OK / OK WITH WARNINGS; --allow-issues accepts anything that was saved."""
    if c["ok"]:
        return 0
    if allow_issues and c["saved"]:
        print("[strcodec] STATUS %s accepted because of --allow-issues" % c["status"], file=sys.stderr)
        return 0
    return 1


def cmd_report(a) -> int:
    import rebuild
    try:
        d = rebuild.resolve_strcode_dir(a.target)
    except rebuild.RebuildError as e:
        print("[strcodec] %s" % e, file=sys.stderr)
        return 1
    prep = rebuild.prep_for_report(d)
    result = rebuild.load_result(prep)
    if result:
        prep["out_str"] = result.get("out_str", prep["out_str"])
        prep["retrain"] = result.get("retrain")
    tail = ""
    if result is None and prep["log"].exists():
        lines = [ln for ln in read_text(prep["log"]).splitlines() if ln.strip()]
        tail = "\n".join(lines[-30:])
    text = rebuild.render_report(prep, result, tail=tail)
    write_text(prep["report"], text)
    print(text, end="")
    return _rebuild_exit(rebuild.classify(result), a.allow_issues)


def cmd_verify(a) -> int:
    from decode import DecodeError, decode_stream
    from verify import compare
    cfg = load_config()
    try:
        ra = decode_stream(a.a, cfg, force=a.force)
        rb = decode_stream(a.b, cfg, force=a.force)
    except DecodeError as e:
        print("[strcodec] verify failed: %s" % e, file=sys.stderr)
        return 1
    sa = read_json(Path(ra["dir"]) / "structure.json")
    sb = read_json(Path(rb["dir"]) / "structure.json")
    ta = read_text(Path(ra["dir"]) / "stream.py")
    tb = read_text(Path(rb["dir"]) / "stream.py")
    ok, props_ok, lines = compare(sa, sb, Path(a.a).name, Path(a.b).name, ta, tb)
    print("\n".join(lines))
    return 0 if (ok and (props_ok or not a.strict)) else 1


def cmd_prewarm(a) -> int:
    cfg = load_config()
    root = Path(a.root or Path.cwd()).resolve()
    if a.background:
        # inherit the current interpreter and its isolation flags (never switch to another Python)
        cmd = python_cmd_prefix() + [str(TOOL_DIR / "strcodec.py"), "prewarm", "--root", str(root), "--max", str(a.max)]
        spawn_detached(cmd, root)
        print("[strcodec] prewarm started in background (max %d files)" % a.max)
        return 0
    from decode import DecodeError, decode_stream, is_cache_valid
    done = 0
    for f in find_str_files(root, cfg):
        if done >= a.max:
            break
        if is_cache_valid(f, strcode_dir_for(f), cfg):
            continue
        try:
            decode_stream(f, cfg, root=root)
            done += 1
            print("[strcodec] prewarmed %s" % rel_to(f, root))
        except DecodeError as e:
            log("prewarm failed for %s: %s" % (f, e))
            print("[strcodec] prewarm failed for %s: %s" % (rel_to(f, root), str(e).splitlines()[0]))
    return 0


def cmd_status(a) -> int:
    from decode import is_cache_valid
    from pyfind import format_current
    cfg = load_config()
    root = Path(a.root or Path.cwd()).resolve()
    print(format_current())
    try:
        from clemb_runner import find_clemb
        print("clemb:  %s" % find_clemb(cfg))
    except FileNotFoundError as e:
        print("clemb:  NOT FOUND (%s)" % e)
    files = find_str_files(root, cfg)
    if not files:
        print("no .str files under %s" % root)
        return 0
    for f in files:
        d = strcode_dir_for(f)
        state = "decoded" if is_cache_valid(f, d, cfg) else ("stale" if d.exists() else "not decoded")
        print("%-12s %8d bytes  %s" % (state, f.stat().st_size, rel_to(f, root)))
    return 0


def cmd_python_info(a) -> int:
    from pyfind import format_current, resolve
    print(format_current())
    chosen, cands = resolve()
    print("candidates (resolution order of strcodec.cmd; first OK wins):")
    for c in cands:
        mark = "OK " if c.ok else "-- "
        print("  %s [%s] %s : %s" % (mark, c.source, c.path, c.detail))
    if chosen is None:
        print("no usable CPython 3.10+ found. Set STRCODEC_PYTHON or write the path into %s" % (TOOL_DIR / "python.path"))
        return 1
    print("launcher would use: %s (%s)" % (chosen.path, chosen.source))
    return 0


def cmd_hook(a) -> int:
    mod = importlib.import_module("hooks.hook_" + a.name.replace("-", "_"))
    return int(mod.main() or 0)


def main(argv=None) -> int:
    setup_utf8_stdio()
    p = argparse.ArgumentParser(prog="strcodec", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decode", help="decode a .str into <stem>.strcode/ and print summary.md")
    d.add_argument("path")
    d.add_argument("--force", action="store_true", help="ignore the cache and decode again")
    d.add_argument("--quiet", action="store_true")
    d.add_argument("--json", action="store_true")
    d.add_argument("--max-lines", type=int, default=0)
    d.set_defaults(fn=cmd_decode)
    r = sub.add_parser("rebuild", help="generate the Jython rebuild script from stream.py (add --run to execute it with clemb)")
    r.add_argument("target")
    r.add_argument("--out", help="output .str path (default: <stem>_rebuilt.str next to the source)")
    r.add_argument("--retrain", action="store_true", help="rebuild nuggets by running builders instead of transplanting .nod files")
    r.add_argument("--map", action="append", help="path prefix mapping OLD=NEW (repeatable)")
    r.add_argument("--no-validate", action="store_true")
    r.add_argument("--run", action="store_true", help="run the generated script with clemb.exe now and write the report")
    r.add_argument("--coding-header", action="store_true", help="add a utf-8 coding header (Modeler GUI only; not with --run)")
    r.add_argument("--allow-stale", action="store_true",
                   help="rebuild even if the original .str changed since decode, the tool version differs or a .nod is missing")
    r.add_argument("--allow-issues", action="store_true",
                   help="with --run: exit 0 as long as the stream was saved, even with failures/count mismatches")
    r.add_argument("--json", action="store_true")
    r.set_defaults(fn=cmd_rebuild)
    rp = sub.add_parser("report", help="render the report of the last rebuild run (e.g. after running it via spss-clemb-mcp)")
    rp.add_argument("target")
    rp.add_argument("--allow-issues", action="store_true", help="exit 0 as long as the stream was saved")
    rp.set_defaults(fn=cmd_report)
    v = sub.add_parser("verify", help="compare two streams: structure (exit code) and property values (informational, --strict)")
    v.add_argument("a")
    v.add_argument("b")
    v.add_argument("--force", action="store_true")
    v.add_argument("--strict", action="store_true", help="exit 1 also when property values or stream settings differ")
    v.set_defaults(fn=cmd_verify)
    pw = sub.add_parser("prewarm", help="decode all not-yet-decoded .str files under the workspace")
    pw.add_argument("--background", action="store_true")
    pw.add_argument("--max", type=int, default=10)
    pw.add_argument("--root")
    pw.set_defaults(fn=cmd_prewarm)
    st = sub.add_parser("status", help="show the Python/clemb in use and list .str files with their cache state")
    st.add_argument("--root")
    st.set_defaults(fn=cmd_status)
    pi = sub.add_parser("python-info", help="show which CPython strcodec.cmd would select and why")
    pi.set_defaults(fn=cmd_python_info)
    hk = sub.add_parser("hook", help="run a Bob lifecycle hook (reads the hook payload from stdin)")
    hk.add_argument("name", choices=["prompt", "session-start", "guard-read"])
    hk.set_defaults(fn=cmd_hook)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
