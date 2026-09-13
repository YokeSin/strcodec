"""Text transformations.

normalize:      JythonGenerator raw output  ->  stream.py (canonical, editable, deterministic)
build_rebuild:  stream.py                   ->  self-contained Jython rebuild script (clemb / GUI)

Performance note: source segments of AST nodes are taken through SourceSegmentCache (one line split +
one UTF-8 encoding per build) instead of ast.get_source_segment(), which on CPython 3.10 re-splits the
whole source on every call (thousands of calls per build made generation take ~90 s on Modeler's bundled
Python). The cache reproduces ast.get_source_segment() semantics exactly (byte column offsets,
\\r\\n / \\r / \\n line endings, no form-feed splitting, optional padding).
"""
from __future__ import annotations

import ast
import io
import json
import re
import tokenize
from dataclasses import dataclass, field

INTERNAL_PROPS = ("builder_node_id", "builder_stream_id", "updating_node_id", "refresh_link_state")
MARKERS = ("NUGGET", "SUPERNODE", "OPAQUE")
KIND_MARKER = {"applier": "NUGGET", "supernode": "SUPERNODE", "opaque": "OPAQUE"}

CREATE_RE = re.compile(
    r'^(\w+) = modeler\.script\.stream\(\)\.createAt\("([^"]*)", (u?"(?:[^"\\]|\\.)*"), (-?\d+), (-?\d+)\)\s*$'
)
FINDID_RE = re.compile(r'^# (\w+) = modeler\.script\.stream\(\)\.findByID\("([^"]+)"\)')
FINDTYPE_RE = re.compile(r'^# (\w+) = modeler\.script\.stream\(\)\.findByType\(')
LINK_RE = re.compile(r'^modeler\.script\.stream\(\)\.link\((\w+), (\w+)\)\s*$')
SETTER_RE = re.compile(r'^(\w+)\.set(Keyed)?PropertyValue\("([^"]+)", ')
INTERNAL_SETTER_RE = re.compile(r'^(\w+)\.setPropertyValue\("(' + "|".join(INTERNAL_PROPS) + r')", (.*)\)\s*$')


# --------------------------------------------------------------------------- helpers
def jy_str(s: str) -> str:
    """Jython unicode literal (escapes backslashes/quotes; keeps non-ASCII raw)."""
    return "u" + json.dumps(s, ensure_ascii=False)


def py_name_lit(s: str | None) -> str:
    return '"%s"' % s if s else "None"


def replace_null(stmt: str) -> str:
    """Replace the bare NAME token `null` with `None` (string literals untouched)."""
    if "null" not in stmt:
        return stmt
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(stmt).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return re.sub(r"(?<![\"'\w.])null(?![\"'\w])", "None", stmt)
    lines = stmt.split("\n")
    edits = [(t.start, t.end) for t in toks if t.type == tokenize.NAME and t.string == "null"]
    for (sr, sc), (er, ec) in reversed(edits):
        line = lines[sr - 1]
        lines[sr - 1] = line[:sc] + "None" + line[ec:]
    return "\n".join(lines)


_STREAM_CALL = ("modeler", ".", "script", ".", "stream", "(", ")")


def replace_stream_call(stmt: str) -> str:
    """Replace the call expression `modeler.script.stream()` with the name `stream` (string literals untouched)."""
    if "modeler.script.stream()" not in stmt:
        return stmt
    try:
        toks = [t for t in tokenize.generate_tokens(io.StringIO(stmt).readline)
                if t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT)]
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return stmt.replace("modeler.script.stream()", "stream")  # unparseable: best effort
    edits = []
    n = len(_STREAM_CALL)
    i = 0
    while i + n <= len(toks):
        win = toks[i:i + n]
        if (all(t.type in (tokenize.NAME, tokenize.OP) and t.string == w for t, w in zip(win, _STREAM_CALL))
                and win[0].start[0] == win[-1].end[0]):
            edits.append((win[0].start, win[-1].end))
            i += n
        else:
            i += 1
    lines = stmt.split("\n")
    for (sr, sc), (er, ec) in reversed(edits):
        line = lines[sr - 1]
        lines[sr - 1] = line[:sc] + "stream" + line[ec:]
    return "\n".join(lines)


def jy_lit(v) -> str:
    """Jython literal for a JSON-compatible value (None/bool/int/float/str/list/dict)."""
    if v is None:
        return "None"
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return jy_str(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(jy_lit(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join("%s: %s" % (jy_lit(k), jy_lit(x)) for k, x in v.items()) + "}"
    return jy_str(str(v))


def indent(text: str, n: int = 4) -> str:
    pad = " " * n
    return "\n".join(pad + ln if ln.strip() else ln for ln in text.split("\n"))


# --------------------------------------------------------------------------- source segments
_LINE_RE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+\Z")


def split_lines_like_parser(source: str) -> list[str]:
    """Split like the Python parser does (and like ast's private _splitlines_no_ff): line endings are kept,
    \\r\\n stays together, \\r alone and \\n alone end a line, form feed / other separators do not."""
    return _LINE_RE.findall(source)


def _pad_whitespace(source: str) -> str:
    """Replace all chars except '\\f\\t' in a line with spaces (same rule as ast.get_source_segment)."""
    return "".join(c if c in "\f\t" else " " for c in source)


class SourceSegmentCache:
    """Build-scoped replacement for ast.get_source_segment(source, node).

    The source is split into lines once and each line is UTF-8 encoded once; segment() then slices the
    cached byte lines with the node's (byte) column offsets. Instances are independent, so concurrent
    builds or threads never share state.
    """

    __slots__ = ("lines", "blines")

    def __init__(self, source: str):
        self.lines = split_lines_like_parser(source)
        self.blines = [ln.encode("utf-8") for ln in self.lines]

    def segment(self, node, padded: bool = False) -> str | None:
        try:
            if node.end_lineno is None or node.end_col_offset is None:
                return None
            lineno = node.lineno - 1
            end_lineno = node.end_lineno - 1
            col_offset = node.col_offset
            end_col_offset = node.end_col_offset
        except AttributeError:
            return None
        blines = self.blines
        if end_lineno == lineno:
            return blines[lineno][col_offset:end_col_offset].decode("utf-8")
        padding = _pad_whitespace(blines[lineno][:col_offset].decode("utf-8")) if padded else ""
        first = padding + blines[lineno][col_offset:].decode("utf-8")
        last = blines[end_lineno][:end_col_offset].decode("utf-8")
        return "".join([first, *self.lines[lineno + 1:end_lineno], last])


# --------------------------------------------------------------------------- parse generator output
@dataclass
class Block:
    var: str
    type: str
    label_lit: str
    x: int
    y: int
    node_id: str | None = None
    setters: list[str] = field(default_factory=list)  # normalized statements / kept comments

    @property
    def label(self) -> str:
        try:
            return str(ast.literal_eval(self.label_lit))
        except Exception:
            return self.label_lit


@dataclass
class Parsed:
    blocks: list[Block]
    links: list[tuple[str, str]]
    other: list[str]

    def block_by_var(self) -> dict[str, Block]:
        return {b.var: b for b in self.blocks}


def parse_generated(code: str) -> Parsed:
    blocks: list[Block] = []
    links: list[tuple[str, str]] = []
    other: list[str] = []
    bmap: dict[str, Block] = {}
    cur: Block | None = None
    for raw in code.splitlines():
        s = raw.strip()
        if not s:
            continue
        m = CREATE_RE.match(s)
        if m:
            cur = Block(var=m.group(1), type=m.group(2), label_lit=m.group(3), x=int(m.group(4)), y=int(m.group(5)))
            blocks.append(cur)
            bmap[cur.var] = cur
            continue
        m = FINDID_RE.match(s)
        if m:
            b = bmap.get(m.group(1))
            if b is not None:
                b.node_id = m.group(2)
            continue
        if FINDTYPE_RE.match(s):
            continue
        m = LINK_RE.match(s)
        if m:
            links.append((m.group(1), m.group(2)))
            continue
        if s.startswith("#"):
            if cur is not None:
                cur.setters.append(s)  # e.g. generator's "# var.setPropertyValue("x", ???)" for unknown props
            else:
                other.append(s)
            continue
        stmt = replace_null(replace_stream_call(s))
        m = SETTER_RE.match(s)
        target = bmap.get(m.group(1)) if m else None
        if target is not None:
            target.setters.append(stmt)
        else:
            other.append(stmt)
    return Parsed(blocks, links, other)


def topo_order(vars_: list[str], links: list[tuple[str, str]], pos: dict[str, tuple]) -> list[str]:
    """Kahn topological order; ties broken by canvas position (x, y) then name."""
    preds: dict[str, set] = {v: set() for v in vars_}
    succs: dict[str, list] = {v: [] for v in vars_}
    for a, b in links:
        if a in preds and b in preds and a != b:
            preds[b].add(a)
            succs[a].append(b)

    def key(v):
        return (pos.get(v, (0, 0)), v)

    ready = sorted([v for v in vars_ if not preds[v]], key=key)
    out: list[str] = []
    done: set = set()
    while ready:
        v = ready.pop(0)
        if v in done:
            continue
        done.add(v)
        out.append(v)
        for s in succs[v]:
            preds[s].discard(v)
            if not preds[s] and s not in done and s not in ready:
                ready.append(s)
        ready.sort(key=key)
    for v in sorted(vars_, key=key):  # cycles / leftovers
        if v not in done:
            out.append(v)
    return out


# --------------------------------------------------------------------------- normalize
FLAG_PAIRS = (("custom_name", "use_custom_name"), ("model_name", "use_model_name"))
# stream-level modified properties that are canvas/state noise or not settable (verified with clemb 19.0)
STREAM_SKIP_PROPS = ("parameters", "parameters_table", "min_canvas_height", "min_canvas_width", "use_max_set_size")
# stream-level properties that do not show up in getModifiedSlotProperties() but persist in the .str
STREAM_EXTRA_PROPS = ("script_language", "annotation")


def stream_settings(structure: dict) -> list[str]:
    """`stream.setPropertyValue(...)` / `PARAM(...)` lines restoring stream-level settings and parameters."""
    sinfo = structure.get("stream", {}) or {}
    mods = sinfo.get("modified_props", {}) or {}
    out: list[str] = []
    for prop in sorted(mods):
        if prop in STREAM_SKIP_PROPS:
            continue
        out.append('stream.setPropertyValue("%s", %s)' % (prop, jy_lit(mods[prop])))
    for prop in STREAM_EXTRA_PROPS:
        v = sinfo.get(prop) if prop not in mods else None
        if isinstance(v, str) and v.strip():
            out.append('stream.setPropertyValue("%s", %s)' % (prop, jy_lit(v)))
    for p in sinfo.get("parameters", []) or []:
        if not p.get("name"):
            continue
        out.append('PARAM(%s, value=%s, storage=%s, label=%s)' % (
            jy_str(p["name"]), jy_lit(p.get("value")), jy_lit(p.get("storage") or p.get("type") or None),
            jy_lit(p.get("label") or None)))
    return out
SETTER_PROP_RE = re.compile(r'^\w+\.set(?:Keyed)?PropertyValue\("([^"]+)"')


def flag_fixups(b: Block, info: dict) -> list[str]:
    """Modeler switches use_custom_name/use_model_name ON as a side effect of setting custom_name/model_name.
    If the original stream had the flag unmodified (= False), emit an explicit False so labels stay identical."""
    if not info:
        return []
    props = set()
    for s in b.setters:
        m = SETTER_PROP_RE.match(s)
        if m:
            props.add(m.group(1))
    modified = set(info.get("modified_props", []) or [])
    out = []
    for prop, flag in FLAG_PAIRS:
        if prop in props and flag not in props and flag not in modified:
            out.append('%s.setPropertyValue("%s", False)  # flag was not set in the original: keep the automatic label' % (b.var, flag))
    return out


def normalize(parsed: Parsed, structure: dict, cfg: dict, header: dict, read_only: bool = False) -> str:
    nodes = structure.get("nodes", []) or []
    by_id = {n.get("id"): n for n in nodes}
    by_var = {n.get("var"): n for n in nodes if n.get("var")}
    info_by_var: dict[str, dict] = {}
    for b in parsed.blocks:
        info = by_id.get(b.node_id) if b.node_id else None
        if info is None:
            info = by_var.get(b.var)
        info_by_var[b.var] = info or {}
    pos = {b.var: (b.x, b.y) for b in parsed.blocks}
    order = topo_order([b.var for b in parsed.blocks], parsed.links, pos)
    bmap = parsed.block_by_var()
    preds: dict[str, list[str]] = {}
    for a, b in parsed.links:
        preds.setdefault(b, []).append(a)

    lines: list[str] = []
    lines.append("# strcodec stream.py -- canonical editable form of: %s" % header.get("source_path", "?"))
    lines.append("# source sha256: %s | decoded: %s | tool: strcodec %s | Modeler: %s" % (
        header.get("sha256", "?"), header.get("decoded_at", "?"), header.get("tool_version", "?"),
        header.get("modeler_version", "?")))
    lines.append("# nodes: %d | links: %d" % (len(parsed.blocks), len(parsed.links)))
    lines.append("#")
    if read_only:
        lines.append("# READ-ONLY (supernode contents). Editing this file has no effect on rebuild in this version;")
        lines.append("# the supernode is transplanted as a whole from its .nod file.")
    else:
        lines.append("# Conventions:")
        lines.append("#  - Do NOT execute this file directly. Run:  .bob\\strcodec\\strcodec.cmd rebuild <the .str>")
        lines.append("#    (the launcher picks a CPython 3.10+ from PATH, or Modeler's bundled one; `python .bob/strcodec/strcodec.py` also works)")
        lines.append("#    -> rebuild/<stem>_rebuild.py (self-contained Jython for clemb / spss-clemb-mcp / Modeler GUI).")
        lines.append("#  - `stream` is bound by the rebuild script (a NEW stream from createStream). Never call modeler.script.stream().")
        lines.append("#  - One statement per line. Keep u\"...\" for strings. Use None (never null). No coding declaration.")
        lines.append("#  - Model nuggets are `var = NUGGET(type, label, x, y, nod=..., builder=..., input=...)`;")
        lines.append("#    supernodes `SUPERNODE(...)`, unknown node types `OPAQUE(...)`. Keep the marker; edit only its arguments.")
        lines.append("#    Nuggets are transplanted from their .nod file; pass --retrain to rebuild them by running the builder.")
        lines.append("#  - Add a node: `v = stream.createAt(\"type\", u\"label\", X, Y)` + setters, then `stream.link(a, v)` in the links section.")
        lines.append("#  - Internal nugget ids (builder_node_id, builder_stream_id, updating_node_id, refresh_link_state) are never restored.")
        lines.append("#  - Verify property names/values with ibm-docs-mcp before inventing new ones.")
        lines.append("#  - Stream-level settings (date/time formats, stream script, parameters) are in the first section;")
        lines.append("#    parameters are `PARAM(name, value=..., storage=..., label=...)`.")
    lines.append("")

    if not read_only:
        settings = stream_settings(structure)
        lines.append("# ---- stream settings | name: %s ----" % (structure.get("stream", {}) or {}).get("name", "?"))
        if settings:
            lines.extend(settings)
        else:
            lines.append("# (none modified)")
        lines.append("")

    for var in order:
        b = bmap[var]
        info = info_by_var.get(var, {})
        kind = info.get("kind", "process")
        lines.append('# ---- %s | %s | "%s" | @(%d, %d) | %s' % (var, b.type, info.get("label") or b.label, b.x, b.y, kind))
        if b.node_id:
            lines.append("# original id: %s" % b.node_id)
        marker = KIND_MARKER.get(kind)
        if marker == "NUGGET":
            nod = info.get("nod")
            builder_id = info.get("builder_node_id")
            builder_var = by_id.get(builder_id, {}).get("var") if builder_id else None
            inputs = preds.get(var, [])
            lines.append('%s = NUGGET("%s", %s, %d, %d, nod=%s, builder=%s, input=%s)' % (
                var, b.type, b.label_lit, b.x, b.y, jy_str(nod) if nod else "None",
                py_name_lit(builder_var), py_name_lit(inputs[0]) if inputs else "None"))
            internal = []
            for s in b.setters:
                m = INTERNAL_SETTER_RE.match(s)
                if m:
                    internal.append("%s=%s" % (m.group(2), m.group(3)))
            if internal:
                lines.append("# internal ids (not restored; Modeler regenerates them): " + ", ".join(internal))
            if not builder_var:
                lines.append("# note: builder node is not part of this stream (external model) -> rebuild needs the .nod file")
            if not nod:
                lines.append("# WARNING: no .nod file was saved for this nugget (%s)" % info.get("nod_error", "unknown reason"))
            for s in b.setters:
                if INTERNAL_SETTER_RE.match(s):
                    continue
                lines.append(s)
            lines.extend(flag_fixups(b, info))
        elif marker in ("SUPERNODE", "OPAQUE"):
            nod = info.get("nod")
            lines.append('%s = %s("%s", %s, %d, %d, nod=%s)' % (
                var, marker, b.type, b.label_lit, b.x, b.y, jy_str(nod) if nod else "None"))
            if marker == "SUPERNODE":
                lines.append("# contents (read-only in this version): supernodes/%s/stream.py" % var)
            else:
                lines.append("# unknown node type (extension not installed?) - transplanted from .nod if available")
            for s in b.setters:
                lines.append(s)
            lines.extend(flag_fixups(b, info))
        else:
            lines.append('%s = stream.createAt("%s", %s, %d, %d)' % (var, b.type, b.label_lit, b.x, b.y))
            lines.extend(b.setters)
            lines.extend(flag_fixups(b, info))
        lines.append("")

    if parsed.other:
        lines.append("# ---- other statements (from generator) ----")
        lines.extend(parsed.other)
        lines.append("")
    lines.append("# ---- links ----")
    idx = {v: i for i, v in enumerate(order)}
    for a, b in sorted(parsed.links, key=lambda ab: (idx.get(ab[0], 10**9), idx.get(ab[1], 10**9), ab)):
        lines.append("stream.link(%s, %s)" % (a, b))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- parse stream.py
@dataclass
class Stmt:
    kind: str  # create | marker | sp | skp | link | other
    src: str
    var: str | None = None
    prop: str | None = None
    marker: str | None = None
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)
    link: tuple | None = None
    node: object = None


def _lit(cache: SourceSegmentCache, node) -> object:
    seg = cache.segment(node)
    return ast.literal_eval(seg) if seg is not None else None


def parse_stream_py(text: str, cache: SourceSegmentCache | None = None) -> tuple[list[Stmt], list[str]]:
    """Split stream.py into classified top-level statements. Returns (stmts, assigned_names).

    `cache` lets a build reuse one SourceSegmentCache for every source lookup (created here otherwise)."""
    tree = ast.parse(text)
    cache = cache or SourceSegmentCache(text)
    stmts: list[Stmt] = []
    assigned: list[str] = []
    for node in tree.body:
        seg = cache.segment(node) or ""
        seg = replace_null(seg)
        st = Stmt(kind="other", src=seg, node=node)
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id not in assigned:
                    assigned.append(t.id)
            v = node.value
            if isinstance(v, ast.Call) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                st.var = node.targets[0].id
                f = v.func
                if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "stream" and f.attr == "createAt":
                    st.kind = "create"
                    st.args = [replace_null(cache.segment(a) or "") for a in v.args]
                elif isinstance(f, ast.Name) and f.id in MARKERS:
                    st.kind = "marker"
                    st.marker = f.id
                    try:
                        st.args = [_lit(cache, a) for a in v.args]
                        st.kwargs = {kw.arg: _lit(cache, kw.value) for kw in v.keywords}
                    except Exception:
                        st.args, st.kwargs = [], {}
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            v = node.value
            f = v.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                if f.attr in ("setPropertyValue", "setKeyedPropertyValue"):
                    st.kind = "sp" if f.attr == "setPropertyValue" else "skp"
                    st.var = f.value.id
                    try:
                        p = _lit(cache, v.args[0]) if v.args else None
                        st.prop = p if isinstance(p, str) else None
                    except Exception:
                        st.prop = None
                elif f.value.id == "stream" and f.attr == "link" and len(v.args) == 2 \
                        and all(isinstance(a, ast.Name) for a in v.args):
                    st.kind = "link"
                    st.link = (v.args[0].id, v.args[1].id)
        stmts.append(st)
    return stmts, assigned


# --------------------------------------------------------------------------- build rebuild script
@dataclass
class RebuildContext:
    stem: str
    source_path: str
    base_dir: str
    out_str: str
    result_json: str
    prelude: str
    tool_version: str = "0"
    generated_at: str = ""
    retrain: bool = False
    validate: bool = True
    path_map: list = field(default_factory=list)
    expected_nodes: int = 0
    expected_links: int = 0
    source_vars: list = field(default_factory=list)
    chunk_statements: int = 40
    chunk_max_chars: int = 20000
    big_literal_chars: int = 4000
    coding_header: bool = False


def _rewrite_setter(cache: SourceSegmentCache, st: Stmt, ctx: RebuildContext, warnings: list[str]) -> str:
    call = st.node.value  # type: ignore[attr-defined]
    fn = "_sp" if st.kind == "sp" else "_skp"
    args_src = [replace_null(cache.segment(a) or "") for a in call.args]
    if not args_src:
        return st.src
    if len(st.src) > ctx.big_literal_chars and len(args_src) >= 2:
        try:
            val = ast.literal_eval(args_src[-1])
            js = json.dumps(val, ensure_ascii=False, separators=(",", ":"))
            args_src[-1] = "_J(%s)" % jy_str(js)
        except Exception as e:  # leave as-is; may still work
            warnings.append("large literal for %s.%s left as-is (%s)" % (st.var, st.prop, e))
    return "%s(%s, %s)" % (fn, st.var, ", ".join(args_src))


def build_rebuild(text: str, ctx: RebuildContext) -> tuple[str, list[str]]:
    warnings: list[str] = []
    cache = SourceSegmentCache(text)  # the one and only line split / encode for this build
    stmts, assigned = parse_stream_py(text, cache)
    special = {s.var for s in stmts if s.kind == "marker"}
    part_stmts: list[str] = []
    special_setters: dict[str, list[str]] = {}
    links1: list[tuple[str, str]] = []
    links2: list[tuple[str, str]] = []
    markers: list[Stmt] = []
    for st in stmts:
        if st.kind == "marker":
            markers.append(st)
        elif st.kind in ("sp", "skp"):
            rewritten = _rewrite_setter(cache, st, ctx, warnings)
            if st.var in special:
                special_setters.setdefault(st.var, []).append(rewritten)
            else:
                part_stmts.append(rewritten)
        elif st.kind == "link":
            a, b = st.link  # type: ignore[misc]
            (links2 if (a in special or b in special) else links1).append((a, b))
        elif st.kind == "create" and len(st.args) == 4:
            # wrapped so that a failing createAt (unknown type, bad label) is recorded instead of aborting the chunk
            part_stmts.append('%s = _create("%s", %s)' % (st.var, st.var, ", ".join(st.args)))
        else:
            part_stmts.append(st.src)

    # chunk into functions (JVM 64KB method limit)
    parts: list[list[str]] = []
    cur: list[str] = []
    cur_chars = 0
    for s in part_stmts:
        if cur and (len(cur) >= ctx.chunk_statements or cur_chars + len(s) > ctx.chunk_max_chars):
            parts.append(cur)
            cur, cur_chars = [], 0
        cur.append(s)
        cur_chars += len(s)
    if cur:
        parts.append(cur)

    nugget_vars = [m.var for m in markers if m.marker == "NUGGET"]
    out: list[str] = []
    if ctx.coding_header:
        out.append("# -*- coding: utf-8 -*-")
        out.append("# NOTE: this header is for the Modeler GUI only; clemb.exe rejects it (strcodec strips it when running).")
    out.append("# ==== strcodec rebuild script (generated - do not edit; edit stream.py and re-run rebuild) ====")
    out.append("# source: %s" % ctx.source_path)
    out.append("# generated: %s | tool: strcodec %s | retrain=%s | validate=%s" % (
        ctx.generated_at, ctx.tool_version, ctx.retrain, ctx.validate))
    out.append("# Runs under SPSS Modeler Jython 2.7: clemb.exe -script <this file> -execute   (or Tools > Standalone Script in the GUI)")
    out.append("import os")
    out.append("import json")
    out.append("import traceback")
    out.append("import modeler.script")
    out.append("import modeler.api")
    out.append("from java.io import File, FileOutputStream, OutputStreamWriter")
    out.append("from java.lang import Throwable, System")
    out.append("")
    out.append("BASE_DIR = %s" % jy_str(ctx.base_dir))
    out.append("OUT_STR = %s" % jy_str(ctx.out_str))
    out.append("RESULT_JSON = %s" % jy_str(ctx.result_json))
    out.append("STREAM_NAME = %s" % jy_str(ctx.stem))
    out.append("RETRAIN = %s" % ("True" if ctx.retrain else "False"))
    out.append("VALIDATE = %s" % ("True" if ctx.validate else "False"))
    out.append("PATH_MAP = [%s]" % ", ".join("(%s, %s)" % (jy_str(a), jy_str(b)) for a, b in ctx.path_map))
    out.append("EXPECTED_NODES = %d" % ctx.expected_nodes)
    out.append("EXPECTED_LINKS = %d" % ctx.expected_links)
    out.append("SOURCE_VARS = [%s]" % ", ".join('"%s"' % v for v in ctx.source_vars))
    out.append("NUGGET_VARS = [%s]" % ", ".join('"%s"' % v for v in nugget_vars))
    out.append("")
    out.append(ctx.prelude.rstrip("\n"))
    out.append("")
    out.append("stream = _new_stream(STREAM_NAME)")
    out.append("")
    names = []
    glob = ", ".join(assigned)
    for i, part in enumerate(parts, 1):
        name = "build_part_%03d" % i
        names.append(name)
        out.append("def %s():" % name)
        if glob:
            out.append("    global %s" % glob)
        for s in part:
            out.append(indent(s))
        out.append("")
    out.append("_run_parts([%s])" % ", ".join(names))
    out.append("")
    out.append("# ---- links (ordinary nodes) ----")
    for a, b in links1:
        out.append('_link_v("%s", "%s")' % (a, b))
    out.append("")
    out.append("# ---- links involving nuggets / supernodes / opaque nodes (applied as soon as both ends exist) ----")
    for a, b in links2:
        out.append('_pend("%s", "%s")' % (a, b))
    out.append("")
    out.append("# ---- nuggets / supernodes / opaque nodes ----")
    for m in markers:
        out.append(m.src)
        for s in special_setters.get(m.var, []):
            out.append(s)
        out.append("_link_pending()")
        out.append("")
    out.append("_link_pending(True)")
    out.append("")
    out.append("# ---- validate / save / report ----")
    out.append("_validate(SOURCE_VARS, NUGGET_VARS)")
    out.append("_finish(EXPECTED_NODES, EXPECTED_LINKS)")
    out.append("")
    return "\n".join(out), warnings
