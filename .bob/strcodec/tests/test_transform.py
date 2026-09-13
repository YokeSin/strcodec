"""Unit tests for strcodec text transformations (no clemb needed).  Run: python -m unittest discover .bob/strcodec/tests"""
import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import transform  # noqa: E402

FIX = HERE / "fixtures"
RAW = (FIX / "campaign_response_generated_raw.py").read_text(encoding="utf-8-sig")
STRUCT = json.loads((FIX / "campaign_response_structure.json").read_text(encoding="utf-8-sig"))
CFG = {"tool_version": "test"}
HEADER = {"source_path": "C:/x/campaign_response.str", "sha256": "abc", "decoded_at": "now", "tool_version": "test",
          "modeler_version": "19"}


def _prelude() -> str:
    return (HERE.parent / "jython" / "rebuild_prelude.py").read_text(encoding="utf-8")


def _ctx(**kw) -> transform.RebuildContext:
    base = dict(stem="campaign_response", source_path="C:/x/campaign_response.str",
                base_dir="C:/x/campaign_response.strcode", out_str="C:/x/campaign_response_rebuilt.str",
                result_json="C:/x/r.json", prelude=_prelude(),
                expected_nodes=8, expected_links=7, source_vars=["variablefile_node1"])
    base.update(kw)
    return transform.RebuildContext(**base)


class ReplaceNullTests(unittest.TestCase):
    def test_list_nulls(self):
        self.assertEqual(transform.replace_null('x.setKeyedPropertyValue("values", u"a", [null, null])'),
                         'x.setKeyedPropertyValue("values", u"a", [None, None])')

    def test_string_untouched(self):
        s = 'x.setPropertyValue("expr", u"if a = null then null else 1")'
        self.assertEqual(transform.replace_null(s), s)

    def test_no_null(self):
        self.assertEqual(transform.replace_null("a = 1"), "a = 1")


class ParseGeneratedTests(unittest.TestCase):
    def test_counts(self):
        p = transform.parse_generated(RAW)
        self.assertEqual(len(p.blocks), 8)
        self.assertEqual(len(p.links), 7)
        self.assertTrue(all(b.node_id for b in p.blocks))
        self.assertEqual(p.other, [])

    def test_setters_normalized(self):
        p = transform.parse_generated(RAW)
        joined = "\n".join(s for b in p.blocks for s in b.setters)
        self.assertNotIn("modeler.script.stream()", joined)
        self.assertIsNone(re.search(r"\bnull\b", joined))


class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.parsed = transform.parse_generated(RAW)
        self.text = transform.normalize(self.parsed, STRUCT, CFG, HEADER)

    def test_markers_and_links(self):
        self.assertEqual(len(re.findall(r"^\w+ = NUGGET\(", self.text, re.M)), 1)
        self.assertNotIn('createAt("applyc50"', self.text)
        self.assertEqual(len(re.findall(r"^stream\.link\(", self.text, re.M)), 7)
        code_only = "\n".join(ln for ln in self.text.split("\n") if not ln.lstrip().startswith("#"))
        self.assertNotIn("modeler.script.stream()", code_only)
        self.assertIsNone(re.search(r"\bnull\b", code_only))

    def test_internal_ids_not_restored(self):
        self.assertNotIn('setPropertyValue("builder_node_id"', self.text)
        self.assertIn("# internal ids (not restored", self.text)

    def test_stream_settings_section(self):
        self.assertIn('# ---- stream settings | name: campaign_response ----', self.text)
        self.assertIn('stream.setPropertyValue("script_language", u"Python")', self.text)
        self.assertNotIn('"parameters_table"', self.text)  # canvas/state noise is skipped

    def test_no_flag_fixup_when_the_flag_was_set(self):
        # this stream sets use_custom_name explicitly, so normalize() must not add the compensating line
        self.assertNotIn('setPropertyValue("use_custom_name", False)', self.text)

    def test_flag_fixup_added_when_the_flag_was_not_set(self):
        # Modeler switches use_custom_name ON as a side effect of setting custom_name; when the original
        # stream had the flag off, normalize() adds an explicit False so the label stays automatic.
        b = transform.Block(var="n1", type="derive", label_lit='u"x"', x=0, y=0,
                            setters=['n1.setPropertyValue("custom_name", u"x")'])
        self.assertEqual(
            transform.flag_fixups(b, {"modified_props": ["custom_name"]}),
            ['n1.setPropertyValue("use_custom_name", False)  # flag was not set in the original: keep the automatic label'])
        self.assertEqual(transform.flag_fixups(b, {"modified_props": ["custom_name", "use_custom_name"]}), [])

    def test_deterministic_and_parseable(self):
        import ast
        ast.parse(self.text)
        again = transform.normalize(self.parsed, STRUCT, CFG, HEADER)
        self.assertEqual(self.text, again)
        first_block = self.text.index("# ---- variablefile_node1")
        self.assertLess(first_block, self.text.index("# ---- type_node1"))


class BuildRebuildTests(unittest.TestCase):
    def setUp(self):
        parsed = transform.parse_generated(RAW)
        self.stream_py = transform.normalize(parsed, STRUCT, CFG, HEADER)

    def test_structure(self):
        script, warnings = transform.build_rebuild(self.stream_py, _ctx())
        self.assertEqual(warnings, [])
        self.assertIn("def build_part_001():", script)
        self.assertIn("_run_parts([build_part_001", script)
        self.assertIn("_finish(EXPECTED_NODES, EXPECTED_LINKS)", script)
        self.assertNotIn("coding:", script.split("\n")[0])
        self.assertEqual(script.count("applyc50_node1 = NUGGET("), 1)
        self.assertIn('_pend("type_node1", "applyc50_node1")', script)
        self.assertIn('_link_v("variablefile_node1", "derive_node1")', script)
        self.assertIsNone(re.search(r"^stream\.link\(", script, re.M))  # links only via _link_v/_pend
        self.assertEqual(len(re.findall(r"^\w+\.setPropertyValue\(", script, re.M)), 0)
        parts = re.findall(r"^def (build_part_\d+)\(\):", script, re.M)
        self.assertGreaterEqual(len(parts), 2)
        for body in re.split(r"^def build_part_\d+\(\):", script, flags=re.M)[1:]:
            stmts = [ln for ln in body.split("\n_run_parts")[0].split("\n") if ln.startswith("    ") and not ln.startswith("    global")]
            self.assertLessEqual(len(stmts), 40)

    def test_big_literal_json(self):
        script, warnings = transform.build_rebuild(self.stream_py, _ctx(big_literal_chars=500))
        self.assertIn("_J(u", script)
        m = re.search(r'_sp\(type_node1, "metadata", _J\((u".*?")\)\)', script)
        self.assertIsNotNone(m)
        js = json.loads(m.group(1)[1:])  # python literal -> the JSON text
        self.assertIsInstance(json.loads(js), list)

    def test_retrain_flag(self):
        script, _ = transform.build_rebuild(self.stream_py, _ctx(retrain=True))
        self.assertIn("RETRAIN = True", script)

    def test_agent_edit_multiline(self):
        edited = self.stream_py.replace(
            'derive_node2.setPropertyValue("custom_name", u"優良顧客")',
            'derive_node2.setPropertyValue(\n    "custom_name",\n    u"優良顧客"\n)')
        self.assertNotEqual(edited, self.stream_py)
        script, _ = transform.build_rebuild(edited, _ctx())
        self.assertIn('_sp(derive_node2, "custom_name", u"優良顧客")', script)


if __name__ == "__main__":
    unittest.main()
