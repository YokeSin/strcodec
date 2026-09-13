"""Generate (and optionally run) the self-contained Jython rebuild script for a decoded stream."""
from __future__ import annotations

import json
from pathlib import Path

import transform
from clemb_runner import parse_sentinel, run_script_file
from common import (CLI_HINT, TOOL_DIR, log, now_iso, read_json, read_text, sha256_file, strcode_dir_for, to_posix,
                    write_json, write_text)

REBUILD_MARK = "===STRCODEC_REBUILD==="


class RebuildError(Exception):
    pass


def resolve_strcode_dir(target: Path | str) -> Path:
    t = Path(target)
    if t.is_dir() and t.name.lower().endswith(".strcode"):
        return t.resolve()
    if t.suffix.lower() == ".str":
        d = strcode_dir_for(t.resolve())
        if not d.is_dir():
            raise RebuildError("not decoded yet: %s (run: %s decode \"%s\")" % (d, CLI_HINT, t))
        return d
    raise RebuildError("target must be a .str file or a *.strcode directory: %s" % t)


def check_ready(d: Path, meta: dict, cfg: dict, text: str, retrain: bool) -> list[str]:
    """Problems that make a rebuild from this .strcode/ unreliable (empty list = ready).

    - the original .str changed since decode (sha256 in meta.json differs)
    - the decode was made by another tool version
    - a .nod file referenced by a NUGGET/SUPERNODE/OPAQUE marker in stream.py is missing (nuggets only when not retraining)
    """
    problems: list[str] = []
    src = Path(meta.get("source_path", ""))
    if src.is_file():
        try:
            if sha256_file(src) != meta.get("sha256"):
                problems.append("the original stream changed after it was decoded: %s (re-run: %s decode \"%s\"; "
                                "your edited stream.py is backed up automatically)" % (to_posix(src), CLI_HINT, to_posix(src)))
        except OSError as e:
            problems.append("cannot read the original stream %s: %s" % (to_posix(src), e))
    if meta.get("tool_version") != cfg.get("tool_version"):
        problems.append("decoded with strcodec %s, this is %s (re-run: %s decode --force)" % (
            meta.get("tool_version"), cfg.get("tool_version"), CLI_HINT))
    try:
        stmts, _ = transform.parse_stream_py(text)
    except SyntaxError:
        return problems  # reported by build_rebuild with the line number
    for st in stmts:
        if st.kind != "marker":
            continue
        nod = st.kwargs.get("nod")
        if st.marker == "NUGGET" and retrain:
            continue
        if not nod:
            problems.append("%s %s has no .nod file (decode could not save it%s)" % (
                st.marker, st.var, "; pass --retrain to rebuild nuggets from their builders" if st.marker == "NUGGET" else ""))
        elif not (d / str(nod)).is_file():
            problems.append("%s %s: referenced file is missing: %s" % (st.marker, st.var, to_posix(d / str(nod))))
    return problems


def prepare(target: Path | str, cfg: dict, out: str | None = None, retrain: bool = False,
            path_map: list[tuple[str, str]] | None = None, validate: bool = True,
            coding_header: bool = False, allow_stale: bool = False) -> dict:
    d = resolve_strcode_dir(target)
    for req in ("stream.py", "structure.json", "meta.json"):
        if not (d / req).exists():
            raise RebuildError("missing %s in %s (re-run: %s decode)" % (req, d, CLI_HINT))
    meta = read_json(d / "meta.json")
    structure = read_json(d / "structure.json")
    stem = meta.get("source_name", d.name)[:-4] if meta.get("source_name", "").lower().endswith(".str") else d.name[:-8]
    source_path = Path(meta.get("source_path", ""))
    text = read_text(d / "stream.py")
    ready_problems = check_ready(d, meta, cfg, text, retrain)
    if ready_problems and not allow_stale:
        raise RebuildError("not ready to rebuild (pass --allow-stale to override):\n  - " + "\n  - ".join(ready_problems))
    source_dir = source_path.parent if source_path.parent.exists() else d.parent
    out_str = Path(out).resolve() if out else (source_dir / (stem + cfg.get("output_suffix", "_rebuilt") + ".str"))
    if source_path.exists() and out_str.resolve() == source_path.resolve():
        raise RebuildError("refusing to overwrite the original stream: %s (choose another --out)" % out_str)
    rebuild_dir = d / "rebuild"
    script = rebuild_dir / (stem + "_rebuild.py")
    result_json = rebuild_dir / (stem + "_rebuild_result.json")
    log_path = rebuild_dir / (stem + "_rebuild.log")
    report = rebuild_dir / (stem + "_rebuild_report.md")
    source_vars = [n.get("var") for n in structure.get("nodes", []) if n.get("kind") == "source" and n.get("var")]
    ctx = transform.RebuildContext(
        stem=stem, source_path=to_posix(source_path), base_dir=to_posix(d), out_str=to_posix(out_str),
        result_json=to_posix(result_json), prelude=read_text(TOOL_DIR / "jython" / "rebuild_prelude.py"),
        tool_version=cfg.get("tool_version", "?"), generated_at=now_iso(), retrain=retrain, validate=validate,
        path_map=list(path_map or []), expected_nodes=int(meta.get("nodes", 0)), expected_links=int(meta.get("links", 0)),
        source_vars=source_vars, chunk_statements=int(cfg.get("chunk_statements", 40)),
        chunk_max_chars=int(cfg.get("chunk_max_chars", 20000)), big_literal_chars=int(cfg.get("big_literal_chars", 4000)),
        coding_header=coding_header,
    )
    try:
        script_text, warnings = transform.build_rebuild(text, ctx)
    except SyntaxError as e:
        raise RebuildError("stream.py is not parseable (line %s): %s" % (e.lineno, e.msg))
    warnings = ["stale decode: " + pr for pr in ready_problems] + warnings
    if result_json.exists():
        try:
            result_json.unlink()
        except OSError:
            pass
    write_text(script, script_text)
    prep = {"strcode_dir": d, "stem": stem, "script": script, "out_str": out_str, "result_json": result_json,
            "log": log_path, "report": report, "warnings": warnings, "retrain": retrain, "validate": validate,
            "expected_nodes": ctx.expected_nodes, "expected_links": ctx.expected_links,
            "script_lines": script_text.count("\n"), "prep_json": prep_json_path(d, stem)}
    # remembered for `report` (when the script is run separately via MCP/GUI): generator warnings, options, output
    saved = {k: (to_posix(v) if isinstance(v, Path) else v) for k, v in prep.items()
             if k in ("warnings", "retrain", "validate", "out_str", "script_lines", "expected_nodes", "expected_links", "script")}
    saved["generated_at"] = ctx.generated_at
    write_json(prep["prep_json"], saved)
    log("rebuild script generated: %s -> %s" % (script, out_str))
    return prep


def prep_json_path(d: Path, stem: str) -> Path:
    return d / "rebuild" / (stem + "_rebuild_prep.json")


def prep_for_report(d: Path) -> dict:
    """Reconstruct the prepare() info for `report` from meta.json and the saved prep json."""
    meta = read_json(d / "meta.json")
    stem = meta.get("source_name", "x.str")[:-4]
    rd = d / "rebuild"
    prep = {"strcode_dir": d, "stem": stem, "script": rd / (stem + "_rebuild.py"),
            "result_json": rd / (stem + "_rebuild_result.json"), "log": rd / (stem + "_rebuild.log"),
            "report": rd / (stem + "_rebuild_report.md"), "warnings": [], "retrain": None, "validate": None,
            "out_str": "?", "script_lines": 0, "expected_nodes": meta.get("nodes"), "expected_links": meta.get("links")}
    pj = prep_json_path(d, stem)
    if pj.exists():
        try:
            saved = read_json(pj)
            for k in ("warnings", "retrain", "validate", "out_str", "script_lines"):
                if k in saved:
                    prep[k] = saved[k]
        except Exception:
            pass
    return prep


def mcp_hint(prep: dict) -> str:
    args = {"script_file": to_posix(prep["script"]), "working_directory": to_posix(prep["strcode_dir"]),
            "log_file": to_posix(prep["log"])}
    return "spss-clemb-mcp execute_clemb " + json.dumps(args, ensure_ascii=False)


def load_result(prep: dict) -> dict | None:
    p = Path(prep["result_json"])
    if not p.exists():
        return None
    try:
        return read_json(p)
    except Exception:
        return None


def run(prep: dict, cfg: dict) -> dict:
    res = run_script_file(prep["script"], prep["strcode_dir"], log_path=prep["log"],
                          timeout=int(cfg.get("clemb_timeout_sec", 600)), cfg=cfg)
    sentinel = parse_sentinel(res.combined, REBUILD_MARK)
    result = load_result(prep)
    report = render_report(prep, result, sentinel=sentinel, tail=res.tail(30) if (result is None or not result.get("saved")) else "")
    write_text(prep["report"], report)
    return {"run": res, "sentinel": sentinel, "result": result, "report_text": report}


def is_benign(f: dict) -> bool:
    """Known-harmless rejection: `values=[None, None]` on Range fields (documented JythonGenerator quirk)."""
    return f.get("kind") == "set" and f.get("prop") == "values" and "[null, null]" in str(f.get("error", ""))


def classify(result: dict | None) -> dict:
    """Outcome of a rebuild run. `ok` is what the exit code follows: saved, no failures, no validation failures,
    node/link counts as expected. Warnings (e.g. a path not found) do not fail the run but are reported."""
    if result is None:
        return {"status": "NO RESULT", "ok": False, "saved": False, "fails": [], "benign": [], "warns": [], "valid": [],
                "vfail": [], "counts_ok": False}
    saved = bool(result.get("saved"))
    all_fails = result.get("fails", []) or []
    benign = [f for f in all_fails if is_benign(f)]
    fails = [f for f in all_fails if not is_benign(f)]
    warns = result.get("warnings", []) or []
    valid = result.get("validation", []) or []
    vfail = [v for v in valid if not v.get("ok")]
    counts_ok = (result.get("nodes") == result.get("expected_nodes") and result.get("links") == result.get("expected_links"))
    if not saved:
        status = "FAILED"
    elif fails or vfail or not counts_ok:
        status = "SAVED WITH ISSUES"
    elif warns:
        status = "OK WITH WARNINGS"
    else:
        status = "OK"
    return {"status": status, "ok": status.startswith("OK"), "saved": saved, "fails": fails, "benign": benign,
            "warns": warns, "valid": valid, "vfail": vfail, "counts_ok": counts_ok}


def render_report(prep: dict, result: dict | None, sentinel: dict | None = None, tail: str = "") -> str:
    L: list[str] = []
    L.append("# rebuild report: %s" % prep["stem"])
    L.append("- generated script: %s (%d lines)" % (to_posix(prep["script"]), prep.get("script_lines", 0)))
    L.append("- output stream: %s" % to_posix(prep["out_str"]))
    L.append("- mode: %s | validate: %s | generated: %s" % ("retrain" if prep.get("retrain") else "transplant .nod", prep.get("validate"), now_iso()))
    for w in prep.get("warnings", []):
        L.append("- generator warning: %s" % w)
    if result is None:
        L.append("")
        L.append("## STATUS: NO RESULT (the script did not reach _finish; see the log)")
        if sentinel:
            L.append("sentinel: %s" % json.dumps(sentinel, ensure_ascii=False))
        if tail:
            L.append("```")
            L.append(tail)
            L.append("```")
        return "\n".join(L) + "\n"
    c = classify(result)
    saved, fails, benign, warns, valid, vfail = c["saved"], c["fails"], c["benign"], c["warns"], c["valid"], c["vfail"]
    L.append("")
    L.append("## STATUS: %s" % c["status"])
    L.append("(OK / OK WITH WARNINGS -> exit 0; SAVED WITH ISSUES / FAILED -> exit 1 unless --allow-issues)")
    L.append("| item | value |")
    L.append("|---|---|")
    L.append("| saved | %s |" % (result.get("out_str") if saved else "no (%s)" % result.get("save_error")))
    L.append("| nodes | %s (expected %s) |" % (result.get("nodes"), result.get("expected_nodes")))
    L.append("| links | %s (expected %s) |" % (result.get("links"), result.get("expected_links")))
    L.append("| setter/link failures | %d (+%d known benign) |" % (len(fails), len(benign)))
    L.append("| warnings | %d |" % len(warns))
    L.append("| validation | %d ok / %d failed |" % (len(valid) - len(vfail), len(vfail)))
    L.append("| elapsed (inside clemb) | %s ms |" % result.get("elapsed_ms"))
    if not c["counts_ok"]:
        L.append("")
        L.append("ISSUE: node/link counts differ from the decoded original. Expected only if you added/removed nodes in "
                 "stream.py (then re-run with --allow-issues); otherwise check the failures below.")
    if fails:
        L.append("")
        L.append("## failures (%d)" % len(fails))
        for f in fails[:60]:
            L.append("- %s" % json.dumps(f, ensure_ascii=False))
        if len(fails) > 60:
            L.append("- ... (%d more, see %s)" % (len(fails) - 60, to_posix(prep["result_json"])))
    if benign:
        L.append("")
        L.append("## known benign setter rejections (%d) - safe to ignore" % len(benign))
        L.append("Modeler rejects `values = [None, None]` for some Range fields (JythonGenerator emits `[null, null]`);")
        L.append("the stream runs normally without them (value ranges are re-read from data).")
        for f in benign[:20]:
            L.append("- %s.%s[%s]" % (f.get("node"), f.get("prop"), f.get("key")))
    if vfail:
        L.append("")
        L.append("## validation failures")
        for v in vfail:
            L.append("- %s: %s" % (v.get("var"), v.get("error")))
    if warns:
        L.append("")
        L.append("## warnings (%d)" % len(warns))
        for w in warns[:40]:
            L.append("- %s" % w)
    infos = result.get("infos", []) or []
    if infos:
        L.append("")
        L.append("## info")
        for i in infos[:40]:
            L.append("- %s" % i)
    if tail:
        L.append("")
        L.append("## clemb output tail")
        L.append("```")
        L.append(tail)
        L.append("```")
    L.append("")
    L.append("Next: `%s verify \"<original.str>\" \"%s\"` to compare structure and properties." % (CLI_HINT, to_posix(prep["out_str"])))
    return "\n".join(L) + "\n"
