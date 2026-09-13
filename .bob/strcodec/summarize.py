"""Build summary.md: a compact, context-injectable digest of a decoded stream."""
from __future__ import annotations

import ast
import re
from pathlib import Path

from common import CLI_HINT, rel_to, to_posix
from transform import Block, Parsed, topo_order

KEY_PROPS = [
    "custom_name", "full_filename", "new_name", "result_type", "formula_expr", "flag_expr", "nominal_expr",
    "cond_expr", "condition", "mode", "method", "model_name", "target", "targets", "inputs", "output_mode",
    "output_format", "keys", "fields", "first_n", "sample_type", "training_size", "testing_size",
    "random_seed", "use_boost", "min_child_records", "encoding", "delimit_other", "other",
]
PATH_PROP_RE = re.compile(r"(^full_filename$|_filename$|file_name$)")
EXPR_PROP_RE = re.compile(r"(_expr$|^condition$|_expression$|^formula$|^expr$)")
SP_RE = re.compile(r'^(\w+)\.setPropertyValue\("([^"]+)", (.*)\)$', re.S)
SKP_RE = re.compile(r'^(\w+)\.setKeyedPropertyValue\("([^"]+)", (u?"(?:[^"\\]|\\.)*"), (.*)\)$', re.S)
KIND_TAG = {"applier": "[nugget]", "supernode": "[super]", "builder": "[builder]", "opaque": "[unknown]"}


def lit(s: str):
    try:
        return ast.literal_eval(s)
    except Exception:
        return s


def short(v, n: int = 60) -> str:
    v = " ".join(str(v).split())
    return v if len(v) <= n else v[: n - 1] + "…"


def block_props(b: Block) -> tuple[dict[str, str], dict[str, dict]]:
    props: dict[str, str] = {}
    keyed: dict[str, dict] = {}
    for s in b.setters:
        if s.startswith("#"):
            continue
        m = SP_RE.match(s)
        if m:
            props[m.group(2)] = m.group(3)
            continue
        m = SKP_RE.match(s)
        if m:
            keyed.setdefault(m.group(2), {})[str(lit(m.group(3)))] = m.group(4)
    return props, keyed


def key_settings(b: Block, props: dict, keyed: dict) -> str:
    items = []
    for p in KEY_PROPS:
        if p in props:
            items.append("%s=%s" % (p, short(props[p], 48)))
    for kp in ("direction", "role"):
        if kp in keyed:
            targets = [k for k, v in keyed[kp].items() if "Target" in v]
            special = [k + ":" + str(lit(v)) for k, v in keyed[kp].items()
                       if any(t in v for t in ("Partition", "Split", "Frequency", "RecordID"))]
            if targets:
                items.append("target=" + ",".join(targets))
            if special:
                items.append("roles=" + ",".join(special))
    if "type" in keyed:
        items.append("typed_fields=%d" % len(keyed["type"]))
    return "; ".join(items)[:220]


def render_tree(nodes: list[dict]) -> list[str]:
    by_id = {n["id"]: n for n in nodes}
    succ = {n["id"]: sorted(n.get("succ_ids", []), key=lambda i: (by_id.get(i, {}).get("x", 0), by_id.get(i, {}).get("y", 0)))
            for n in nodes}
    roots = sorted([n for n in nodes if not n.get("pred_ids")], key=lambda n: (n.get("x", 0), n.get("y", 0)))
    lines: list[str] = []
    visited: set = set()

    def name(n):
        tag = KIND_TAG.get(n.get("kind"), "")
        return '%s "%s"%s' % (n.get("var") or n.get("id"), n.get("label", ""), (" " + tag) if tag else "")

    def walk(n, prefix, is_last, first):
        connector = "" if first else ("└─ " if is_last else "├─ ")
        if n["id"] in visited:
            lines.append(prefix + connector + name(n) + "  (see above)")
            return
        visited.add(n["id"])
        extra = ""
        if len(n.get("pred_ids", [])) > 1:
            others = [by_id.get(p, {}).get("var", p) for p in n["pred_ids"]]
            extra = "  (inputs: %s)" % ", ".join(others)
        lines.append(prefix + connector + name(n) + extra)
        children = [by_id[c] for c in succ.get(n["id"], []) if c in by_id]
        child_prefix = prefix + ("" if first else ("   " if is_last else "│  "))
        for i, c in enumerate(children):
            walk(c, child_prefix, i == len(children) - 1, False)

    for r in roots:
        walk(r, "", True, True)
        lines.append("")
    leftovers = [n for n in nodes if n["id"] not in visited]
    if leftovers:
        lines.append("(not reachable from a source node:)")
        for n in leftovers:
            lines.append("  " + name(n))
    return lines


def path_status(value: str, str_dir: Path) -> str:
    if value.startswith("$"):
        return "Modeler variable, not checked"
    if value.startswith("."):
        return "relative to the stream directory (Modeler notation), not checked"
    p = Path(value)
    if not p.is_absolute():
        p = str_dir / value
    try:
        return "exists" if p.exists() else "NOT FOUND"
    except OSError:
        return "unchecked"


def build_summary(structure: dict, parsed: Parsed, meta: dict, cfg: dict, str_path: Path, out_dir: Path, root: Path) -> str:
    nodes = structure.get("nodes", []) or []
    links = structure.get("links", []) or []
    by_id = {n["id"]: n for n in nodes}
    bmap = parsed.block_by_var()
    pos = {b.var: (b.x, b.y) for b in parsed.blocks}
    order = topo_order([b.var for b in parsed.blocks], parsed.links, pos)
    rel_dir = rel_to(out_dir, root)
    info_by_var = {n.get("var"): n for n in nodes if n.get("var")}
    nuggets = [n for n in nodes if n.get("kind") == "applier"]
    supers = [n for n in nodes if n.get("kind") == "supernode"]
    opaque = [n for n in nodes if n.get("kind") == "opaque"]
    sinfo = structure.get("stream", {}) or {}

    L: list[str] = []
    L.append("# %s — SPSS Modeler stream (%d nodes / %d links)" % (str_path.name, len(nodes), len(links)))
    L.append("source: %s | sha256: %s | decoded: %s | Modeler: %s" % (
        to_posix(str_path), meta.get("sha256", "")[:12], meta.get("decoded_at", "?"), short(meta.get("modeler_version", "?"), 40)))
    L.append("decoded: %s/stream.py (%d lines, canonical editable Jython) | %s/structure.json | %s/summary.md" % (
        rel_dir, meta.get("stream_py_lines", 0), rel_dir, rel_dir))
    L.append("nuggets: %s | supernodes: %s | stream name: %s | execute_method: %s | parameters: %d" % (
        ", ".join(n.get("var", "?") for n in nuggets) or "none",
        ", ".join(n.get("var", "?") for n in supers) or "none",
        sinfo.get("name", "?"), sinfo.get("execute_method", "?"), len(sinfo.get("parameters", []) or [])))
    L.append("")

    L.append("## ノード一覧 (data-flow order)")
    L.append("| var | type | label | @(x,y) | kind | key settings |")
    L.append("|---|---|---|---|---|---|")
    for var in order:
        b = bmap[var]
        info = info_by_var.get(var, {})
        props, keyed = block_props(b)
        L.append("| %s | %s | %s | (%d,%d) | %s | %s |" % (
            var, b.type, short(info.get("label", b.label), 40).replace("|", "\\|"), b.x, b.y,
            info.get("kind", "?"), key_settings(b, props, keyed).replace("|", "\\|")))
    L.append("")

    L.append("## データフロー")
    L.append("```")
    L.extend(render_tree(nodes))
    L.append("```")

    paths = []
    exprs = []
    str_dir = str_path.parent
    for var in order:
        b = bmap[var]
        props, keyed = block_props(b)
        for p, v in props.items():
            if PATH_PROP_RE.search(p):
                val = lit(v)
                if isinstance(val, str):
                    paths.append("- %s.%s = %s  (%s)" % (var, p, val, path_status(val, str_dir)))
            if EXPR_PROP_RE.search(p):
                exprs.append("- %s.%s = %s" % (var, p, short(lit(v), 160)))
    if paths:
        L.append("## 入出力パス")
        L.extend(paths)
        L.append("")
    if nuggets or any(n.get("kind") == "builder" for n in nodes):
        L.append("## モデル")
        for n in nodes:
            if n.get("kind") == "builder":
                b = bmap.get(n.get("var"))
                props, _ = block_props(b) if b else ({}, {})
                mn = short(lit(props.get("model_name", '""')), 40)
                L.append("- builder %s (%s) \"%s\"%s" % (
                    n.get("var"), n.get("type"), n.get("label"), (" model_name=" + mn) if mn else ""))
        for n in nuggets:
            bvar = by_id.get(n.get("builder_node_id") or "", {}).get("var")
            L.append("- nugget %s (%s) \"%s\" builder=%s nod=%s%s" % (
                n.get("var"), n.get("type"), n.get("label"), bvar or "external/none",
                n.get("nod") or "MISSING", (" algorithm=" + n["algorithm"]) if n.get("algorithm") else ""))
        L.append("")
    if exprs:
        L.append("## CLEM 式 / 条件")
        L.extend(exprs)
        L.append("")
    params = sinfo.get("parameters") or []
    script = sinfo.get("script") or ""
    if params or script:
        L.append("## パラメータ / ストリームスクリプト")
        for p in params:
            L.append("- param %s = %s (%s)" % (p.get("name"), short(p.get("value"), 60), p.get("type")))
        if script:
            L.append("- stream script (%d lines, execute_method=%s): first lines:" % (len(str(script).splitlines()), sinfo.get("execute_method")))
            for ln in str(script).splitlines()[:8]:
                L.append("    " + ln)
        L.append("")
    notes = []
    for n in nodes:
        if n.get("nod_error"):
            notes.append("- %s: .nod could not be saved (%s)" % (n.get("var"), short(n["nod_error"], 100)))
        if n.get("children_error"):
            notes.append("- %s: supernode contents could not be decoded (%s)" % (n.get("var"), short(n["children_error"], 100)))
        if n.get("kind") == "opaque":
            notes.append("- %s: unknown node type '%s' (extension not installed?); rebuild transplants it from .nod" % (n.get("var"), n.get("type")))
        if n.get("annotation"):
            notes.append("- %s annotation: %s" % (n.get("var"), short(n["annotation"], 160)))
    for s in supers:
        notes.append("- %s: supernode contents are read-only in this version -> %s/supernodes/%s/stream.py" % (s.get("var"), rel_dir, s.get("var")))
    if notes:
        L.append("## 注意")
        L.extend(notes)
        L.append("")
    L.append("## 使い方 (for the agent)")
    L.append("- .str と .nod はバイナリ。read_file しない。詳細は %s/stream.py をノード単位で読む（末尾に links）。" % rel_dir)
    L.append("- 変更・再現: skill `spss-str-rebuild` → `%s rebuild \"%s\"` → 生成された rebuild/%s_rebuild.py を spss-clemb-mcp (execute_clemb) で実行 → `%s report` / `verify`。" % (
        CLI_HINT, to_posix(str_path), str_path.stem, CLI_HINT))
    L.append("- 未知のノード型・プロパティは ibm-docs-mcp で裏取りしてから編集する。")
    return "\n".join(L) + "\n"
