# strcodec extract template (Jython 2.7 inside SPSS Modeler batch / clemb.exe).
# The CPython driver prepends parameter lines:  STR_PATH, OUT_DIR, TOOL_VERSION  (unicode literals).
# NOTE: never add a coding declaration to this file (clemb compiles scripts from a unicode string).
import re
import json
import traceback
import modeler.script
from java.io import File, FileInputStream, FileOutputStream, OutputStreamWriter
from java.lang import Throwable, System
from java.util import ArrayList

INTERNAL_PROPS = ("builder_node_id", "builder_stream_id", "updating_node_id", "refresh_link_state")
ID_RE = re.compile(r'^# (\w+) = modeler\.script\.stream\(\)\.findByID\("([^"]+)"\)', re.M)
_TR = None


def _w(path, text):
    f = File(path)
    p = f.getParentFile()
    if p is not None and not p.exists():
        p.mkdirs()
    w = OutputStreamWriter(FileOutputStream(f), "UTF-8")
    try:
        w.write(text)
    finally:
        w.close()


def _u(v):
    if v is None:
        return None
    if isinstance(v, unicode):
        return v
    if isinstance(v, str):
        return v.decode("utf-8", "replace")
    try:
        return unicode(v)
    except Exception:
        try:
            return unicode(repr(v))
        except Exception:
            return u"?"


def _jsonable(v, depth=0):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, long, float)):
        return v
    if isinstance(v, unicode):
        return v
    if isinstance(v, str):
        return v.decode("utf-8", "replace")
    if depth > 8:
        return _u(v)
    if isinstance(v, dict):
        return dict([(_u(k), _jsonable(x, depth + 1)) for k, x in v.items()])
    if hasattr(v, "entrySet"):
        try:
            return dict([(_u(e.getKey()), _jsonable(e.getValue(), depth + 1)) for e in v.entrySet()])
        except Exception:
            return _u(v)
    if isinstance(v, (list, tuple)) or hasattr(v, "iterator") or hasattr(v, "__iter__"):
        try:
            return [_jsonable(x, depth + 1) for x in v]
        except Exception:
            return _u(v)
    return _u(v)


def _safe(fn, default=None):
    try:
        return fn()
    except Throwable, e:
        return default
    except Exception, e:
        return default


def _err(e):
    try:
        if isinstance(e, Throwable):
            return _u(e.getClass().getName()) + u": " + _u(e.getMessage() or u"")
        return _u(e)
    except Exception:
        return u"?"


def _kind(n):
    t = _u(n.getTypeName())
    cls = type(n).__name__
    if t in (u"input_connector", u"output_connector"):
        return u"connector"
    if t.startswith(u"apply") or cls.startswith("Apply"):
        return u"applier"
    if t.endswith(u"_super") or hasattr(n, "getChildDiagram"):
        return u"supernode"
    if t.startswith(u"unknown"):
        return u"opaque"
    if cls.startswith("Build"):
        return u"builder"
    if _safe(lambda: n.isInitialNode(), False):
        return u"source"
    if _safe(lambda: n.isTerminalNode(), False):
        return u"terminal"
    return u"process"


def _gen(session, nodes):
    from com.spss.clementine.scripting.jython import JythonGenerator
    g = JythonGenerator(session)
    lst = ArrayList()
    for n in nodes:
        lst.add(n)
    return _u(g.generateStreamFragment(lst))


def _sorted_nodes(diagram):
    return sorted(list(diagram.iterator()), key=lambda n: (n.getXPosition(), n.getYPosition(), _u(n.getID())))


def _varmap(code):
    m = {}
    for mm in ID_RE.finditer(code):
        m[mm.group(2)] = mm.group(1)
    return m


def _node_info(diagram, n, varmap):
    info = {}
    nid = _u(n.getID())
    info["id"] = nid
    info["var"] = varmap.get(nid, u"")
    info["type"] = _u(n.getTypeName())
    info["class"] = _u(type(n).__name__)
    info["label"] = _u(_safe(lambda: n.getLabel(), u"")) or u""
    info["custom_name"] = _jsonable(_safe(lambda: n.getPropertyValue("custom_name"), None))
    info["x"] = _safe(lambda: n.getXPosition(), 0)
    info["y"] = _safe(lambda: n.getYPosition(), 0)
    info["kind"] = _kind(n)
    info["annotation"] = _u(_safe(lambda: n.getAnnotation(), u"")) or u""
    info["tooltip"] = _u(_safe(lambda: n.getToolTipText(), u"")) or u""
    mods = _safe(lambda: list(n.getModifiedSlotProperties()), None) or []
    info["modified_props"] = [_u(p) for p in mods]
    preds = []
    for i in range(_safe(lambda: diagram.predecessorCount(n), 0) or 0):
        p = _safe(lambda i=i: diagram.predecessorAt(n, i), None)
        if p is not None:
            preds.append(_u(p.getID()))
    succs = []
    for i in range(_safe(lambda: diagram.successorCount(n), 0) or 0):
        s = _safe(lambda i=i: diagram.successorAt(n, i), None)
        if s is not None:
            succs.append(_u(s.getID()))
    info["pred_ids"] = preds
    info["succ_ids"] = succs
    if info["kind"] == u"applier":
        for p in INTERNAL_PROPS:
            info[p] = _jsonable(_safe(lambda p=p: n.getPropertyValue(p), None))
        info["algorithm"] = _u(_safe(lambda: n.getLocalizedAlgorithmName(), u"")) or u""
    return info


def _extract_diagram(session, diagram, out_dir, rel_prefix, depth):
    nodes = _sorted_nodes(diagram)
    code = _gen(session, nodes)
    varmap = _varmap(code)
    infos = []
    links = []
    for n in nodes:
        info = _node_info(diagram, n, varmap)
        for s in info["succ_ids"]:
            links.append({"from": info["id"], "to": s})
        kind = info["kind"]
        if kind in (u"applier", u"supernode", u"opaque") and info["var"]:
            sub = {u"applier": u"nuggets", u"supernode": u"supernodes", u"opaque": u"opaque"}[kind]
            nod_rel = rel_prefix + sub + u"/" + info["var"] + u".nod"
            try:
                nod_abs = OUT_DIR + u"/" + nod_rel
                parent = File(nod_abs).getParentFile()
                if parent is not None and not parent.exists():
                    parent.mkdirs()
                _TR.saveNodeToFile(n, nod_abs)
                if not File(nod_abs).exists():
                    raise Exception("saveNodeToFile produced no file")
                info["nod"] = nod_rel
            except Throwable, e:
                info["nod"] = None
                info["nod_error"] = _err(e)
            except Exception, e:
                info["nod"] = None
                info["nod_error"] = _err(e)
        if kind == u"supernode" and depth < 3 and info["var"]:
            try:
                cd = n.getChildDiagram()
                info["children"] = _extract_diagram(session, cd, out_dir, rel_prefix + u"supernodes/" + info["var"] + u"/", depth + 1)
            except Throwable, e:
                info["children_error"] = _err(e)
            except Exception, e:
                info["children_error"] = _err(e)
        infos.append(info)
    code_file = rel_prefix + u"generated_raw.py"
    _w(OUT_DIR + u"/" + code_file, code)
    return {"code_file": code_file, "nodes": infos, "links": links, "node_count": len(infos), "link_count": len(links)}


def _modeler_version(session):
    vi = _safe(lambda: session.getServerVersionInfo(), None)
    if vi is None:
        return u""
    for name in ("getVersionString", "getVersion", "getProductVersion", "getFullVersion", "toString"):
        fn = getattr(vi, name, None)
        if fn is None:
            continue
        v = _safe(fn, None)
        if v is not None and not unicode(v).startswith(u"com.spss."):
            return _u(v)
    parts = []
    for name in sorted(dir(vi)):
        if name.startswith("get") and ("ersion" in name or "elease" in name):
            v = _safe(getattr(vi, name), None)
            if v is not None and not hasattr(v, "getClass"):
                parts.append(name[3:] + u"=" + _u(v))
    return u" ".join(parts)


def _stream_info(st):
    info = {}
    info["name"] = _u(_safe(lambda: st.getName(), u""))
    info["id"] = _u(_safe(lambda: st.getID(), u""))
    props = {}
    for p in (_safe(lambda: list(st.getModifiedSlotProperties()), None) or []):
        props[_u(p)] = _jsonable(_safe(lambda p=p: st.getPropertyValue(p), None))
    info["modified_props"] = props
    for p in ("execute_method", "script", "script_language", "encoding", "date_format", "time_format", "decimal_separator"):
        info[p] = _jsonable(_safe(lambda p=p: st.getPropertyValue(p), None))
    params = []
    for name in (_safe(lambda: list(st.getParameterNames()), None) or []):
        params.append({
            "name": _u(name),
            "value": _jsonable(_safe(lambda name=name: st.getParameterValue(name), None)),
            "type": _u(_safe(lambda name=name: st.getParameterType(name), None)),
            "storage": _u(_safe(lambda name=name: st.getParameterStorage(name), None)),
            "label": _u(_safe(lambda name=name: st.getParameterLabel(name), None)),
        })
    info["parameters"] = params
    info["annotation"] = _u(_safe(lambda: st.getAnnotation(), u"")) or u""
    info["comment_count"] = _safe(lambda: st.getCommentCount(), 0)
    return info


def main():
    global _TR
    t0 = System.currentTimeMillis()
    session = modeler.script.session()
    _TR = session.getTaskRunner()
    st = session.openProcessorStream(FileInputStream(File(STR_PATH)), True)
    result = {
        "tool_version": TOOL_VERSION,
        "source": STR_PATH,
        "modeler_version": _modeler_version(session),
        "stream": _stream_info(st),
    }
    d = _extract_diagram(session, st, OUT_DIR, u"", 0)
    result["code_file"] = d["code_file"]
    result["nodes"] = d["nodes"]
    result["links"] = d["links"]
    result["elapsed_ms"] = System.currentTimeMillis() - t0
    _w(OUT_DIR + u"/structure.json", json.dumps(result, ensure_ascii=False, indent=1))
    print("===STRCODEC_RESULT=== " + json.dumps({
        "nodes": len(d["nodes"]),
        "links": len(d["links"]),
        "elapsed_ms": result["elapsed_ms"],
    }))


try:
    main()
except Throwable, e:
    print("===STRCODEC_ERROR=== " + _err(e))
    traceback.print_exc()
    raise
except Exception, e:
    print("===STRCODEC_ERROR=== " + _u(e))
    traceback.print_exc()
    raise
