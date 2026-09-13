"""Unit tests for verify.compare (structure + property values) and rebuild.classify / check_ready (no clemb needed)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import rebuild  # noqa: E402
import transform  # noqa: E402
import verify  # noqa: E402

STRUCT = json.loads((HERE / "fixtures" / "campaign_response_structure.json").read_text(encoding="utf-8-sig"))
STREAM_PY = (HERE / "fixtures" / "campaign_response_stream_expected.py").read_text(encoding="utf-8")


class VerifyTests(unittest.TestCase):
    def test_identical(self):
        ok, pok, lines = verify.compare(STRUCT, STRUCT, "a", "b", STREAM_PY, STREAM_PY)
        self.assertTrue(ok and pok)
        self.assertEqual(lines[0], "RESULT: STRUCTURE_MATCH")
        self.assertTrue(any("PROPERTIES_MATCH" in ln for ln in lines))

    def test_value_change_is_reported(self):
        edited = STREAM_PY.replace('derive_node1.setPropertyValue("formula_expr", u"spend / visits")',
                                   'derive_node1.setPropertyValue("formula_expr", u"spend / age")')
        self.assertNotEqual(edited, STREAM_PY)
        ok, pok, lines = verify.compare(STRUCT, STRUCT, "a", "b", STREAM_PY, edited)
        self.assertTrue(ok)          # structure unchanged
        self.assertFalse(pok)        # but a property value differs
        self.assertTrue(any('formula_expr: a=u"spend / visits" | b=u"spend / age"' in ln for ln in lines), lines)

    def test_stream_setting_change_is_reported(self):
        sb = json.loads(json.dumps(STRUCT))
        sb["stream"]["modified_props"]["date_format"] = "YYYY-MM-DD"
        sb["stream"]["modified_props"]["min_canvas_width"] = 1  # ignored canvas noise
        ok, pok, lines = verify.compare(STRUCT, sb, "a", "b", STREAM_PY, STREAM_PY)
        self.assertTrue(ok)
        self.assertFalse(pok)
        self.assertTrue(any(ln.strip().startswith("stream.date_format:") for ln in lines))
        self.assertFalse(any("min_canvas_width" in ln for ln in lines))

    def test_structure_difference(self):
        sb = json.loads(json.dumps(STRUCT))
        sb["nodes"][0]["x"] += 10
        ok, pok, lines = verify.compare(STRUCT, sb, "a", "b")
        self.assertFalse(ok)
        self.assertTrue(pok)  # no stream.py given -> properties not compared
        self.assertEqual(lines[0], "RESULT: STRUCTURE_DIFFERENT")

    def test_internal_ids_ignored(self):
        edited = STREAM_PY + '\napplyc50_node1.setPropertyValue("builder_node_id", u"idX")\n'
        ok, pok, lines = verify.compare(STRUCT, STRUCT, "a", "b", STREAM_PY, edited)
        self.assertTrue(pok, lines)


def _result(**kw) -> dict:
    base = {"saved": True, "nodes": 8, "links": 7, "expected_nodes": 8, "expected_links": 7,
            "fails": [], "warnings": [], "validation": [{"var": "v", "ok": True}]}
    base.update(kw)
    return base


class ClassifyTests(unittest.TestCase):
    def test_ok(self):
        c = rebuild.classify(_result())
        self.assertEqual((c["status"], c["ok"]), ("OK", True))

    def test_warnings_do_not_fail(self):
        c = rebuild.classify(_result(warnings=["path not found: x"]))
        self.assertEqual((c["status"], c["ok"]), ("OK WITH WARNINGS", True))

    def test_count_mismatch_is_an_issue(self):
        c = rebuild.classify(_result(nodes=9, links=8))   # e.g. a select node was added on purpose
        self.assertEqual((c["status"], c["ok"], c["saved"]), ("SAVED WITH ISSUES", False, True))

    def test_validation_failure_is_an_issue(self):
        c = rebuild.classify(_result(validation=[{"var": "n", "ok": False, "error": "boom"}]))
        self.assertEqual((c["status"], c["ok"]), ("SAVED WITH ISSUES", False))

    def test_benign_fail_is_ok(self):
        c = rebuild.classify(_result(fails=[{"kind": "set", "prop": "values", "error": "[null, null] rejected"}]))
        self.assertEqual(c["status"], "OK")
        self.assertEqual(len(c["benign"]), 1)

    def test_not_saved(self):
        self.assertEqual(rebuild.classify(_result(saved=False))["status"], "FAILED")
        self.assertEqual(rebuild.classify(None)["status"], "NO RESULT")


class CheckReadyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name) / "x.strcode"
        (self.d / "nuggets").mkdir(parents=True)
        self.src = Path(self.tmp.name) / "x.str"
        self.src.write_bytes(b"binary")
        from common import sha256_file
        self.meta = {"source_path": str(self.src), "sha256": sha256_file(self.src), "tool_version": "t"}
        self.cfg = {"tool_version": "t"}
        self.text = 'a = NUGGET("applyc50", u"n", 1, 2, nod=u"nuggets/a.nod", builder=None, input=None)\n'

    def tearDown(self):
        self.tmp.cleanup()

    def test_ready(self):
        (self.d / "nuggets" / "a.nod").write_bytes(b"x")
        self.assertEqual(rebuild.check_ready(self.d, self.meta, self.cfg, self.text, retrain=False), [])

    def test_missing_nod(self):
        problems = rebuild.check_ready(self.d, self.meta, self.cfg, self.text, retrain=False)
        self.assertEqual(len(problems), 1)
        self.assertIn("a.nod", problems[0])
        # retraining does not need the nugget file
        self.assertEqual(rebuild.check_ready(self.d, self.meta, self.cfg, self.text, retrain=True), [])

    def test_source_changed_and_tool_version(self):
        (self.d / "nuggets" / "a.nod").write_bytes(b"x")
        self.src.write_bytes(b"changed")
        problems = rebuild.check_ready(self.d, self.meta, {"tool_version": "u"}, self.text, retrain=False)
        self.assertEqual(len(problems), 2)
        self.assertIn("changed after it was decoded", problems[0])
        self.assertIn("decoded with strcodec", problems[1])


class TransformSafetyTests(unittest.TestCase):
    def test_stream_call_literal_protected(self):
        s = 'x.setPropertyValue("formula_expr", u"modeler.script.stream()")'
        self.assertEqual(transform.replace_stream_call(s), s)
        self.assertEqual(transform.replace_stream_call('modeler.script.stream().link(a, b)'), 'stream.link(a, b)')
        self.assertEqual(transform.replace_stream_call('n = modeler.script.stream().createAt("t", u"modeler.script.stream()", 1, 2)'),
                         'n = stream.createAt("t", u"modeler.script.stream()", 1, 2)')

    def test_parse_generated_keeps_literal(self):
        p = transform.parse_generated('x = modeler.script.stream().createAt("derive", u"d", 1, 2)\n'
                                      'x.setPropertyValue("formula_expr", u"modeler.script.stream()")\n')
        self.assertEqual(p.blocks[0].setters, ['x.setPropertyValue("formula_expr", u"modeler.script.stream()")'])

    def test_stream_settings_emitted_and_rebuilt(self):
        text = transform.normalize(transform.parse_generated(
            (HERE / "fixtures" / "campaign_response_generated_raw.py").read_text(encoding="utf-8-sig")), STRUCT,
            {"tool_version": "test"}, {"source_path": "x"})
        self.assertIn('stream.setPropertyValue("script_language", u"Python")', text)
        self.assertNotIn('"parameters_table"', text)  # canvas/state noise skipped
        import fixture_ctx as fx
        script, _ = transform.build_rebuild(text, fx.ctx())
        self.assertIn('_sp(stream, "script_language", u"Python")', script)
        self.assertIn('type_node1 = _create("type_node1", "type", u"データ型", 462, 97)', script)
        self.assertNotIn("stream.createAt(", script.split("stream = _new_stream(STREAM_NAME)")[1])

    def test_param_marker(self):
        s = json.loads(json.dumps(STRUCT))
        s["stream"]["parameters"] = [{"name": "P1", "value": 42, "type": "Typeless", "storage": "Integer", "label": "L"}]
        self.assertEqual(transform.stream_settings(s)[-1], 'PARAM(u"P1", value=42, storage=u"Integer", label=u"L")')

    def test_jy_lit(self):
        self.assertEqual(transform.jy_lit({"a": [1, 2.5, None, True, "x"]}), '{u"a": [1, 2.5, None, True, u"x"]}')


if __name__ == "__main__":
    unittest.main()
