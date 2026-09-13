"""Compare two decoded streams.

Structure (decides the exit code): node types / labels / positions and links.
Properties (informational unless --strict): per node, the values of the setters in stream.py, and the stream-level
settings. Internal nugget ids and canvas/state properties are ignored.
"""
from __future__ import annotations

import re
from collections import Counter

import transform

IGNORE_NODE_PROPS = {"builder_node_id", "builder_stream_id", "updating_node_id", "refresh_link_state"}
IGNORE_STREAM_PROPS = set(transform.STREAM_SKIP_PROPS)
_WS = re.compile(r"\s+")


def node_key(n: dict) -> tuple:
    return (n.get("type", "?"), n.get("label", ""), int(n.get("x", 0) or 0), int(n.get("y", 0) or 0))


def _fmt(k: tuple) -> str:
    return '%s "%s" @(%d,%d)' % k


def node_props(text: str) -> dict[str, dict[str, str]]:
    """var -> {prop or prop[key]: normalized value source} for every setter in a stream.py."""
    out: dict[str, dict[str, str]] = {}
    try:
        stmts, _ = transform.parse_stream_py(text)
    except SyntaxError:
        return out
    cache = transform.SourceSegmentCache(text)
    for st in stmts:
        if st.kind not in ("sp", "skp") or not st.var or not st.prop or st.prop in IGNORE_NODE_PROPS:
            continue
        args = st.node.value.args  # type: ignore[attr-defined]
        segs = [_WS.sub(" ", transform.replace_null(cache.segment(a) or "")).strip() for a in args[1:]]
        if st.kind == "skp" and len(segs) >= 2:
            key, val = segs[0], ", ".join(segs[1:])
            out.setdefault(st.var, {})["%s[%s]" % (st.prop, key)] = val
        else:
            out.setdefault(st.var, {})[st.prop] = ", ".join(segs)
    return out


def compare_props(sa: dict, sb: dict, ta: str, tb: str, name_a: str, name_b: str) -> tuple[bool, list[str]]:
    """Per-node property values (matched by node key) and stream-level settings."""
    lines: list[str] = []
    ok = True
    pa, pb = node_props(ta), node_props(tb)
    ka = {node_key(n): n.get("var") for n in sa.get("nodes", []) or [] if n.get("var")}
    kb = {node_key(n): n.get("var") for n in sb.get("nodes", []) or [] if n.get("var")}
    nodes_diff = 0
    shown = 0
    for k in sorted(set(ka) & set(kb), key=str):
        da, db = pa.get(ka[k], {}), pb.get(kb[k], {})
        only_a = sorted(set(da) - set(db))
        only_b = sorted(set(db) - set(da))
        changed = sorted(p for p in set(da) & set(db) if da[p] != db[p])
        if not (only_a or only_b or changed):
            continue
        ok = False
        nodes_diff += 1
        if shown < 20:
            shown += 1
            lines.append("  %s:" % _fmt(k))
            for p in changed[:10]:
                lines.append("    %s: %s=%s | %s=%s" % (p, name_a, _short(da[p]), name_b, _short(db[p])))
            if only_a:
                lines.append("    only set in %s: %s" % (name_a, ", ".join(only_a[:15]) + (" ..." if len(only_a) > 15 else "")))
            if only_b:
                lines.append("    only set in %s: %s" % (name_b, ", ".join(only_b[:15]) + (" ..." if len(only_b) > 15 else "")))
    if nodes_diff > shown:
        lines.append("  ... (%d more node(s) with property differences)" % (nodes_diff - shown))
    ma = {k: v for k, v in ((sa.get("stream") or {}).get("modified_props") or {}).items() if k not in IGNORE_STREAM_PROPS}
    mb = {k: v for k, v in ((sb.get("stream") or {}).get("modified_props") or {}).items() if k not in IGNORE_STREAM_PROPS}
    sdiff = sorted(k for k in set(ma) | set(mb) if ma.get(k, None) != mb.get(k, None))
    for k in sdiff:
        ok = False
        lines.append("  stream.%s: %s=%s | %s=%s" % (k, name_a, _short(repr(ma.get(k))), name_b, _short(repr(mb.get(k)))))
    lines.insert(0, "properties: %d node(s) with different values, %d stream setting(s) differ%s" % (
        nodes_diff, len(sdiff), "" if (nodes_diff or sdiff) else " -> PROPERTIES_MATCH"))
    return ok, lines


def _short(s: str, n: int = 70) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def compare(sa: dict, sb: dict, name_a: str = "A", name_b: str = "B",
            ta: str | None = None, tb: str | None = None) -> tuple[bool, bool, list[str]]:
    """Returns (structure_ok, properties_ok, report lines). properties_ok is True when no stream.py texts are given."""
    na = sa.get("nodes", []) or []
    nb = sb.get("nodes", []) or []
    lines: list[str] = []
    ok = True
    ca, cb = Counter(node_key(n) for n in na), Counter(node_key(n) for n in nb)
    lines.append("nodes: %s=%d, %s=%d" % (name_a, len(na), name_b, len(nb)))
    only_a = ca - cb
    only_b = cb - ca
    for k, c in sorted(only_a.items()):
        ok = False
        lines.append("  only in %s: %s x%d" % (name_a, _fmt(k), c))
    for k, c in sorted(only_b.items()):
        ok = False
        lines.append("  only in %s: %s x%d" % (name_b, _fmt(k), c))

    def link_keys(s: dict) -> Counter:
        by_id = {n["id"]: node_key(n) for n in s.get("nodes", []) or []}
        return Counter((by_id.get(l.get("from")), by_id.get(l.get("to"))) for l in s.get("links", []) or [])

    la, lb = link_keys(sa), link_keys(sb)
    lines.append("links: %s=%d, %s=%d" % (name_a, sum(la.values()), name_b, sum(lb.values())))
    for k, c in sorted((la - lb).items(), key=str):
        ok = False
        lines.append("  only in %s: %s -> %s x%d" % (name_a, _fmt(k[0]) if k[0] else "?", _fmt(k[1]) if k[1] else "?", c))
    for k, c in sorted((lb - la).items(), key=str):
        ok = False
        lines.append("  only in %s: %s -> %s x%d" % (name_b, _fmt(k[0]) if k[0] else "?", _fmt(k[1]) if k[1] else "?", c))

    props_ok = True
    if ta is not None and tb is not None:
        props_ok, plines = compare_props(sa, sb, ta, tb, name_a, name_b)
        lines.extend(plines)
        if not props_ok:
            lines.append("  (property differences do not change the exit code unless --strict; values that Modeler "
                         "derives from data or re-applies as defaults may legitimately differ)")
    lines.insert(0, "RESULT: %s" % ("STRUCTURE_MATCH" if ok else "STRUCTURE_DIFFERENT"))
    return ok, props_ok, lines
