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
