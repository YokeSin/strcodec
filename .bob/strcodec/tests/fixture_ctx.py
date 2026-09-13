"""Shared, fully deterministic inputs for transform tests and fixture (re)generation.

Everything here is fixed (no timestamps, no machine paths) so that the generated stream.py and rebuild
script are byte-for-byte reproducible across Python versions and machines.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
if str(TOOL) not in sys.path:
    sys.path.insert(0, str(TOOL))

import transform  # noqa: E402

FIX = HERE / "fixtures"
CFG = {"tool_version": "test"}
HEADER = {"source_path": "C:/x/campaign_response.str", "sha256": "abc", "decoded_at": "now", "tool_version": "test",
          "modeler_version": "19"}
EXPECTED_STREAM = FIX / "campaign_response_stream_expected.py"
EXPECTED_REBUILD = FIX / "campaign_response_rebuild_expected.py"


def raw() -> str:
    return (FIX / "campaign_response_generated_raw.py").read_text(encoding="utf-8-sig")


def structure() -> dict:
    return json.loads((FIX / "campaign_response_structure.json").read_text(encoding="utf-8-sig"))


def prelude() -> str:
    return (TOOL / "jython" / "rebuild_prelude.py").read_text(encoding="utf-8")


def ctx(**kw) -> "transform.RebuildContext":
    base = dict(stem="campaign_response", source_path="C:/x/campaign_response.str",
                base_dir="C:/x/campaign_response.strcode", out_str="C:/x/campaign_response_rebuilt.str",
                result_json="C:/x/r.json", prelude=prelude(),
                expected_nodes=8, expected_links=7, source_vars=["variablefile_node1"])
    base.update(kw)
    return transform.RebuildContext(**base)


def normalized() -> str:
    return transform.normalize(transform.parse_generated(raw()), structure(), CFG, HEADER)


def rebuilt(**kw) -> tuple[str, list[str]]:
    return transform.build_rebuild(normalized(), ctx(**kw))
