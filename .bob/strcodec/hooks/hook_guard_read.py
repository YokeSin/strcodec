"""Bob PreToolUse hook (matcher: ^read_file$): block reading binary .str/.nod files and point to the decoder.

stdin : {"event": "PreToolUse", "session_id": "...", "tool": "read_file", "input": {...}}
exit 2 blocks the tool call (stderr carries the reason); exit 0 lets it run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import CLI_HINT, load_config, log, setup_utf8_stdio, strcode_dir_for  # noqa: E402

BINARY_SUFFIXES = (".str", ".nod")


def collect_strings(obj, out: list, depth: int = 0) -> None:
    if depth > 6:
        return
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_strings(v, out, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            collect_strings(v, out, depth + 1)


def main() -> int:
    setup_utf8_stdio()
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except Exception:
        return 0
    cfg = load_config()
    if not cfg.get("guard_read", True):
        return 0
    if str(data.get("tool", "")) != "read_file":
        return 0
    strings: list = []
    collect_strings(data.get("input") or {}, strings)
    hits = [s for s in strings if s.strip().lower().endswith(BINARY_SUFFIXES)]
    if not hits:
        return 0
    hit = hits[0].strip()
    p = Path(hit)
    d = strcode_dir_for(p) if hit.lower().endswith(".str") else None
    msg = [
        "[strcodec] '%s' is a binary SPSS Modeler file and cannot be read as text." % hit,
        "Use the decoded form instead:",
        "  1. execute_command: %s decode \"%s\"   (prints summary; instant when cached)" % (CLI_HINT, hit),
    ]
    if d is not None:
        msg.append("  2. read_file: %s/summary.md (overview) and %s/stream.py (node-by-node Jython)" % (d.as_posix(), d.as_posix()))
    msg.append("Skills: spss-str-decode (inspect/explain), spss-str-rebuild (reproduce/modify).")
    print("\n".join(msg), file=sys.stderr)
    log("hook_guard_read: blocked read_file of %s" % hit, "hooks.log")
    return 2


if __name__ == "__main__":
    sys.exit(main())
