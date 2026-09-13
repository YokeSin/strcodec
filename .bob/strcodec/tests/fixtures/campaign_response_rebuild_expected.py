# ==== strcodec rebuild script (generated - do not edit; edit stream.py and re-run rebuild) ====
# source: C:/x/campaign_response.str
# generated:  | tool: strcodec 0 | retrain=False | validate=True
# Runs under SPSS Modeler Jython 2.7: clemb.exe -script <this file> -execute   (or Tools > Standalone Script in the GUI)
import os
import json
import traceback
import modeler.script
import modeler.api
from java.io import File, FileOutputStream, OutputStreamWriter
from java.lang import Throwable, System

BASE_DIR = u"C:/x/campaign_response.strcode"
OUT_STR = u"C:/x/campaign_response_rebuilt.str"
RESULT_JSON = u"C:/x/r.json"
STREAM_NAME = u"campaign_response"
RETRAIN = False
VALIDATE = True
PATH_MAP = []
EXPECTED_NODES = 8
EXPECTED_LINKS = 7
SOURCE_VARS = ["variablefile_node1"]
NUGGET_VARS = ["applyc50_node1"]

# ---- strcodec runtime prelude (embedded verbatim into every generated rebuild script) ----
# Jython 2.7 / SPSS Modeler. Expects module-level constants defined before this block:
#   BASE_DIR, OUT_STR, RESULT_JSON, STREAM_NAME, RETRAIN, VALIDATE, PATH_MAP
# and `stream` assigned right after this block via _new_stream(STREAM_NAME).
null = None
_FAILS = []
_WARNS = []
_INFOS = []
_VALID = []
_PENDING = []
_T0 = System.currentTimeMillis()
_TR = modeler.script.session().getTaskRunner()


def _log(msg):
    try:
        print(u"[strcodec] " + unicode(msg))
    except Exception:
        print("[strcodec] (unprintable message)")


def _err(e):
    try:
        if isinstance(e, Throwable):
            return unicode(e.getClass().getName()) + u": " + unicode(e.getMessage() or u"")
        return unicode(e)
    except Exception:
        return u"?"


def _new_stream(name):
    s = _TR.createStream(name, True, True)
    _log(u"created new stream: " + unicode(name))
    return s


def _abs(p):
    p = unicode(p).replace(u"\\", u"/")
    if p.startswith(u"$") or p.startswith(u"/") or (len(p) > 1 and p[1] == u":"):
        return p
    return BASE_DIR.rstrip(u"/") + u"/" + p


def _is_path_prop(prop):
    p = unicode(prop)
    return p == u"full_filename" or p.endswith(u"_filename") or p.endswith(u"file_name")


_CASE_INSENSITIVE = (File.separator == u"\\")  # Windows file system


def _norm_path(p):
    p = unicode(p).replace(u"\\", u"/")
    return p.lower() if _CASE_INSENSITIVE else p


def _map_prefix(s, old, new):
    """`old` must match `s` on a path-segment boundary (both compared normalized). Returns the mapped value or None."""
    ns, no = _norm_path(s), _norm_path(old).rstrip(u"/")
    if not no or not ns.startswith(no):
        return None
    rest = s.replace(u"\\", u"/")[len(no):]
    if rest and not rest.startswith(u"/"):
        return None  # e.g. C:/old matching C:/older
    return unicode(new).replace(u"\\", u"/").rstrip(u"/") + rest


def _path(v):
    if not isinstance(v, basestring):
        return v
    s = unicode(v)
    for old, new in PATH_MAP:
        m = _map_prefix(s, old, new)
        if m is not None:
            s = m
            _INFOS.append(u"path mapped: " + unicode(v) + u" -> " + s)
            break
    if s and not s.startswith(u"$") and not s.startswith(u".") and not File(s).exists():
        _WARNS.append(u"path not found: " + s)
    return s


def _nodename(node):
    try:
        return unicode(node.getTypeName()) + u":" + unicode(node.getLabel())
    except Exception:
        pass
    try:
        return u"stream:" + unicode(node.getName())
    except Exception:
        return u"?"


def _create(var, type_name, label, x, y):
    """stream.createAt with the failure recorded (never raises, so the rest of the chunk still runs)."""
    try:
        return stream.createAt(type_name, label, x, y)
    except Throwable, e:
        _FAILS.append({"kind": "create", "var": unicode(var), "type": unicode(type_name), "label": unicode(label), "error": _err(e)})
    except Exception, e:
        _FAILS.append({"kind": "create", "var": unicode(var), "type": unicode(type_name), "label": unicode(label), "error": _err(e)})
    return None


_STORAGE = {u"integer": u"INTEGER", u"real": u"REAL", u"string": u"STRING", u"boolean": u"BOOLEAN", u"flag": u"BOOLEAN",
            u"date": u"DATE", u"time": u"TIME", u"timestamp": u"TIMESTAMP"}


def PARAM(name, value=None, storage=None, label=None):
    """Stream parameter: storage (Integer/Real/String/Boolean/Date/Time/Timestamp) then value and label."""
    try:
        key = _STORAGE.get(unicode(storage or u"").lower())
        if key is not None:
            stream.setParameterStorage(name, getattr(modeler.api.ParameterStorage, key))
        stream.setParameterValue(name, value)
        if label:
            stream.setParameterLabel(name, label)
        _INFOS.append(u"parameter set: " + unicode(name))
    except Throwable, e:
        _FAILS.append({"kind": "param", "name": unicode(name), "error": _err(e)})
    except Exception, e:
        _FAILS.append({"kind": "param", "name": unicode(name), "error": _err(e)})


def _sp(node, prop, value):
    if node is None:
        _FAILS.append({"kind": "set", "prop": unicode(prop), "error": "target node is None"})
        return
    if _is_path_prop(prop):
        value = _path(value)
    try:
        node.setPropertyValue(prop, value)
    except Throwable, e:
        _FAILS.append({"kind": "set", "node": _nodename(node), "prop": unicode(prop), "error": _err(e)})
    except Exception, e:
        _FAILS.append({"kind": "set", "node": _nodename(node), "prop": unicode(prop), "error": _err(e)})


def _skp(node, prop, key, value):
    if node is None:
        _FAILS.append({"kind": "set", "prop": unicode(prop), "key": unicode(key), "error": "target node is None"})
        return
    if _is_path_prop(prop):
        value = _path(value)
    try:
        node.setKeyedPropertyValue(prop, key, value)
    except Throwable, e:
        _FAILS.append({"kind": "set", "node": _nodename(node), "prop": unicode(prop), "key": unicode(key), "error": _err(e)})
    except Exception, e:
        _FAILS.append({"kind": "set", "node": _nodename(node), "prop": unicode(prop), "key": unicode(key), "error": _err(e)})


def _J(s):
    return json.loads(s)


def _link_v(a, b):
    na = globals().get(a)
    nb = globals().get(b)
    if na is None or nb is None:
        _FAILS.append({"kind": "link", "from": a, "to": b, "error": "node variable missing or None"})
        return
    try:
        stream.link(na, nb)
    except Throwable, e:
        _FAILS.append({"kind": "link", "from": a, "to": b, "error": _err(e)})
    except Exception, e:
        _FAILS.append({"kind": "link", "from": a, "to": b, "error": _err(e)})


def _pend(a, b):
    _PENDING.append((a, b))


def _link_pending(final=False):
    remaining = []
    for a, b in _PENDING:
        na = globals().get(a)
        nb = globals().get(b)
        if na is None or nb is None:
            if final:
                _FAILS.append({"kind": "link", "from": a, "to": b, "error": "node variable missing or None"})
            else:
                remaining.append((a, b))
            continue
        try:
            stream.link(na, nb)
        except Throwable, e:
            _FAILS.append({"kind": "link", "from": a, "to": b, "error": _err(e)})
        except Exception, e:
            _FAILS.append({"kind": "link", "from": a, "to": b, "error": _err(e)})
    _PENDING[:] = remaining


def _run_parts(fns):
    for fn in fns:
        try:
            fn()
        except Throwable, e:
            _FAILS.append({"kind": "part", "part": fn.__name__, "error": _err(e)})
        except Exception, e:
            _FAILS.append({"kind": "part", "part": fn.__name__, "error": unicode(traceback.format_exc())})


def _insert_nod(nod, label, x, y, what):
    if not nod:
        return None
    p = _abs(nod)
    if not File(p).exists():
        _WARNS.append(what + u" file missing: " + p)
        return None
    try:
        node = _TR.insertNodeFromFile(p, stream)
    except Throwable, e:
        _FAILS.append({"kind": what, "label": unicode(label), "error": u"insertNodeFromFile failed: " + _err(e)})
        return None
    except Exception, e:
        _FAILS.append({"kind": what, "label": unicode(label), "error": u"insertNodeFromFile failed: " + _err(e)})
        return None
    try:
        if node.getXPosition() != x or node.getYPosition() != y:
            node.setXYPosition(x, y)
    except Throwable, e:
        _WARNS.append(u"could not reposition " + unicode(label))
    except Exception, e:
        _WARNS.append(u"could not reposition " + unicode(label))
    _INFOS.append(what + u" inserted from " + unicode(nod) + u": " + unicode(label))
    return node


def NUGGET(type_name, label, x, y, nod=None, builder=None, input=None):
    if not RETRAIN:
        node = _insert_nod(nod, label, x, y, u"nugget")
        if node is not None:
            return node
        # never retrain silently: retraining reads the data and produces a different model
        _FAILS.append({"kind": "nugget", "label": unicode(label),
                       "error": u"nugget .nod unavailable (%s); re-run decode, or pass --retrain to rebuild it from the builder" % (nod,)})
        return None
    b = globals().get(builder) if builder else None
    if b is None:
        _FAILS.append({"kind": "nugget", "label": unicode(label), "error": u"no builder node available (builder=%s) and no usable .nod" % (builder,)})
        return None
    before = set()
    for n in stream.iterator():
        try:
            before.add(unicode(n.getID()))
        except Exception:
            pass
    results = []
    try:
        b.run(results)
    except Throwable, e:
        _FAILS.append({"kind": "nugget", "label": unicode(label), "error": u"builder run failed: " + _err(e)})
        return None
    except Exception, e:
        _FAILS.append({"kind": "nugget", "label": unicode(label), "error": u"builder run failed: " + _err(e)})
        return None
    # Modeler may auto-insert the generated nugget into the stream when a builder runs; remove such
    # auto-added applier nodes so that the applier is created exactly once at the intended position.
    for n in list(stream.iterator()):
        try:
            if unicode(n.getID()) not in before and unicode(n.getTypeName()).startswith(u"apply"):
                stream.delete(n)
                _INFOS.append(u"removed auto-inserted nugget created by the builder run: " + unicode(label))
        except Throwable, e:
            _WARNS.append(u"could not remove auto-inserted nugget: " + _err(e))
        except Exception, e:
            _WARNS.append(u"could not remove auto-inserted nugget: " + _err(e))
    if len(results) == 0:
        _FAILS.append({"kind": "nugget", "label": unicode(label), "error": u"builder produced no model output"})
        return None
    try:
        node = stream.createModelApplierAt(results[0], label, x, y)
    except Throwable, e:
        _FAILS.append({"kind": "nugget", "label": unicode(label), "error": u"createModelApplierAt failed: " + _err(e)})
        return None
    except Exception, e:
        _FAILS.append({"kind": "nugget", "label": unicode(label), "error": u"createModelApplierAt failed: " + _err(e)})
        return None
    _INFOS.append(u"nugget rebuilt by running builder " + unicode(builder) + u": " + unicode(label))
    return node


def SUPERNODE(type_name, label, x, y, nod=None):
    node = _insert_nod(nod, label, x, y, u"supernode")
    if node is not None:
        return node
    # an empty supernode would silently drop its whole contents: record a failure instead
    _FAILS.append({"kind": "supernode", "label": unicode(label),
                   "error": u"supernode .nod unavailable (%s); re-run decode so that the contents are saved" % (nod,)})
    return None


def OPAQUE(type_name, label, x, y, nod=None):
    node = _insert_nod(nod, label, x, y, u"opaque node")
    if node is None:
        _FAILS.append({"kind": "opaque", "label": unicode(label), "error": u"unknown node type %s could not be inserted from .nod" % (type_name,)})
    return node


def _validate(source_vars, nugget_vars):
    if not VALIDATE:
        return
    for name in list(source_vars) + list(nugget_vars):
        node = globals().get(name)
        if node is None:
            continue
        t = None
        try:
            t = stream.createAt("table", u"_strcodec_validate_" + unicode(name), 2000, 2000)
            stream.link(node, t)
            outs = []
            t.run(outs)
            _VALID.append({"var": name, "ok": True})
        except Throwable, e:
            _VALID.append({"var": name, "ok": False, "error": _err(e)})
        except Exception, e:
            _VALID.append({"var": name, "ok": False, "error": _err(e)})
        if t is not None:
            try:
                stream.delete(t)
            except Throwable, e:
                _WARNS.append(u"could not delete validation table for " + unicode(name))
            except Exception, e:
                _WARNS.append(u"could not delete validation table for " + unicode(name))


def _write_utf8(path, text):
    f = File(path)
    p = f.getParentFile()
    if p is not None and not p.exists():
        p.mkdirs()
    w = OutputStreamWriter(FileOutputStream(f), "UTF-8")
    try:
        w.write(text)
    finally:
        w.close()


def _finish(expected_nodes, expected_links):
    nodes = list(stream.iterator())
    links = 0
    for n in nodes:
        try:
            links += stream.successorCount(n)
        except Throwable, e:
            pass
        except Exception, e:
            pass
    saved = False
    save_error = None
    try:
        d = File(OUT_STR).getParentFile()
        if d is not None and not d.exists():
            d.mkdirs()
        _TR.saveStreamToFile(stream, OUT_STR)
        saved = File(OUT_STR).exists()
    except Throwable, e:
        save_error = _err(e)
    except Exception, e:
        save_error = _err(e)
    types = []
    for n in nodes:
        try:
            types.append(unicode(n.getTypeName()))
        except Exception:
            types.append(u"?")
    result = {
        "saved": saved,
        "save_error": save_error,
        "out_str": OUT_STR,
        "nodes": len(nodes),
        "links": links,
        "expected_nodes": expected_nodes,
        "expected_links": expected_links,
        "node_types": sorted(types),
        "fails": _FAILS,
        "warnings": _WARNS,
        "infos": _INFOS,
        "validation": _VALID,
        "retrain": RETRAIN,
        "elapsed_ms": System.currentTimeMillis() - _T0,
    }
    try:
        _write_utf8(RESULT_JSON, json.dumps(result, ensure_ascii=False, indent=1))
    except Throwable, e:
        _log(u"could not write result json: " + _err(e))
    except Exception, e:
        _log(u"could not write result json: " + _err(e))
    vfail = len([v for v in _VALID if not v["ok"]])
    print("===STRCODEC_REBUILD=== " + json.dumps({
        "saved": saved,
        "nodes": len(nodes),
        "links": links,
        "expected_nodes": expected_nodes,
        "expected_links": expected_links,
        "fails": len(_FAILS),
        "warnings": len(_WARNS),
        "validation_failed": vfail,
        "elapsed_ms": result["elapsed_ms"],
    }))
    for f in _FAILS[:30]:
        _log(u"FAIL " + unicode(f))
    for w in _WARNS[:30]:
        _log(u"WARN " + unicode(w))
    for v in _VALID:
        _log(u"VALIDATE " + unicode(v))
    if saved:
        _log(u"saved: " + unicode(OUT_STR))
    else:
        _log(u"NOT SAVED: " + unicode(save_error))
# ---- end of prelude ----

stream = _new_stream(STREAM_NAME)

def build_part_001():
    global variablefile_node1, derive_node1, derive_node2, type_node1, c50_node1, applyc50_node1, analysis_node1, table_node1
    _sp(stream, "script_language", u"Python")
    variablefile_node1 = _create("variablefile_node1", "variablefile", u"顧客データ", 78, 97)
    _sp(variablefile_node1, "use_custom_name", True)
    _sp(variablefile_node1, "full_filename", u"C:/Users/Public/strcodec-sample/sample_customers.csv")
    _sp(variablefile_node1, "custom_name", u"顧客データ")
    derive_node1 = _create("derive_node1", "derive", u"単価", 210, 97)
    _sp(derive_node1, "formula_measure_type", u"Default")
    _sp(derive_node1, "use_custom_name", True)
    _sp(derive_node1, "has_coordinate_system", False)
    _sp(derive_node1, "custom_name", u"訪問あたり単価")
    _sp(derive_node1, "coordinate_system", u"")
    _sp(derive_node1, "formula_expr", u"spend / visits")
    _sp(derive_node1, "conditional_measure_type", u"Default")
    _sp(derive_node1, "collection_measure", u"Typeless")
    _sp(derive_node1, "new_name", u"spend_per_visit")
    derive_node2 = _create("derive_node2", "derive", u"優良顧客", 342, 97)
    _sp(derive_node2, "formula_measure_type", u"Default")
    _sp(derive_node2, "use_custom_name", True)
    _sp(derive_node2, "result_type", u"Flag")
    _sp(derive_node2, "custom_name", u"優良顧客")
    _sp(derive_node2, "flag_expr", u"'visits' > 12 and 'membership' == \"Y\"")
    _sp(derive_node2, "conditional_measure_type", u"Default")
    _sp(derive_node2, "new_name", u"heavy_user")
    type_node1 = _create("type_node1", "type", u"データ型", 462, 97)
    _sp(type_node1, "metadata", [[u"customer_id", u"Set", u"None", u"Specify", [u"C0001", u"C0002", u"C0003", u"C0004", u"C0005", u"C0006", u"C0007", u"C0008", u"C0009", u"C0010", u"C0011", u"C0012", u"C0013", u"C0014", u"C0015", u"C0016", u"C0017", u"C0018", u"C0019", u"C0020", u"C0021", u"C0022", u"C0023", u"C0024", u"C0025", u"C0026", u"C0027", u"C0028", u"C0029", u"C0030", u"C0031", u"C0032", u"C0033", u"C0034", u"C0035", u"C0036", u"C0037", u"C0038", u"C0039", u"C0040", u"C0041", u"C0042", u"C0043", u"C0044", u"C0045", u"C0046", u"C0047", u"C0048", u"C0049", u"C0050", u"C0051", u"C0052", u"C0053", u"C0054", u"C0055", u"C0056", u"C0057", u"C0058", u"C0059", u"C0060", u"C0061", u"C0062", u"C0063", u"C0064", u"C0065", u"C0066", u"C0067", u"C0068", u"C0069", u"C0070", u"C0071", u"C0072", u"C0073", u"C0074", u"C0075", u"C0076", u"C0077", u"C0078", u"C0079", u"C0080", u"C0081", u"C0082", u"C0083", u"C0084", u"C0085", u"C0086", u"C0087", u"C0088", u"C0089", u"C0090", u"C0091", u"C0092", u"C0093", u"C0094", u"C0095", u"C0096", u"C0097", u"C0098", u"C0099", u"C0100", u"C0101", u"C0102", u"C0103", u"C0104", u"C0105", u"C0106", u"C0107", u"C0108", u"C0109", u"C0110", u"C0111", u"C0112", u"C0113", u"C0114", u"C0115", u"C0116", u"C0117", u"C0118", u"C0119", u"C0120", u"C0121", u"C0122", u"C0123", u"C0124", u"C0125", u"C0126", u"C0127", u"C0128", u"C0129", u"C0130", u"C0131", u"C0132", u"C0133", u"C0134", u"C0135", u"C0136", u"C0137", u"C0138", u"C0139", u"C0140", u"C0141", u"C0142", u"C0143", u"C0144", u"C0145", u"C0146", u"C0147", u"C0148", u"C0149", u"C0150", u"C0151", u"C0152", u"C0153", u"C0154", u"C0155", u"C0156", u"C0157", u"C0158", u"C0159", u"C0160", u"C0161", u"C0162", u"C0163", u"C0164", u"C0165", u"C0166", u"C0167", u"C0168", u"C0169", u"C0170", u"C0171", u"C0172", u"C0173", u"C0174", u"C0175", u"C0176", u"C0177", u"C0178", u"C0179", u"C0180", u"C0181", u"C0182", u"C0183", u"C0184", u"C0185", u"C0186", u"C0187", u"C0188", u"C0189", u"C0190", u"C0191", u"C0192", u"C0193", u"C0194", u"C0195", u"C0196", u"C0197", u"C0198", u"C0199", u"C0200"], [], 5, u"None", u""], [u"age", u"Range", u"Input", u"Specify", [None, None], [], 8, u"None", u""], [u"region", u"Set", u"Input", u"Specify", [u"east", u"north", u"south", u"west"], [], 5, u"None", u""], [u"membership", u"Flag", u"Input", u"Specify", [u"N", u"Y"], [], 1, u"None", u""], [u"visits", u"Range", u"Input", u"Specify", [None, None], [], 8, u"None", u""], [u"spend", u"Range", u"Input", u"Specify", [11.45, 476.28], [], 8, u"None", u""], [u"responded", u"Flag", u"Target", u"Specify", [u"F", u"T"], [], 1, u"None", u""], [u"spend_per_visit", u"Range", u"Input", u"Specify", [0.715625, 459.27], [], 8, u"None", u""], [u"heavy_user", u"Flag", u"Input", u"Pass", [u"F", u"T"], [], 1, u"None", u""]])
    _skp(type_node1, "role", u"customer_id", u"None")
    _skp(type_node1, "role", u"responded", u"Target")
    _skp(type_node1, "values", u"visits", [None, None])
    _skp(type_node1, "values", u"spend", [11.45, 476.28])
    _skp(type_node1, "values", u"spend_per_visit", [0.715625, 459.27])
    _skp(type_node1, "values", u"membership", [u"N", u"Y"])
    _skp(type_node1, "values", u"customer_id", [u"C0001", u"C0002", u"C0003", u"C0004", u"C0005", u"C0006", u"C0007", u"C0008", u"C0009", u"C0010", u"C0011", u"C0012", u"C0013", u"C0014", u"C0015", u"C0016", u"C0017", u"C0018", u"C0019", u"C0020", u"C0021", u"C0022", u"C0023", u"C0024", u"C0025", u"C0026", u"C0027", u"C0028", u"C0029", u"C0030", u"C0031", u"C0032", u"C0033", u"C0034", u"C0035", u"C0036", u"C0037", u"C0038", u"C0039", u"C0040", u"C0041", u"C0042", u"C0043", u"C0044", u"C0045", u"C0046", u"C0047", u"C0048", u"C0049", u"C0050", u"C0051", u"C0052", u"C0053", u"C0054", u"C0055", u"C0056", u"C0057", u"C0058", u"C0059", u"C0060", u"C0061", u"C0062", u"C0063", u"C0064", u"C0065", u"C0066", u"C0067", u"C0068", u"C0069", u"C0070", u"C0071", u"C0072", u"C0073", u"C0074", u"C0075", u"C0076", u"C0077", u"C0078", u"C0079", u"C0080", u"C0081", u"C0082", u"C0083", u"C0084", u"C0085", u"C0086", u"C0087", u"C0088", u"C0089", u"C0090", u"C0091", u"C0092", u"C0093", u"C0094", u"C0095", u"C0096", u"C0097", u"C0098", u"C0099", u"C0100", u"C0101", u"C0102", u"C0103", u"C0104", u"C0105", u"C0106", u"C0107", u"C0108", u"C0109", u"C0110", u"C0111", u"C0112", u"C0113", u"C0114", u"C0115", u"C0116", u"C0117", u"C0118", u"C0119", u"C0120", u"C0121", u"C0122", u"C0123", u"C0124", u"C0125", u"C0126", u"C0127", u"C0128", u"C0129", u"C0130", u"C0131", u"C0132", u"C0133", u"C0134", u"C0135", u"C0136", u"C0137", u"C0138", u"C0139", u"C0140", u"C0141", u"C0142", u"C0143", u"C0144", u"C0145", u"C0146", u"C0147", u"C0148", u"C0149", u"C0150", u"C0151", u"C0152", u"C0153", u"C0154", u"C0155", u"C0156", u"C0157", u"C0158", u"C0159", u"C0160", u"C0161", u"C0162", u"C0163", u"C0164", u"C0165", u"C0166", u"C0167", u"C0168", u"C0169", u"C0170", u"C0171", u"C0172", u"C0173", u"C0174", u"C0175", u"C0176", u"C0177", u"C0178", u"C0179", u"C0180", u"C0181", u"C0182", u"C0183", u"C0184", u"C0185", u"C0186", u"C0187", u"C0188", u"C0189", u"C0190", u"C0191", u"C0192", u"C0193", u"C0194", u"C0195", u"C0196", u"C0197", u"C0198", u"C0199", u"C0200"])
    _skp(type_node1, "values", u"region", [u"east", u"north", u"south", u"west"])
    _skp(type_node1, "values", u"age", [None, None])
    _skp(type_node1, "values", u"responded", [u"F", u"T"])
    _skp(type_node1, "type", u"visits", u"Range")
    _skp(type_node1, "type", u"spend", u"Range")
    _skp(type_node1, "type", u"spend_per_visit", u"Range")
    _skp(type_node1, "type", u"membership", u"Flag")
    _skp(type_node1, "type", u"customer_id", u"Set")

def build_part_002():
    global variablefile_node1, derive_node1, derive_node2, type_node1, c50_node1, applyc50_node1, analysis_node1, table_node1
    _skp(type_node1, "type", u"region", u"Set")
    _skp(type_node1, "type", u"age", u"Range")
    _skp(type_node1, "type", u"responded", u"Flag")
    _skp(type_node1, "max_list_length", u"visits", 0)
    _skp(type_node1, "max_list_length", u"spend", 0)
    _skp(type_node1, "max_list_length", u"spend_per_visit", 0)
    _skp(type_node1, "max_list_length", u"membership", 0)
    _skp(type_node1, "max_list_length", u"customer_id", 0)
    _skp(type_node1, "max_list_length", u"region", 0)
    _skp(type_node1, "max_list_length", u"age", 0)
    _skp(type_node1, "max_list_length", u"responded", 0)
    _skp(type_node1, "field_metadata", u"visits", [u"Range", u"Input", u"Specify", [None, None], [], 8, u"None", u""])
    _skp(type_node1, "field_metadata", u"spend", [u"Range", u"Input", u"Specify", [11.45, 476.28], [], 8, u"None", u""])
    _skp(type_node1, "field_metadata", u"spend_per_visit", [u"Range", u"Input", u"Specify", [0.715625, 459.27], [], 8, u"None", u""])
    _skp(type_node1, "field_metadata", u"membership", [u"Flag", u"Input", u"Specify", [u"N", u"Y"], [], 1, u"None", u""])
    _skp(type_node1, "field_metadata", u"customer_id", [u"Set", u"None", u"Specify", [u"C0001", u"C0002", u"C0003", u"C0004", u"C0005", u"C0006", u"C0007", u"C0008", u"C0009", u"C0010", u"C0011", u"C0012", u"C0013", u"C0014", u"C0015", u"C0016", u"C0017", u"C0018", u"C0019", u"C0020", u"C0021", u"C0022", u"C0023", u"C0024", u"C0025", u"C0026", u"C0027", u"C0028", u"C0029", u"C0030", u"C0031", u"C0032", u"C0033", u"C0034", u"C0035", u"C0036", u"C0037", u"C0038", u"C0039", u"C0040", u"C0041", u"C0042", u"C0043", u"C0044", u"C0045", u"C0046", u"C0047", u"C0048", u"C0049", u"C0050", u"C0051", u"C0052", u"C0053", u"C0054", u"C0055", u"C0056", u"C0057", u"C0058", u"C0059", u"C0060", u"C0061", u"C0062", u"C0063", u"C0064", u"C0065", u"C0066", u"C0067", u"C0068", u"C0069", u"C0070", u"C0071", u"C0072", u"C0073", u"C0074", u"C0075", u"C0076", u"C0077", u"C0078", u"C0079", u"C0080", u"C0081", u"C0082", u"C0083", u"C0084", u"C0085", u"C0086", u"C0087", u"C0088", u"C0089", u"C0090", u"C0091", u"C0092", u"C0093", u"C0094", u"C0095", u"C0096", u"C0097", u"C0098", u"C0099", u"C0100", u"C0101", u"C0102", u"C0103", u"C0104", u"C0105", u"C0106", u"C0107", u"C0108", u"C0109", u"C0110", u"C0111", u"C0112", u"C0113", u"C0114", u"C0115", u"C0116", u"C0117", u"C0118", u"C0119", u"C0120", u"C0121", u"C0122", u"C0123", u"C0124", u"C0125", u"C0126", u"C0127", u"C0128", u"C0129", u"C0130", u"C0131", u"C0132", u"C0133", u"C0134", u"C0135", u"C0136", u"C0137", u"C0138", u"C0139", u"C0140", u"C0141", u"C0142", u"C0143", u"C0144", u"C0145", u"C0146", u"C0147", u"C0148", u"C0149", u"C0150", u"C0151", u"C0152", u"C0153", u"C0154", u"C0155", u"C0156", u"C0157", u"C0158", u"C0159", u"C0160", u"C0161", u"C0162", u"C0163", u"C0164", u"C0165", u"C0166", u"C0167", u"C0168", u"C0169", u"C0170", u"C0171", u"C0172", u"C0173", u"C0174", u"C0175", u"C0176", u"C0177", u"C0178", u"C0179", u"C0180", u"C0181", u"C0182", u"C0183", u"C0184", u"C0185", u"C0186", u"C0187", u"C0188", u"C0189", u"C0190", u"C0191", u"C0192", u"C0193", u"C0194", u"C0195", u"C0196", u"C0197", u"C0198", u"C0199", u"C0200"], [], 5, u"None", u""])
    _skp(type_node1, "field_metadata", u"region", [u"Set", u"Input", u"Specify", [u"east", u"north", u"south", u"west"], [], 5, u"None", u""])
    _skp(type_node1, "field_metadata", u"age", [u"Range", u"Input", u"Specify", [None, None], [], 8, u"None", u""])
    _skp(type_node1, "field_metadata", u"responded", [u"Flag", u"Target", u"Specify", [u"F", u"T"], [], 1, u"None", u""])
    _sp(type_node1, "default_value_mode", u"Read")
    _skp(type_node1, "max_string_length", u"visits", 8)
    _skp(type_node1, "max_string_length", u"spend", 8)
    _skp(type_node1, "max_string_length", u"spend_per_visit", 8)
    _skp(type_node1, "max_string_length", u"membership", 1)
    _skp(type_node1, "max_string_length", u"customer_id", 5)
    _skp(type_node1, "max_string_length", u"region", 5)
    _skp(type_node1, "max_string_length", u"age", 8)
    _skp(type_node1, "max_string_length", u"responded", 1)
    _sp(type_node1, "metadata_all", [[u"customer_id", u"Set", u"None", u"Specify", [u"C0001", u"C0002", u"C0003", u"C0004", u"C0005", u"C0006", u"C0007", u"C0008", u"C0009", u"C0010", u"C0011", u"C0012", u"C0013", u"C0014", u"C0015", u"C0016", u"C0017", u"C0018", u"C0019", u"C0020", u"C0021", u"C0022", u"C0023", u"C0024", u"C0025", u"C0026", u"C0027", u"C0028", u"C0029", u"C0030", u"C0031", u"C0032", u"C0033", u"C0034", u"C0035", u"C0036", u"C0037", u"C0038", u"C0039", u"C0040", u"C0041", u"C0042", u"C0043", u"C0044", u"C0045", u"C0046", u"C0047", u"C0048", u"C0049", u"C0050", u"C0051", u"C0052", u"C0053", u"C0054", u"C0055", u"C0056", u"C0057", u"C0058", u"C0059", u"C0060", u"C0061", u"C0062", u"C0063", u"C0064", u"C0065", u"C0066", u"C0067", u"C0068", u"C0069", u"C0070", u"C0071", u"C0072", u"C0073", u"C0074", u"C0075", u"C0076", u"C0077", u"C0078", u"C0079", u"C0080", u"C0081", u"C0082", u"C0083", u"C0084", u"C0085", u"C0086", u"C0087", u"C0088", u"C0089", u"C0090", u"C0091", u"C0092", u"C0093", u"C0094", u"C0095", u"C0096", u"C0097", u"C0098", u"C0099", u"C0100", u"C0101", u"C0102", u"C0103", u"C0104", u"C0105", u"C0106", u"C0107", u"C0108", u"C0109", u"C0110", u"C0111", u"C0112", u"C0113", u"C0114", u"C0115", u"C0116", u"C0117", u"C0118", u"C0119", u"C0120", u"C0121", u"C0122", u"C0123", u"C0124", u"C0125", u"C0126", u"C0127", u"C0128", u"C0129", u"C0130", u"C0131", u"C0132", u"C0133", u"C0134", u"C0135", u"C0136", u"C0137", u"C0138", u"C0139", u"C0140", u"C0141", u"C0142", u"C0143", u"C0144", u"C0145", u"C0146", u"C0147", u"C0148", u"C0149", u"C0150", u"C0151", u"C0152", u"C0153", u"C0154", u"C0155", u"C0156", u"C0157", u"C0158", u"C0159", u"C0160", u"C0161", u"C0162", u"C0163", u"C0164", u"C0165", u"C0166", u"C0167", u"C0168", u"C0169", u"C0170", u"C0171", u"C0172", u"C0173", u"C0174", u"C0175", u"C0176", u"C0177", u"C0178", u"C0179", u"C0180", u"C0181", u"C0182", u"C0183", u"C0184", u"C0185", u"C0186", u"C0187", u"C0188", u"C0189", u"C0190", u"C0191", u"C0192", u"C0193", u"C0194", u"C0195", u"C0196", u"C0197", u"C0198", u"C0199", u"C0200"], [], 5, u"None", False, [], False, None, None, True, True], [u"age", u"Range", u"Input", u"Specify", [None, None], [], 8, u"None", False, [], False, None, None, True, True], [u"region", u"Set", u"Input", u"Specify", [u"east", u"north", u"south", u"west"], [], 5, u"None", False, [], False, None, None, True, True], [u"membership", u"Flag", u"Input", u"Specify", [u"N", u"Y"], [], 1, u"None", False, [], False, None, None, True, True], [u"visits", u"Range", u"Input", u"Specify", [None, None], [], 8, u"None", False, [], False, None, None, True, True], [u"spend", u"Range", u"Input", u"Specify", [11.45, 476.28], [], 8, u"None", False, [], False, None, None, True, True], [u"responded", u"Flag", u"Target", u"Specify", [u"F", u"T"], [], 1, u"None", False, [], False, None, None, True, True], [u"spend_per_visit", u"Range", u"Input", u"Specify", [0.715625, 459.27], [], 8, u"None", False, [], False, None, None, True, False], [u"heavy_user", u"Flag", u"Input", u"Pass", [u"F", u"T"], [], 1, u"None", False, [], False, None, None, True, True]])
    _skp(type_node1, "missing_values", u"visits", [])
    _skp(type_node1, "missing_values", u"spend", [])
    _skp(type_node1, "missing_values", u"spend_per_visit", [])
    _skp(type_node1, "missing_values", u"membership", [])
    _skp(type_node1, "missing_values", u"customer_id", [])
    _skp(type_node1, "missing_values", u"region", [])
    _skp(type_node1, "missing_values", u"age", [])
    _skp(type_node1, "missing_values", u"responded", [])
    _sp(type_node1, "missing_metadata", [[u"customer_id", False, [], True, True, False, None, None], [u"age", False, [], True, True, False, None, None], [u"region", False, [], True, True, False, None, None], [u"membership", False, [], True, True, False, None, None], [u"visits", False, [], True, True, False, None, None], [u"spend", False, [], True, True, False, None, None], [u"responded", False, [], True, True, False, None, None], [u"spend_per_visit", False, [], True, False, False, None, None], [u"heavy_user", False, [], True, True, False, None, None]])
    c50_node1 = _create("c50_node1", "c50", u"応答予測", 462, 217)
    _sp(c50_node1, "model_name", u"応答予測")

def build_part_003():
    global variablefile_node1, derive_node1, derive_node2, type_node1, c50_node1, applyc50_node1, analysis_node1, table_node1
    _sp(c50_node1, "use_model_name", True)
    analysis_node1 = _create("analysis_node1", "analysis", u"精度分析", 714, 37)
    table_node1 = _create("table_node1", "table", u"テーブル", 714, 157)

_run_parts([build_part_001, build_part_002, build_part_003])

# ---- links (ordinary nodes) ----
_link_v("variablefile_node1", "derive_node1")
_link_v("derive_node1", "derive_node2")
_link_v("derive_node2", "type_node1")
_link_v("type_node1", "c50_node1")

# ---- links involving nuggets / supernodes / opaque nodes (applied as soon as both ends exist) ----
_pend("type_node1", "applyc50_node1")
_pend("applyc50_node1", "analysis_node1")
_pend("applyc50_node1", "table_node1")

# ---- nuggets / supernodes / opaque nodes ----
applyc50_node1 = NUGGET("applyc50", u"応答予測", 594, 97, nod=u"nuggets/applyc50_node1.nod", builder="c50_node1", input="type_node1")
_sp(applyc50_node1, "use_custom_name", True)
_sp(applyc50_node1, "calculate_variable_importance", True)
_sp(applyc50_node1, "custom_name", u"応答予測")
_link_pending()

_link_pending(True)

# ---- validate / save / report ----
_validate(SOURCE_VARS, NUGGET_VARS)
_finish(EXPECTED_NODES, EXPECTED_LINKS)
