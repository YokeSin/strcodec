"""SourceSegmentCache must reproduce ast.get_source_segment() exactly, and a build must preprocess the source once."""
import ast
import sys
import unittest
from unittest import mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import fixture_ctx as fx  # noqa: E402
import transform  # noqa: E402

SAMPLES = {
    "ascii": "a = 1\nb = foo(a, 2)\n",
    "no_trailing_newline": "a = 1\nb = 2",
    "crlf": "x = [1,\r\n     2,\r\n     3]\r\ny = u\"abc\"\r\n",
    "cr_only": "x = 1\ry = 2\r",
    "mixed_endings": "x = 1\r\ny = [\n 2,\r 3]\nz = 4",
    "japanese": 'n = stream.createAt("derive", u"健康的", 1, 2)\nn.setPropertyValue("flag_expr", u"\'果物･野菜\' == \'T\'")\n',
    "japanese_multiline": 'v.setPropertyValue(\n    "new_name",\n    u"健康的"\n)\nw = u"ﾋﾞｰﾙ"\n',
    "tabs": "if True:\n\tx = (1,\n\t     2)\n\ty = x\n",
    "formfeed": "a = 1\n\x0c\nb = 2\n",
    "unicode_line_sep": "a = 'x y'\nb = 2\n",
    "nested_multiline": "d = {\n  'k': [\n     1, 2,\n     3],\n  'j': (4,\n        5)}\n",
    "padded_call": "    x = 1\n" if False else "def f():\n    return call(\n        1,\n        2)\n",
    "emoji": "s = '😀'\nt = ('😀',\n     '日本')\n",
}


def nodes_with_positions(tree, limit: int = 0):
    nodes = [n for n in ast.walk(tree) if hasattr(n, "lineno") and hasattr(n, "end_lineno")]
    if limit and len(nodes) > limit:
        # the reference ast.get_source_segment() is very slow on CPython 3.10 (re-splits the whole source per
        # call), so compare an evenly spread sample of the big fixture instead of every node
        step = len(nodes) / float(limit)
        nodes = [nodes[int(i * step)] for i in range(limit)]
    return nodes


class SegmentCompatibilityTests(unittest.TestCase):
    def check_source(self, name, src, limit: int = 0):
        tree = ast.parse(src)
        cache = transform.SourceSegmentCache(src)
        count = 0
        for node in nodes_with_positions(tree, limit):
            for padded in (False, True):
                expected = ast.get_source_segment(src, node, padded=padded)
                got = cache.segment(node, padded=padded)
                self.assertEqual(got, expected, "%s: %s padded=%s" % (name, type(node).__name__, padded))
                count += 1
        self.assertGreater(count, 0)

    def test_samples(self):
        for name, src in SAMPLES.items():
            with self.subTest(sample=name):
                self.check_source(name, src)

    def test_fixture_stream_py(self):
        self.check_source("fixture", fx.normalized(), limit=120)

    def test_split_lines_like_parser(self):
        cases = {
            "": [], "a": ["a"], "a\n": ["a\n"], "a\r\nb": ["a\r\n", "b"], "a\rb\n": ["a\r", "b\n"],
            "\n\n": ["\n", "\n"], "a\x0cb\nc": ["a\x0cb\n", "c"], "x y\n": ["x y\n"],
        }
        for src, expected in cases.items():
            self.assertEqual(transform.split_lines_like_parser(src), expected, repr(src))

    def test_missing_positions_return_none(self):
        cache = transform.SourceSegmentCache("a = 1\n")
        self.assertIsNone(cache.segment(ast.Load()))
        node = ast.parse("a = 1\n").body[0]
        node.end_lineno = None
        self.assertIsNone(cache.segment(node))


class OncePerBuildTests(unittest.TestCase):
    def test_source_is_preprocessed_once_and_ast_helper_unused(self):
        text = fx.normalized()
        calls = []
        real = transform.SourceSegmentCache

        class Counting(real):
            __slots__ = ()

            def __init__(self, source):
                calls.append(len(source))
                super().__init__(source)

        def forbidden(*a, **k):
            raise AssertionError("ast.get_source_segment must not be used by build_rebuild")

        with mock.patch.object(transform, "SourceSegmentCache", Counting), \
                mock.patch.object(ast, "get_source_segment", forbidden):
            script, warnings = transform.build_rebuild(text, fx.ctx())
        self.assertEqual(len(calls), 1, "SourceSegmentCache must be built exactly once per build_rebuild")
        self.assertEqual(calls[0], len(text))
        self.assertTrue(script.startswith("# ==== strcodec rebuild script"))
        self.assertEqual(warnings, [])

    def test_parse_stream_py_reuses_given_cache(self):
        text = "a = stream.createAt(\"type\", u\"t\", 1, 2)\nstream.link(a, a)\n"
        cache = transform.SourceSegmentCache(text)
        with mock.patch.object(transform, "SourceSegmentCache", side_effect=AssertionError("must reuse cache")):
            stmts, assigned = transform.parse_stream_py(text, cache)
        self.assertEqual([s.kind for s in stmts], ["create", "link"])
        self.assertEqual(assigned, ["a"])


if __name__ == "__main__":
    unittest.main()
